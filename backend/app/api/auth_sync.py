"""
认证与同步 API（验证码、登录、同步状态、手动同步）。
"""

import base64
import os
import re
import time
import secrets
from datetime import datetime, timedelta, timezone

import requests
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import SERVERS, get_server_candidates
from app.core.runtime import DB_AVAILABLE, EducationData, User, get_db, logger, session_store
from app.models import EducationSyncSnapshot
from app.services.education_sync import auto_crawl_and_store
from app.services.agent_access import get_agent_access_service
from app.security import enforce_username_isolation

router = APIRouter(tags=["认证与同步"])
SYNC_REUSE_TTL_HOURS = 12
DEV_PREVIEW_USERNAME = os.getenv("DEV_PREVIEW_USERNAME", "24251102121").strip() or "24251102121"

class LoginRequest(BaseModel):
    username: str
    password: str
    code: str
    captcha_session_id: str | None = None


def _is_dev_preview_login(username: str, password: str, code: str, captcha_session_id: str) -> bool:
    """
    预览账号直入：不依赖环境变量，避免本地/容器部署遗漏配置时失效。
    仅对指定账号生效，且要求前端显式传入预览占位值。
    """
    return (
        str(username).strip() == DEV_PREVIEW_USERNAME
        and str(password).strip() == "preview"
        and str(code).strip() == "preview"
        and str(captcha_session_id).strip() == "preview"
    )


def select_server(username: str) -> str:
    """根据学号选择服务器。"""
    if username.isdigit():
        server_index = int(username) % len(SERVERS)
        return SERVERS[server_index]
    return SERVERS[0]


@router.get("/api/captcha")
def get_captcha(username: str = None):
    """获取验证码图片，返回 base64。"""
    try:
        if username and username.isdigit():
            server_index = int(username) % len(SERVERS)
        else:
            server_index = 0

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                )
            }
        )

        last_error = None
        selected_server_url = ""
        response = None
        for server_url in get_server_candidates(server_index):
            captcha_url = f"{server_url}verifycode.servlet"
            logger.info(f"【验证码】尝试服务器: {server_url}")
            try:
                response = session.get(captcha_url, timeout=10)
                if response.status_code != 200:
                    last_error = f"{server_url} -> HTTP {response.status_code}"
                    continue
                if len(response.content) < 100:
                    last_error = f"{server_url} -> 返回内容不是有效的图片"
                    continue
                selected_server_url = server_url
                break
            except Exception as e:
                last_error = f"{server_url} -> {e}"
                continue

        if response is None or not selected_server_url:
            raise HTTPException(status_code=500, detail=f"获取验证码失败: {last_error or '未找到可用教务入口'}")

        image_base64 = base64.b64encode(response.content).decode("utf-8")
        captcha_session_id = f"captcha_{time.time()}_{server_index}"
        session_store.set_captcha_session(captcha_session_id, session, server_url=selected_server_url)

        return {"success": True, "image": f"data:image/jpeg;base64,{image_base64}", "captcha_session_id": captcha_session_id}
    except Exception as e:
        logger.error(f"【验证码】获取失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取验证码失败: {str(e)}")


