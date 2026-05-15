from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.security import enforce_username_isolation
from app.services.yuketang_qr_login import get_yuketang_qr_login_service

router = APIRouter(prefix="/api/yuketang", tags=["yuketang"])


class QrLoginSessionCreateRequest(BaseModel):
    username: str


def _serialize_session(session: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "owner_username": session.get("owner_username"),
        "session_token": session.get("session_token"),
        "status": session.get("status"),
        "login_url": session.get("login_url"),
        "page_title": session.get("page_title"),
        "qr_image_url": session.get("qr_image_url"),
        "qr_image_data": session.get("qr_image_data"),
        "last_error": session.get("last_error"),
        "created_at": session.get("created_at"),
        "last_seen_at": session.get("last_seen_at"),
        "expires_at": session.get("expires_at"),
        "dashboard_url": session.get("dashboard_url"),
        "course_count": session.get("course_count"),
        "courses": session.get("courses") or [],
        "course_overviews": session.get("course_overviews") or [],
        "auth_payload": session.get("auth_payload") or {},
        "bind_payload": session.get("bind_payload") or {},
    }


@router.post("/qr-login/session")
async def create_qr_login_session(payload: QrLoginSessionCreateRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    try:
        session = get_yuketang_qr_login_service().create_login_session(payload.username)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"创建雨课堂二维码会话失败: {exc}")
    return {"success": True, "session": _serialize_session(session)}


@router.get("/qr-login/session")
async def get_qr_login_session(username: str, session_token: str, http_request: Request = None):
    enforce_username_isolation(http_request, username)
    session = get_yuketang_qr_login_service().get_session_state(session_token)
    if not session:
        raise HTTPException(status_code=404, detail="雨课堂二维码会话不存在")
    if str(session.get("owner_username") or "") != str(username):
        raise HTTPException(status_code=403, detail="无权访问该会话")
    return {"success": True, "session": _serialize_session(session)}


@router.get("/qr-login/wait")
async def wait_qr_login_session(
    username: str,
    session_token: str,
    timeout_seconds: float = 60.0,
    http_request: Request = None,
):
    enforce_username_isolation(http_request, username)
    session = get_yuketang_qr_login_service().get_session_state(session_token)
    if not session:
        raise HTTPException(status_code=404, detail="雨课堂二维码会话不存在")
    if str(session.get("owner_username") or "") != str(username):
        raise HTTPException(status_code=403, detail="无权访问该会话")

    result = get_yuketang_qr_login_service().wait_for_status(
        session_token,
        {"scannable", "scanned", "confirmed", "error", "closed"},
        timeout=max(1.0, min(timeout_seconds, 300.0)),
    )
    if not result:
        raise HTTPException(status_code=404, detail="雨课堂二维码会话不存在")
    return {"success": True, "session": _serialize_session(result)}
