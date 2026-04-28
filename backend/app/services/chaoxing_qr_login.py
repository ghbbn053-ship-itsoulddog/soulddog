from __future__ import annotations

import base64
import html
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

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

COURSE_METRICS_FETCH_TIMEOUT = 8


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

    def _fetch_optional_html(self, session: requests.Session, url: str, referer: str = "") -> Dict[str, str]:
        if not url:
            return {"url": "", "html": "", "error": ""}
        headers = {}
        if referer:
            headers["Referer"] = referer
        try:
            resp = session.get(url, headers=headers, timeout=COURSE_METRICS_FETCH_TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            return {"url": resp.url, "html": resp.text, "error": ""}
        except Exception as exc:
            return {"url": url, "html": "", "error": str(exc)}

    def _append_query_params(self, url: str, extra_params: Dict[str, Any]) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        for key, value in extra_params.items():
            text = str(value or "").strip()
            if text and key not in query:
                query[key] = text
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _build_course_metric_key(self, course: Dict[str, Any]) -> str:
        course_id = str(course.get("course_id") or "").strip()
        class_id = str(course.get("class_id") or "").strip()
        title = str(course.get("title") or "").strip()
        return f"{course_id}::{class_id}::{title}"

    def _extract_course_page_meta(self, html_text: str, base_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html_text, "lxml")

        def hidden_value(*keys: str) -> str:
            for key in keys:
                node = soup.find("input", {"id": key}) or soup.find("input", {"name": key})
                if node and str(node.get("value") or "").strip():
                    return str(node.get("value") or "").strip()
            return ""

        nav_urls: Dict[str, str] = {}
        for anchor in soup.select("a[title][data-url]"):
            title = str(anchor.get("title") or "").strip()
            data_url = str(anchor.get("data-url") or "").strip()
            if title and data_url:
                nav_urls[title] = urljoin(base_url, html.unescape(data_url))

        iframe = soup.select_one("#frame_content-zj")
        iframe_src = ""
        if iframe:
            iframe_src = urljoin(base_url, html.unescape(str(iframe.get("src") or "").strip()))

        title_node = soup.select_one(".classDl dd, .classDl .textHidden, title")
        course_title = title_node.get_text(" ", strip=True) if title_node else ""

        score_url = ""
        score_match = re.search(
            r"(https://stat2-ans\.chaoxing\.com/stat2/overall-score/stu-score\?[^\"']+)",
            html_text,
            flags=re.I,
        )
        if score_match:
            score_url = html.unescape(score_match.group(1))

        return {
            "course_title": course_title,
            "courseid": hidden_value("courseid", "courseId"),
            "clazzid": hidden_value("clazzid", "clazzId"),
            "cpi": hidden_value("cpi"),
            "enc": hidden_value("enc"),
            "oldenc": hidden_value("oldenc"),
            "workEnc": hidden_value("workEnc"),
            "examEnc": hidden_value("examEnc"),
            "ut": hidden_value("heardUt", "ut") or "s",
            "v": hidden_value("v") or "2",
            "t": hidden_value("t"),
            "mooc_domain": hidden_value("moocDomainName") or "https://mooc1.chaoxing.com",
            "iframe_src": iframe_src,
            "score_url": score_url,
            "nav_urls": nav_urls,
        }

    def _build_course_detail_urls(self, course: Dict[str, Any], page_meta: Dict[str, Any], base_url: str) -> Dict[str, str]:
        course_id = str(page_meta.get("courseid") or course.get("course_id") or "").strip()
        clazz_id = str(page_meta.get("clazzid") or course.get("class_id") or "").strip()
        cpi = str(page_meta.get("cpi") or course.get("cpi") or "").strip()
        ut = str(page_meta.get("ut") or "s").strip() or "s"
        t = str(page_meta.get("t") or int(time.time() * 1000)).strip()
        common_params = {
            "courseid": course_id,
            "courseId": course_id,
            "clazzid": clazz_id,
            "clazzId": clazz_id,
            "classId": clazz_id,
            "cpi": cpi,
            "ut": ut,
            "enc": page_meta.get("enc", ""),
            "oldenc": page_meta.get("oldenc", ""),
            "workEnc": page_meta.get("workEnc", ""),
            "examEnc": page_meta.get("examEnc", ""),
            "v": page_meta.get("v", "2"),
            "t": t,
        }

        chapter_url = str(page_meta.get("iframe_src") or "").strip()
        if not chapter_url:
            chapter_base = str(page_meta.get("nav_urls", {}).get("章节") or "").strip()
            chapter_url = self._append_query_params(chapter_base, common_params)

        work_base = str(page_meta.get("nav_urls", {}).get("作业") or "").strip()
        exam_base = str(page_meta.get("nav_urls", {}).get("考试") or "").strip()
        score_base = str(page_meta.get("score_url") or "").strip()
        mooc_domain = str(page_meta.get("mooc_domain") or "").strip() or "https://mooc1.chaoxing.com"

        if work_base and work_base.startswith("/"):
            work_base = urljoin(mooc_domain, work_base)
        if exam_base and exam_base.startswith("/"):
            exam_base = urljoin(mooc_domain, exam_base)

        return {
            "chapter_url": chapter_url,
            "work_url": self._append_query_params(work_base, common_params),
            "exam_url": self._append_query_params(exam_base, common_params),
            "score_url": self._append_query_params(score_base, common_params),
            "base_url": base_url,
        }

    def _pick_best_count(self, values: List[int]) -> Optional[int]:
        candidates = [value for value in values if isinstance(value, int) and value > 0]
        if not candidates:
            return None
        return max(candidates)

    def _extract_number_near_labels(self, text: str, labels: List[str]) -> Optional[int]:
        compact = re.sub(r"\s+", "", text or "")
        for label in labels:
            match = re.search(rf"{re.escape(label)}[:：]?(?:共)?(\d+)", compact, flags=re.I)
            if match:
                return int(match.group(1))
            match = re.search(rf"(\d+)(?:项|个|门|次)?{re.escape(label)}", compact, flags=re.I)
            if match:
                return int(match.group(1))
        return None

    def _extract_progress_percent(self, text: str) -> Optional[float]:
        compact = re.sub(r"\s+", "", text or "")
        labelled_patterns = [
            r"(?:学习进度|课程进度|当前进度|完成率|平均完成率)[:：]?(\d{1,3}(?:\.\d+)?)%",
            r"(?:已完成|完成)[:：]?(\d{1,3}(?:\.\d+)?)%",
        ]
        for pattern in labelled_patterns:
            match = re.search(pattern, compact, flags=re.I)
            if match:
                return float(match.group(1))
        standalone = [float(value) for value in re.findall(r"(\d{1,3}(?:\.\d+)?)%", compact)]
        standalone = [value for value in standalone if 0 <= value <= 100]
        if standalone:
            return max(standalone)
        return None

    def _parse_chapter_metrics(self, html_text: str) -> Dict[str, Any]:
        if not html_text:
            return {
                "chapter_count": None,
                "completed_chapter_count": None,
                "chapter_completion_percent": None,
            }

        soup = BeautifulSoup(html_text, "lxml")
        text_content = soup.get_text(" ", strip=True)

        chapter_nodes: List[str] = []
        for selector in [
            ".catalog_level",
            ".chapter_unit",
            ".chapter_item",
            ".chapter",
            ".posCatalog_level",
            ".catalog_points li",
            ".chapterList li",
            "li[data-chapterid]",
            "[id^=cur]",
        ]:
            for node in soup.select(selector):
                item_text = node.get_text(" ", strip=True)
                if item_text:
                    chapter_nodes.append(item_text)
        unique_chapters = list(dict.fromkeys(chapter_nodes))

        completed_by_text = sum(1 for item in unique_chapters if re.search(r"(已完成|已学完|100%)", item))
        chapter_count = self._pick_best_count(
            [
                self._extract_number_near_labels(text_content, ["章节", "章", "节"]) or 0,
                len(unique_chapters),
            ]
        )
        completed_chapter_count = self._pick_best_count(
            [
                self._extract_number_near_labels(text_content, ["已完成", "完成章节", "已学完"]) or 0,
                completed_by_text,
            ]
        )
        chapter_completion_percent = self._extract_progress_percent(text_content)
        if chapter_completion_percent is None and chapter_count and completed_chapter_count is not None and chapter_count > 0:
            chapter_completion_percent = round((completed_chapter_count / chapter_count) * 100, 1)

        return {
            "chapter_count": chapter_count,
            "completed_chapter_count": completed_chapter_count,
            "chapter_completion_percent": chapter_completion_percent,
        }

    def _parse_list_count(self, html_text: str, kind: str) -> Dict[str, Any]:
        if not html_text:
            return {"count": None, "completed_count": None}

        soup = BeautifulSoup(html_text, "lxml")
        text_content = soup.get_text(" ", strip=True)
        selectors = {
            "work": [
                ".ulDiv li",
                ".work-list li",
                ".operation .list li",
                "tr[role='row']",
                "tbody tr",
                "li[data-id]",
            ],
            "exam": [
                ".ulDiv li",
                ".exam-list li",
                ".test-list li",
                "tr[role='row']",
                "tbody tr",
                "li[data-id]",
            ],
        }

        items: List[str] = []
        for selector in selectors.get(kind, []):
            for node in soup.select(selector):
                row_text = node.get_text(" ", strip=True)
                if row_text and len(row_text) > 1:
                    items.append(row_text)
        unique_items = list(dict.fromkeys(items))

        label_map = {
            "work": ["作业", "测验", "任务"],
            "exam": ["考试", "测验"],
        }
        total_from_text = self._extract_number_near_labels(text_content, label_map.get(kind, []))
        completed_count = sum(1 for item in unique_items if re.search(r"(已完成|已提交|已结束|已批阅|已交)", item))

        count = self._pick_best_count([total_from_text or 0, len(unique_items)])
        return {
            "count": count,
            "completed_count": completed_count or None,
        }

    def _parse_score_metrics(self, html_text: str) -> Dict[str, Any]:
        if not html_text:
            return {"progress_percent": None, "score_text": "", "status_text": ""}
        soup = BeautifulSoup(html_text, "lxml")
        text_content = soup.get_text(" ", strip=True)
        progress_percent = self._extract_progress_percent(text_content)

        score_text = ""
        score_match = re.search(r"(?:总成绩|综合成绩|成绩)[:：]?\s*([A-Za-z0-9.\-]+)", text_content)
        if score_match:
            score_text = score_match.group(1).strip()

        status_text = ""
        for token in ["已完成", "进行中", "未开始", "待完成"]:
            if token in text_content:
                status_text = token
                break

        return {
            "progress_percent": progress_percent,
            "score_text": score_text,
            "status_text": status_text,
        }

    def _build_course_status(self, metrics: Dict[str, Any]) -> str:
        progress_percent = metrics.get("progress_percent")
        chapter_count = metrics.get("chapter_count")
        completed_chapter_count = metrics.get("completed_chapter_count")
        status_text = str(metrics.get("status_text") or "").strip()

        if isinstance(progress_percent, (int, float)) and progress_percent >= 100:
            return "completed"
        if chapter_count and completed_chapter_count is not None and chapter_count > 0 and completed_chapter_count >= chapter_count:
            return "completed"
        if status_text == "已完成":
            return "completed"
        if isinstance(progress_percent, (int, float)) and progress_percent > 0:
            return "in_progress"
        if completed_chapter_count:
            return "in_progress"
        return "unknown"

    def _fetch_course_metrics(
        self,
        session: requests.Session,
        course: Dict[str, Any],
        course_home_url: str = "",
    ) -> Dict[str, Any]:
        course_url = str(course.get("url") or "").strip()
        if not course_url:
            return {
                "metric_key": self._build_course_metric_key(course),
                "title": str(course.get("title") or "").strip(),
                "status": "unknown",
                "error": "missing course url",
            }

        main_resp = self._fetch_optional_html(session, course_url, referer=course_home_url)
        page_meta = self._extract_course_page_meta(main_resp.get("html", ""), main_resp.get("url", course_url))
        detail_urls = self._build_course_detail_urls(course, page_meta, main_resp.get("url", course_url))

        chapter_resp = self._fetch_optional_html(session, detail_urls.get("chapter_url", ""), referer=main_resp.get("url", course_url))
        work_resp = self._fetch_optional_html(session, detail_urls.get("work_url", ""), referer=main_resp.get("url", course_url))
        exam_resp = self._fetch_optional_html(session, detail_urls.get("exam_url", ""), referer=main_resp.get("url", course_url))
        score_resp = self._fetch_optional_html(session, detail_urls.get("score_url", ""), referer=main_resp.get("url", course_url))

        chapter_metrics = self._parse_chapter_metrics(chapter_resp.get("html", ""))
        work_metrics = self._parse_list_count(work_resp.get("html", ""), "work")
        exam_metrics = self._parse_list_count(exam_resp.get("html", ""), "exam")
        score_metrics = self._parse_score_metrics(score_resp.get("html", "") or main_resp.get("html", ""))

        metrics = {
            "metric_key": self._build_course_metric_key(course),
            "title": str(course.get("title") or page_meta.get("course_title") or "").strip(),
            "teacher": str(course.get("teacher") or "").strip(),
            "course_id": str(page_meta.get("courseid") or course.get("course_id") or "").strip(),
            "class_id": str(page_meta.get("clazzid") or course.get("class_id") or "").strip(),
            "cpi": str(page_meta.get("cpi") or course.get("cpi") or "").strip(),
            "progress_percent": score_metrics.get("progress_percent"),
            "chapter_count": chapter_metrics.get("chapter_count"),
            "completed_chapter_count": chapter_metrics.get("completed_chapter_count"),
            "chapter_completion_percent": chapter_metrics.get("chapter_completion_percent"),
            "assignment_count": work_metrics.get("count"),
            "completed_assignment_count": work_metrics.get("completed_count"),
            "exam_count": exam_metrics.get("count"),
            "completed_exam_count": exam_metrics.get("completed_count"),
            "score_text": score_metrics.get("score_text") or "",
            "status_text": score_metrics.get("status_text") or "",
            "source_urls": {
                "course_url": course_url,
                "chapter_url": chapter_resp.get("url", ""),
                "work_url": work_resp.get("url", ""),
                "exam_url": exam_resp.get("url", ""),
                "score_url": score_resp.get("url", ""),
            },
            "fetch_errors": {
                "course": main_resp.get("error", ""),
                "chapter": chapter_resp.get("error", ""),
                "work": work_resp.get("error", ""),
                "exam": exam_resp.get("error", ""),
                "score": score_resp.get("error", ""),
            },
            "fetched_at": _now_utc().isoformat(),
        }
        metrics["status"] = self._build_course_status(metrics)
        return metrics

    def _fetch_all_course_metrics(
        self,
        session: requests.Session,
        courses: List[Dict[str, Any]],
        course_home_url: str = "",
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for course in courses:
            try:
                results.append(self._fetch_course_metrics(session, course, course_home_url=course_home_url))
            except Exception as exc:
                results.append(
                    {
                        "metric_key": self._build_course_metric_key(course),
                        "title": str(course.get("title") or "").strip(),
                        "teacher": str(course.get("teacher") or "").strip(),
                        "course_id": str(course.get("course_id") or "").strip(),
                        "class_id": str(course.get("class_id") or "").strip(),
                        "cpi": str(course.get("cpi") or "").strip(),
                        "status": "unknown",
                        "error": str(exc),
                        "fetched_at": _now_utc().isoformat(),
                    }
                )
        return results

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
        if not raw_text:
            return []

        patterns = [
            r'https?://[^\s"\'<>]*mycourse/stu\?[^"\'<>]+',
            r'/[^\s"\'<>]*mycourse/stu\?[^"\'<>]+',
            r'https?://[^\s"\'<>]*courseid=[^"\'<>&]+\&clazzid=[^"\'<>]+',
            r'/[^\s"\'<>]*courseid=[^"\'<>&]+\&clazzid=[^"\'<>]+',
        ]

        seen: set[str] = set()
        urls: List[str] = []
        for pattern in patterns:
            for match in re.findall(pattern, raw_text, flags=re.I):
                normalized = urljoin(base_url, html.unescape(match))
                if normalized in seen:
                    continue
                seen.add(normalized)
                urls.append(normalized)
        return urls

    def _extract_course_cards(self, html_text: str, base_url: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html_text, "lxml")
        courses: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def add_course(url: str, title: str, teacher: str = "", image: str = "") -> None:
            lowered = url.lower()
            if "courseid=" not in lowered or "clazzid=" not in lowered:
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

        if not courses:
            for node in soup.select("[dataurl], [onclick], iframe[src], a[href]"):
                values = [str(node.get(attr) or "") for attr in ("href", "dataurl", "onclick", "src")]
                candidate_urls: List[str] = []
                for value in values:
                    candidate_urls.extend(self._extract_candidate_course_urls(value, base_url))
                if not candidate_urls:
                    continue
                title = ""
                teacher = ""
                container = node.find_parent(["li", "div", "section", "article"]) if hasattr(node, "find_parent") else None
                if container:
                    title_node = container.select_one(
                        "h3, h4, h5, h6, .course-name, .overHidden2, .zt_name, .catalog_name, .clazzname"
                    )
                    teacher_node = container.select_one(".teacher, .color3, .course-teacher, .person, .teaName")
                    title = title_node.get_text(" ", strip=True) if title_node else ""
                    teacher = teacher_node.get_text(" ", strip=True) if teacher_node else ""
                for candidate_url in candidate_urls:
                    add_course(candidate_url, title, teacher)

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
            course_catalog = catalog.get("courses", [])
            course_home_url = catalog.get("course_home_url", "")
            meta["business_landing_url"] = login_bridge_resp.url
            meta["course_catalog"] = course_catalog
            meta["course_base_url"] = catalog.get("base_url", "")
            meta["course_home_url"] = course_home_url
            meta["course_metrics"] = self._fetch_all_course_metrics(session, course_catalog, course_home_url=course_home_url)
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
