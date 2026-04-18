"""
选项查询 API（院系/学期/课程筛选条件）。
"""

from fastapi import APIRouter, HTTPException

from education_options import (
    EducationOptions,
    query_departments,
    query_semesters,
    query_course_options,
    query_schedule_options,
    query_grade_options,
    get_option_description,
)

router = APIRouter(prefix="/api/options", tags=["选项查询"])


@router.get("/departments")
async def get_departments_api(keyword: str = "", include_admin: bool = False, include_vocational: bool = False):
    try:
        if keyword:
            result = query_departments(keyword)
        else:
            result = EducationOptions.get_departments(include_admin, include_vocational)
        return {"success": True, "data": result, "count": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询院系失败: {str(e)}")


@router.get("/semesters")
async def get_semesters_api(include_past: bool = True, include_future: bool = False):
    try:
        result = query_semesters(include_past, include_future)
        return {"success": True, "data": result, "count": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询学期失败: {str(e)}")


@router.get("/current-semester")
async def get_current_semester_api():
    try:
        result = EducationOptions.get_current_semester()
        return {"success": True, "data": {"code": result, "name": get_option_description("semester", result)}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取当前学期失败: {str(e)}")


@router.get("/course")
async def get_course_options_api():
    try:
        result = query_course_options()
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询课程选项失败: {str(e)}")


@router.get("/schedule")
async def get_schedule_options_api():
    try:
        result = query_schedule_options()
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询课表选项失败: {str(e)}")


@router.get("/grade")
async def get_grade_options_api():
    try:
        result = query_grade_options()
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询成绩选项失败: {str(e)}")


@router.get("/all")
async def get_all_options_api():
    try:
        result = EducationOptions.get_all_options()
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询所有选项失败: {str(e)}")

