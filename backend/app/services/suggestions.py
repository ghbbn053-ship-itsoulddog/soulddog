from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import EducationData, User
from app.models.platform import Workspace, WorkspaceSuggestion
from app.services.composition_manager import get_composition_manager
from app.services.learning_status import get_learning_status_service
from app.services.workspace_knowledge import get_workspace_knowledge_service


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SuggestionService:
    def _upsert_suggestion(
        self,
        db: Session,
        workspace_id: int,
        username: str,
        suggestion_key: str,
        suggestion_type: str,
        title: str,
        content: str,
        reason: str,
        tone: str = "normal",
        payload: Dict[str, Any] | None = None,
    ) -> WorkspaceSuggestion:
        item = (
            db.query(WorkspaceSuggestion)
            .filter(
                WorkspaceSuggestion.workspace_id == workspace_id,
                WorkspaceSuggestion.owner_username == username,
                WorkspaceSuggestion.suggestion_key == suggestion_key,
            )
            .first()
        )
        if item:
            item.suggestion_type = suggestion_type
            item.title = title
            item.content = content
            item.reason = reason
            item.tone = tone
            item.payload_json = payload or {}
            if item.status == "expired":
                item.status = "active"
            return item
        item = WorkspaceSuggestion(
            workspace_id=workspace_id,
            owner_username=username,
            suggestion_key=suggestion_key,
            suggestion_type=suggestion_type,
            title=title,
            content=content,
            reason=reason,
            tone=tone,
            status="active",
            payload_json=payload or {},
        )
        db.add(item)
        return item

    def _build_candidates(self, db: Session, username: str, workspace_id: int) -> List[Dict[str, Any]]:
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == workspace_id, Workspace.owner_username == username)
            .first()
        )
        if not workspace:
            raise ValueError("工作区不存在")

        knowledge_svc = get_workspace_knowledge_service()
        learning_status = get_learning_status_service().get_workspace_status(db, username, workspace_id)
        overview = knowledge_svc.get_workspace_knowledge_overview(db, username, workspace_id)
        docs = overview.get("documents", [])
        stats = overview.get("stats", {})
        metrics = learning_status.get("metrics", {})
        signals = learning_status.get("signals", {})
        composition = get_composition_manager().resolved(username)

        user = db.query(User).filter(User.username == username).first()
        edu = db.query(EducationData).filter(EducationData.user_id == user.id).first() if user else None
        now = _utc_now()
        freshness_days = signals.get("education_freshness_days")

        suggestions: List[Dict[str, Any]] = []

        if metrics.get("knowledge_documents", 0) == 0:
            suggestions.append(
                {
                    "suggestion_key": "seed-knowledge-base",
                    "suggestion_type": "knowledge_gap",
                    "title": "先补第一批知识材料",
                    "content": "当前工作区还是空的，先上传一份课程资料、制度说明或你自己的整理笔记，再进入聊天验证。",
                    "reason": "没有基础文档时，Agent 只能依赖模型直答，无法形成可回溯依据。",
                    "tone": "warning",
                }
            )

        if metrics.get("documents_failed", 0) > 0:
            suggestions.append(
                {
                    "suggestion_key": "repair-failed-documents",
                    "suggestion_type": "knowledge_gap",
                    "title": "处理解析失败的文档",
                    "content": f"当前有 {metrics.get('documents_failed', 0)} 份文档解析失败，建议先修复格式或换成更稳定的文件类型。",
                    "reason": "失败文档不会进入知识检索，继续堆文档只会污染工作区状态。",
                    "tone": "warning",
                }
            )

        if not composition.get("skills"):
            suggestions.append(
                {
                    "suggestion_key": "enable-skill",
                    "suggestion_type": "study_plan",
                    "title": "给工作区启用至少一个 Skill",
                    "content": "当前工作区没有启用 Skill，适合先接入一个检索、计划或教务相关 Skill，再验证 Agent 执行效果。",
                    "reason": "没有 Skill 时，工作区只是知识容器，还不是可编排的 Agent 工作台。",
                    "tone": "normal",
                }
            )

        if not composition.get("mcp_tools"):
            suggestions.append(
                {
                    "suggestion_key": "enable-mcp",
                    "suggestion_type": "study_plan",
                    "title": "补一个 MCP 工具入口",
                    "content": "当前还没有挂接 MCP 工具，适合至少补一个检索或执行类工具，让工作区具备真实行动能力。",
                    "reason": "没有 MCP 时，Agent 只能阅读上下文，不能形成更强的执行链。",
                    "tone": "normal",
                }
            )

        if metrics.get("today_prompts", 0) == 0 and metrics.get("knowledge_documents", 0) > 0:
            suggestions.append(
                {
                    "suggestion_key": "validate-workspace-chat",
                    "suggestion_type": "review_reminder",
                    "title": "现在适合做一次工作区验证对话",
                    "content": "工作区已经有文档，但今天还没有围绕它发起提问。可以直接进聊天页验证知识引用、来源跳转和回答质量。",
                    "reason": "知识库不经过实际对话验证，无法判断检索和回答链是否真的生效。",
                    "tone": "normal",
                }
            )

        if freshness_days is not None and freshness_days >= 14:
            suggestions.append(
                {
                    "suggestion_key": "refresh-education-data-urgent",
                    "suggestion_type": "data_refresh",
                    "title": "教务缓存已经明显过期",
                    "content": f"当前教务数据已 {freshness_days} 天未同步，涉及课表、考试、个人信息的问题都可能不可靠，建议先刷新数据。",
                    "reason": "缓存过旧会直接导致回答依据失真，这类问题必须优先处理。",
                    "tone": "urgent",
                }
            )
        elif freshness_days is not None and freshness_days >= 7:
            suggestions.append(
                {
                    "suggestion_key": "refresh-education-data-soft",
                    "suggestion_type": "data_refresh",
                    "title": "教务缓存建议更新",
                    "content": f"当前教务数据已 {freshness_days} 天未同步，虽然还能参考，但最好先刷新一次保持数据新鲜度。",
                    "reason": "数据越旧，课表和考试安排偏差越大。",
                    "tone": "warning",
                }
            )

        exams = list((edu.exam_schedule or [])) if edu and isinstance(edu.exam_schedule, list) else []
        upcoming = []
        for exam in exams:
            text = " ".join(str(exam.get(key, "")).strip() for key in exam.keys())
            if not text.strip():
                continue
            upcoming.append(text)
        if upcoming:
            suggestions.append(
                {
                    "suggestion_key": "review-exam-schedule",
                    "suggestion_type": "exam_reminder",
                    "title": "检查最近考试安排",
                    "content": "教务缓存里已经有考试安排数据，适合围绕考试时间、地点和复习节奏做一次专项整理。",
                    "reason": "考试安排是强时效信息，应该优先沉淀到工作区并转成复习任务。",
                    "tone": "normal",
                }
            )

        ready_docs = stats.get("ready_documents", 0)
        if ready_docs >= 3 and metrics.get("knowledge_references", 0) == 0:
            suggestions.append(
                {
                    "suggestion_key": "increase-grounded-usage",
                    "suggestion_type": "knowledge_gap",
                    "title": "提高知识引用命中率",
                    "content": "工作区已经有一定文档量，但当前对话里还几乎没有引用片段，建议测试更具体的问题或补充更结构化的文档。",
                    "reason": "文档多但不被命中，说明知识组织或提问方式还不够对路。",
                    "tone": "warning",
                }
            )

        return suggestions[:6]

    def scan_workspace(self, db: Session, username: str, workspace_id: int) -> List[Dict[str, Any]]:
        candidates = self._build_candidates(db, username, workspace_id)
        for item in candidates:
            self._upsert_suggestion(
                db=db,
                workspace_id=workspace_id,
                username=username,
                suggestion_key=item["suggestion_key"],
                suggestion_type=item["suggestion_type"],
                title=item["title"],
                content=item["content"],
                reason=item.get("reason", ""),
                tone=item.get("tone", "normal"),
                payload=item.get("payload"),
            )
        db.commit()
        return self.list_workspace_suggestions(db, username, workspace_id)

    def list_workspace_suggestions(self, db: Session, username: str, workspace_id: int) -> List[Dict[str, Any]]:
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == workspace_id, Workspace.owner_username == username)
            .first()
        )
        if not workspace:
            raise ValueError("工作区不存在")

        items = (
            db.query(WorkspaceSuggestion)
            .filter(
                WorkspaceSuggestion.workspace_id == workspace_id,
                WorkspaceSuggestion.owner_username == username,
                WorkspaceSuggestion.status == "active",
            )
            .order_by(WorkspaceSuggestion.created_at.desc(), WorkspaceSuggestion.id.desc())
            .all()
        )
        return [
            {
                "id": item.id,
                "key": item.suggestion_key,
                "type": item.suggestion_type,
                "title": item.title,
                "content": item.content,
                "reason": item.reason,
                "tone": item.tone,
                "status": item.status,
                "payload": item.payload_json or {},
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ]

    def get_reminders(self, db: Session, username: str, workspace_id: int) -> List[Dict[str, Any]]:
        suggestions = self.list_workspace_suggestions(db, username, workspace_id)
        reminders = []
        for item in suggestions:
            if item["tone"] in {"urgent", "warning"} or item["type"] in {"exam_reminder", "data_refresh"}:
                reminders.append(item)
        return reminders[:3]

    def accept(self, db: Session, username: str, workspace_id: int, suggestion_id: int) -> Dict[str, Any]:
        item = (
            db.query(WorkspaceSuggestion)
            .filter(
                WorkspaceSuggestion.id == suggestion_id,
                WorkspaceSuggestion.workspace_id == workspace_id,
                WorkspaceSuggestion.owner_username == username,
            )
            .first()
        )
        if not item:
            raise ValueError("建议不存在")
        item.status = "accepted"
        item.accepted_at = _utc_now()
        db.commit()
        return {"success": True}

    def dismiss(self, db: Session, username: str, workspace_id: int, suggestion_id: int) -> Dict[str, Any]:
        item = (
            db.query(WorkspaceSuggestion)
            .filter(
                WorkspaceSuggestion.id == suggestion_id,
                WorkspaceSuggestion.workspace_id == workspace_id,
                WorkspaceSuggestion.owner_username == username,
            )
            .first()
        )
        if not item:
            raise ValueError("建议不存在")
        item.status = "dismissed"
        item.dismissed_at = _utc_now()
        db.commit()
        return {"success": True}


_suggestion_service: SuggestionService | None = None


def get_suggestion_service() -> SuggestionService:
    global _suggestion_service
    if _suggestion_service is None:
        _suggestion_service = SuggestionService()
    return _suggestion_service
