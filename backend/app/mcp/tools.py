"""
MCP工具定义 - 教务系统助手
将教务系统功能暴露为MCP工具，可被OpenClaw等AI Agent调用
"""

from mcp.server.fastmcp import FastMCP
from typing import Optional
import json
import logging
import requests
from sqlalchemy.orm import Session

from education_options import EducationOptions
from app.models.base import SessionLocal
from app.services.education_cache import get_education_cache_service
from app.services.session_store import get_session_store

logger = logging.getLogger(__name__)

# 创建MCP实例
mcp = FastMCP(
    name="教务系统助手",
    description="查询成绩、课表、学业进度等教务系统数据",
    version="1.0.0"
)


def _get_scraper(username: str):
    """
    获取爬虫实例
    从 SessionStore 中获取用户的session和server_url
    """
    session_store = get_session_store()

    user_data = session_store.get_user_session(username)
    if not user_data:
        raise ValueError(f"用户 {username} 未登录，请先在Web端登录")

    session = user_data["session"]
    server_url = user_data["server_url"]
    
    from scraper import JwxtScraper
    return JwxtScraper(session, server_url)


def _load_cached_bundle(username: str):
    db: Session = SessionLocal()
    try:
        return get_education_cache_service().get_bundle(db, username)
    finally:
        db.close()


def _load_cached_section(username: str, key: str):
    bundle = _load_cached_bundle(username)
    if not bundle or not bundle.education_data:
        return None, None

    svc = get_education_cache_service()
    payload = svc.build_payload(bundle)
    status = svc.build_status(bundle, username)
    return payload.get(key), status


def _current_semester() -> str:
    try:
        return str(EducationOptions.get_current_semester() or "").strip()
    except Exception:
        return ""


def _resolve_semester(semester: str = "") -> str:
    normalized = str(semester or "").strip()
    if not normalized:
        return _current_semester()
    resolved = str(EducationOptions.resolve_semester_reference(normalized) or "").strip()
    return resolved or normalized


def _normalize_weekday_label(value: object) -> str:
    raw_day = str(value or "").strip()
    weekday_alias = {
        "周一": "星期一",
        "周二": "星期二",
        "周三": "星期三",
        "周四": "星期四",
        "周五": "星期五",
        "周六": "星期六",
        "周日": "星期日",
        "星期天": "星期日",
        "周天": "星期日",
    }
    return weekday_alias.get(raw_day, raw_day)


def _format_cached_personal_info(username: str) -> Optional[str]:
    info, status = _load_cached_section(username, "个人信息")
    if not info:
        return None

    lines = ["个人信息", ""]
    for key, value in info.items():
        if value and value != "N/A":
            lines.append(f"{key}: {value}")
    if status and status.get("cached_at"):
        lines.append("")
        lines.append(f"数据来源: 平台缓存 ({status.get('cached_at')})")
    return "\n".join(lines)


def _format_cached_schedule(username: str, semester: str = "") -> Optional[str]:
    schedule, status = _load_cached_section(username, "课表信息")
    if not schedule:
        return None

    target_semester = _resolve_semester(semester)
    actual_semester = str(schedule.get("学期") or target_semester or "当前学期")
    schedule_by_semester = dict(schedule.get("按学期") or {})
    courses = list(schedule.get("课程列表") or [])
    if target_semester and schedule_by_semester.get(target_semester):
        courses = list(schedule_by_semester.get(target_semester) or [])
        actual_semester = target_semester
    elif target_semester:
        filtered = [course for course in courses if str(course.get("学期") or "") == target_semester]
        if filtered:
            courses = filtered
            actual_semester = target_semester

    output = f"{actual_semester} 学期课表\n"
    output += f"共 {len(courses)} 门课程\n\n"

    schedule_by_day = {}
    for course in courses:
        day = _normalize_weekday_label(course.get("星期") or course.get("weekday"))
        schedule_by_day.setdefault(day, []).append(course)

    day_order = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    for day in day_order:
        if day in schedule_by_day:
            output += f"【{day}】\n"
            for course in schedule_by_day[day]:
                period = course.get("节次") or course.get("节次信息") or course.get("上课时间") or ""
                output += f"  {period} - {course.get('课程名称', '')}\n"
                output += f"    教师: {course.get('教师', '')} | 地点: {course.get('地点', '')}\n"
                output += f"    周次: {course.get('周次', '')}\n\n"

    if status and status.get("cached_at"):
        output += f"数据来源: 平台缓存 ({status.get('cached_at')})\n"
    return output


