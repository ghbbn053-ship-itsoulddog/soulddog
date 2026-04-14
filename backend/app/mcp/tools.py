"""
MCP工具定义 - 教务系统助手
将教务系统功能暴露为MCP工具，可被OpenClaw等AI Agent调用
"""

from mcp.server.fastmcp import FastMCP
from typing import Optional
import json
import logging

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
    从全局SESSIONS中获取用户的session和server_url
    """
    # 延迟导入，避免循环依赖
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from main import SESSIONS
    
    if username not in SESSIONS:
        raise ValueError(f"用户 {username} 未登录，请先在Web端登录")
    
    user_data = SESSIONS[username]
    session = user_data["session"]
    server_url = user_data["server_url"]
    
    from scraper import JwxtScraper
    return JwxtScraper(session, server_url)


@mcp.tool()
async def query_grades(username: str, semester: str = "") -> str:
    """查询学生成绩
    
    Args:
        username: 学号
        semester: 学期，如"2024-2025-1"，空则查询所有成绩
    
    Returns:
        成绩列表的JSON字符串，包含课程名称、成绩、学分等信息
    """
    try:
        scraper = _get_scraper(username)
        result = scraper.get_grades(kksj=semester)
        
        if result["success"]:
            grades = result["data"]
            count = result.get("count", len(grades))
            
            # 格式化输出
            output = f"共查询到 {count} 条成绩记录\n\n"
            for i, grade in enumerate(grades[:20], 1):  # 最多显示20条
                output += f"{i}. {grade.get('课程名称', 'N/A')}\n"
                output += f"   成绩: {grade.get('成绩', 'N/A')} | 学分: {grade.get('学分', 'N/A')}\n"
                output += f"   学期: {grade.get('学期', 'N/A')} | 性质: {grade.get('课程性质', 'N/A')}\n\n"
            
            if len(grades) > 20:
                output += f"... 还有 {len(grades) - 20} 条记录未显示\n"
            
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
        scraper = _get_scraper(username)
        result = scraper.get_schedule(semester=semester)
        
        if result["success"]:
            courses = result["data"]
            count = result.get("count", len(courses))
            actual_semester = result.get("semester", semester)
            
            output = f"{actual_semester} 学期课表\n"
            output += f"共 {count} 门课程\n\n"
            
            # 按星期分组
            schedule_by_day = {}
            for course in courses:
                day = course.get("星期", "")
                if day not in schedule_by_day:
                    schedule_by_day[day] = []
                schedule_by_day[day].append(course)
            
            # 按星期一到星期日排序
            day_order = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            for day in day_order:
                if day in schedule_by_day:
                    output += f"【{day}】\n"
                    for course in schedule_by_day[day]:
                        output += f"  {course.get('节次', '')} - {course.get('课程名称', '')}\n"
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
        scraper = _get_scraper(username)
        result = scraper.get_academic_progress()
        
        if result["success"]:
            data = result["data"]
            
            output = "学业进度概览\n\n"
            
            # 总体统计
            if "总学分" in data:
                output += f"总学分要求: {data['总学分']}\n"
            if "已修学分" in data:
                output += f"已修学分: {data['已修学分']}\n"
            if "未修学分" in data:
                output += f"未修学分: {data['未修学分']}\n"
            
            output += "\n"
            
            # 各模块进度
            if "模块进度" in data:
                output += "各模块进度:\n"
                for module in data["模块进度"]:
                    output += f"  {module.get('模块名称', 'N/A')}: "
                    output += f"已修 {module.get('已修', 0)}/{module.get('要求', 0)} 学分\n"
            
            return output
        else:
            return f"查询失败: {result.get('message', '未知错误')}"
    
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"查询学业进度失败: {e}")
        return f"查询学业进度时发生错误: {str(e)}"


@mcp.tool()
async def query_training_plan(username: str) -> str:
    """查询培养方案
    
    Args:
        username: 学号
    
    Returns:
        培养方案信息，包含课程要求、学分分布等
    """
    try:
        scraper = _get_scraper(username)
        result = scraper.get_my_training_plan()
        
        if result["success"]:
            plan = result["data"]
            count = result.get("count", 0)
            
            output = f"培养方案\n"
            output += f"共 {count} 门课程要求\n\n"
            
            # 按课程类型分组
            by_type = {}
            for course in plan:
                course_type = course.get("课程类型", "其他")
                if course_type not in by_type:
                    by_type[course_type] = []
                by_type[course_type].append(course)
            
            for course_type, courses in by_type.items():
                output += f"【{course_type}】\n"
                total_credits = sum(c.get("学分", 0) for c in courses)
                output += f"  课程数: {len(courses)} | 总学分: {total_credits}\n\n"
                
                for course in courses[:10]:  # 每个类型最多显示10门
                    output += f"  - {course.get('课程名称', 'N/A')} ({course.get('学分', 0)}学分)\n"
                
                if len(courses) > 10:
                    output += f"  ... 还有 {len(courses) - 10} 门课程\n"
                
                output += "\n"
            
            return output
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
        scraper = _get_scraper(username)
        result = scraper.get_exam_schedule(semester=semester)
        
        if result["success"]:
            exams = result["data"]
            count = result.get("count", len(exams))
            actual_semester = result.get("semester", semester)
            
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
