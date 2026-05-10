from __future__ import annotations

import hashlib
import json
import re
import secrets
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.platform import ExternalServiceBinding, Workspace
from app.models.question_bank import (
    LearningActivity,
    LearningAutomationEvent,
    LearningAutomationTask,
    LearningQuestion,
    LearningQuestionAttempt,
    LearningStudyMemory,
)
from app.services.model_provider import get_model_provider_for_user
from app.services.session_store import get_session_store

SERVICE_NAME = "chaoxing_learning"


def default_automation_profile() -> Dict[str, Any]:
    return {
        "site_kind": "browser_simulation",
        "login_url": "https://v8.chaoxing.com/",
        "login_mode": "qr_iframe",
        "login_qr_iframe_selector": "#iframe",
        "login_tab_selector": ".login-area .tab li",
        "course_entry_url_keyword": "mycourse/stu?courseid",
        "study_page_url_keyword": "/mycourse/studentstudy",
        "course_main_iframe_selector": "#frame_content-zj",
        "chapter_nav_selector": 'a[title="章节"]',
        "task_nav_selector": 'a[title="任务"]',
        "work_nav_selector": 'a[title="作业"]',
        "exam_nav_selector": 'a[title="考试"]',
        "next_chapter_selectors": [
            "#prevNextFocusNext",
            ".jb_btn.jb_btn_92.fr.fs14.nextChapter",
        ],
        "task_iframe_strategy": "scan_nested_iframes",
        "task_types": [
            "video",
            "audio",
            "ppt",
            "document",
            "work",
            "exam",
        ],
        "question_roots": [
            ".TiMu",
            ".questionLi",
            ".examPaper_subject",
        ],
        "control_channel": "browser_local_storage",
        "runner_storage_prefix": "soulddog-learning-runner",
        "allowed_host_keywords": [
            "chaoxing.com",
            "mycourse",
        ],
        "notes": [
            "二维码登录有时效，适合浏览器侧自动化 runner。",
            "课程页通过 iframe 承载章节学习内容，任务识别要支持多层 iframe。",
            "范本脚本的主逻辑是：识别 URL -> 扫描 iframe -> 区分视频/作业/考试 -> 执行对应动作。",
        ],
    }


def default_browser_bridge() -> Dict[str, Any]:
    return {
        "token": f"lb_{secrets.token_urlsafe(24)}",
        "course_catalog": [],
        "last_course_sync_at": None,
        "last_seen_at": None,
        "last_seen_url": "",
        "pending_command": None,
        "active_task_id": None,
    }


def _workspace_filter(query, workspace_id: int | None):
    if workspace_id:
        query = query.filter(LearningQuestion.workspace_id == workspace_id)
    return query


