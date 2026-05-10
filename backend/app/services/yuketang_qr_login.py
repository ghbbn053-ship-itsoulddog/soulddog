from __future__ import annotations

import asyncio
import base64
import json
import random
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from yarl import URL

BASE_URL = "https://rain.gdufemooc.cn"
LOGIN_URL = f"{BASE_URL}/web"
LOGIN_ENTRY_URL = f"{BASE_URL}/web?next=/v2/web/index&type=3"
LOGIN_REDIRECT_URL = f"{BASE_URL}/v2/web/index"
WS_URL = "wss://rain.gdufemooc.cn/wsapp/"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "DNT": "1",
}
USER_PROFILE_URL = f"{BASE_URL}/v/course_meta/user_info"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> str:
    return dt.isoformat() if dt else ""


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _dedupe_repeated_halves(value: str) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    parts = text.split(" ")
    if len(parts) % 2 == 0 and parts[: len(parts) // 2] == parts[len(parts) // 2 :]:
        return " ".join(parts[: len(parts) // 2]).strip()
    half = len(text) // 2
    if half > 0 and len(text) % 2 == 0 and text[:half] == text[half:]:
        return text[:half].strip()
    return text


def _cookie_dict_list(cookie_jar: aiohttp.CookieJar) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for cookie in cookie_jar:
        items.append(
            {
                "name": cookie.key,
                "value": cookie.value,
                "domain": cookie["domain"] or "",
                "path": cookie["path"] or "/",
                "expires": cookie["expires"] or "",
            }
        )
    return items


def _image_to_data_url(image_bytes: bytes, mime: str = "image/png") -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _get_cookie_value(cookie_jar: aiohttp.CookieJar, name: str) -> str:
    for cookie in cookie_jar:
        if cookie.key == name:
            return str(cookie.value or "").strip()
    return ""


def _build_sensors_cookie_payload() -> str:
    now_ms = int(time.time() * 1000)
    first_id = (
        f"{now_ms:x}{secrets.token_hex(4)}-"
        f"{random.randint(0, 0xFFFFFFFF):08x}-"
        f"4c657b58-2538900-"
        f"{now_ms:x}{secrets.token_hex(2)}"
    )
    identities_json = json.dumps({"$identity_cookie_id": first_id}, separators=(",", ":"), ensure_ascii=False)
    payload = {
        "distinct_id": first_id,
        "first_id": "",
        "props": {},
        "identities": base64.b64encode(identities_json.encode("utf-8")).decode("ascii"),
        "history_login_id": {"name": "", "value": ""},
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _seed_login_context_cookies(cookie_jar: aiohttp.CookieJar) -> None:
    cookie_jar.update_cookies(
        {
            "django_language": "zh-cn",
            "login_type": "WX",
            "xtbz": "ykt",
            "platform_type": "1",
            "sensorsdata2015jssdkcross": _build_sensors_cookie_payload(),
            "sajssdk_2015_cross_new_user": "1",
        },
        response_url=URL(BASE_URL),
    )


def _extract_query_value(url: str, key: str) -> str:
    query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
    return str(query.get(key) or "").strip()


def _build_browser_headers(
    *,
    referer: str,
    accept: str,
    x_requested_with: bool = False,
    x_csrftoken: str = "",
    origin: str = "",
    content_type: str = "",
) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Accept": accept,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": referer,
        "sec-ch-ua": '"Microsoft Edge";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    if origin:
        headers["Origin"] = origin
    if content_type:
        headers["Content-Type"] = content_type
    if x_requested_with:
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["sec-fetch-dest"] = "empty"
        headers["sec-fetch-mode"] = "cors"
        headers["sec-fetch-site"] = "same-origin"
    else:
        headers["sec-fetch-dest"] = "document"
        headers["sec-fetch-mode"] = "navigate"
        headers["sec-fetch-site"] = "same-origin"
    if x_csrftoken:
        headers["X-CSRFToken"] = x_csrftoken
    return headers


def extract_student_log_urls(raw_text: str, base_url: str = BASE_URL) -> List[str]:
    patterns = [
        r"https://rain\.gdufemooc\.cn/v2/web/studentLog/\d+[^\s\"'<>]*",
        r"/v2/web/studentLog/\d+[^\s\"'<>]*",
    ]
    urls: List[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.findall(pattern, raw_text or "", flags=re.I):
            normalized = urljoin(base_url, match.replace("&amp;", "&"))
            if normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
    return urls


def extract_studycontent_urls(raw_text: str, base_url: str = BASE_URL) -> List[str]:
    patterns = [
        r"https://rain\.gdufemooc\.cn/pro/lms/[^\s\"'<>]+",
        r"/pro/lms/[^\s\"'<>]+",
    ]
    urls: List[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.findall(pattern, raw_text or "", flags=re.I):
            normalized = urljoin(base_url, match.replace("&amp;", "&"))
            if normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
    return urls


def parse_dashboard_courses(html_text: str, base_url: str = BASE_URL) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html_text or "", "lxml")
    candidate_urls = extract_student_log_urls(html_text, base_url=base_url)
    candidate_iter = iter(candidate_urls)
    courses: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    def next_candidate_url() -> str:
        try:
            return next(candidate_iter)
        except StopIteration:
            return ""

    for card in soup.select(".lesson-cardS"):
        card_html = str(card)
        url_matches = extract_student_log_urls(card_html, base_url=base_url)
        course_url = url_matches[0] if url_matches else next_candidate_url()

        title_node = card.select_one(".top h1 .title-inner-wrapper, .top h1")
        teacher_node = card.select_one(".teacherName .title-inner-wrapper, .teacherName")
        image_node = card.select_one(".avatarContainer img")
        auditor_node = card.select_one(".auditor")

        title = _dedupe_repeated_halves(title_node.get_text(" ", strip=True) if title_node else "")
        teacher = _dedupe_repeated_halves(teacher_node.get_text(" ", strip=True) if teacher_node else "")
        avatar = str(image_node.get("src") or "").strip() if image_node else ""
        classroom_id = _extract_query_value(course_url, "classroom_id")
        if not classroom_id:
            match = re.search(r"/studentLog/(\d+)", course_url)
            classroom_id = match.group(1) if match else ""

        if not title and not teacher and not classroom_id:
            continue

        dedupe_key = course_url or f"{title}::{teacher}::{classroom_id}"
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        courses.append(
            {
                "title": title,
                "teacher": teacher,
                "avatar": avatar,
                "course_url": course_url,
                "classroom_id": classroom_id,
                "university_id": _extract_query_value(course_url, "university_id"),
                "platform_id": _extract_query_value(course_url, "platform_id"),
                "content_url": _extract_query_value(course_url, "content_url"),
                "is_auditor": bool(auditor_node),
            }
        )

    if courses:
        return courses

    for url in candidate_urls:
        courses.append(
            {
                "title": "",
                "teacher": "",
                "avatar": "",
                "course_url": url,
                "classroom_id": _extract_query_value(url, "classroom_id") or (re.search(r"/studentLog/(\d+)", url).group(1)),
                "university_id": _extract_query_value(url, "university_id"),
                "platform_id": _extract_query_value(url, "platform_id"),
                "content_url": _extract_query_value(url, "content_url"),
                "is_auditor": False,
            }
        )
    return courses


def parse_course_page_overview(html_text: str, base_url: str = BASE_URL) -> Dict[str, Any]:
    soup = BeautifulSoup(html_text or "", "lxml")

    title_node = soup.select_one(".headerCard h1 .title-inner-wrapper, .headerCard h1")
    teacher_node = soup.select_one(".userInfo .avatarContainer .title-inner-wrapper, .teacherName")
    classroom_node = soup.select_one(".classroom-name .title-inner-wrapper, .classroom-name")
    iframe_node = soup.select_one("iframe.tab-pane-content-iframe")

    tabs = [
        _normalize_text(node.get_text(" ", strip=True))
        for node in soup.select("ul li span")
        if _normalize_text(node.get_text(" ", strip=True))
    ]
    tabs = list(dict.fromkeys(tabs))

    text_content = _normalize_text(soup.get_text(" ", strip=True))
    percent_values = [
        float(value)
        for value in re.findall(r"(\d{1,3}(?:\.\d+)?)%", text_content)
        if 0 <= float(value) <= 100
    ]
    stats: Dict[str, Any] = {
        "title": _dedupe_repeated_halves(title_node.get_text(" ", strip=True) if title_node else ""),
        "teacher": _dedupe_repeated_halves(teacher_node.get_text(" ", strip=True) if teacher_node else ""),
        "classroom_name": _dedupe_repeated_halves(classroom_node.get_text(" ", strip=True) if classroom_node else ""),
        "iframe_url": urljoin(base_url, str(iframe_node.get("src") or "").strip().replace("&amp;", "&")) if iframe_node else "",
        "tabs": tabs,
        "progress_percent_candidates": percent_values,
        "contains_archive_hint": "归档" in text_content,
        "contains_discuss_tab": "讨论" in tabs or "讨论" in text_content,
        "contains_notify_tab": "公告" in tabs or "通知" in text_content,
        "contains_group_tab": "分组" in tabs or "小组" in text_content,
        "contains_report_tab": "报告" in text_content,
    }

    iframe_url = stats["iframe_url"]
    if iframe_url:
        stats["classroom_id"] = _extract_query_value(iframe_url, "classroom_id")
        stats["university_id"] = _extract_query_value(iframe_url, "university_id")
        stats["platform_id"] = _extract_query_value(iframe_url, "platform_id")
    else:
        stats["classroom_id"] = ""
        stats["university_id"] = ""
        stats["platform_id"] = ""

    return stats


@dataclass
class _RuntimeSession:
    owner_username: str
    session_token: str
    lock: threading.Lock = field(default_factory=threading.Lock)
    ready_event: threading.Event = field(default_factory=threading.Event)
    done_event: threading.Event = field(default_factory=threading.Event)
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: Optional[threading.Thread] = None
    state: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)


class YukeTangQrLoginService:
    def __init__(self) -> None:
        self._sessions: Dict[str, _RuntimeSession] = {}
        self._lock = threading.Lock()

    def _update_state(self, runtime: _RuntimeSession, **patch: Any) -> None:
        with runtime.lock:
            runtime.state.update(patch)

    def _snapshot_state(self, runtime: _RuntimeSession) -> Dict[str, Any]:
        with runtime.lock:
            return json.loads(json.dumps(runtime.state, ensure_ascii=False, default=str))

    def create_login_session(self, owner_username: str) -> Dict[str, Any]:
        token = f"ykt_{secrets.token_urlsafe(24)}"
        runtime = _RuntimeSession(
            owner_username=owner_username,
            session_token=token,
            state={
                "owner_username": owner_username,
                "session_token": token,
                "status": "pending",
                "login_url": LOGIN_ENTRY_URL,
                "qr_image_url": "",
                "qr_image_data": "",
                "cookies": [],
                "created_at": _iso(_now_utc()),
                "last_seen_at": _iso(_now_utc()),
                "expires_at": "",
                "last_error": "",
                "auth_payload": {},
                "bind_payload": {},
                "dashboard_url": "",
                "course_count": 0,
                "courses": [],
                "course_overviews": [],
            },
        )

        thread = threading.Thread(
            target=self._run_session_thread,
            args=(runtime,),
            name=f"yuketang-qr-{token[:12]}",
            daemon=True,
        )
        runtime.thread = thread
        with self._lock:
            self._sessions[token] = runtime
        thread.start()
        return self._snapshot_state(runtime)

    def get_session_state(self, session_token: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            runtime = self._sessions.get(session_token)
        if runtime is None:
            return None
        return self._snapshot_state(runtime)

    def wait_for_status(self, session_token: str, statuses: set[str], timeout: float = 120.0) -> Optional[Dict[str, Any]]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            state = self.get_session_state(session_token)
            if state is None:
                return None
            if str(state.get("status") or "") in statuses:
                return state
            time.sleep(1.0)
        return self.get_session_state(session_token)

    def export_debug_artifacts(self, session_token: str, out_dir: Path) -> List[Path]:
        with self._lock:
            runtime = self._sessions.get(session_token)
        if runtime is None:
            raise ValueError("session not found")

        out_dir.mkdir(parents=True, exist_ok=True)
        created: List[Path] = []
        state = self._snapshot_state(runtime)

        qr_data = str(state.get("qr_image_data") or "")
        if qr_data.startswith("data:") and ";base64," in qr_data:
            _, encoded = qr_data.split(";base64,", 1)
            qr_path = out_dir / "yuketang_qr_debug.png"
            qr_path.write_bytes(base64.b64decode(encoded))
            created.append(qr_path)

        session_json_path = out_dir / "yuketang_qr_debug_session.json"
        session_json_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append(session_json_path)

        dashboard_html = str(runtime.artifacts.get("dashboard_html") or "")
        if dashboard_html:
            dashboard_path = out_dir / "yuketang_dashboard_after_login.html"
            dashboard_path.write_text(dashboard_html, encoding="utf-8")
            created.append(dashboard_path)

        debug_artifacts = {
            "ws_handshake": runtime.artifacts.get("ws_handshake") or {},
            "pre_qr_user_info": runtime.artifacts.get("pre_qr_user_info") or {},
            "post_scan_user_info": runtime.artifacts.get("post_scan_user_info") or {},
            "loginsuccess_payload": runtime.artifacts.get("loginsuccess_payload") or {},
            "web_login_response": runtime.artifacts.get("web_login_response") or {},
            "pro_bind_response": runtime.artifacts.get("pro_bind_response") or {},
            "pro_bind_attempts": runtime.artifacts.get("pro_bind_attempts") or [],
            "dashboard_checks": runtime.artifacts.get("dashboard_checks") or [],
        }
        debug_path = out_dir / "yuketang_debug_artifacts.json"
        debug_path.write_text(json.dumps(debug_artifacts, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append(debug_path)

        for index, item in enumerate(runtime.artifacts.get("course_pages") or [], start=1):
            title = re.sub(r"[\\\\/:*?\"<>|]+", "_", str(item.get("title") or f"course_{index}")).strip("_") or f"course_{index}"
            page_path = out_dir / f"yuketang_course_{index:02d}_{title}.html"
            page_path.write_text(str(item.get("html") or ""), encoding="utf-8")
            created.append(page_path)

        return created

    def _run_session_thread(self, runtime: _RuntimeSession) -> None:
        try:
            asyncio.run(self._run_session_async(runtime))
        except Exception as exc:
            self._update_state(
                runtime,
                status="error",
                last_error=str(exc),
                last_seen_at=_iso(_now_utc()),
            )
            runtime.ready_event.set()
            runtime.done_event.set()

    async def _run_session_async(self, runtime: _RuntimeSession) -> None:
        timeout = aiohttp.ClientTimeout(total=30)
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        _seed_login_context_cookies(cookie_jar)
        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS, timeout=timeout, cookie_jar=cookie_jar) as session:
            await self._fetch_login_page(runtime, session)
            async with session.ws_connect(
                WS_URL,
                heartbeat=20,
                origin=BASE_URL,
                headers={"Referer": LOGIN_ENTRY_URL},
            ) as ws:
                runtime.artifacts["ws_handshake"] = {
                    "url": str(ws._response.url),
                    "headers": dict(ws._response.headers),
                }
                runtime.artifacts["pre_qr_user_info"] = await self._prime_login_cookies(session)
                self._update_state(
                    runtime,
                    cookies=_cookie_dict_list(session.cookie_jar),
                    last_seen_at=_iso(_now_utc()),
                )
                await ws.send_str(json.dumps({"op": "requestlogin", "role": "web", "version": 1.4, "type": "qrcode", "from": "web"}))
                while not runtime.stop_event.is_set():
                    try:
                        message = await asyncio.wait_for(ws.receive(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue

                    if message.type == aiohttp.WSMsgType.TEXT:
                        payload = json.loads(message.data)
                        op = str(payload.get("op") or "").strip()
                        if op == "requestlogin":
                            await self._handle_requestlogin(runtime, session, payload)
                            runtime.ready_event.set()
                        elif op == "loginsuccess":
                            await self._handle_loginsuccess(runtime, session, payload)
                            runtime.done_event.set()
                            return
                    elif message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR}:
                        break

        state = self._snapshot_state(runtime)
        if state.get("status") not in {"confirmed", "error"}:
            self._update_state(
                runtime,
                status="closed",
                last_error=str(state.get("last_error") or "websocket closed"),
                last_seen_at=_iso(_now_utc()),
            )
        runtime.done_event.set()

    async def _fetch_login_page(self, runtime: _RuntimeSession, session: aiohttp.ClientSession) -> None:
        async with session.get(
            LOGIN_ENTRY_URL,
            headers=_build_browser_headers(referer=LOGIN_URL, accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"),
        ) as response:
            response.raise_for_status()
            html_text = await response.text()
        self._update_state(
            runtime,
            login_url=str(response.url),
            page_title=_extract_page_title(html_text),
            cookies=_cookie_dict_list(session.cookie_jar),
            last_seen_at=_iso(_now_utc()),
        )

    async def _prime_login_cookies(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        async with session.get(
            USER_PROFILE_URL,
            headers=_build_browser_headers(
                referer=LOGIN_ENTRY_URL,
                accept="application/json",
                x_requested_with=True,
            ),
            allow_redirects=True,
        ) as response:
            body = await response.text()
            return {
                "status": response.status,
                "url": str(response.url),
                "headers": dict(response.headers),
                "body": body,
            }

    async def _handle_requestlogin(
        self,
        runtime: _RuntimeSession,
        session: aiohttp.ClientSession,
        payload: Dict[str, Any],
    ) -> None:
        qr_url = str(payload.get("ticket") or "").strip()
        expire_seconds = int(payload.get("expire_seconds") or 0)
        qr_bytes = b""
        qr_mime = "image/png"
        if qr_url:
            async with session.get(qr_url, headers={"Referer": LOGIN_ENTRY_URL}) as response:
                response.raise_for_status()
                qr_bytes = await response.read()
                qr_mime = response.headers.get("content-type", "image/png").split(";")[0].strip() or "image/png"

        self._update_state(
            runtime,
            status="scannable",
            qr_image_url=qr_url,
            qr_image_data=_image_to_data_url(qr_bytes, qr_mime) if qr_bytes else "",
            expires_at=_iso(_now_utc() + timedelta(seconds=max(expire_seconds, 0))),
            cookies=_cookie_dict_list(session.cookie_jar),
            last_error="",
            last_seen_at=_iso(_now_utc()),
        )
        runtime.artifacts["qr_bytes"] = qr_bytes

    async def _handle_loginsuccess(
        self,
        runtime: _RuntimeSession,
        session: aiohttp.ClientSession,
        payload: Dict[str, Any],
    ) -> None:
        auth_payload = {
            "UserID": str(payload.get("UserID") or "").strip(),
            "Auth": str(payload.get("Auth") or "").strip(),
        }
        user_id = auth_payload["UserID"]
        runtime.artifacts["loginsuccess_payload"] = payload
        self._update_state(
            runtime,
            status="scanned",
            auth_payload=auth_payload,
            cookies=_cookie_dict_list(session.cookie_jar),
            last_seen_at=_iso(_now_utc()),
        )

        csrf_token = _get_cookie_value(session.cookie_jar, "csrftoken")
        login_attempts: List[Dict[str, Any]] = []
        raw_text = ""
        for referer in (LOGIN_ENTRY_URL, LOGIN_URL):
            async with session.post(
                f"{BASE_URL}/pc/web_login",
                data=auth_payload,
                headers=_build_browser_headers(
                    referer=referer,
                    accept="text/plain",
                    x_requested_with=True,
                    x_csrftoken=csrf_token,
                    origin=BASE_URL,
                    content_type="application/x-www-form-urlencoded",
                ),
            ) as response:
                response.raise_for_status()
                raw_text = await response.text()
                attempt = {
                    "referer": referer,
                    "status": response.status,
                    "url": str(response.url),
                    "headers": dict(response.headers),
                    "body": raw_text,
                    "cookies_after": _cookie_dict_list(session.cookie_jar),
                }
                login_attempts.append(attempt)
                if _get_cookie_value(session.cookie_jar, "sessionid"):
                    break
                if "sessionid=" in " ".join(response.headers.getall("Set-Cookie", [])):
                    break
        runtime.artifacts["web_login_response"] = login_attempts[-1] if login_attempts else {}
        runtime.artifacts["web_login_attempts"] = login_attempts
        try:
            login_result = json.loads(raw_text)
        except Exception:
            login_result = {"raw": raw_text}

        bind_attempts: List[Dict[str, Any]] = []
        bind_result: Dict[str, Any] = {}
        for bind_params in ({"user_id": ""}, {"user_id": user_id}):
            for referer in (LOGIN_ENTRY_URL, LOGIN_URL):
                async with session.get(
                    f"{BASE_URL}/api/web/checkin/pro_bind",
                    params=bind_params,
                    headers=_build_browser_headers(
                        referer=referer,
                        accept="application/json",
                        x_requested_with=True,
                        x_csrftoken=_get_cookie_value(session.cookie_jar, "csrftoken"),
                    ),
                ) as response:
                    response.raise_for_status()
                    current_result = await response.json(content_type=None)
                    bind_attempt = {
                        "params": bind_params,
                        "referer": referer,
                        "status": response.status,
                        "url": str(response.url),
                        "headers": dict(response.headers),
                        "body": current_result,
                        "cookies_after": _cookie_dict_list(session.cookie_jar),
                    }
                    bind_attempts.append(bind_attempt)
                    if current_result.get("success"):
                        bind_result = current_result
                        break
            if bind_result:
                break
        runtime.artifacts["pro_bind_response"] = bind_attempts[-1] if bind_attempts else {}
        runtime.artifacts["pro_bind_attempts"] = bind_attempts

        dashboard_url, dashboard_html = await self._fetch_dashboard_html(session)
        courses = parse_dashboard_courses(dashboard_html, base_url=dashboard_url or BASE_URL)
        course_overviews = await self._fetch_course_overviews(session, dashboard_url, courses)

        runtime.artifacts["dashboard_html"] = dashboard_html
        runtime.artifacts["dashboard_checks"] = list(session.__dict__.get("ykt_dashboard_checks", []))
        runtime.artifacts["course_pages"] = course_overviews
        self._update_state(
            runtime,
            status="confirmed",
            auth_payload=auth_payload,
            bind_payload=bind_result,
            dashboard_url=dashboard_url,
            course_count=len(courses),
            courses=courses,
            course_overviews=[
                {
                    "title": item.get("title") or "",
                    "course_url": item.get("course_url") or "",
                    "overview": item.get("overview") or {},
                }
                for item in course_overviews
            ],
            cookies=_cookie_dict_list(session.cookie_jar),
            login_result=login_result,
            last_error="",
            last_seen_at=_iso(_now_utc()),
        )

    async def _fetch_dashboard_html(self, session: aiohttp.ClientSession) -> tuple[str, str]:
        candidate_urls = [LOGIN_REDIRECT_URL, f"{BASE_URL}/v2/web", f"{BASE_URL}/v2/web/index"]
        checks: List[Dict[str, Any]] = []
        for candidate_url in candidate_urls:
            try:
                async with session.get(
                    candidate_url,
                    headers=_build_browser_headers(
                        referer=LOGIN_ENTRY_URL,
                        accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    ),
                    allow_redirects=True,
                ) as response:
                    response.raise_for_status()
                    text = await response.text()
                    checks.append(
                        {
                            "candidate_url": candidate_url,
                            "final_url": str(response.url),
                            "status": response.status,
                            "title": _extract_page_title(text),
                            "contains_lesson_card": "lesson-cardS" in text,
                            "contains_course_marker": "课程班级" in text or "搜索课程" in text,
                            "contains_login_marker": "扫码登录" in text or "正在登录中" in text,
                            "contains_401_hint": 'data-status_code="401"' in text,
                        }
                    )
                    if "课程班级" in text or "lesson-cardS" in text or "搜索课程" in text:
                        session.__dict__["ykt_dashboard_checks"] = checks
                        return str(response.url), text
            except Exception:
                continue
        session.__dict__["ykt_dashboard_checks"] = checks
        return "", ""

    async def _fetch_course_overviews(
        self,
        session: aiohttp.ClientSession,
        dashboard_url: str,
        courses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for course in courses:
            course_url = str(course.get("course_url") or "").strip()
            if not course_url:
                continue
            try:
                async with session.get(
                    course_url,
                    headers=_build_browser_headers(
                        referer=dashboard_url or LOGIN_REDIRECT_URL,
                        accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    ),
                    allow_redirects=True,
                ) as response:
                    response.raise_for_status()
                    html_text = await response.text()
                items.append(
                    {
                        "title": course.get("title") or "",
                        "course_url": str(response.url),
                        "html": html_text,
                        "overview": parse_course_page_overview(html_text, base_url=str(response.url)),
                    }
                )
            except Exception as exc:
                items.append(
                    {
                        "title": course.get("title") or "",
                        "course_url": course_url,
                        "html": "",
                        "overview": {"error": str(exc)},
                    }
                )
        return items


def _extract_page_title(html_text: str) -> str:
    soup = BeautifulSoup(html_text or "", "lxml")
    node = soup.find("title")
    return _normalize_text(node.get_text(" ", strip=True) if node else "")


_yuketang_qr_login_service_singleton: YukeTangQrLoginService | None = None


def get_yuketang_qr_login_service() -> YukeTangQrLoginService:
    global _yuketang_qr_login_service_singleton
    if _yuketang_qr_login_service_singleton is None:
        _yuketang_qr_login_service_singleton = YukeTangQrLoginService()
    return _yuketang_qr_login_service_singleton
