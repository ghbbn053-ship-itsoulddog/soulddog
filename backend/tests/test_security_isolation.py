from starlette.requests import Request
from fastapi import HTTPException

from app.security import enforce_username_isolation


def _build_request_with_cookie(cookie_header: str | None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    if cookie_header is not None:
        scope["headers"] = [(b"cookie", cookie_header.encode("utf-8"))]
    return Request(scope)


def test_isolation_allows_when_cookie_missing():
    req = _build_request_with_cookie(None)
    enforce_username_isolation(req, "20230001")


def test_isolation_allows_when_cookie_matches():
    req = _build_request_with_cookie("session_username=20230001")
    enforce_username_isolation(req, "20230001")


def test_isolation_blocks_when_cookie_mismatch():
    req = _build_request_with_cookie("session_username=20239999")
    try:
        enforce_username_isolation(req, "20230001")
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "学号与登录会话不一致" in str(exc.detail)
        return
    raise AssertionError("Expected HTTPException for username mismatch")


def test_isolation_blocks_when_auth_session_cookie_exists_without_store():
    class _DummyStore:
        def get_auth_session(self, _sid):
            return None

    req = _build_request_with_cookie("auth_session_id=test_session")
    req.scope["app"] = type("A", (), {"state": type("S", (), {"session_store": _DummyStore()})()})()
    try:
        enforce_username_isolation(req, "20230001")
    except HTTPException as exc:
        assert exc.status_code == 401
        return
    raise AssertionError("Expected HTTPException for invalid auth session")