def _render_academic_progress(data: dict, cached_at: str = "") -> str:
    output = "学业进度概览\n\n"
    study_type = str(data.get("修读类型") or "").strip()
    if study_type:
        output += f"修读类型: {study_type}\n"
    total_required = data.get("总学分要求") or data.get("总学分")
    earned = data.get("已获学分") or data.get("已修学分")
    remaining = data.get("还需学分") or data.get("未修学分")
    if total_required not in (None, ""):
        output += f"总学分要求: {total_required}\n"
    if earned not in (None, ""):
        output += f"已获学分: {earned}\n"
    if remaining not in (None, ""):
        output += f"还需学分: {remaining}\n"

    course_list = list(data.get("课程列表") or data.get("模块进度") or [])
    if course_list:
        output += "\n课程进度:\n"
        for item in course_list[:20]:
            name = (
                item.get("课程名称")
                or item.get("模块名称")
                or item.get("课程模块")
                or item.get("课程类别")
                or "N/A"
            )
            details_parts = []
            for label, value in [
                ("课程性质", item.get("课程性质")),
                ("学分", item.get("学分")),
                ("已获学分", item.get("已获学分") or item.get("已修")),
                ("模块应修学分", item.get("模块应修学分") or item.get("要求")),
                ("建议修读学期", item.get("建议修读学期")),
                ("免听免修", item.get("免听免修") or item.get("免听、免修")),
                ("状态", item.get("状态") or item.get("完成情况")),
            ]:
                text = str(value or "").strip()
                if text:
                    details_parts.append(f"{label}: {text}")
            details = " | ".join(details_parts)
            output += f"  - {name}"
            if details:
                output += f" ({details})"
            output += "\n"
        if len(course_list) > 20:
            output += f"  ... 还有 {len(course_list) - 20} 条课程进度未展开\n"

    if cached_at:
        output += f"\n数据来源: 平台缓存 ({cached_at})"
    return output


def _render_training_plan(plan: dict, count: int | None = None, cached_at: str = "") -> str:
    course_list = list(plan.get("课程列表") or [])
    output = "培养方案\n"
    basic_info = plan.get("基本信息") or {}
    stats = plan.get("学分统计") or {}
    plan_name = str(basic_info.get("方案名称") or basic_info.get("页面标题") or "").strip()
    total_required = stats.get("总学分要求") or plan.get("总学分要求")
    if plan_name:
        output += f"方案名称: {plan_name}\n"
    if total_required not in (None, ""):
        output += f"总学分要求: {total_required}\n"
    output += f"共 {count if count is not None else len(course_list)} 门课程要求\n\n"

    by_type = {}
    for course in course_list:
        course_type = (
            course.get("课程类型")
            or course.get("课程性质")
            or course.get("课程类别")
            or "其他"
        )
        by_type.setdefault(course_type, []).append(course)

    for course_type, courses in by_type.items():
        total_credits = sum(float(c.get("学分", 0) or 0) for c in courses)
        output += f"【{course_type}】\n"
        output += f"  课程数: {len(courses)} | 总学分: {total_credits}\n\n"
        for course in courses[:10]:
            details_parts = []
            for label, value in [
                ("学分", course.get("学分")),
                ("建议修读学期", course.get("建议修读学期")),
                ("考核方式", course.get("建议考核方式") or course.get("考核方式")),
                ("课程模块", course.get("课程模块")),
            ]:
                text = str(value or "").strip()
                if text:
                    details_parts.append(f"{label}: {text}")
            output += f"  - {course.get('课程名称', 'N/A')}"
            if details_parts:
                output += f" ({' | '.join(details_parts)})"
            output += "\n"
        if len(courses) > 10:
            output += f"  ... 还有 {len(courses) - 10} 门课程\n"
        output += "\n"

    if cached_at:
        output += f"数据来源: 平台缓存 ({cached_at})\n"
    return output


