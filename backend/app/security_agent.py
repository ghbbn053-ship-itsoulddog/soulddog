from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.services.agent_access import get_agent_access_service


def resolve_agent_identity(request: Request, db: Session) -> Optional[Dict[str, Any]]:
    auth_header = (request.headers.get("Authorization") or "").strip()
    if not auth_header.lower().startswith("bearer "):
        return None
    raw_token = auth_header[7:].strip()
    if not raw_token:
        return None
    return get_agent_access_service().resolve_bearer_token(db, raw_token)


def require_agent_identity(request: Request, db: Session) -> Dict[str, Any]:
    identity = resolve_agent_identity(request, db)
    if not identity:
        raise HTTPException(status_code=401, detail="缺少有效的 Agent Access Token")
    return identity
