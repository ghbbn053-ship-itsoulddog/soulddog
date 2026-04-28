from __future__ import annotations

import base64
import html
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models.chaoxing_qr_session import ChaoxingQrSession

LOGIN_PAGE_URL = "https://v8.chaoxing.com/"
QR_LOGIN_FALLBACK_URL = (
    "https://passport2.chaoxing.com/cloudscanlogin"
    "?mobiletip=%E7%94%B5%E8%84%91%E7%AB%AF%E7%99%BB%E5%BD%95%E7%A1%AE%E8%AE%A4"
    "&time={timestamp}&pcrefer=https://v1.chaoxing.com/backSchool/toLogin?source=num8"
)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _cookie_dict_list(session: requests.Session) -> List[Dict[str, Any]]:
    return [
        {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "expires": cookie.expires,
        }
        for cookie in session.cookies
    ]


def _apply_cookies(session: requests.Session, cookies_json: List[Dict[str, Any]]) -> None:
    for item in cookies_json or []:
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "")
        domain = str(item.get("domain") or "").strip() or None
        path = str(item.get("path") or "").strip() or "/"
        if not name:
            continue
        session.cookies.set(name, value, domain=domain, path=path)


class ChaoxingQrLoginService:
    def __init__(self) -> None:
        self._sessions: Dict[str, requests.Session] = {}
        self._lock = threading.Lock()

    def _new_http_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        return session

    def _remember_session(self, token: str, session: requests.Session) -> None:
        with self._lock:
            self._sessions[token] = session

    def _get_http_session(self, row: ChaoxingQrSession) -> requests.Session:
        with self._lock:
            cached = self._sessions.get(row.session_token)
        if cached is not None:
            return cached
        session = self._new_http_session()
        _apply_cookies(session, list(row.cookies_json or []))
        self._remember_session(row.session_token, session)
        return session

    def _build_qr_page_url(self, login_html: str) -> str:
        match = re.search(r'<iframe[^>]+id="iframe"[^>]+src="([^"]+)"', login_html, flags=re.I)
        if match:
            return html.unescape(match.group(1))
        return QR_LOGIN_FALLBACK_URL.format(timestamp=int(time.time() * 1000))

    def _extract_hidden_input(self, qr_html: str, input_id: str) -> str:
        soup = BeautifulSoup(qr_html, "lxml")
        node = soup.find("input", {"id": input_id})
        if node:
            return str(node.get("value") or "").strip()
        match = re.search(rf'id\s*=\s*"{re.escape(input_id)}"[^>]*value\s*=\s*"([^"]*)"', qr_html, flags=re.I)
        return match.group(1).strip() if match else ""

    def _extract_qr_image_url(self, qr_html: str, qr_page_url: str) -> str:
        soup = BeautifulSoup(qr_html, "lxml")
        node = soup.find("img", {"id": "ewm"})
        src = str(node.get("src") or "").strip() if node else ""
        return urljoin(qr_page_url, src) if src else ""

    def _fetch_qr_image_data(self, session: requests.Session, qr_image_url: str, referer: str) -> str:
        if not qr_image_url:
            return ""
        resp = session.get(qr_image_url, headers={"Referer": referer}, timeout=20)
        resp.raise_for_status()
        mime = resp.headers.get("content-type", "image/png").split(";")[0].strip() or "image/png"
        encoded = base64.b64encode(resp.content).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _get_or_create_row(self, db: Session, owner_username: str) -> ChaoxingQrSession:
        row = (
            db.query(ChaoxingQrSession)
            .filter(ChaoxingQrSession.owner_username == owner_username)
            .order_by(ChaoxingQrSession.created_at.desc())
            .first()
        )
        if row and row.status in {"pending", "scannable", "scanned", "confirmed"}:
            return row
        row = ChaoxingQrSession(
            owner_username=owner_username,
            session_token=f"cxs_{secrets.token_urlsafe(24)}",
            status="pending",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def create_login_session(self, db: Session, owner_username: str) -> Dict[str, Any]:
        row = self._get_or_create_row(db, owner_username)
        session = self._new_http_session()

        login_resp = session.get(LOGIN_PAGE_URL, timeout=20)
        login_resp.raise_for_status()
        qr_page_url = self._build_qr_page_url(login_resp.text)
        qr_resp = session.get(qr_page_url, headers={"Referer": LOGIN_PAGE_URL}, timeout=20)
        qr_resp.raise_for_status()

        qr_html = qr_resp.text
        uuid = self._extract_hidden_input(qr_html, "uuid")
        enc = self._extract_hidden_input(qr_html, "enc")
        pcrefer = self._extract_hidden_input(qr_html, "pcrefer") or "https://v1.chaoxing.com/backSchool/toLogin?source=num8"
        qr_image_url = self._extract_qr_image_url(qr_html, qr_page_url)
        qr_image_data = self._fetch_qr_image_data(session, qr_image_url, qr_page_url)

        row.status = "scannable"
        row.login_url = LOGIN_PAGE_URL
        row.qr_page_url = qr_page_url
        row.qr_image_url = qr_image_url
        row.qr_image_data = qr_image_data
        row.page_title = "扫码登录"
        row.browser_meta_json = {
            "uuid": uuid,
            "enc": enc,
            "pcrefer": pcrefer,
            "iframe_login_url": qr_page_url,
        }
        row.cookies_json = _cookie_dict_list(session)
        row.last_error = None
        row.last_seen_at = _now_utc()
        row.expires_at = _now_utc() + timedelta(minutes=5)
        db.add(row)
        db.commit()
        db.refresh(row)
        self._remember_session(row.session_token, session)
        return row.to_dict()

    def get_row(self, db: Session, owner_username: str, session_token: str) -> Optional[ChaoxingQrSession]:
        return (
            db.query(ChaoxingQrSession)
            .filter(
                ChaoxingQrSession.owner_username == owner_username,
                ChaoxingQrSession.session_token == session_token,
            )
            .first()
        )

    def _post_auth_status(self, session: requests.Session, row: ChaoxingQrSession) -> Dict[str, Any]:
        meta = dict(row.browser_meta_json or {})
        resp = session.post(
            "https://passport2.chaoxing.com/getauthstatus",
            headers={
                "Referer": row.qr_page_url or LOGIN_PAGE_URL,
                "Origin": "https://passport2.chaoxing.com",
                "X-Requested-With": "XMLHttpRequest",
            },
            data={
                "enc": meta.get("enc", ""),
                "uuid": meta.get("uuid", ""),
            },
            timeout=20,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

    def _fetch_html(self, session: requests.Session, url: str, referer: str = "") -> requests.Response:
        headers = {}
        if referer:
            headers["Referer"] = referer
        resp = session.get(url, headers=headers, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        return resp

    def _extract_course_home_url(self, html_text: str, base_url: str) -> str:
        patterns = [
            r'dataurl="([^"]*visit/interaction[^"]*)"',
            r'src="([^"]*visit/interaction[^"]*)"',
            r"setUrl\('[^']+','([^']*visit/interaction[^']*)'",
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text, flags=re.I)
            if match:
                return urljoin(base_url, html.unescape(match.group(1)))
        return ""

    def _extract_candidate_course_urls(self, raw_text: str, base_url: str) -> List[str]:
        matches = re.findall(
            r'(https?://[^\s"\']*mycourse/stu\?[^"\']+|/[^"\']*mycourse/stu\?[^"\']+)',
            raw_text,
            flags=re.I,
        )
        return [urljoin(base_url, html.unescape(match)) for match in matches]

    def _extract_course_cards(self, html_text: str, base_url: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html_text, "lxml")
        courses: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def add_course(url: str, title: str, teacher: str = "", image: str = "") -> None:
            if "courseid=" not in url.lower():
                return
            normalized_url = urljoin(base_url, html.unescape(url))
            if normalized_url in seen:
                return
            seen.add(normalized_url)
            course_id_match = re.search(r"courseid=([^&]+)", normalized_url, flags=re.I)
            clazz_id_match = re.search(r"clazzid=([^&]+)", normalized_url, flags=re.I)
            cpi_match = re.search(r"cpi=([^&]+)", normalized_url, flags=re.I)
            courses.append(
                {
                    "title": title.strip() or f"课程 {course_id_match.group(1) if course_id_match else len(courses) + 1}",
                    "url": normalized_url,
                    "teacher": teacher.strip(),
                    "course_id": course_id_match.group(1) if course_id_match else "",
                    "class_id": clazz_id_match.group(1) if clazz_id_match else "",
                    "cpi": cpi_match.group(1) if cpi_match else "",
                    "image": image.strip(),
                }
            )

        for anchor in soup.find_all("a"):
            values = [str(anchor.get(attr) or "") for attr in ("href", "data", "dataurl", "onclick")]
            candidate_urls: List[str] = []
            for value in values:
                candidate_urls.extend(self._extract_candidate_course_urls(value, base_url))
            if not candidate_urls:
                continue
            title = str(anchor.get("title") or "").strip() or anchor.get_text(" ", strip=True)
            card = anchor.find_parent(["li", "div", "section", "article"])
            teacher = ""
            image = ""
            if card:
                teacher_node = card.select_one(".teacher, .color3, .course-teacher, .person")
                image_node = card.select_one("img")
                teacher = teacher_node.get_text(" ", strip=True) if teacher_node else ""
                image = str(image_node.get("src") or "").strip() if image_node else ""
                if not title:
                    title_node = card.select_one("h3, h4, h5, h6, .course-name, .overHidden2")
                    title = title_node.get_text(" ", strip=True) if title_node else ""
            for candidate_url in candidate_urls:
                add_course(candidate_url, title, teacher, image)

        raw_urls = self._extract_candidate_course_urls(html_text, base_url)
        for raw_url in raw_urls:
            add_course(raw_url, "")

        return courses

    def _fetch_course_catalog(self, session: requests.Session) -> Dict[str, Any]:
        base_url = f"https://i.chaoxing.com/base?ws=1&t={int(time.time() * 1000)}"
        base_resp = self._fetch_html(session, base_url, referer="https://v1.chaoxing.com/")
        course_home_url = self._extract_course_home_url(base_resp.text, base_resp.url)

        course_home_html = ""
        final_course_home_url = course_home_url
        if course_home_url:
            course_home_resp = self._fetch_html(session, course_home_url, referer=base_resp.url)
            final_course_home_url = course_home_resp.url
            course_home_html = course_home_resp.text

        courses = self._extract_course_cards(course_home_html or base_resp.text, final_course_home_url or base_resp.url)
        return {
            "base_url": base_resp.url,
            "course_home_url": final_course_home_url or "",
            "courses": courses,
        }

    def poll_login_session(self, db: Session, owner_username: str, session_token: str) -> Dict[str, Any]:
        row = self.get_row(db, owner_username, session_token)
        if not row:
            raise ValueError("二维码登录会话不存在")

        if row.status == "confirmed":
            return row.to_dict()

        session = self._get_http_session(row)
        payload = self._post_auth_status(session, row)

        row.last_seen_at = _now_utc()
        row.cookies_json = _cookie_dict_list(session)
        row.last_error = None

        status = bool(payload.get("status"))
        status_type = int(payload.get("type") or 0) if str(payload.get("type") or "").isdigit() else payload.get("type")
        meta = dict(row.browser_meta_json or {})
        meta["last_auth_status"] = payload

        if status:
            pcrefer = str(meta.get("pcrefer") or "https://v1.chaoxing.com/backSchool/toLogin?source=num8").strip()
            login_bridge_resp = session.get(pcrefer, headers={"Referer": "https://passport2.chaoxing.com/"}, timeout=20, allow_redirects=True)
            login_bridge_resp.raise_for_status()

            catalog = self._fetch_course_catalog(session)
            meta["business_landing_url"] = login_bridge_resp.url
            meta["course_catalog"] = catalog.get("courses", [])
            meta["course_base_url"] = catalog.get("base_url", "")
            meta["course_home_url"] = catalog.get("course_home_url", "")
            row.status = "confirmed"
            row.page_title = "登录成功"
            row.expires_at = _now_utc() + timedelta(days=7)
        elif status_type == 4:
            row.status = "scanned"
            row.page_title = str(payload.get("nickname") or "已扫码，待确认").strip() or "已扫码，待确认"
        elif status_type == 6:
            row.status = "expired"
            row.last_error = "用户取消登录"
        else:
            row.status = "scannable"

        row.browser_meta_json = meta
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.to_dict()


_chaoxing_qr_login_service_singleton: ChaoxingQrLoginService | None = None


def get_chaoxing_qr_login_service() -> ChaoxingQrLoginService:
    global _chaoxing_qr_login_service_singleton
    if _chaoxing_qr_login_service_singleton is None:
        _chaoxing_qr_login_service_singleton = ChaoxingQrLoginService()
    return _chaoxing_qr_login_service_singleton
