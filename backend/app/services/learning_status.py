from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import Conversation, EducationData, Message, User
from app.models.platform import KnowledgeChunk, KnowledgeDocument, Workspace


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class LearningStatusService:
    def get_workspace_status_briefs(self, db: Session, username: str, workspace_ids: list[int]) -> Dict[int, Dict[str, int]]:
        ids = [int(item) for item in workspace_ids if int(item or 0) > 0]
        if not ids:
            return {}

        user = db.query(User).filter(User.username == username).first()
        if not user:
            return {}

        docs = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.owner_username == username, KnowledgeDocument.workspace_id.in_(ids))
            .all()
        )
        docs_by_workspace: Dict[int, int] = defaultdict(int)
        for doc in docs:
            wid = int(doc.workspace_id or 0)
            if wid > 0:
                docs_by_workspace[wid] += 1

        conversations = db.query(Conversation).filter(Conversation.user_id == user.id).all()
        conversation_workspace_map = {}
        for item in conversations:
            meta = item.conversation_meta or {}
            wid = int(meta.get("workspace_id") or 0)
            if wid in ids:
                conversation_workspace_map[item.id] = wid

        recent_messages = (
            db.query(Message)
            .filter(Message.conversation_id.in_(list(conversation_workspace_map.keys())))
            .all()
            if conversation_workspace_map
            else []
        )

        now = _utc_now()
        today_start = now - timedelta(hours=24)
        prompts_by_workspace: Dict[int, int] = defaultdict(int)
        assistant_by_workspace: Dict[int, int] = defaultdict(int)
        highlights_by_workspace: Dict[int, int] = defaultdict(int)

        for msg in recent_messages:
            meta = msg.message_meta or {}
            message_workspace_id = int(meta.get("workspace_id") or 0)
            workspace_id = message_workspace_id if message_workspace_id in ids else conversation_workspace_map.get(msg.conversation_id, 0)
            if workspace_id not in ids:
                continue
            created = _safe_dt(msg.created_at)
            if msg.role == "user" and created and created >= today_start:
                prompts_by_workspace[workspace_id] += 1
            if msg.role == "assistant" and created and created >= today_start:
                assistant_by_workspace[workspace_id] += 1
                highlights_by_workspace[workspace_id] += len(meta.get("highlights") or [])

        output: Dict[int, Dict[str, int]] = {}
        for wid in ids:
            today_prompts = int(prompts_by_workspace.get(wid, 0))
            today_assistant = int(assistant_by_workspace.get(wid, 0))
            highlight_count = int(highlights_by_workspace.get(wid, 0))
            today_minutes = max(
                5,
                today_prompts * 6 + today_assistant * 2 + min(highlight_count, 20),
            ) if today_prompts or today_assistant else 0
            output[wid] = {
                "today_minutes": today_minutes,
                "today_prompts": today_prompts,
                "documents": int(docs_by_workspace.get(wid, 0)),
            }
        return output

    def get_workspace_status(self, db: Session, username: str, workspace_id: int) -> Dict[str, Any]:
        user = db.query(User).filter(User.username == username).first()
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == workspace_id, Workspace.owner_username == username)
            .first()
        )
        if not user or not workspace:
            raise ValueError("工作区不存在")

        now = _utc_now()
        today_start = now - timedelta(hours=24)
        week_start = now - timedelta(days=7)

        docs = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.owner_username == username, KnowledgeDocument.workspace_id == workspace_id)
            .all()
        )
        chunks_count = (
            db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.owner_username == username, KnowledgeChunk.workspace_id == workspace_id)
            .count()
        )

        conversations = db.query(Conversation).filter(Conversation.user_id == user.id).all()
        conversation_ids = [item.id for item in conversations]
        conversation_workspace_map = {}
        for item in conversations:
            meta = item.conversation_meta or {}
            wid = int(meta.get("workspace_id") or 0)
            if wid:
                conversation_workspace_map[item.id] = wid

        recent_messages = (
            db.query(Message)
            .filter(Message.conversation_id.in_(conversation_ids))
            .all()
            if conversation_ids
            else []
        )

        workspace_messages = []
        for msg in recent_messages:
            meta = msg.message_meta or {}
            message_workspace_id = int(meta.get("workspace_id") or 0)
            conversation_workspace_id = conversation_workspace_map.get(msg.conversation_id, 0)
            if message_workspace_id == workspace_id or conversation_workspace_id == workspace_id:
                workspace_messages.append(msg)

        user_messages = [msg for msg in workspace_messages if msg.role == "user"]
        assistant_messages = [msg for msg in workspace_messages if msg.role == "assistant"]

        def _in_window(items, start: datetime):
            output = []
            for item in items:
                created = _safe_dt(item.created_at)
                if created and created >= start:
                    output.append(item)
            return output

        today_user_messages = _in_window(user_messages, today_start)
        week_user_messages = _in_window(user_messages, week_start)
        today_assistant_messages = _in_window(assistant_messages, today_start)

        highlight_count = 0
        source_count = 0
        for msg in assistant_messages:
            meta = msg.message_meta or {}
            highlight_count += len(meta.get("highlights") or [])
            source_count += len(meta.get("sources") or [])

        documents_ready = sum(1 for doc in docs if doc.status == "ready")
        documents_failed = sum(1 for doc in docs if doc.status == "failed")
        total_tokens = sum(int(doc.token_estimate or 0) for doc in docs)
        authority_counter = Counter(str((doc.metadata_json or {}).get("authority_level", "user")) for doc in docs)

        estimated_today_minutes = max(
            5,
            len(today_user_messages) * 6 + len(today_assistant_messages) * 2 + min(highlight_count, 20),
        ) if today_user_messages or today_assistant_messages else 0
        estimated_week_minutes = max(
            estimated_today_minutes,
            len(week_user_messages) * 6 + min(highlight_count, 60),
        ) if week_user_messages else estimated_today_minutes

        education = db.query(EducationData).filter(EducationData.user_id == user.id).first()
        last_updated = _safe_dt(education.last_updated) if education else None
        freshness_days = None
        if last_updated:
            freshness_days = max(0, int((now - last_updated).total_seconds() // 86400))

        return {
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "slug": workspace.slug,
            },
            "metrics": {
                "today_minutes": estimated_today_minutes,
                "week_minutes": estimated_week_minutes,
                "total_prompts": len(user_messages),
                "today_prompts": len(today_user_messages),
                "assistant_replies": len(assistant_messages),
                "knowledge_documents": len(docs),
                "knowledge_chunks": chunks_count,
                "documents_ready": documents_ready,
                "documents_failed": documents_failed,
                "knowledge_references": highlight_count,
                "source_citations": source_count,
                "total_tokens": total_tokens,
            },
            "signals": {
                "knowledge_density": round(chunks_count / max(len(docs), 1), 2) if docs else 0,
                "document_failure_ratio": round(documents_failed / max(len(docs), 1), 2) if docs else 0,
                "authority_breakdown": dict(authority_counter),
                "education_freshness_days": freshness_days,
                "last_education_sync_at": last_updated.isoformat() if last_updated else None,
            },
        }


_learning_status_service: LearningStatusService | None = None


def get_learning_status_service() -> LearningStatusService:
    global _learning_status_service
    if _learning_status_service is None:
        _learning_status_service = LearningStatusService()
    return _learning_status_service
