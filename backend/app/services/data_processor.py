"""
数据处理服务 - 爬取数据的存储和向量化
"""

import json
import logging
from typing import Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class DataProcessor:
    """教务数据处理器：负责 PostgreSQL 存储 + Milvus 向量化"""

    def process_and_store(self, username: str, raw_data: Dict, db) -> bool:
        """
        将爬取的原始数据存入 PostgreSQL EducationData 表
        
        Args:
            username: 学号
            raw_data: scraper.get_all_data_for_vectorization() 的返回数据
            db: SQLAlchemy Session
        
        Returns:
            是否成功
        """
        from app.models import User, EducationData

        try:
            # 1. 查找或创建用户
            user = db.query(User).filter(User.username == username).first()
            if not user:
                personal = raw_data.get("个人信息", {})
                user = User(
                    username=username,
                    name=personal.get("name", ""),
                    department=personal.get("department", ""),
                    major=personal.get("major", ""),
                    class_name=personal.get("class", ""),
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"【数据处理】创建用户: {username}")
            else:
                # 更新用户基本信息
                personal = raw_data.get("个人信息", {})
                if personal.get("name"):
                    user.name = personal["name"]
                if personal.get("department"):
                    user.department = personal["department"]
                if personal.get("major"):
                    user.major = personal["major"]
                if personal.get("class"):
                    user.class_name = personal["class"]
                user.last_login = datetime.utcnow()
                db.commit()

            # 2. 更新或创建 EducationData
            edu_data = db.query(EducationData).filter(
                EducationData.user_id == user.id
            ).first()

            grades_info = raw_data.get("成绩信息", {})

            if not edu_data:
                edu_data = EducationData(
                    user_id=user.id,
                    personal_info=raw_data.get("个人信息", {}),
                    grades=grades_info.get("成绩列表", []),
                    grade_stats=grades_info.get("统计信息", {}),
                    schedule=raw_data.get("课表信息", []),
                    training_plan=raw_data.get("培养方案", {}),
                    academic_progress=raw_data.get("学业进度", {}),
                    exam_schedule=raw_data.get("考试安排", []),
                )
                db.add(edu_data)
            else:
                edu_data.personal_info = raw_data.get("个人信息", {})
                edu_data.grades = grades_info.get("成绩列表", [])
                edu_data.grade_stats = grades_info.get("统计信息", {})
                edu_data.schedule = raw_data.get("课表信息", [])
                edu_data.training_plan = raw_data.get("培养方案", {})
                edu_data.academic_progress = raw_data.get("学业进度", {})
                edu_data.exam_schedule = raw_data.get("考试安排", [])

            db.commit()
            logger.info(f"【数据处理】用户 {username} 教务数据已保存到 PostgreSQL")
            return True

        except Exception as e:
            logger.error(f"【数据处理】存储失败: {str(e)}")
            db.rollback()
            return False

    def vectorize_and_store(self, user_id: int, username: str, raw_data: Dict) -> bool:
        """
        将爬取数据分块、向量化、存入 Milvus
        
        Args:
            user_id: 数据库用户 ID
            username: 学号
            raw_data: 爬取的原始数据
        
        Returns:
            是否成功
        """
        from app.services.vector_store import get_vector_store
        from app.services.qwen_service import get_qwen_service

        try:
            vs = get_vector_store()
            qs = get_qwen_service()

            if not vs.available:
                logger.warning("【向量化】Milvus 不可用，跳过向量化")
                return False
            if not qs.available:
                logger.warning("【向量化】千问服务不可用，跳过向量化")
                return False

            # 1. 确保 Collection 存在
            if not vs.collection:
                vs.create_collection(dim=1536)

            # 2. 删除该用户的旧向量数据
            vs.delete_user_data(user_id)

            # 3. 数据分块
            chunks = self.chunk_education_data(raw_data, username)
            if not chunks:
                logger.warning("【向量化】无数据可向量化")
                return False

            logger.info(f"【向量化】共 {len(chunks)} 个数据块待向量化")

            # 3. 批量向量化（每批 10 个，避免超时）
            batch_size = 10
            total_stored = 0

            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                texts = [c["text"] for c in batch]
                sources = [c["source"] for c in batch]
                metadatas = [c.get("metadata", {}) for c in batch]

                # 生成向量
                embeddings = []
                for text in texts:
                    emb = qs.generate_embedding(text)
                    if emb:
                        embeddings.append(emb)
                    else:
                        logger.warning(f"【向量化】生成向量失败: {text[:50]}...")
                        embeddings.append([0.0] * 1536)  # 占位向量

                # 过滤掉全零向量的条目
                valid_indices = [j for j, e in enumerate(embeddings) if any(v != 0.0 for v in e)]
                if valid_indices:
                    valid_texts = [texts[j] for j in valid_indices]
                    valid_embeddings = [embeddings[j] for j in valid_indices]
                    valid_sources = [sources[j] for j in valid_indices]
                    valid_metadatas = [metadatas[j] for j in valid_indices]

                    vs.add_documents(
                        user_id=user_id,
                        texts=valid_texts,
                        embeddings=valid_embeddings,
                        sources=valid_sources,
                        metadatas=valid_metadatas,
                    )
                    total_stored += len(valid_indices)

            logger.info(f"【向量化】成功存入 {total_stored} 个向量到 Milvus")
            return True

        except Exception as e:
            logger.error(f"【向量化】失败: {str(e)}")
            return False

    def chunk_education_data(self, raw_data: Dict, username: str) -> List[Dict]:
        """
        将教务数据分块，每块是一个适合向量检索的文本单元
        
        分块策略:
        - 个人信息 → 1 chunk
        - 每门课成绩 → 1 chunk
        - 每天课表 → 1 chunk
        - 培养方案按类别 → 每类 1 chunk
        - 学业进度 → 1 chunk
        - 每门考试 → 1 chunk
        """
        chunks = []

        # === 1. 个人信息 ===
        personal = raw_data.get("个人信息", {})
        if personal and any(personal.values()):
            text = f"学生个人信息：姓名{personal.get('name', '')}，" \
                   f"学号{personal.get('student_id', username)}，" \
                   f"专业{personal.get('major', '')}，" \
                   f"班级{personal.get('class', '')}，" \
                   f"学院{personal.get('department', '')}"
            chunks.append({
                "text": text,
                "source": "个人信息",
                "metadata": {"type": "personal_info"},
            })

        # === 2. 成绩 — 每门课 1 chunk ===
        grades_info = raw_data.get("成绩信息", {})
        grades_list = grades_info.get("成绩列表", [])
        for grade in grades_list:
            name = grade.get("课程名称", "")
            if not name:
                continue
            text = (
                f"课程成绩：{name}，"
                f"学期{grade.get('开课学期', '')}，"
                f"成绩{grade.get('成绩', '')}，"
                f"学分{grade.get('学分', '')}，"
                f"课程性质{grade.get('课程性质', '')}，"
                f"平时成绩{grade.get('平时成绩', '')}，"
                f"期末成绩{grade.get('期末成绩', '')}"
            )
            chunks.append({
                "text": text,
                "source": "成绩",
                "metadata": {"type": "grade", "course": name},
            })

        # 成绩统计
        stats = grades_info.get("统计信息", {})
        if stats:
            text = f"成绩统计：{json.dumps(stats, ensure_ascii=False)}"
            chunks.append({
                "text": text,
                "source": "成绩统计",
                "metadata": {"type": "grade_stats"},
            })

        # === 3. 课表 — 按天分组 ===
        schedule = raw_data.get("课表信息", [])
        if isinstance(schedule, list) and schedule:
            # 按星期分组
            day_courses = {}
            for course in schedule:
                day = course.get("星期", course.get("weekday", "未知"))
                if day not in day_courses:
                    day_courses[day] = []
                day_courses[day].append(course)

            for day, courses in day_courses.items():
                lines = [f"{day}课表："]
                for c in courses:
                    line = (
                        f"  {c.get('节次', c.get('period', ''))} "
                        f"{c.get('课程名称', c.get('course_name', ''))} "
                        f"教师{c.get('教师', c.get('teacher', ''))} "
                        f"地点{c.get('教室', c.get('classroom', ''))} "
                        f"周次{c.get('周次', c.get('weeks', ''))}"
                    )
                    lines.append(line)
                text = "\n".join(lines)
                chunks.append({
                    "text": text,
                    "source": "课表",
                    "metadata": {"type": "schedule", "day": day},
                })

        # === 4. 培养方案 — 按课程类别分组 ===
        plan = raw_data.get("培养方案", {})
        if isinstance(plan, dict):
            plan_courses = plan.get("课程列表", [])
            if plan_courses:
                category_courses = {}
                for c in plan_courses:
                    cat = c.get("课程类别", "其他")
                    if cat not in category_courses:
                        category_courses[cat] = []
                    category_courses[cat].append(c)

                for cat, courses in category_courses.items():
                    lines = [f"培养方案 - {cat}："]
                    for c in courses:
                        line = (
                            f"  {c.get('课程名称', '')} "
                            f"学分{c.get('学分', '')} "
                            f"建议学期{c.get('建议修读学期', '')}"
                        )
                        lines.append(line)
                    text = "\n".join(lines)
                    chunks.append({
                        "text": text,
                        "source": "培养方案",
                        "metadata": {"type": "training_plan", "category": cat},
                    })

            # 基本信息和学分统计
            basic = plan.get("基本信息", {})
            credit_stats = plan.get("学分统计", {})
            if basic or credit_stats:
                text = (
                    f"培养方案信息：{json.dumps(basic, ensure_ascii=False)}，"
                    f"学分统计：{json.dumps(credit_stats, ensure_ascii=False)}"
                )
                chunks.append({
                    "text": text,
                    "source": "培养方案",
                    "metadata": {"type": "training_plan_summary"},
                })

        # === 5. 学业进度 ===
        progress = raw_data.get("学业进度", {})
        if isinstance(progress, dict) and progress:
            text = f"学业进度：{json.dumps(progress, ensure_ascii=False)}"
            # 截断过长的文本
            if len(text) > 3000:
                text = text[:3000] + "..."
            chunks.append({
                "text": text,
                "source": "学业进度",
                "metadata": {"type": "academic_progress"},
            })

        # === 6. 考试安排 — 每门考试 1 chunk ===
        exams = raw_data.get("考试安排", [])
        if isinstance(exams, list):
            for exam in exams:
                name = exam.get("课程名称", exam.get("course_name", ""))
                if not name:
                    continue
                text = (
                    f"考试安排：{name}，"
                    f"时间{exam.get('考试时间', exam.get('exam_time', ''))}，"
                    f"地点{exam.get('考试地点', exam.get('location', ''))}，"
                    f"座位号{exam.get('座位号', exam.get('seat', ''))}"
                )
                chunks.append({
                    "text": text,
                    "source": "考试安排",
                    "metadata": {"type": "exam", "course": name},
                })

        logger.info(f"【分块】共生成 {len(chunks)} 个数据块")
        return chunks


# 全局实例
data_processor = DataProcessor()
