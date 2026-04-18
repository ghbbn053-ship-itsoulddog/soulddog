from fastapi import HTTPException, Request


def enforce_username_isolation(http_request: Request, username: str):
    """
    基于登录阶段写入的 session_username cookie 做最小隔离：
    - 有 cookie 时，必须与请求学号一致
    - 无 cookie 时，保持兼容（允许）
    """
    cookie_username = http_request.cookies.get("session_username")
    if cookie_username and cookie_username != username:
        raise HTTPException(status_code=403, detail="学号与登录会话不一致")

