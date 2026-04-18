"""
认证与同步 API（验证码、登录、同步状态、手动同步）。
"""

import base64
import re
import time

import requests
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import SERVERS
from app.core.runtime import DB_AVAILABLE, EducationData, User, get_db, logger, session_store
from app.services.education_sync import auto_crawl_and_store

router = APIRouter(tags=["认证与同步"])


def select_server(username: str) -> str:
    """根据学号选择服务器。"""
    if username.isdigit():
        server_index = int(username) % len(SERVERS)
        return SERVERS[server_index]
    return SERVERS[0]


@router.get("/api/captcha")
async def get_captcha(username: str = None):
    """获取验证码图片，返回 base64。"""
    try:
        if username and username.isdigit():
            server_index = int(username) % len(SERVERS)
            server_url = SERVERS[server_index]
        else:
            server_index = 0
            server_url = SERVERS[0]

        captcha_url = f"{server_url}verifycode.servlet"
        logger.info(f"【验证码】使用服务器: {server_url}")

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                )
            }
        )

        response = session.get(captcha_url, timeout=10)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"获取验证码失败: {response.status_code}")
        if len(response.content) < 100:
            raise HTTPException(status_code=500, detail="获取验证码失败：返回内容不是有效的图片")

        image_base64 = base64.b64encode(response.content).decode("utf-8")
        captcha_session_id = f"captcha_{time.time()}_{server_index}"
        session_store.set_captcha_session(captcha_session_id, session)

        return {"success": True, "image": f"data:image/jpeg;base64,{image_base64}", "captcha_session_id": captcha_session_id}
    except Exception as e:
        logger.error(f"【验证码】获取失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取验证码失败: {str(e)}")


@router.post("/api/login")
async def login(request: Request, background_tasks: BackgroundTasks):
    """登录接口。"""
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        code = data.get("code")
        captcha_session_id = data.get("captcha_session_id")
        if not all([username, password, code]):
            raise HTTPException(status_code=400, detail="缺少必要参数")

        server_index = None
        if captcha_session_id:
            parts = captcha_session_id.split("_")
            if len(parts) >= 3:
                try:
                    server_index = int(parts[2])
                except ValueError:
                    pass

        session = session_store.pop_captcha_session(captcha_session_id) if captcha_session_id else None
        if not session:
            return {"success": False, "message": "验证码已过期，请刷新验证码后重试"}

        if server_index is not None and 0 <= server_index < len(SERVERS):
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
            raise HTTPException(status_code=500, detail=f"登录请求失败: {response.status_code}")

        for encoding in ["utf-8", "gbk", "gb2312", "gb18030"]:
            try:
                response.encoding = encoding
                content = response.text
                if any(c in content for c in ["用户", "密码", "验证", "登录", "framework"]):
                    break
            except Exception:
                continue
        else:
            response.encoding = response.apparent_encoding
            content = response.text

        if "密码错误" in content or "验证码错误" in content or "用户名不存在" in content:
            return {"success": False, "message": "用户名、密码或验证码错误"}

        is_login_page = ("LoginToXkLdap" in content or ("用户名" in content and "密码" in content and "验证码" in content)) and "framework" not in response.url
        if is_login_page:
            if "密码错误" in content:
                return {"success": False, "message": "密码错误"}
            if "验证码错误" in content:
                return {"success": False, "message": "验证码错误"}
            if "用户名不存在" in content:
                return {"success": False, "message": "用户名不存在"}
            return {"success": False, "message": "登录失败，请检查用户名、密码或验证码"}

        if "/jsxsd/framework/" in content or "framework" in response.url:
            match = re.match(r"(https?://[^/]+/jsxsd/)", response.url)
            final_server_url = match.group(1) if match else server_url
            session_store.set_user_session(username, session, final_server_url)

            needs_sync = True
            if DB_AVAILABLE:
                try:
                    db = next(get_db())
                    try:
                        user = db.query(User).filter(User.username == username).first()
                        if user:
                            data_count = db.query(EducationData).filter(EducationData.user_id == user.id).count()
                            if data_count > 0:
                                needs_sync = False
                                session_store.set_sync_status(
                                    username,
                                    {
                                        "status": "completed",
                                        "message": f"使用已有数据（{data_count}条）",
                                        "timestamp": time.time(),
                                        "cached": True,
                                    },
                                )
                    finally:
                        db.close()
                except Exception as e:
                    logger.warning(f"【登录】检查数据失败: {e}，将执行爬取")

            if needs_sync:
                background_tasks.add_task(auto_crawl_and_store, username, session, final_server_url)
                sync_message = "首次登录，正在后台同步教务数据..."
            else:
                sync_message = "已加载历史数据"

            resp = JSONResponse(
                content={
                    "success": True,
                    "message": "登录成功",
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
            return resp

        return {"success": False, "message": "登录失败，请重试"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


@router.get("/api/sync-status")
async def get_sync_status(username: str):
    """查询数据同步状态。"""
    status = session_store.get_sync_status(username)
    if not status:
        return {"status": "none", "message": "未开始同步"}
    return status


@router.post("/api/sync-data")
async def sync_education_data(username: str, background_tasks: BackgroundTasks):
    """手动触发数据同步。"""
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