class LearningAssistantService:
    def ensure_binding(self, db: Session, owner_username: str) -> ExternalServiceBinding:
        binding = (
            db.query(ExternalServiceBinding)
            .filter(
                ExternalServiceBinding.owner_username == owner_username,
                ExternalServiceBinding.service_name == SERVICE_NAME,
            )
            .first()
        )
        if not binding:
            binding = ExternalServiceBinding(
                owner_username=owner_username,
                service_name=SERVICE_NAME,
                auth_type="manual_assist",
                status="pending",
                display_name="学习平台辅助",
                metadata_json={},
            )
            db.add(binding)
            db.commit()
            db.refresh(binding)

        metadata = dict(binding.metadata_json or {})
        metadata.setdefault("connection_mode", "manual_assist")
        metadata.setdefault("verified", False)
        metadata.setdefault("automation_profile", default_automation_profile())
        metadata.setdefault(
            "capabilities",
            [
                "question_bank",
                "activity_log",
                "ai_explanation",
                "workspace_link",
                "automation_profile",
                "browser_bridge",
            ],
        )
        metadata.setdefault("browser_bridge", default_browser_bridge())
        binding.metadata_json = metadata
        db.add(binding)
        db.commit()
        db.refresh(binding)
        return binding

    def update_binding_profile(
        self,
        db: Session,
        owner_username: str,
        display_name: str = "",
        note: str = "",
        account_label: str = "",
    ) -> ExternalServiceBinding:
        binding = self.ensure_binding(db, owner_username)
        metadata = dict(binding.metadata_json or {})
        metadata["note"] = note.strip()
        metadata["account_label"] = account_label.strip()
        metadata["updated_by_user"] = True
        binding.display_name = display_name.strip() or binding.display_name or "学习平台辅助"
        binding.metadata_json = metadata
        if binding.status not in {"active", "pending"}:
            binding.status = "pending"
        db.add(binding)
        db.commit()
        db.refresh(binding)
        return binding

    def update_automation_profile(
        self,
        db: Session,
        owner_username: str,
        profile_patch: Dict[str, Any],
    ) -> ExternalServiceBinding:
        binding = self.ensure_binding(db, owner_username)
        metadata = dict(binding.metadata_json or {})
        profile = dict(metadata.get("automation_profile") or default_automation_profile())
        for key, value in (profile_patch or {}).items():
            profile[key] = value
        metadata["automation_profile"] = profile
        metadata.setdefault("browser_bridge", default_browser_bridge())
        binding.metadata_json = metadata
        db.add(binding)
        db.commit()
        db.refresh(binding)
        return binding

    def get_browser_bridge(self, db: Session, owner_username: str) -> Dict[str, Any]:
        binding = self.ensure_binding(db, owner_username)
        metadata = dict(binding.metadata_json or {})
        bridge = dict(metadata.get("browser_bridge") or default_browser_bridge())
        if not bridge.get("token"):
            bridge["token"] = default_browser_bridge()["token"]
            metadata["browser_bridge"] = bridge
            binding.metadata_json = metadata
            db.add(binding)
            db.commit()
            db.refresh(binding)
        return bridge

    def _find_binding_by_bridge_token(self, db: Session, bridge_token: str) -> Optional[ExternalServiceBinding]:
        rows = (
            db.query(ExternalServiceBinding)
            .filter(ExternalServiceBinding.service_name == SERVICE_NAME)
            .all()
        )
        for row in rows:
            metadata = dict(row.metadata_json or {})
            bridge = dict(metadata.get("browser_bridge") or {})
            if bridge.get("token") == bridge_token:
                return row
        return None

    def sync_course_catalog(
        self,
        db: Session,
        *,
        bridge_token: str,
        courses: List[Dict[str, Any]],
        current_url: str,
        page_title: str,
    ) -> Dict[str, Any]:
        binding = self._find_binding_by_bridge_token(db, bridge_token)
        if not binding:
            raise ValueError("bridge token 无效")
        metadata = dict(binding.metadata_json or {})
        bridge = dict(metadata.get("browser_bridge") or default_browser_bridge())
        normalized = []
        for item in courses or []:
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            if not url or not title:
                continue
            normalized.append(
                {
                    "title": title,
                    "url": url,
                    "teacher": str(item.get("teacher") or "").strip(),
                    "course_id": str(item.get("course_id") or "").strip(),
                    "class_id": str(item.get("class_id") or "").strip(),
                    "image": str(item.get("image") or "").strip(),
                }
            )
        bridge["course_catalog"] = normalized
        bridge["last_course_sync_at"] = datetime.now(timezone.utc).isoformat()
        bridge["last_seen_at"] = bridge["last_course_sync_at"]
        bridge["last_seen_url"] = current_url.strip()
        bridge["last_page_title"] = page_title.strip()
        metadata["browser_bridge"] = bridge
        binding.metadata_json = metadata
        db.add(binding)
        db.commit()
        return {
            "owner_username": binding.owner_username,
            "count": len(normalized),
            "last_course_sync_at": bridge["last_course_sync_at"],
        }

    def touch_browser_bridge(
        self,
        db: Session,
        *,
        bridge_token: str,
        current_url: str,
        page_title: str,
    ) -> Dict[str, Any]:
        binding = self._find_binding_by_bridge_token(db, bridge_token)
        if not binding:
            raise ValueError("bridge token 无效")
        metadata = dict(binding.metadata_json or {})
        bridge = dict(metadata.get("browser_bridge") or default_browser_bridge())
        bridge["last_seen_at"] = datetime.now(timezone.utc).isoformat()
        bridge["last_seen_url"] = current_url.strip()
        bridge["last_page_title"] = page_title.strip()
        metadata["browser_bridge"] = bridge
        binding.metadata_json = metadata
        db.add(binding)
        db.commit()
        return {
            "owner_username": binding.owner_username,
            "last_seen_at": bridge["last_seen_at"],
        }

    def poll_browser_bridge_state(self, db: Session, bridge_token: str) -> Dict[str, Any]:
        binding = self._find_binding_by_bridge_token(db, bridge_token)
        if not binding:
            raise ValueError("bridge token 无效")
        metadata = dict(binding.metadata_json or {})
        bridge = dict(metadata.get("browser_bridge") or default_browser_bridge())
        active_task = None
        active_task_id = bridge.get("active_task_id")
        if active_task_id:
            row = self.get_automation_task(db, binding.owner_username, int(active_task_id))
            if row:
                active_task = row.to_dict()
        return {
            "owner_username": binding.owner_username,
            "bridge": bridge,
            "active_task": active_task,
            "automation_profile": (dict(binding.metadata_json or {}).get("automation_profile") or default_automation_profile()),
        }

    def ack_browser_command(self, db: Session, bridge_token: str, command_id: str) -> None:
        binding = self._find_binding_by_bridge_token(db, bridge_token)
        if not binding:
            raise ValueError("bridge token 无效")
        metadata = dict(binding.metadata_json or {})
        bridge = dict(metadata.get("browser_bridge") or default_browser_bridge())
        pending = bridge.get("pending_command") or {}
        if pending.get("id") == command_id:
            bridge["pending_command"] = None
            metadata["browser_bridge"] = bridge
            binding.metadata_json = metadata
            db.add(binding)
            db.commit()

    def queue_open_course_command(
        self,
        db: Session,
        *,
        owner_username: str,
        task_id: int,
        course_url: str,
    ) -> Dict[str, Any]:
        binding = self.ensure_binding(db, owner_username)
        metadata = dict(binding.metadata_json or {})
        bridge = dict(metadata.get("browser_bridge") or default_browser_bridge())
        command = {
            "id": f"cmd_{secrets.token_urlsafe(12)}",
            "kind": "open_course",
            "course_url": course_url.strip(),
            "task_id": task_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        bridge["pending_command"] = command
        bridge["active_task_id"] = task_id
        metadata["browser_bridge"] = bridge
        binding.metadata_json = metadata
        db.add(binding)
        db.commit()
        return command

    def _workspace_name(self, db: Session, owner_username: str, workspace_id: int | None) -> str:
        if not workspace_id:
            return ""
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == workspace_id, Workspace.owner_username == owner_username)
            .first()
        )
        return workspace.name if workspace else ""

    def get_overview(self, db: Session, owner_username: str, workspace_id: int | None = None) -> Dict[str, Any]:
        binding = self.ensure_binding(db, owner_username)
        question_query = db.query(LearningQuestion).filter(LearningQuestion.owner_username == owner_username)
        activity_query = db.query(LearningActivity).filter(LearningActivity.owner_username == owner_username)
        attempt_query = db.query(LearningQuestionAttempt).filter(LearningQuestionAttempt.owner_username == owner_username)
        if workspace_id:
            question_query = question_query.filter(LearningQuestion.workspace_id == workspace_id)
            activity_query = activity_query.filter(LearningActivity.workspace_id == workspace_id)
            attempt_query = attempt_query.filter(LearningQuestionAttempt.workspace_id == workspace_id)

        questions = question_query.order_by(LearningQuestion.created_at.desc()).limit(200).all()
        activities = activity_query.order_by(LearningActivity.created_at.desc()).limit(20).all()
        attempts = attempt_query.order_by(LearningQuestionAttempt.created_at.desc()).limit(50).all()

        verified_count = sum(1 for item in questions if item.verified_status == "verified")
        reviewed_count = sum(1 for item in questions if item.verified_status == "reviewed")
        course_names = [item.course_name for item in questions if (item.course_name or "").strip()]
        activity_types = Counter(item.activity_type for item in activities if item.activity_type)
        attempt_status = Counter(item.result_status for item in attempts if item.result_status)
        metadata = dict(binding.metadata_json or {})

        return {
            "binding": {
                "service_name": binding.service_name,
                "status": binding.status,
                "auth_type": binding.auth_type,
                "display_name": binding.display_name,
                "last_verified_at": binding.last_verified_at.isoformat() if binding.last_verified_at else None,
                "connection_mode": metadata.get("connection_mode", "manual_assist"),
                "verified": bool(metadata.get("verified")),
                "note": metadata.get("note", ""),
                "account_label": metadata.get("account_label", ""),
                "capabilities": metadata.get("capabilities", []),
                "automation_profile": metadata.get("automation_profile") or default_automation_profile(),
            },
            "workspace": {
                "id": workspace_id,
                "name": self._workspace_name(db, owner_username, workspace_id),
            },
            "metrics": {
                "questions": len(questions),
                "verified_questions": verified_count,
                "reviewed_questions": reviewed_count,
                "activities": len(activities),
                "attempts": len(attempts),
                "distinct_courses": len(set(course_names)),
            },
            "signals": {
                "top_activity_types": [{"name": key, "count": value} for key, value in activity_types.most_common(4)],
                "attempt_status": [{"name": key, "count": value} for key, value in attempt_status.most_common(4)],
            },
            "recent_questions": [item.to_dict() for item in questions[:5]],
            "recent_activities": [item.to_dict() for item in activities[:6]],
        }

    def create_automation_task(
        self,
        db: Session,
        *,
        owner_username: str,
        workspace_id: int | None,
        task_name: str,
        course_name: str,
        course_url: str,
        start_url: str,
        automation_options: Optional[Dict[str, Any]] = None,
    ) -> LearningAutomationTask:
        if not course_url.strip():
            raise ValueError("course_url 不能为空")
        task = LearningAutomationTask(
            owner_username=owner_username,
            workspace_id=workspace_id,
            platform_name="chaoxing",
            task_name=task_name.strip() or "浏览器自动化任务",
            course_name=course_name.strip() or None,
            course_url=course_url.strip(),
            start_url=(start_url or "").strip() or course_url.strip(),
            status="pending",
            runner_token=f"lr_{secrets.token_urlsafe(24)}",
            automation_options_json=automation_options or {},
            runner_meta_json={},
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        self.log_automation_event(
            db,
            task=task,
            event_type="task_created",
            level="info",
            stage="control",
            message="控制台已创建自动化任务，等待浏览器 runner 接管",
            current_url=task.start_url,
            payload={"automation_options": task.automation_options_json or {}},
        )
        db.refresh(task)
        return task

    def list_automation_tasks(
        self,
        db: Session,
        owner_username: str,
        workspace_id: int | None = None,
        limit: int = 20,
    ) -> List[LearningAutomationTask]:
        rows = db.query(LearningAutomationTask).filter(LearningAutomationTask.owner_username == owner_username)
        if workspace_id:
            rows = rows.filter(LearningAutomationTask.workspace_id == workspace_id)
        return rows.order_by(LearningAutomationTask.created_at.desc()).limit(max(1, min(limit, 50))).all()

    def get_automation_task(
        self,
        db: Session,
        owner_username: str,
        task_id: int,
    ) -> Optional[LearningAutomationTask]:
        return (
            db.query(LearningAutomationTask)
            .filter(
                LearningAutomationTask.id == task_id,
                LearningAutomationTask.owner_username == owner_username,
            )
            .first()
        )

    def list_automation_events(
        self,
        db: Session,
        owner_username: str,
        task_id: int,
        limit: int = 100,
    ) -> List[LearningAutomationEvent]:
        task = self.get_automation_task(db, owner_username, task_id)
        if not task:
            return []
        return (
            db.query(LearningAutomationEvent)
            .filter(LearningAutomationEvent.task_id == task.id, LearningAutomationEvent.owner_username == owner_username)
            .order_by(LearningAutomationEvent.created_at.desc())
            .limit(max(1, min(limit, 300)))
            .all()
        )

    def update_automation_task_status(
        self,
        db: Session,
        *,
        owner_username: str,
        task_id: int,
        status: str,
    ) -> LearningAutomationTask:
        task = self.get_automation_task(db, owner_username, task_id)
        if not task:
            raise ValueError("任务不存在")
        task.status = (status or "pending").strip() or "pending"
        if task.status == "running" and not task.started_at:
            task.started_at = datetime.now(timezone.utc)
        if task.status in {"completed", "failed", "stopped"}:
            task.finished_at = datetime.now(timezone.utc)
        db.add(task)
        db.commit()
        db.refresh(task)
        self.log_automation_event(
            db,
            task=task,
            event_type="task_status",
            level="info",
            stage=task.last_stage or "control",
            message=f"任务状态更新为 {task.status}",
            current_url=task.last_url or task.start_url,
            payload={},
        )
        db.refresh(task)
        return task

    def get_automation_task_by_token(self, db: Session, runner_token: str) -> Optional[LearningAutomationTask]:
        return db.query(LearningAutomationTask).filter(LearningAutomationTask.runner_token == runner_token).first()

    def log_automation_event(
        self,
        db: Session,
        *,
        task: LearningAutomationTask,
        event_type: str,
        level: str,
        stage: str,
        message: str,
        current_url: str,
        payload: Optional[Dict[str, Any]] = None,
        status_hint: Optional[str] = None,
    ) -> LearningAutomationEvent:
        event = LearningAutomationEvent(
            task_id=task.id,
            owner_username=task.owner_username,
            event_type=(event_type or "log").strip() or "log",
            level=(level or "info").strip() or "info",
            stage=(stage or "").strip() or None,
            message=message.strip() or "runner event",
            current_url=(current_url or "").strip() or None,
            payload_json=payload or {},
        )
        task.last_stage = (stage or "").strip() or task.last_stage
        task.last_url = (current_url or "").strip() or task.last_url
        task.last_message = message.strip() or task.last_message
        task.last_ping_at = datetime.now(timezone.utc)
        if status_hint:
            task.status = status_hint
            if status_hint == "running" and not task.started_at:
                task.started_at = datetime.now(timezone.utc)
            if status_hint in {"completed", "failed", "stopped"}:
                task.finished_at = datetime.now(timezone.utc)
        db.add(event)
        db.add(task)
        db.commit()
        db.refresh(event)
        return event

    def build_runner_manifest(
        self,
        db: Session,
        *,
        owner_username: str,
        task_id: int,
    ) -> Dict[str, Any]:
        task = self.get_automation_task(db, owner_username, task_id)
        if not task:
            raise ValueError("任务不存在")
        binding = self.ensure_binding(db, owner_username)
        profile = dict(binding.metadata_json or {}).get("automation_profile") or default_automation_profile()
        return {
            "task": task.to_dict(),
            "profile": profile,
            "runner_api": {
                "event_url": f"/api/chaoxing/automation/tasks/{task.id}/runner-events",
            },
            "notes": [
                "runner 必须在目标课程页自己的浏览器上下文执行，控制台页面本身不会跨域操控 DOM。",
                "推荐先点击“打开课程页”，完成登录后，再把注入脚本粘贴到课程页控制台执行。",
            ],
        }

    def build_runner_script_text(self, task: Dict[str, Any], profile: Dict[str, Any], task_id: int) -> str:
        task_json = json.dumps(task, ensure_ascii=False)
        profile_json = json.dumps(profile, ensure_ascii=False)
        event_url = f"/api/chaoxing/automation/tasks/{task_id}/runner-events"
        return f"""
(() => {{
  const task = {task_json};
  const profile = {profile_json};
  const apiBase = window.location.origin;
  const eventUrl = apiBase + "{event_url}";
  const storagePrefix = profile.runner_storage_prefix || "soulddog-learning-runner";
  const stateKey = `${{storagePrefix}}:${{task.id}}:state`;
  const eventLogKey = `${{storagePrefix}}:${{task.id}}:events`;

  const persistState = (patch) => {{
    const current = JSON.parse(localStorage.getItem(stateKey) || "{{}}");
    const next = {{
      ...current,
      ...patch,
      task_id: task.id,
      updated_at: new Date().toISOString(),
    }};
    localStorage.setItem(stateKey, JSON.stringify(next));
    return next;
  }};

  const appendLocalEvent = (evt) => {{
    const current = JSON.parse(localStorage.getItem(eventLogKey) || "[]");
    const next = [evt, ...current].slice(0, 100);
    localStorage.setItem(eventLogKey, JSON.stringify(next));
  }};

  const emit = async (eventType, message, extra = {{}}) => {{
    const body = {{
      runner_token: task.runner_token,
      event_type: eventType,
      level: extra.level || "info",
      stage: extra.stage || "",
      message,
      current_url: location.href,
      payload: extra.payload || {{}},
      status_hint: extra.status_hint || null,
    }};
    appendLocalEvent({{
      ...body,
      created_at: new Date().toISOString(),
    }});
    persistState({{
      status: body.status_hint || "running",
      stage: body.stage || "",
      current_url: location.href,
      message,
    }});
    try {{
      await fetch(eventUrl, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        credentials: "include",
        body: JSON.stringify(body),
      }});
    }} catch (error) {{
      console.warn("[runner] failed to sync event", error);
    }}
  }};

  const detectStage = () => {{
    const href = location.href;
    if (href.includes(profile.course_entry_url_keyword || "")) return "course_entry";
    if (href.includes(profile.study_page_url_keyword || "")) return "study_page";
    if (href.includes("v8.chaoxing.com")) return "login_or_home";
    return "unknown";
  }};

  const safeCount = (selector) => {{
    try {{
      return selector ? document.querySelectorAll(selector).length : 0;
    }} catch {{
      return 0;
    }}
  }};

  const scanFrames = () => {{
    const frames = Array.from(document.querySelectorAll("iframe"));
    return frames.map((frame, index) => {{
      let href = "";
      try {{
        href = frame.contentWindow?.location?.href || "";
      }} catch {{}}
      return {{
        index,
        id: frame.id || "",
        name: frame.name || "",
        src: frame.getAttribute("src") || "",
        href,
      }};
    }});
  }};

  const nextSelectors = Array.isArray(profile.next_chapter_selectors) ? profile.next_chapter_selectors : [];
  const summary = {{
    title: document.title,
    detected_stage: detectStage(),
    iframe_count: document.querySelectorAll("iframe").length,
    chapter_nav_count: safeCount(profile.chapter_nav_selector),
    task_nav_count: safeCount(profile.task_nav_selector),
    work_nav_count: safeCount(profile.work_nav_selector),
    exam_nav_count: safeCount(profile.exam_nav_selector),
    next_button_count: nextSelectors.reduce((count, selector) => count + safeCount(selector), 0),
    question_root_hits: Array.isArray(profile.question_roots)
      ? profile.question_roots.map((selector) => ({{ selector, count: safeCount(selector) }}))
      : [],
    frames: scanFrames(),
  }};

  persistState({{
    task_id: task.id,
    task_name: task.task_name,
    course_name: task.course_name,
    course_url: task.course_url,
    current_url: location.href,
    status: "running",
    stage: summary.detected_stage,
    title: document.title,
  }});

  emit("runner_started", "浏览器 runner 已挂载到当前页面", {{
    stage: summary.detected_stage,
    status_hint: "running",
    payload: summary,
  }});

  window.__SOULDDOG_LEARNING_RUNNER__ = {{
    task,
    profile,
    emit,
    detectStage,
    scanFrames,
    summary,
    persistState,
  }};

  console.log("[soulddog runner] mounted", {{ task, profile, summary }});
}})();
""".strip()

    def list_questions(
        self,
        db: Session,
        owner_username: str,
        workspace_id: int | None = None,
        limit: int = 50,
        query: str = "",
    ) -> List[LearningQuestion]:
        rows = db.query(LearningQuestion).filter(LearningQuestion.owner_username == owner_username)
        if workspace_id:
            rows = rows.filter(LearningQuestion.workspace_id == workspace_id)
        if query.strip():
            rows = rows.filter(LearningQuestion.title.ilike(f"%{query.strip()}%"))
        return rows.order_by(LearningQuestion.created_at.desc()).limit(max(1, min(limit, 200))).all()

    def save_question(
        self,
        db: Session,
        *,
        owner_username: str,
        workspace_id: int | None,
        platform_name: str,
        course_name: str,
        chapter_name: str,
        title: str,
        question_type: str,
        options: List[str],
        answer: List[str],
        explanation: str,
        source: str,
        verified_status: str,
        tags: List[str],
        created_by: str,
    ) -> LearningQuestion:
        existing = (
            db.query(LearningQuestion)
            .filter(
                LearningQuestion.owner_username == owner_username,
                LearningQuestion.workspace_id == workspace_id,
                LearningQuestion.platform_name == (platform_name or "chaoxing"),
                LearningQuestion.title == title.strip(),
            )
            .first()
        )
        row = existing or LearningQuestion(owner_username=owner_username)
        row.workspace_id = workspace_id
        row.platform_name = (platform_name or "chaoxing").strip() or "chaoxing"
        row.course_name = course_name.strip() or None
        row.chapter_name = chapter_name.strip() or None
        row.title = title.strip()
        row.question_type = (question_type or "unknown").strip() or "unknown"
        row.options_json = [item.strip() for item in options if str(item).strip()]
        row.answer_json = [item.strip() for item in answer if str(item).strip()]
        row.explanation_text = explanation.strip() or None
        row.source = (source or "manual").strip() or "manual"
        row.verified_status = (verified_status or "draft").strip() or "draft"
        row.tags_json = [item.strip() for item in tags if str(item).strip()]
        row.created_by = created_by.strip() or owner_username
        if not existing:
            db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def list_activities(
        self,
        db: Session,
        owner_username: str,
        workspace_id: int | None = None,
        limit: int = 30,
    ) -> List[LearningActivity]:
        rows = db.query(LearningActivity).filter(LearningActivity.owner_username == owner_username)
        if workspace_id:
            rows = rows.filter(LearningActivity.workspace_id == workspace_id)
        return rows.order_by(LearningActivity.created_at.desc()).limit(max(1, min(limit, 100))).all()

    def log_activity(
        self,
        db: Session,
        *,
        owner_username: str,
        workspace_id: int | None,
        platform_name: str,
        activity_type: str,
        title: str,
        course_name: str,
        chapter_name: str,
        status: str,
        detail: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> LearningActivity:
        row = LearningActivity(
            owner_username=owner_username,
            workspace_id=workspace_id,
            platform_name=(platform_name or "chaoxing").strip() or "chaoxing",
            activity_type=(activity_type or "study_note").strip() or "study_note",
            title=title.strip(),
            course_name=course_name.strip() or None,
            chapter_name=chapter_name.strip() or None,
            status=(status or "recorded").strip() or "recorded",
            detail_text=detail.strip() or None,
            meta_json=meta or {},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def _normalize_memory_text(text: str) -> str:
        value = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        return re.sub(r"\s+", " ", value)

    @staticmethod
    def _shorten_text(text: str, limit: int = 120) -> str:
        value = LearningAssistantService._normalize_memory_text(text)
        if len(value) <= limit:
            return value
        return value[: max(0, limit - 1)].rstrip() + "…"

    @staticmethod
    def _should_capture_learning_memory(question_text: str) -> bool:
        q = LearningAssistantService._normalize_memory_text(question_text)
        if len(q) < 6:
            return False
        low_value_exact = {
            "你好",
            "在吗",
            "收到吗",
            "继续",
            "下一步",
            "好的",
            "可以",
            "行",
            "嗯",
            "测试",
            "1",
            "2",
            "3",
        }
        if q.lower() in low_value_exact:
            return False
        low_value_fragments = [
            "谢谢",
            "辛苦了",
            "先这样",
            "回头再说",
            "晚点再说",
            "就这样",
            "推送代码",
            "继续做",
            "开始吧",
        ]
        if any(fragment in q for fragment in low_value_fragments):
            return False
        learning_signal_fragments = [
            "为什么",
            "怎么",
            "如何",
            "区别",
            "原理",
            "概念",
            "定义",
            "推导",
            "证明",
            "计算",
            "步骤",
            "公式",
            "题",
            "不会",
            "不懂",
            "记不住",
            "复习",
            "总结",
            "易错",
            "重点",
        ]
        return any(fragment in q for fragment in learning_signal_fragments) or len(q) >= 18

    @staticmethod
    def _infer_memory_question_type(question_text: str) -> str:
        q = (question_text or "").strip()
        if not q:
            return "general"
        if any(keyword in q for keyword in ["怎么做", "如何做", "步骤", "流程", "做题", "例题", "题目", "习题"]):
            return "practice"
        if any(keyword in q for keyword in ["为什么", "原理", "概念", "定义", "是什么"]):
            return "concept"
        if any(keyword in q for keyword in ["区别", "对比", "容易混淆", "怎么区分", "分不清"]):
            return "confusion"
        if any(keyword in q for keyword in ["记不住", "背", "重点", "复习", "总结"]):
            return "review"
        if any(keyword in q for keyword in ["推导", "证明", "公式", "计算"]):
            return "reasoning"
        return "general"

    @staticmethod
    def _infer_memory_importance(question_text: str, answer_text: str = "") -> int:
        text = f"{question_text}\n{answer_text}"
        score = 3
        for keyword in ["不会", "不懂", "卡住", "搞不清", "分不清", "忘了", "记不住"]:
            if keyword in text:
                score += 1
        for keyword in ["考试", "重点", "高频", "必考"]:
            if keyword in text:
                score += 1
        return max(1, min(score, 5))

    @staticmethod
    def _extract_memory_points(question_text: str, answer_text: str = "", limit: int = 6) -> List[str]:
        raw = f"{question_text}\n{answer_text}"
        candidates = re.findall(r"[\u4e00-\u9fffA-Za-z0-9_+\-]{2,}", raw)
        stop_words = {
            "这个", "那个", "什么", "怎么", "如何", "为什么", "是不是", "然后", "一个",
            "我们", "你们", "他们", "老师", "课件", "课程", "知识", "问题", "学习",
        }
        points: List[str] = []
        for item in candidates:
            token = item.strip()
            if len(token) < 2 or token in stop_words:
                continue
            if token not in points:
                points.append(token)
            if len(points) >= limit:
                break
        return points

    @staticmethod
    def _fingerprint_memory(owner_username: str, workspace_id: int | None, question_text: str) -> str:
        raw = f"{owner_username}:{workspace_id or 0}:{LearningAssistantService._normalize_memory_text(question_text).lower()}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def record_learning_memory(
        self,
        db: Session,
        *,
        owner_username: str,
        workspace_id: int | None,
        question_text: str,
        answer_text: str = "",
        course_name: str = "",
        status: str = "unresolved",
        source_refs: Optional[Dict[str, Any]] = None,
        conversation_id: int | None = None,
        prompt_strategy: str = "",
    ) -> Optional[LearningStudyMemory]:
        normalized_question = self._normalize_memory_text(question_text)
        if len(normalized_question) < 4:
            return None
        if not self._should_capture_learning_memory(normalized_question):
            return None
        fingerprint = self._fingerprint_memory(owner_username, workspace_id, normalized_question)
        existing = (
            db.query(LearningStudyMemory)
            .filter(
                LearningStudyMemory.owner_username == owner_username,
                LearningStudyMemory.workspace_id == workspace_id,
                LearningStudyMemory.question_fingerprint == fingerprint,
            )
            .first()
        )
        memory_course_name = course_name.strip() or self._workspace_name(db, owner_username, workspace_id)
        row = existing or LearningStudyMemory(
            owner_username=owner_username,
            workspace_id=workspace_id,
            question_fingerprint=fingerprint,
        )
        row.course_name = memory_course_name or None
        row.question_text = normalized_question
        row.question_summary = self._shorten_text(normalized_question, 160)
        row.question_type = self._infer_memory_question_type(normalized_question)
        row.knowledge_points_json = self._extract_memory_points(normalized_question, answer_text, limit=6)
        row.status = (status or "unresolved").strip() or "unresolved"
        row.answer_summary = self._shorten_text(answer_text, 280) if answer_text else (row.answer_summary or "")
        next_source_refs = dict(source_refs or {})
        if prompt_strategy.strip():
            next_source_refs["prompt_strategy"] = prompt_strategy.strip()
        row.source_refs_json = next_source_refs
        row.importance = self._infer_memory_importance(normalized_question, answer_text)
        row.conversation_id = conversation_id
        if not existing:
            db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def list_learning_memories(
        self,
        db: Session,
        owner_username: str,
        workspace_id: int | None = None,
        *,
        status: str = "",
        query: str = "",
        course_name: str = "",
        question_type: str = "",
        knowledge_point: str = "",
        limit: int = 20,
        apply_limit: bool = True,
    ) -> List[LearningStudyMemory]:
        rows = db.query(LearningStudyMemory).filter(LearningStudyMemory.owner_username == owner_username)
        if workspace_id:
            rows = rows.filter(LearningStudyMemory.workspace_id == workspace_id)
        if status:
            rows = rows.filter(LearningStudyMemory.status == status)
        if query.strip():
            q = f"%{query.strip()}%"
            rows = rows.filter(
                (LearningStudyMemory.question_text.ilike(q))
                | (LearningStudyMemory.question_summary.ilike(q))
                | (LearningStudyMemory.answer_summary.ilike(q))
            )
        rows = rows.order_by(
            (LearningStudyMemory.status == "resolved").asc(),
            LearningStudyMemory.importance.desc(),
            LearningStudyMemory.updated_at.desc(),
            LearningStudyMemory.created_at.desc(),
        )
        items = rows.all()
        if course_name.strip():
            target_course = course_name.strip()
            items = [item for item in items if (item.course_name or "未命名课程") == target_course]
        if question_type.strip():
            target_type = question_type.strip()
            items = [item for item in items if (item.question_type or "").strip() == target_type]
        if knowledge_point.strip():
            target_point = knowledge_point.strip()
            filtered_items = []
            for item in items:
                points = [str(point).strip() for point in (item.knowledge_points_json or []) if str(point).strip()]
                if target_point in points:
                    filtered_items.append(item)
            items = filtered_items
        if apply_limit:
            items = items[: max(1, min(limit, 100))]
        return items

    def update_learning_memory_status(
        self,
        db: Session,
        owner_username: str,
        memory_id: int,
        status: str,
    ) -> LearningStudyMemory:
        row = (
            db.query(LearningStudyMemory)
            .filter(LearningStudyMemory.id == memory_id, LearningStudyMemory.owner_username == owner_username)
            .first()
        )
        if not row:
            raise ValueError("学习疑问不存在")
        row.status = (status or "unresolved").strip() or "unresolved"
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def get_learning_memory_overview(
        self,
        db: Session,
        owner_username: str,
        workspace_id: int | None = None,
        *,
        status: str = "",
        query: str = "",
        course_name: str = "",
        question_type: str = "",
        knowledge_point: str = "",
        limit: int = 20,
    ) -> Dict[str, Any]:
        all_items = self.list_learning_memories(
            db,
            owner_username,
            workspace_id=workspace_id,
            status=status,
            query=query,
            limit=limit,
            apply_limit=False,
        )
        items = self.list_learning_memories(
            db,
            owner_username,
            workspace_id=workspace_id,
            status=status,
            query=query,
            course_name=course_name,
            question_type=question_type,
            knowledge_point=knowledge_point,
            limit=limit,
            apply_limit=True,
        )
        unresolved = [item for item in all_items if (item.status or "").strip() != "resolved"]
        by_status: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        by_course: Dict[str, int] = {}
        by_course_type: Dict[str, Counter[str]] = {}
        points_counter: Counter[str] = Counter()
        source_material_counter: Counter[str] = Counter()
        source_material_map: Dict[str, Dict[str, Any]] = {}
        for item in all_items:
            by_status[item.status] = by_status.get(item.status, 0) + 1
            by_type[item.question_type] = by_type.get(item.question_type, 0) + 1
            course = item.course_name or "未命名课程"
            by_course[course] = by_course.get(course, 0) + 1
            by_course_type.setdefault(course, Counter())
            if item.question_type:
                by_course_type[course][item.question_type] += 1
            for point in item.knowledge_points_json or []:
                text = str(point).strip()
                if text:
                    points_counter[text] += 1
            refs = item.source_refs_json or {}
            highlights = refs.get("highlights") or []
            if isinstance(highlights, list):
                seen_materials = set()
                for raw in highlights:
                    row = raw if isinstance(raw, dict) else {}
                    source = str(row.get("source") or "").strip()
                    title = str(row.get("title") or "").strip() or "未命名资料"
                    document_id = row.get("document_id")
                    chunk_index = row.get("chunk_index")
                    material_key = f"{document_id or source or title}"
                    if not material_key or material_key in seen_materials:
                        continue
                    seen_materials.add(material_key)
                    source_material_counter[material_key] += 1
                    source_material_map.setdefault(
                        material_key,
                        {
                            "title": title,
                            "source": source,
                            "document_id": document_id,
                            "chunk_index": chunk_index,
                            "hit_count": 0,
                        },
                    )
        course_rank = sorted(
            by_course.items(),
            key=lambda pair: (-pair[1], pair[0]),
        )
        review_priority = sorted(
            [
                {
                    "course_name": item.course_name or "未命名课程",
                    "question_summary": item.question_summary,
                    "question_type": item.question_type,
                    "importance": int(item.importance or 0),
                    "status": item.status,
                    "id": item.id,
                }
                for item in unresolved
            ],
            key=lambda item: (-item["importance"], item["course_name"], item["question_summary"]),
        )[:5]
        source_material_rank = []
        for key, count in source_material_counter.most_common(5):
            payload = dict(source_material_map.get(key) or {})
            if not payload:
                continue
            payload["hit_count"] = count
            source_material_rank.append(payload)
        course_insights = []
        for course_name, total in sorted(by_course.items(), key=lambda pair: (-pair[1], pair[0]))[:8]:
            type_counter = by_course_type.get(course_name) or Counter()
            dominant_type, dominant_count = ("general", 0)
            if type_counter:
                dominant_type, dominant_count = type_counter.most_common(1)[0]
            unresolved_count = sum(
                1
                for item in unresolved
                if (item.course_name or "未命名课程") == course_name
            )
            course_insights.append(
                {
                    "course_name": course_name,
                    "total": total,
                    "unresolved": unresolved_count,
                    "dominant_type": dominant_type,
                    "dominant_type_count": dominant_count,
                }
            )
        blind_spots = []
        prompt_strategy_counter: Counter[str] = Counter()
        unresolved_points_by_course: Dict[str, Counter[str]] = {}
        for item in unresolved:
            course_name = item.course_name or "未命名课程"
            unresolved_points_by_course.setdefault(course_name, Counter())
            refs = item.source_refs_json or {}
            strategy = str(refs.get("prompt_strategy") or "").strip()
            if strategy:
                prompt_strategy_counter[strategy] += 1
            for point in item.knowledge_points_json or []:
                text = str(point).strip()
                if text:
                    unresolved_points_by_course[course_name][text] += 1
        for course_name, total in sorted(by_course.items(), key=lambda pair: (-pair[1], pair[0]))[:8]:
            unresolved_count = sum(
                1
                for item in unresolved
                if (item.course_name or "未命名课程") == course_name
            )
            if unresolved_count <= 0:
                continue
            type_counter = by_course_type.get(course_name) or Counter()
            dominant_type, dominant_count = ("general", 0)
            if type_counter:
                dominant_type, dominant_count = type_counter.most_common(1)[0]
            point_counter = unresolved_points_by_course.get(course_name) or Counter()
            top_point, top_point_count = ("", 0)
            if point_counter:
                top_point, top_point_count = point_counter.most_common(1)[0]
            blind_spots.append(
                {
                    "course_name": course_name,
                    "unresolved": unresolved_count,
                    "dominant_type": dominant_type,
                    "dominant_type_count": dominant_count,
                    "top_point": top_point,
                    "top_point_count": top_point_count,
                }
            )
        blind_spots.sort(
            key=lambda item: (-item["unresolved"], -item["dominant_type_count"], item["course_name"])
        )
        prompt_strategy_rank = [
            {"strategy": strategy, "count": count}
            for strategy, count in prompt_strategy_counter.most_common(3)
        ]
        return {
            "items": [item.to_dict() for item in items],
            "summary": {
                "total": len(all_items),
                "unresolved": len(unresolved),
                "resolved": sum(1 for item in all_items if (item.status or "").strip() == "resolved"),
                "by_status": by_status,
                "by_type": by_type,
                "by_course": by_course,
                "course_rank": [name for name, _ in course_rank[:8]],
                "top_points": [item for item, _ in points_counter.most_common(8)],
                "review_priority": review_priority,
                "top_source_materials": source_material_rank,
                "course_insights": course_insights,
                "blind_spots": blind_spots[:6],
                "prompt_strategy_rank": prompt_strategy_rank,
            },
        }

    def log_attempt(
        self,
        db: Session,
        *,
        owner_username: str,
        workspace_id: int | None,
        question_id: int,
        submitted_answer: List[str],
        result_status: str,
        note: str,
    ) -> LearningQuestionAttempt:
        question = (
            db.query(LearningQuestion)
            .filter(LearningQuestion.id == question_id, LearningQuestion.owner_username == owner_username)
            .first()
        )
        if not question:
            raise ValueError("题目不存在")
        question.usage_count = int(question.usage_count or 0) + 1
        question.last_used_at = datetime.now(timezone.utc)
        attempt = LearningQuestionAttempt(
            owner_username=owner_username,
            workspace_id=workspace_id,
            question_id=question_id,
            submitted_answer_json=[item.strip() for item in submitted_answer if str(item).strip()],
            result_status=(result_status or "unknown").strip() or "unknown",
            note=note.strip() or None,
        )
        db.add(question)
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        return attempt

    def build_non_llm_analysis(self, title: str, question_type: str, options: List[str]) -> Dict[str, Any]:
        option_count = len([item for item in options if str(item).strip()])
        type_label = {
            "single": "单选题",
            "multiple": "多选题",
            "blank": "填空题",
            "judge": "判断题",
            "essay": "问答题",
        }.get((question_type or "").strip(), "题目")
        return {
            "summary": f"当前未启用模型，先按 {type_label} 方式做结构化拆解。",
            "knowledge_points": [
                "先识别题干中的核心概念、限定条件、否定词与时间范围",
                "如果有选项，优先比较相近选项的区别点",
                "把题目改写成自己的话，再核对课程讲义或笔记",
            ],
            "reasoning_steps": [
                f"题型判断：这是一个 {type_label}，共有 {option_count} 个可见选项" if option_count else f"题型判断：这是一个 {type_label}",
                "定位题干关键词，判断它是在考概念、流程、定义还是案例",
                "如果无法直接判断，回到教材章节标题与老师强调过的术语",
            ],
            "verification_strategy": "建议结合课程笔记、课件截图或教材原文做二次核对，不直接把临时判断写入已验证题库。",
            "risk_note": "该结果是无模型回退版本，只提供学习拆解，不给最终答案。",
        }

    def analyze_question(
        self,
        owner_username: str,
        *,
        title: str,
        question_type: str,
        options: List[str],
        course_name: str = "",
    ) -> Dict[str, Any]:
        base = self.build_non_llm_analysis(title, question_type, options)
        session_store = get_session_store()
        provider = get_model_provider_for_user(owner_username, session_store)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是学习辅导助手。目标是帮助学生理解题目，不直接给出标准答案。"
                    "请输出 JSON，字段必须包含 summary, knowledge_points, reasoning_steps, verification_strategy, risk_note。"
                    "knowledge_points 和 reasoning_steps 必须是字符串数组。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "course_name": course_name,
                        "question_type": question_type,
                        "title": title,
                        "options": options,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        result = provider.chat(messages, temperature=0.2)
        if not result.get("success"):
            return {"provider_ready": False, "analysis": base}

        content = str(result.get("content") or "").strip()
        if not content:
            return {"provider_ready": True, "analysis": base}
        try:
            parsed = json.loads(content)
            return {
                "provider_ready": True,
                "analysis": {
                    "summary": str(parsed.get("summary") or base["summary"]).strip(),
                    "knowledge_points": [str(item).strip() for item in parsed.get("knowledge_points", []) if str(item).strip()] or base["knowledge_points"],
                    "reasoning_steps": [str(item).strip() for item in parsed.get("reasoning_steps", []) if str(item).strip()] or base["reasoning_steps"],
                    "verification_strategy": str(parsed.get("verification_strategy") or base["verification_strategy"]).strip(),
                    "risk_note": str(parsed.get("risk_note") or base["risk_note"]).strip(),
                },
            }
        except Exception:
            return {
                "provider_ready": True,
                "analysis": {
                    **base,
                    "summary": content[:300] if content else base["summary"],
                },
            }


_learning_assistant_service_singleton: LearningAssistantService | None = None


def get_learning_assistant_service() -> LearningAssistantService:
    global _learning_assistant_service_singleton
    if _learning_assistant_service_singleton is None:
        _learning_assistant_service_singleton = LearningAssistantService()
    return _learning_assistant_service_singleton


