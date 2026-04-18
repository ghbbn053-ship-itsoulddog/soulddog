import requests

from app.services.session_store import get_session_store


def test_session_store_singleton_instance():
    s1 = get_session_store()
    s2 = get_session_store()
    assert s1 is s2


def test_session_store_roundtrip_user_session_memory_fallback():
    store = get_session_store()
    # 测试时统一走内存，避免依赖外部 redis
    store.redis_available = False

    username = "20230001"
    session = requests.Session()
    session.headers.update({"User-Agent": "pytest-agent"})
    session.cookies.set("JSESSIONID", "abc123")

    store.set_user_session(username, session, "http://example.com/jsxsd/")
    got = store.get_user_session(username)

    assert got is not None
    assert got["server_url"] == "http://example.com/jsxsd/"
    assert got["session"].cookies.get("JSESSIONID") == "abc123"
    assert got["session"].headers.get("User-Agent") == "pytest-agent"

