"""
教务缓存读取 API
所有读取优先走 PostgreSQL 缓存，不依赖当前 JSESSIONID。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.models import get_db
from app.security import enforce_username_isolation
from app.services.agent_access import get_agent_access_service
from app.services.education_cache import get_education_cache_service

router = APIRouter(tags=["教务缓存"])


def _get_bundle(db: Session, username: str):
    svc = get_education_cache_service()
    return svc, svc.get_bundle(db, username)


@router.get("/api/education/status")
async def education_cache_status(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc, bundle = _get_bundle(db, username)
    status = svc.build_status(bundle, username)
    bindings = get_agent_access_service().sync_default_bindings(db, username)
    education_binding = next((item for item in bindings if item.get("service_name") == "education"), None)
    metadata = (education_binding or {}).get("metadata_json") or {}
    status["connection"] = {
        "binding_status": (education_binding or {}).get("status", "pending"),
        "auth_type": (education_binding or {}).get("auth_type", "web_session"),
        "last_verified_at": (education_binding or {}).get("last_verified_at"),
        "has_active_session": bool(metadata.get("has_active_session")),
        "has_live_session": bool(metadata.get("has_live_session")),
        "has_cache": bool(status.get("has_cache")),
        "mode": metadata.get("binding_mode", "unknown"),
        "label": (
            "教务实时连接正常"
            if metadata.get("has_live_session")
            else "仅缓存可用"
            if status.get("has_cache")
            else "未连接"
        ),
    }
    return status


@router.get("/api/user/info/db")
async def get_user_info_cached(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc, bundle = _get_bundle(db, username)
    return svc.response_for_key(bundle, username, "个人信息")


@router.get("/api/grades/db")
async def get_grades_cached(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc, bundle = _get_bundle(db, username)
    return svc.response_for_key(bundle, username, "成绩信息")


@router.get("/api/schedule/db")
async def get_schedule_cached(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc, bundle = _get_bundle(db, username)
    return svc.response_for_key(bundle, username, "课表信息")


@router.get("/api/training-plan/my/db")
async def get_training_plan_cached(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc, bundle = _get_bundle(db, username)
    return svc.response_for_key(bundle, username, "培养方案")


@router.get("/api/academic-progress/db")
async def get_academic_progress_cached(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc, bundle = _get_bundle(db, username)
    return svc.response_for_key(bundle, username, "学业进度")


@router.get("/api/exam-schedule/db")
async def get_exam_schedule_cached(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc, bundle = _get_bundle(db, username)
    return svc.response_for_key(bundle, username, "考试安排")


@router.get("/api/execution-plan/db")
async def get_execution_plan_cached(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc, bundle = _get_bundle(db, username)
    return svc.response_for_key(bundle, username, "执行计划")


@router.get("/api/course-selection/db")
async def get_course_selection_cached(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc, bundle = _get_bundle(db, username)
    return svc.response_for_key(bundle, username, "选课信息")
