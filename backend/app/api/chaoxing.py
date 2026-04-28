"""
学习辅助 API
职责：
- 显示学习平台辅助状态
- 记录学习活动
- 维护辅助接入资料
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import get_db
from app.security import enforce_username_isolation
from app.services.chaoxing_qr_login import get_chaoxing_qr_login_service
from app.services.learning_assistant import get_learning_assistant_service

router = APIRouter(prefix="/api/chaoxing", tags=["learning-assistant"])


class BindingProfileRequest(BaseModel):
    username: str
    display_name: Optional[str] = ""
    account_label: Optional[str] = ""
    note: Optional[str] = ""


class AutomationProfileRequest(BaseModel):
    username: str
    automation_profile: dict


class LearningActivityRequest(BaseModel):
    username: str
    workspace_id: Optional[int] = None
    platform_name: Optional[str] = "chaoxing"
    activity_type: Optional[str] = "study_note"
    title: str
    course_name: Optional[str] = ""
    chapter_name: Optional[str] = ""
    status: Optional[str] = "recorded"
    detail: Optional[str] = ""


class AutomationTaskCreateRequest(BaseModel):
    username: str
    workspace_id: Optional[int] = None
    task_name: Optional[str] = ""
    course_name: Optional[str] = ""
    course_url: str
    start_url: Optional[str] = ""
    automation_options: Optional[Dict[str, Any]] = None


class AutomationTaskStatusRequest(BaseModel):
    username: str
    status: str


class AutomationRunnerEventRequest(BaseModel):
    runner_token: str
    event_type: Optional[str] = "log"
    level: Optional[str] = "info"
    stage: Optional[str] = ""
    message: str
    current_url: Optional[str] = ""
    payload: Optional[Dict[str, Any]] = None
    status_hint: Optional[str] = None


class BrowserCourseItem(BaseModel):
    title: str
    url: str
    teacher: Optional[str] = ""
    course_id: Optional[str] = ""
    class_id: Optional[str] = ""
    image: Optional[str] = ""


class BrowserCourseSyncRequest(BaseModel):
    bridge_token: str
    current_url: Optional[str] = ""
    page_title: Optional[str] = ""
    courses: list[BrowserCourseItem] = []


class BrowserCommandAckRequest(BaseModel):
    bridge_token: str
    command_id: str


class CreateTaskFromCourseRequest(BaseModel):
    username: str
    workspace_id: Optional[int] = None
    task_name: Optional[str] = ""
    course_name: str
    course_url: str
    automation_options: Optional[Dict[str, Any]] = None


class BrowserHeartbeatRequest(BaseModel):
    bridge_token: str
    current_url: Optional[str] = ""
    page_title: Optional[str] = ""


class QrLoginSessionCreateRequest(BaseModel):
    username: str


class QrLoginSessionPollRequest(BaseModel):
    username: str
    session_token: str


def _serialize_qr_session(session_row: Any) -> Dict[str, Any]:
    if hasattr(session_row, "to_dict"):
        data = session_row.to_dict()
    else:
        data = dict(session_row or {})
    meta = dict(data.get("browser_meta") or {})
    return {
        "id": data.get("id"),
        "owner_username": data.get("owner_username"),
        "session_token": data.get("session_token"),
        "status": data.get("status"),
        "login_url": data.get("login_url"),
        "qr_page_url": data.get("qr_page_url"),
        "qr_image_url": data.get("qr_image_url"),
        "qr_image_data": data.get("qr_image_data"),
        "page_title": data.get("page_title"),
        "last_error": data.get("last_error"),
        "last_seen_at": data.get("last_seen_at"),
        "expires_at": data.get("expires_at"),
        "created_at": data.get("created_at"),
        "browser_meta": {
            "course_catalog": meta.get("course_catalog") or [],
            "course_metrics": meta.get("course_metrics") or [],
            "course_base_url": meta.get("course_base_url") or "",
            "course_home_url": meta.get("course_home_url") or "",
            "business_landing_url": meta.get("business_landing_url") or "",
            "last_auth_status": meta.get("last_auth_status") or {},
        },
    }


@router.get("/status")
async def get_learning_status(
    username: str,
    workspace_id: Optional[int] = None,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    return {
        "success": True,
        **get_learning_assistant_service().get_overview(db, username, workspace_id=workspace_id),
        "browser_bridge": get_learning_assistant_service().get_browser_bridge(db, username),
    }


@router.post("/qr-login/session")
async def create_qr_login_session(
    payload: QrLoginSessionCreateRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, payload.username)
    try:
        session_data = get_chaoxing_qr_login_service().create_login_session(db, payload.username)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建二维码登录会话失败: {e}")
    return {"success": True, "session": _serialize_qr_session(session_data)}


@router.get("/qr-login/session")
async def get_qr_login_session(
    username: str,
    session_token: str,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    row = get_chaoxing_qr_login_service().get_row(db, username, session_token)
    if not row:
        raise HTTPException(status_code=404, detail="二维码登录会话不存在")
    return {"success": True, "session": _serialize_qr_session(row)}


@router.post("/qr-login/poll")
async def poll_qr_login_session(
    payload: QrLoginSessionPollRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, payload.username)
    try:
        session_data = get_chaoxing_qr_login_service().poll_login_session(
            db,
            payload.username,
            payload.session_token,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"轮询二维码登录状态失败: {e}")
    return {"success": True, "session": _serialize_qr_session(session_data)}


@router.post("/binding/profile")
async def update_binding_profile(payload: BindingProfileRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    row = get_learning_assistant_service().update_binding_profile(
        db,
        payload.username,
        display_name=payload.display_name or "",
        note=payload.note or "",
        account_label=payload.account_label or "",
    )
    return {
        "success": True,
        "binding": {
            "service_name": row.service_name,
            "status": row.status,
            "auth_type": row.auth_type,
            "display_name": row.display_name,
            "metadata_json": row.metadata_json or {},
        },
    }


@router.post("/binding/automation-profile")
async def update_automation_profile(payload: AutomationProfileRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    row = get_learning_assistant_service().update_automation_profile(
        db,
        payload.username,
        profile_patch=payload.automation_profile or {},
    )
    return {
        "success": True,
        "binding": {
            "service_name": row.service_name,
            "status": row.status,
            "auth_type": row.auth_type,
            "display_name": row.display_name,
            "metadata_json": row.metadata_json or {},
        },
    }


@router.get("/activities")
async def list_learning_activities(
    username: str,
    workspace_id: Optional[int] = None,
    limit: int = 20,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    rows = get_learning_assistant_service().list_activities(
        db,
        username,
        workspace_id=workspace_id,
        limit=limit,
    )
    return {"success": True, "items": [item.to_dict() for item in rows]}


@router.post("/activities")
async def create_learning_activity(payload: LearningActivityRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    if not (payload.title or "").strip():
        raise HTTPException(status_code=400, detail="title 不能为空")
    row = get_learning_assistant_service().log_activity(
        db,
        owner_username=payload.username,
        workspace_id=payload.workspace_id,
        platform_name=payload.platform_name or "chaoxing",
        activity_type=payload.activity_type or "study_note",
        title=payload.title,
        course_name=payload.course_name or "",
        chapter_name=payload.chapter_name or "",
        status=payload.status or "recorded",
        detail=payload.detail or "",
        meta={},
    )
    return {"success": True, "item": row.to_dict()}


@router.post("/automation/tasks")
async def create_automation_task(payload: AutomationTaskCreateRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    try:
        task = get_learning_assistant_service().create_automation_task(
            db,
            owner_username=payload.username,
            workspace_id=payload.workspace_id,
            task_name=payload.task_name or "",
            course_name=payload.course_name or "",
            course_url=payload.course_url,
            start_url=payload.start_url or payload.course_url,
            automation_options=payload.automation_options or {},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    manifest = get_learning_assistant_service().build_runner_manifest(
        db,
        owner_username=payload.username,
        task_id=task.id,
    )
    return {"success": True, "task": task.to_dict(), "runner_manifest": manifest}


@router.get("/automation/tasks")
async def list_automation_tasks(
    username: str,
    workspace_id: Optional[int] = None,
    limit: int = 20,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    rows = get_learning_assistant_service().list_automation_tasks(
        db,
        username,
        workspace_id=workspace_id,
        limit=limit,
    )
    return {"success": True, "items": [item.to_dict() for item in rows]}


@router.get("/automation/tasks/{task_id}")
async def get_automation_task(
    task_id: int,
    username: str,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    task = get_learning_assistant_service().get_automation_task(db, username, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    manifest = get_learning_assistant_service().build_runner_manifest(db, owner_username=username, task_id=task_id)
    return {"success": True, "task": task.to_dict(), "runner_manifest": manifest}


@router.post("/automation/tasks/{task_id}/status")
async def update_automation_task_status(
    task_id: int,
    payload: AutomationTaskStatusRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, payload.username)
    try:
        task = get_learning_assistant_service().update_automation_task_status(
            db,
            owner_username=payload.username,
            task_id=task_id,
            status=payload.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"success": True, "task": task.to_dict()}


@router.get("/automation/tasks/{task_id}/events")
async def list_automation_task_events(
    task_id: int,
    username: str,
    limit: int = 100,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    task = get_learning_assistant_service().get_automation_task(db, username, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    rows = get_learning_assistant_service().list_automation_events(db, username, task_id=task_id, limit=limit)
    return {"success": True, "task": task.to_dict(), "items": [item.to_dict() for item in rows]}


@router.post("/automation/tasks/{task_id}/runner-events")
async def create_runner_event(task_id: int, payload: AutomationRunnerEventRequest, db: Session = Depends(get_db)):
    task = get_learning_assistant_service().get_automation_task_by_token(db, payload.runner_token)
    if not task or task.id != task_id:
        raise HTTPException(status_code=401, detail="runner token 无效")
    row = get_learning_assistant_service().log_automation_event(
        db,
        task=task,
        event_type=payload.event_type or "log",
        level=payload.level or "info",
        stage=payload.stage or "",
        message=payload.message,
        current_url=payload.current_url or "",
        payload=payload.payload or {},
        status_hint=payload.status_hint,
    )
    return {"success": True, "event": row.to_dict()}


@router.get("/automation/tasks/{task_id}/runner-script")
async def get_runner_script(
    task_id: int,
    username: str,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    manifest = get_learning_assistant_service().build_runner_manifest(
        db,
        owner_username=username,
        task_id=task_id,
    )
    task = manifest["task"]
    profile = manifest["profile"]
    task_json = json.dumps(task, ensure_ascii=False)
    profile_json = json.dumps(profile, ensure_ascii=False)
    event_url = f"/api/chaoxing/automation/tasks/{task_id}/runner-events"
    script = f"""
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
    return {"success": True, "task": task, "runner_manifest": manifest, "script": script}


