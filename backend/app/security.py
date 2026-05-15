import os

from fastapi import HTTPException, Request


DEV_PREVIEW_USERNAME = os.getenv("DEV_PREVIEW_USERNAME", "24251102121").strip() or "24251102121"


def _is_dev_preview_auth_enabled() -> bool:
    raw = str(os.getenv("ENABLE_DEV_PREVIEW_AUTH", "")).strip().lower()
    return raw in {"1", "true", "on", "yes"}


def enforce_username_isolation(http_request: Request, username: str):
    """
    严格会话隔离：
    1) 优先使用 auth_session_id（服务端会话）校验 username 一致性
    2) 兼容旧 session_username cookie 校验
    """
    if _is_dev_preview_auth_enabled() and username == DEV_PREVIEW_USERNAME:
        return

    # 新版：服务端会话强校验
    auth_session_id = http_request.cookies.get("auth_session_id")
    app_obj = http_request.scope.get("app")
    session_store = getattr(getattr(app_obj, "state", None), "session_store", None) if app_obj else None
    if auth_session_id:
        if not session_store:
            raise HTTPException(status_code=401, detail="登录会话不可用，请重新登录")
        auth_payload = session_store.get_auth_session(auth_session_id)
        if not auth_payload:
            raise HTTPException(status_code=401, detail="登录会话已失效，请重新登录")
        if auth_payload.get("username") != username:
            raise HTTPException(status_code=403, detail="学号与登录会话不一致")
        return

    # 兼容：旧 cookie 最小校验
    cookie_username = http_request.cookies.get("session_username")
    if cookie_username:
        if cookie_username != username:
            raise HTTPException(status_code=403, detail="学号与登录会话不一致")
        return

    raise HTTPException(status_code=401, detail="未检测到登录会话，请重新登录")
