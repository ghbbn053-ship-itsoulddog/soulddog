"""
教务数据标准化服务
将爬虫/数据库中的多种历史结构统一为稳定契约，供存储、检索、对话共用。
"""

from typing import Dict, List, Any


def _as_dict(value: Any) -> Dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List:
    return value if isinstance(value, list) else []


def _group_grades_by_semester(grades: List[Dict]) -> Dict[str, List[Dict]]:
    grouped: Dict[str, List[Dict]] = {}
    for grade in grades:
        if not isinstance(grade, dict):
            continue
        semester = grade.get("开课学期", "未知学期")
        grouped.setdefault(semester, []).append(grade)
    return grouped


def _group_items_by_semester(items: List[Dict], keys: tuple[str, ...] = ("学期", "开课学期")) -> Dict[str, List[Dict]]:
    grouped: Dict[str, List[Dict]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        semester = ""
        for key in keys:
            value = str(item.get(key, "") or "").strip()
            if value:
                semester = value
                break
        if semester:
            grouped.setdefault(semester, []).append(item)
    return grouped


def normalize_education_payload(raw_data: Dict) -> Dict:
    """
    标准化后的结构：
    {
      "个人信息": {},
      "成绩信息": {"成绩列表": [], "按学期": {}, "统计信息": {}},
      "课表信息": {"学期": "", "课程列表": []},
      "培养方案": {},
      "学业进度": {},
      "考试安排": {"学期": "", "考试列表": []}
    }
    """
    raw_data = _as_dict(raw_data)

    personal_info = _as_dict(raw_data.get("个人信息", {}))

    # 成绩信息
    raw_grades = raw_data.get("成绩信息", {})
    grade_list: List[Dict] = []
    grade_stats: Dict = {}
    grades_by_semester: Dict[str, List[Dict]] = {}

    if isinstance(raw_grades, list):
        grade_list = [g for g in raw_grades if isinstance(g, dict)]
    elif isinstance(raw_grades, dict):
        grade_stats = _as_dict(raw_grades.get("统计信息", {}))
        explicit_list = _as_list(raw_grades.get("成绩列表", []))
        explicit_by_sem = _as_dict(raw_grades.get("按学期", {}))

        if explicit_list:
            grade_list = [g for g in explicit_list if isinstance(g, dict)]
        if explicit_by_sem:
            for sem, courses in explicit_by_sem.items():
                clean_courses = [c for c in _as_list(courses) if isinstance(c, dict)]
                if clean_courses:
                    grades_by_semester[sem] = clean_courses
                    if not explicit_list:
                        grade_list.extend(clean_courses)

    if not grades_by_semester:
        grades_by_semester = _group_grades_by_semester(grade_list)

    # 课表信息
    raw_schedule = raw_data.get("课表信息", [])
    schedule_semester = ""
    schedule_courses: List[Dict] = []
    schedule_by_semester: Dict[str, List[Dict]] = {}
    if isinstance(raw_schedule, list):
        schedule_courses = [c for c in raw_schedule if isinstance(c, dict)]
        if schedule_courses:
            schedule_semester = str(schedule_courses[0].get("学期", ""))
    elif isinstance(raw_schedule, dict):
        schedule_semester = str(raw_schedule.get("学期", ""))
        schedule_courses = [c for c in _as_list(raw_schedule.get("课程列表", [])) if isinstance(c, dict)]
        raw_schedule_by_semester = _as_dict(raw_schedule.get("按学期", {}))
        if raw_schedule_by_semester:
            for sem, courses in raw_schedule_by_semester.items():
                clean_courses = [c for c in _as_list(courses) if isinstance(c, dict)]
                if clean_courses:
                    schedule_by_semester[sem] = clean_courses

    if not schedule_by_semester:
        schedule_by_semester = _group_items_by_semester(schedule_courses)

    # 培养方案 / 学业进度
    training_plan = _as_dict(raw_data.get("培养方案", {}))
    academic_progress = _as_dict(raw_data.get("学业进度", {}))

    # 考试安排
    raw_exam = raw_data.get("考试安排", [])
    exam_semester = ""
    exam_list: List[Dict] = []
    exams_by_semester: Dict[str, List[Dict]] = {}
    if isinstance(raw_exam, list):
        exam_list = [e for e in raw_exam if isinstance(e, dict)]
    elif isinstance(raw_exam, dict):
        exam_semester = str(raw_exam.get("学期", ""))
        exam_list = [e for e in _as_list(raw_exam.get("考试列表", [])) if isinstance(e, dict)]
        raw_exam_by_semester = _as_dict(raw_exam.get("按学期", {}))
        if raw_exam_by_semester:
            for sem, exams in raw_exam_by_semester.items():
                clean_exams = [e for e in _as_list(exams) if isinstance(e, dict)]
                if clean_exams:
                    exams_by_semester[sem] = clean_exams

    if not exams_by_semester:
        exams_by_semester = _group_items_by_semester(exam_list)

    return {
        "个人信息": personal_info,
        "成绩信息": {
            "成绩列表": grade_list,
            "按学期": grades_by_semester,
            "统计信息": grade_stats,
        },
        "课表信息": {
            "学期": schedule_semester,
            "课程列表": schedule_courses,
            "按学期": schedule_by_semester,
        },
        "培养方案": training_plan,
        "学业进度": academic_progress,
        "考试安排": {
            "学期": exam_semester,
            "考试列表": exam_list,
            "按学期": exams_by_semester,
        },
    }


def summarize_education_payload(raw_data: Dict) -> Dict[str, int]:
    """返回稳定口径的计数字段。"""
    normalized = normalize_education_payload(raw_data)
    return {
        "成绩数量": len(normalized["成绩信息"]["成绩列表"]),
        "课表数量": len(normalized["课表信息"]["课程列表"]),
        "考试数量": len(normalized["考试安排"]["考试列表"]),
    }


def build_payload_from_education_data_record(edu_data) -> Dict:
    """
    将 EducationData ORM 记录转换为标准化结构。
    """
    raw = {
        "个人信息": getattr(edu_data, "personal_info", {}) or {},
        "成绩信息": {
            "成绩列表": getattr(edu_data, "grades", []) or [],
            "统计信息": getattr(edu_data, "grade_stats", {}) or {},
        },
        "课表信息": getattr(edu_data, "schedule", []) or [],
        "培养方案": getattr(edu_data, "training_plan", {}) or {},
        "学业进度": getattr(edu_data, "academic_progress", {}) or {},
        "考试安排": getattr(edu_data, "exam_schedule", []) or [],
    }
    return normalize_education_payload(raw)