@router.get("/browser-bridge")
async def get_browser_bridge(
    username: str,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    return {
        "success": True,
        "bridge": get_learning_assistant_service().get_browser_bridge(db, username),
    }


@router.post("/browser-bridge/course-sync")
async def sync_browser_courses(payload: BrowserCourseSyncRequest, db: Session = Depends(get_db)):
    try:
        result = get_learning_assistant_service().sync_course_catalog(
            db,
            bridge_token=payload.bridge_token,
            courses=[item.model_dump() for item in payload.courses],
            current_url=payload.current_url or "",
            page_title=payload.page_title or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"success": True, **result}


@router.post("/browser-bridge/heartbeat")
async def browser_bridge_heartbeat(payload: BrowserHeartbeatRequest, db: Session = Depends(get_db)):
    try:
        result = get_learning_assistant_service().touch_browser_bridge(
            db,
            bridge_token=payload.bridge_token,
            current_url=payload.current_url or "",
            page_title=payload.page_title or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"success": True, **result}


@router.get("/browser-bridge/poll")
async def poll_browser_bridge(bridge_token: str, db: Session = Depends(get_db)):
    try:
        result = get_learning_assistant_service().poll_browser_bridge_state(db, bridge_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"success": True, **result}


@router.post("/browser-bridge/ack")
async def ack_browser_command(payload: BrowserCommandAckRequest, db: Session = Depends(get_db)):
    try:
        get_learning_assistant_service().ack_browser_command(db, payload.bridge_token, payload.command_id)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"success": True}