def _format_cached_academic_progress(username: str) -> Optional[str]:
    data, status = _load_cached_section(username, "学业进度")
    if not data:
        return None
    return _render_academic_progress(data, str((status or {}).get("cached_at") or ""))


def _format_cached_training_plan(username: str, semester: str = "") -> Optional[str]:
    plan, status = _load_cached_section(username, "培养方案")
    if not plan:
        return None
    target_semester = _resolve_semester(semester)
    if target_semester:
        filtered_courses = [
            course for course in list(plan.get("课程列表") or [])
            if str(course.get("学期") or course.get("建议修读学期") or "").strip() == target_semester
        ]
        scoped_plan = dict(plan)
        scoped_plan["课程列表"] = filtered_courses
        return _render_training_plan(scoped_plan, count=len(filtered_courses), cached_at=str((status or {}).get("cached_at") or ""))
    return _render_training_plan(plan, cached_at=str((status or {}).get("cached_at") or ""))


def _format_cached_exam_schedule(username: str, semester: str = "") -> Optional[str]:
    exam_data, status = _load_cached_section(username, "考试安排")
    if not exam_data:
        return None

    target_semester = _resolve_semester(semester)
    actual_semester = str(exam_data.get("学期") or target_semester or "当前学期")
    exam_by_semester = dict(exam_data.get("按学期") or {})
    exams = list(exam_data.get("考试列表") or [])
    if target_semester and exam_by_semester.get(target_semester):
        exams = list(exam_by_semester.get(target_semester) or [])
        actual_semester = target_semester
    elif target_semester:
        filtered = [exam for exam in exams if str(exam.get("学期") or "") == target_semester]
        if filtered:
            exams = filtered
            actual_semester = target_semester

    output = f"{actual_semester} 学期考试安排\n"
    output += f"共 {len(exams)} 门考试\n\n"
    exams_sorted = sorted(exams, key=lambda x: x.get("考试时间", ""))
    for exam in exams_sorted:
        output += f"📅 {exam.get('考试时间', 'N/A')}\n"
        output += f"   课程: {exam.get('课程名称', 'N/A')}\n"
        output += f"   地点: {exam.get('考试地点', 'N/A')}\n"
        output += f"   方式: {exam.get('考试方式', 'N/A')}\n\n"

    if status and status.get("cached_at"):
        output += f"数据来源: 平台缓存 ({status.get('cached_at')})\n"
    return output


def _format_cached_grades(username: str, semester: str = "") -> Optional[str]:
    grades_data, status = _load_cached_section(username, "成绩信息")
    if not grades_data:
        return None

    target_semester = _resolve_semester(semester)
    grade_list = list(grades_data.get("成绩列表") or [])
    if target_semester:
        grade_list = [
            grade for grade in grade_list
            if str(grade.get("开课学期") or grade.get("学期") or "") == target_semester
        ]

    output = f"共查询到 {len(grade_list)} 条成绩记录\n\n"
    for i, grade in enumerate(grade_list, 1):
        output += f"{i}. {grade.get('课程名称', 'N/A')}\n"
        output += f"   成绩: {grade.get('成绩', 'N/A')} | 学分: {grade.get('学分', 'N/A')}\n"
        output += f"   学期: {grade.get('开课学期', grade.get('学期', 'N/A'))} | 性质: {grade.get('课程性质', 'N/A')}\n\n"

    if status and status.get("cached_at"):
        output += f"数据来源: 平台缓存 ({status.get('cached_at')})\n"
    return output


