"""
教务系统数据查询 API。
"""

from fastapi import APIRouter, HTTPException

from app.core.config import JWXT_BASE_URL
from app.services.education_sync import ensure_user_session
from scraper import JwxtScraper

router = APIRouter(tags=["教务查询"])


@router.get("/api/user/info")
async def get_user_info(username: str):
    """获取用户个人信息"""
    try:
        session, server_url = ensure_user_session(username)
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_personal_info()
        if result["success"]:
            return {"success": True, "data": result["data"]}
        raise HTTPException(status_code=500, detail=result.get("message", "获取信息失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取个人信息失败: {str(e)}")


@router.get("/api/user/card")
async def get_user_card(username: str):
    """获取学籍卡片详细信息"""
    try:
        session, server_url = ensure_user_session(username)
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_student_card()
        if result["success"]:
            return {"success": True, "data": result["data"]}
        raise HTTPException(status_code=500, detail=result.get("message", "获取学籍卡片失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取学籍卡片失败: {str(e)}")


@router.get("/api/grades")
async def get_grades(
    username: str,
    kksj: str = "",
    kcxz: str = "",
    kcmc: str = "",
    fxkc: str = "0",
    xsfs: str = "all",
):
    """获取成绩列表"""
    try:
        session, server_url = ensure_user_session(username)
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_grades(kksj=kksj, kcxz=kcxz, kcmc=kcmc, fxkc=fxkc, xsfs=xsfs)
        if result["success"]:
            return {"success": True, "data": result["data"], "count": result.get("count", 0)}
        raise HTTPException(status_code=500, detail=result.get("message", "获取成绩失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取成绩失败: {str(e)}")


@router.get("/api/grades/all")
async def get_all_grades(username: str):
    """获取所有成绩（快捷接口）"""
    return await get_grades(username=username, kksj="", kcxz="", kcmc="", fxkc="0", xsfs="all")


@router.get("/api/schedule")
async def get_schedule_api(username: str, semester: str = "", week: str = ""):
    """获取学期课表"""
    try:
        session, server_url = ensure_user_session(username)
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_schedule(semester=semester, week=week)
        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "count": result.get("count", 0),
                "semester": result.get("semester", ""),
                "week": result.get("week", ""),
                "未安排时间课程": result.get("未安排时间课程", []),
            }
        raise HTTPException(status_code=500, detail=result.get("message", "获取课表失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取课表失败: {str(e)}")


@router.get("/api/training-plan/my")
async def get_my_training_plan_api(username: str):
    """获取我的培养方案"""
    try:
        session, server_url = ensure_user_session(username)
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_my_training_plan()
        if result["success"]:
            return {"success": True, "data": result["data"], "count": result.get("count", 0)}
        raise HTTPException(status_code=500, detail=result.get("message", "获取培养方案失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取培养方案失败: {str(e)}")


@router.get("/api/academic-progress")
async def get_academic_progress_api(username: str, study_type: str = "0"):
    """获取学业进度"""
    try:
        session, server_url = ensure_user_session(username)
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_academic_progress(study_type=study_type)
        if result["success"]:
            return {"success": True, "data": result["data"], "count": result.get("count", 0)}
        raise HTTPException(status_code=500, detail=result.get("message", "获取学业进度失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取学业进度失败: {str(e)}")


@router.get("/api/exam-schedule")
async def get_exam_schedule_api(username: str, semester: str = ""):
    """获取考试安排"""
    try:
        session, server_url = ensure_user_session(username)
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_exam_schedule(semester=semester)
        if result["success"]:
            return {
                "success": True,
                "data": result["data"],
                "count": result.get("count", 0),
                "semester": result.get("semester", ""),
            }
        raise HTTPException(status_code=500, detail=result.get("message", "获取考试安排失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取考试安排失败: {str(e)}")


@router.get("/api/teacher/search")
async def search_teacher_api(name: str = "", department: str = ""):
    """查询教师信息"""
    try:
        scraper = JwxtScraper(None, JWXT_BASE_URL)
        result = scraper.search_teacher(name=name, department=department)
        if result["success"]:
            return {"success": True, "data": result["data"], "count": result.get("count", 0)}
        raise HTTPException(status_code=500, detail=result.get("message", "查询教师失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询教师失败: {str(e)}")


@router.get("/api/course/search")
async def search_course_api(course_name: str = "", course_code: str = "", department: str = ""):
    """查询课程信息"""
    try:
        scraper = JwxtScraper(None, JWXT_BASE_URL)
        result = scraper.search_course(course_name=course_name, course_code=course_code, department=department)
        if result["success"]:
            return {"success": True, "data": result["data"], "count": result.get("count", 0)}
        raise HTTPException(status_code=500, detail=result.get("message", "查询课程失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询课程失败: {str(e)}")


@router.get("/api/course-selection")
async def get_course_selection_api(username: str):
    """获取选课信息"""
    try:
        session, server_url = ensure_user_session(username)
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_course_selection_info()
        if result["success"]:
            return {"success": True, "data": result["data"]}
        raise HTTPException(status_code=500, detail=result.get("message", "获取选课信息失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取选课信息失败: {str(e)}")


@router.get("/api/execution-plan")
async def get_execution_plan_api(username: str):
    """获取执行计划"""
    try:
        session, server_url = ensure_user_session(username)
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_execution_plan()
        if result["success"]:
            return {"success": True, "data": result["data"], "count": result.get("count", 0)}
        raise HTTPException(status_code=500, detail=result.get("message", "获取执行计划失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取执行计划失败: {str(e)}")


@router.get("/api/all-data")
async def get_all_data_api(username: str):
    """获取所有数据（用于向量化/RAG）"""
    try:
        session, server_url = ensure_user_session(username)
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_all_data_for_vectorization()
        if result["success"]:
            return {"success": True, "data": result["data"]}
        raise HTTPException(status_code=500, detail=result.get("message", "获取数据失败"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")