@router.post("/api/login")
def login(payload: LoginRequest, background_tasks: BackgroundTasks):
    """登录接口。"""
    try:
        username = payload.username
        password = payload.password
        code = payload.code
        captcha_session_id = payload.captcha_session_id
        if not all([username, password, code]):
            raise HTTPException(status_code=400, detail="\u7f3a\u5c11\u5fc5\u8981\u53c2\u6570")

        if _is_dev_preview_login(username, password, code, captcha_session_id):
            auth_session_id = secrets.token_urlsafe(32)
            session_store.set_auth_session(auth_session_id, username=DEV_PREVIEW_USERNAME, user_id=None)
            resp = JSONResponse(
                content={
                    "success": True,
                    "message": "\u9884\u89c8\u6a21\u5f0f\u767b\u5f55\u6210\u529f",
                    "username": DEV_PREVIEW_USERNAME,
                    "session_id": "",
                    "sync_status": "completed",
                    "sync_message": "\u9884\u89c8\u6a21\u5f0f\u4e0d\u6267\u884c\u6559\u52a1\u540c\u6b65",
                }
            )
            resp.set_cookie(
                key="session_username",
                value=DEV_PREVIEW_USERNAME,
                max_age=24 * 3600,
                path="/",
                samesite="lax",
                httponly=False,
            )
            resp.set_cookie(
                key="auth_session_id",
                value=auth_session_id,
                max_age=24 * 3600,
                path="/",
                samesite="lax",
                httponly=True,
            )
            return resp

        server_index = None
        if captcha_session_id:
            parts = captcha_session_id.split("_")
            if len(parts) >= 3:
                try:
                    server_index = int(parts[2])
                except ValueError:
                    pass

        captcha_payload = session_store.pop_captcha_session(captcha_session_id) if captcha_session_id else None
        if not captcha_payload:
            return {
                "success": False,
                "message": "\u9a8c\u8bc1\u7801\u5df2\u8fc7\u671f\uff0c\u8bf7\u5237\u65b0\u9a8c\u8bc1\u7801\u540e\u91cd\u8bd5",
            }
        session = captcha_payload["session"]

        stored_server_url = (captcha_payload.get("server_url") or "").strip()
        if stored_server_url:
            server_url = stored_server_url
        elif server_index is not None and 0 <= server_index < len(SERVERS):
            server_url = SERVERS[server_index]
        else:
            server_url = select_server(username)
        login_url = f"{server_url}xk/LoginToXkLdap"

        response = session.post(
            login_url,
            data={"USERNAME": username, "PASSWORD": password, "RANDOMCODE": code},
            timeout=10,
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"\u767b\u5f55\u8bf7\u6c42\u5931\u8d25: {response.status_code}")

        for encoding in ["utf-8", "gbk", "gb2312", "gb18030"]:
            try:
                response.encoding = encoding
                content = response.text
                if any(c in content for c in ["\u7528\u6237", "\u5bc6\u7801", "\u9a8c\u8bc1", "\u767b\u5f55", "framework"]):
                    break
            except Exception:
                continue
        else:
            response.encoding = response.apparent_encoding
            content = response.text

        if "\u5bc6\u7801\u9519\u8bef" in content or "\u9a8c\u8bc1\u7801\u9519\u8bef" in content or "\u7528\u6237\u540d\u4e0d\u5b58\u5728" in content:
            return {"success": False, "message": "\u7528\u6237\u540d\u3001\u5bc6\u7801\u6216\u9a8c\u8bc1\u7801\u9519\u8bef"}

        is_login_page = (
            ("LoginToXkLdap" in content or ("\u7528\u6237\u540d" in content and "\u5bc6\u7801" in content and "\u9a8c\u8bc1\u7801" in content))
            and "framework" not in response.url
        )
        if is_login_page:
            if "\u5bc6\u7801\u9519\u8bef" in content:
                return {"success": False, "message": "\u5bc6\u7801\u9519\u8bef"}
            if "\u9a8c\u8bc1\u7801\u9519\u8bef" in content:
                return {"success": False, "message": "\u9a8c\u8bc1\u7801\u9519\u8bef"}
            if "\u7528\u6237\u540d\u4e0d\u5b58\u5728" in content:
                return {"success": False, "message": "\u7528\u6237\u540d\u4e0d\u5b58\u5728"}
            return {
                "success": False,
                "message": "\u767b\u5f55\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u7528\u6237\u540d\u3001\u5bc6\u7801\u6216\u9a8c\u8bc1\u7801",
            }

        if "/jsxsd/framework/" in content or "framework" in response.url:
            match = re.match(r"(https?://[^/]+/jsxsd/)", response.url)
            final_server_url = match.group(1) if match else server_url
            session_store.set_user_session(username, session, final_server_url)

            needs_sync = True
            user_id = None
            if DB_AVAILABLE:
                try:
                    db = next(get_db())
                    try:
                        user = db.query(User).filter(User.username == username).first()
                        if user:
                            user_id = user.id
                            latest_snapshot = (
                                db.query(EducationSyncSnapshot)
                                .filter(
                                    EducationSyncSnapshot.user_id == user.id,
                                    EducationSyncSnapshot.status == "success",
                                    EducationSyncSnapshot.is_active == True,
                                )
                                .order_by(EducationSyncSnapshot.created_at.desc())
                                .first()
                            )
                            data_count = db.query(EducationData).filter(EducationData.user_id == user.id).count()
                            snapshot_fresh = False
                            if latest_snapshot and latest_snapshot.created_at:
                                created_at = latest_snapshot.created_at
                                if getattr(created_at, "tzinfo", None) is None:
                                    created_at = created_at.replace(tzinfo=timezone.utc)
                                snapshot_fresh = created_at >= datetime.now(timezone.utc) - timedelta(hours=SYNC_REUSE_TTL_HOURS)
                            if data_count > 0 and snapshot_fresh:
                                needs_sync = False
                                session_store.set_sync_status(
                                    username,
                                    {
                                        "status": "completed",
                                        "message": f"\u4f7f\u7528\u6700\u8fd1\u4e00\u6b21\u6210\u529f\u5feb\u7167\uff08{data_count}\u6761\uff09",
                                        "timestamp": time.time(),
                                        "cached": True,
                                    },
                                )
                    finally:
                        db.close()
                except Exception as e:
                    logger.warning(f"\u3010\u767b\u5f55\u3011\u68c0\u67e5\u6570\u636e\u5931\u8d25: {e}\uff0c\u5c06\u6267\u884c\u722c\u53d6")

            if needs_sync:
                background_tasks.add_task(auto_crawl_and_store, username, session, final_server_url)
                sync_message = "\u9996\u6b21\u767b\u5f55\uff0c\u6b63\u5728\u540e\u53f0\u540c\u6b65\u6559\u52a1\u6570\u636e..."
            else:
                sync_message = "\u5df2\u52a0\u8f7d\u5386\u53f2\u6570\u636e"

            auth_session_id = secrets.token_urlsafe(32)
            session_store.set_auth_session(auth_session_id, username=username, user_id=user_id)

            if DB_AVAILABLE:
                try:
                    db = next(get_db())
                    try:
                        get_agent_access_service().sync_default_bindings(db, username)
                    finally:
                        db.close()
                except Exception as e:
                    logger.warning(f"\u3010\u767b\u5f55\u3011\u540c\u6b65\u5916\u90e8\u670d\u52a1\u7ed1\u5b9a\u72b6\u6001\u5931\u8d25: {e}")

            resp = JSONResponse(
                content={
                    "success": True,
                    "message": "\u767b\u5f55\u6210\u529f",
                    "username": username,
                    "session_id": session.cookies.get("JSESSIONID", ""),
                    "sync_status": "completed" if not needs_sync else "syncing",
                    "sync_message": sync_message,
                }
            )
            resp.set_cookie(
                key="session_username",
                value=username,
                max_age=24 * 3600,
                path="/",
                samesite="lax",
                httponly=False,
            )
            resp.set_cookie(
                key="auth_session_id",
                value=auth_session_id,
                max_age=24 * 3600,
                path="/",
                samesite="lax",
                httponly=True,
            )
            return resp

        return {"success": False, "message": "\u767b\u5f55\u5931\u8d25\uff0c\u8bf7\u91cd\u8bd5"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("\u3010\u767b\u5f55\u3011\u5904\u7406\u5931\u8d25")
        raise HTTPException(status_code=500, detail=f"\u767b\u5f55\u5931\u8d25: {str(e)}")

@router.get("/api/sync-status")
async def get_sync_status(username: str, http_request: Request):
    """查询数据同步状态。"""
    enforce_username_isolation(http_request, username)
    status = session_store.get_sync_status(username)
    if not status:
        return {"status": "none", "message": "未开始同步"}
    return status


@router.post("/api/sync-data")
async def sync_education_data(username: str, background_tasks: BackgroundTasks, http_request: Request):
    """手动触发数据同步。"""
    enforce_username_isolation(http_request, username)
    user_data = session_store.get_user_session(username)
    if not user_data:
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    sync_status = session_store.get_sync_status(username)
    if sync_status and sync_status.get("status") == "syncing":
        return {"success": False, "message": "数据同步中，请稍后重试"}

    session = user_data["session"]
    server_url = user_data["server_url"]
    background_tasks.add_task(auto_crawl_and_store, username, session, server_url)
    return {"success": True, "message": "已开始同步数据，可在后台查看进度"}


@router.get("/api/auth/me")
async def auth_me(request: Request):
    """获取当前登录会话信息（仅信任服务端 auth_session_id）。"""
    auth_session_id = request.cookies.get("auth_session_id")
    if not auth_session_id:
        return {"authenticated": False}

    auth_payload = session_store.get_auth_session(auth_session_id)
    if not auth_payload:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "username": auth_payload.get("username"),
        "user_id": auth_payload.get("user_id"),
    }


@router.post("/api/logout")
async def logout(request: Request):
    """退出登录并清理服务端会话。"""
    auth_session_id = request.cookies.get("auth_session_id")
    if auth_session_id:
        session_store.delete_auth_session(auth_session_id)

    response = JSONResponse({"success": True, "message": "已退出登录"})
    response.delete_cookie("session_username", path="/")
    response.delete_cookie("auth_session_id", path="/")
    return response
