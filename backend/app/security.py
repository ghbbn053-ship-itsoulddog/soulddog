from fastapi import HTTPException, Request


def enforce_username_isolation(http_request: Request, username: str):
    """
    严格会话隔离：
    1) 优先使用 auth_session_id（服务端会话）校验 username 一致性
    2) 兼容旧 session_username cookie 校验
    """
    # 新版：服务端会话强校验
    auth_session_id = http_request.cookies.get("auth_session_id")
    session_store = getattr(http_request.app.state, "session_store", None)
    if auth_session_id and session_store:
        auth_payload = session_store.get_auth_session(auth_session_id)
        if not auth_payload:
            raise HTTPException(status_code=401, detail="登录会话已失效，请重新登录")
        if auth_payload.get("username") != username:
            raise HTTPException(status_code=403, detail="学号与登录会话不一致")
        return

    # 兼容：旧 cookie 最小校验
    cookie_username = http_request.cookies.get("session_username")
    if cookie_username and cookie_username != username:
        raise HTTPException(status_code=403, detail="学号与登录会话不一致")