@mcp.tool()
async def query_grades(username: str, semester: str = "") -> str:
    """查询学生成绩
    
    Args:
        username: 学号
        semester: 学期，如"2024-2025-1"，空则默认查询当前学期
    
    Returns:
        成绩列表的JSON字符串，包含课程名称、成绩、学分等信息
    """
    try:
        target_semester = _resolve_semester(semester)
        cached = _format_cached_grades(username, target_semester)
        if cached:
            return cached
        scraper = _get_scraper(username)
        result = scraper.get_grades(kksj=target_semester)
        
        if result["success"]:
            grades = result["data"]
            count = result.get("count", len(grades))
            
            # 格式化输出
            output = f"{target_semester or '当前学期'} 共查询到 {count} 条成绩记录\n\n"
            for i, grade in enumerate(grades, 1):
                output += f"{i}. {grade.get('课程名称', 'N/A')}\n"
                output += f"   成绩: {grade.get('成绩', 'N/A')} | 学分: {grade.get('学分', 'N/A')}\n"
                output += f"   学期: {grade.get('学期', 'N/A')} | 性质: {grade.get('课程性质', 'N/A')}\n\n"

            return output
        else:
            return f"查询失败: {result.get('message', '未知错误')}"
    
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"查询成绩失败: {e}")
        return f"查询成绩时发生错误: {str(e)}"


@mcp.tool()
async def query_schedule(username: str, semester: str = "") -> str:
    """查询课程表
    
    Args:
        username: 学号
        semester: 学期，如"2024-2025-2"，空则查询当前学期
    
    Returns:
        课表信息，包含课程名称、时间、地点、教师等
    """
    try:
        target_semester = _resolve_semester(semester)
        cached = _format_cached_schedule(username, target_semester)
        if cached:
            return cached
        scraper = _get_scraper(username)
        result = scraper.get_schedule(semester=target_semester)
        
        if result["success"]:
            courses = result["data"]
            count = result.get("count", len(courses))
            actual_semester = result.get("semester", target_semester)
            
            output = f"{actual_semester} 学期课表\n"
            output += f"共 {count} 门课程\n\n"
            
            # 按星期分组
            schedule_by_day = {}
            for course in courses:
                day = _normalize_weekday_label(course.get("星期") or course.get("weekday"))
                if day not in schedule_by_day:
                    schedule_by_day[day] = []
                schedule_by_day[day].append(course)
            
            # 按星期一到星期日排序
            day_order = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            for day in day_order:
                if day in schedule_by_day:
                    output += f"【{day}】\n"
                    for course in schedule_by_day[day]:
                        period = course.get("节次") or course.get("节次信息") or course.get("上课时间") or ""
                        output += f"  {period} - {course.get('课程名称', '')}\n"
                        output += f"    教师: {course.get('教师', '')} | 地点: {course.get('地点', '')}\n"
                        output += f"    周次: {course.get('周次', '')}\n\n"
            
            return output
        else:
            return f"查询失败: {result.get('message', '未知错误')}"
    
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"查询课表失败: {e}")
        return f"查询课表时发生错误: {str(e)}"


@mcp.tool()
async def query_academic_progress(username: str) -> str:
    """查询学业进度和学分情况
    
    Args:
        username: 学号
    
    Returns:
        学业进度信息，包含已修学分、未完成学分、各模块进度等
    """
    try:
        cached = _format_cached_academic_progress(username)
        if cached:
            return cached
        scraper = _get_scraper(username)
        result = scraper.get_academic_progress()
        
        if result["success"]:
            return _render_academic_progress(result["data"])
        else:
            return f"查询失败: {result.get('message', '未知错误')}"
    
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"查询学业进度失败: {e}")
        return f"查询学业进度时发生错误: {str(e)}"


@mcp.tool()
async def query_training_plan(username: str, semester: str = "") -> str:
    """查询培养方案
    
    Args:
        username: 学号
    
    Returns:
        培养方案信息，包含课程要求、学分分布等
    """
    try:
        target_semester = _resolve_semester(semester)
        cached = _format_cached_training_plan(username, target_semester)
        if cached:
            return cached
        scraper = _get_scraper(username)
        result = scraper.get_my_training_plan()
        
        if result["success"]:
            plan = dict(result["data"] or {})
            if target_semester:
                filtered_courses = [
                    course for course in list(plan.get("课程列表") or [])
                    if str(course.get("学期") or course.get("建议修读学期") or "").strip() == target_semester
                ]
                plan["课程列表"] = filtered_courses
                return _render_training_plan(plan, len(filtered_courses))
            return _render_training_plan(plan, result.get("count"))
        else:
            return f"查询失败: {result.get('message', '未知错误')}"
    
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"查询培养方案失败: {e}")
        return f"查询培养方案时发生错误: {str(e)}"


