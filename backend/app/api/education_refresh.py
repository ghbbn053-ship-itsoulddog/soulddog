"""
教务缓存刷新 API
只负责触发刷新和返回刷新状态，不承担爬虫读取逻辑。
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.core.runtime import session_store
from app.security import enforce_username_isolation
from app.services.education_sync import auto_crawl_and_store

router = APIRouter(tags=["教务刷新"])


@router.post("/api/refresh")
async def refresh_education(username: str, background_tasks: BackgroundTasks, http_request: Request):
    enforce_username_isolation(http_request, username)
    user_data = session_store.get_user_session(username)
    if not user_data:
        raise HTTPException(status_code=401, detail="登录会话已失效，请重新登录")

    sync_status = session_store.get_sync_status(username)
    if sync_status and sync_status.get("status") == "syncing":
        return {"success": False, "message": "数据同步中，请稍后重试", "status": sync_status}

    background_tasks.add_task(auto_crawl_and_store, username, user_data["session"], user_data["server_url"])
    return {"success": True, "message": "已开始刷新缓存数据"}


@router.post("/api/refresh/check")
async def refresh_check(username: str, http_request: Request):
    enforce_username_isolation(http_request, username)
    user_data = session_store.get_user_session(username)
    if not user_data:
        return {
            "success": False,
            "need_login": True,
            "message": "登录会话已失效，请重新登录",
        }
    return {
        "success": True,
        "need_login": False,
        "message": "当前会话有效，可直接刷新",
    }


@router.get("/api/refresh/progress")
async def refresh_progress(username: str, http_request: Request):
    enforce_username_isolation(http_request, username)
    status = session_store.get_sync_status(username) or {"status": "none", "message": "未开始同步"}
    return {
        "success": True,
        "status": status.get("status", "none"),
        "message": status.get("message", ""),
        "timestamp": status.get("timestamp"),
        "raw": status,
    }