@router.post("/automation/tasks/from-course")
async def create_automation_task_from_course(
    payload: CreateTaskFromCourseRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, payload.username)
    try:
        task = get_learning_assistant_service().create_automation_task(
            db,
            owner_username=payload.username,
            workspace_id=payload.workspace_id,
            task_name=payload.task_name or payload.course_name,
            course_name=payload.course_name,
            course_url=payload.course_url,
            start_url=payload.course_url,
            automation_options=payload.automation_options or {},
        )
        command = get_learning_assistant_service().queue_open_course_command(
            db,
            owner_username=payload.username,
            task_id=task.id,
            course_url=payload.course_url,
        )
        manifest = get_learning_assistant_service().build_runner_manifest(
            db,
            owner_username=payload.username,
            task_id=task.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "success": True,
        "task": task.to_dict(),
        "runner_manifest": manifest,
        "bridge_command": command,
    }


@router.get("/browser-bridge/runner-script")
async def get_runner_script_for_bridge(bridge_token: str, task_id: int, db: Session = Depends(get_db)):
    state = get_learning_assistant_service().poll_browser_bridge_state(db, bridge_token)
    owner_username = str(state["owner_username"])
    task = get_learning_assistant_service().get_automation_task(db, owner_username, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    manifest = get_learning_assistant_service().build_runner_manifest(
        db,
        owner_username=owner_username,
        task_id=task_id,
    )
    script = get_learning_assistant_service().build_runner_script_text(
        manifest["task"],
        manifest["profile"],
        task_id,
    )
    return {
        "success": True,
        "task": manifest["task"],
        "runner_manifest": manifest,
        "script": script,
    }