@mcp.tool()
async def query_exam_schedule(username: str, semester: str = "") -> str:
    """查询考试安排
    
    Args:
        username: 学号
        semester: 学期，如"2024-2025-1"，空则查询当前学期
    
    Returns:
        考试安排信息，包含考试时间、地点、课程等
    """
    try:
        target_semester = _resolve_semester(semester)
        cached = _format_cached_exam_schedule(username, target_semester)
        if cached:
            return cached
        scraper = _get_scraper(username)
        result = scraper.get_exam_schedule(semester=target_semester)
        
        if result["success"]:
            exams = result["data"]
            count = result.get("count", len(exams))
            actual_semester = result.get("semester", target_semester)
            
            output = f"{actual_semester} 学期考试安排\n"
            output += f"共 {count} 门考试\n\n"
            
            # 按日期排序
            exams_sorted = sorted(exams, key=lambda x: x.get("考试时间", ""))
            
            for exam in exams_sorted:
                output += f"📅 {exam.get('考试时间', 'N/A')}\n"
                output += f"   课程: {exam.get('课程名称', 'N/A')}\n"
                output += f"   地点: {exam.get('考试地点', 'N/A')}\n"
                output += f"   方式: {exam.get('考试方式', 'N/A')}\n\n"
            
            return output
        else:
            return f"查询失败: {result.get('message', '未知错误')}"
    
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"查询考试安排失败: {e}")
        return f"查询考试安排时发生错误: {str(e)}"


@mcp.tool()
async def query_personal_info(username: str) -> str:
    """查询个人基本信息
    
    Args:
        username: 学号
    
    Returns:
        个人信息，包含姓名、学院、专业、班级等
    """
    try:
        cached = _format_cached_personal_info(username)
        if cached:
            return cached
        scraper = _get_scraper(username)
        result = scraper.get_personal_info()
        
        if result["success"]:
            info = result["data"]
            
            output = "个人信息\n\n"
            for key, value in info.items():
                if value and value != "N/A":
                    output += f"{key}: {value}\n"
            
            return output
        else:
            return f"查询失败: {result.get('message', '未知错误')}"
    
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"查询个人信息失败: {e}")
        return f"查询个人信息时发生错误: {str(e)}"


@mcp.tool()
async def query_weather(username: str, location: str = "") -> str:
    """查询天气信息

    Args:
        username: 学号（用于统一工具签名，实际天气查询不依赖登录态）
        location: 地点，如“佛山”“广州天河”“Beijing”

    Returns:
        天气摘要文本
    """
    try:
        target = (location or "").strip()
        if not target:
            return "请提供要查询天气的地点，例如：佛山、广州、北京。"

        encoded = requests.utils.quote(target)
        url = f"https://wttr.in/{encoded}?format=j1"
        resp = requests.get(url, timeout=12, headers={"User-Agent": "campus-ai-weather/1.0"})
        resp.raise_for_status()
        payload = resp.json()

        current = (payload.get("current_condition") or [{}])[0]
        weather_desc = ((current.get("weatherDesc") or [{}])[0].get("value") or "").strip()
        temp_c = str(current.get("temp_C", "")).strip()
        feels_c = str(current.get("FeelsLikeC", "")).strip()
        humidity = str(current.get("humidity", "")).strip()
        wind = str(current.get("windspeedKmph", "")).strip()

        lines = [f"{target} 当前天气"]
        if weather_desc:
            lines.append(f"天气: {weather_desc}")
        if temp_c:
            lines.append(f"气温: {temp_c}°C")
        if feels_c:
            lines.append(f"体感: {feels_c}°C")
        if humidity:
            lines.append(f"湿度: {humidity}%")
        if wind:
            lines.append(f"风速: {wind} km/h")

        forecast = payload.get("weather") or []
        if forecast:
            today = forecast[0] or {}
            maxtemp = str(today.get("maxtempC", "")).strip()
            mintemp = str(today.get("mintempC", "")).strip()
            if maxtemp or mintemp:
                lines.append(f"今日预报: {mintemp or '-'}°C ~ {maxtemp or '-'}°C")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"查询天气失败: {e}")
        return f"查询天气时发生错误: {str(e)}"
