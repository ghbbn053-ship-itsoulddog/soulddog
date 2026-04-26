from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.platform import AgentAccessToken, ExternalServiceBinding
from app.services.session_store import get_session_store


DEFAULT_AGENT_SCOPE = {
    "mcp": {
        "allowed_boundaries": ["hosted_web", "remote_service"],
        "allowed_services": ["education"],
    }
}


class AgentAccessService:
    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def create_token(
        self,
        db: Session,
        owner_username: str,
        token_name: str,
        scope_json: Optional[Dict[str, Any]] = None,
        ttl_days: int = 30,
    ) -> Dict[str, Any]:
        raw_token = f"soulddog_at_{secrets.token_urlsafe(32)}"
        token_hash = self._hash_token(raw_token)
        prefix = raw_token[:18]
        expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, ttl_days))

        record = AgentAccessToken(
            owner_username=owner_username,
            token_name=(token_name or "Agent Token").strip() or "Agent Token",
            token_hash=token_hash,
            token_prefix=prefix,
            status="active",
            scope_json=scope_json or DEFAULT_AGENT_SCOPE,
            expires_at=expires_at,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        return {
            "id": record.id,
            "token": raw_token,
            "token_name": record.token_name,
            "token_prefix": record.token_prefix,
            "status": record.status,
            "scope_json": record.scope_json or {},
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        }

    def list_tokens(self, db: Session, owner_username: str) -> List[Dict[str, Any]]:
        rows = (
            db.query(AgentAccessToken)
            .filter(AgentAccessToken.owner_username == owner_username)
            .order_by(AgentAccessToken.created_at.desc())
            .all()
        )
        return [
            {
                "id": row.id,
                "token_name": row.token_name,
                "token_prefix": row.token_prefix,
                "status": row.status,
                "scope_json": row.scope_json or {},
                "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    def revoke_token(self, db: Session, owner_username: str, token_id: int) -> bool:
        row = (
            db.query(AgentAccessToken)
            .filter(AgentAccessToken.id == token_id, AgentAccessToken.owner_username == owner_username)
            .first()
        )
        if not row:
            return False
        row.status = "revoked"
        db.add(row)
        db.commit()
        return True

    def resolve_bearer_token(self, db: Session, raw_token: str) -> Optional[Dict[str, Any]]:
        token_hash = self._hash_token(raw_token)
        row = db.query(AgentAccessToken).filter(AgentAccessToken.token_hash == token_hash).first()
        if not row or row.status != "active":
            return None
        if row.expires_at:
            expires_at = row.expires_at
            if getattr(expires_at, "tzinfo", None) is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                row.status = "expired"
                db.add(row)
                db.commit()
                return None
        row.last_used_at = datetime.now(timezone.utc)
        db.add(row)
        db.commit()
        return {
            "owner_username": row.owner_username,
            "token_id": row.id,
            "token_name": row.token_name,
            "scope_json": row.scope_json or {},
        }

    def get_binding(self, db: Session, owner_username: str, service_name: str) -> Optional[ExternalServiceBinding]:
        return (
            db.query(ExternalServiceBinding)
            .filter(
                ExternalServiceBinding.owner_username == owner_username,
                ExternalServiceBinding.service_name == service_name,
            )
            .first()
        )

    def has_active_binding(self, db: Session, owner_username: str, service_name: str) -> bool:
        binding = self.get_binding(db, owner_username, service_name)
        return bool(binding and binding.status == "active")

    def sync_default_bindings(self, db: Session, owner_username: str) -> List[Dict[str, Any]]:
        session_store = get_session_store()
        current_session = session_store.get_user_session(owner_username)
        rows = []

        education = (
            db.query(ExternalServiceBinding)
            .filter(
                ExternalServiceBinding.owner_username == owner_username,
                ExternalServiceBinding.service_name == "education",
            )
            .first()
        )
        if not education:
            education = ExternalServiceBinding(
                owner_username=owner_username,
                service_name="education",
                auth_type="web_session",
                status="pending",
            )
            db.add(education)

        education.status = "active" if current_session else "pending"
        education.display_name = owner_username
        education.metadata_json = {
            "login_source": "web_login",
            "has_active_session": bool(current_session),
        }
        education.last_verified_at = datetime.now(timezone.utc) if current_session else None
        db.add(education)
        db.commit()

        rows = (
            db.query(ExternalServiceBinding)
            .filter(ExternalServiceBinding.owner_username == owner_username)
            .order_by(ExternalServiceBinding.service_name.asc())
            .all()
        )
        return [
            {
                "id": row.id,
                "service_name": row.service_name,
                "auth_type": row.auth_type,
                "status": row.status,
                "display_name": row.display_name,
                "metadata_json": row.metadata_json or {},
                "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            }
            for row in rows
        ]


_agent_access_service_singleton: AgentAccessService | None = None


def get_agent_access_service() -> AgentAccessService:
    global _agent_access_service_singleton
    if _agent_access_service_singleton is None:
        _agent_access_service_singleton = AgentAccessService()
    return _agent_access_service_singleton
