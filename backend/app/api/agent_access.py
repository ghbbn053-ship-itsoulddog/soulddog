from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import get_db
from app.security import enforce_username_isolation
from app.services.agent_access import get_agent_access_service

router = APIRouter(prefix="/api/agent-access", tags=["Agent Access"])


class CreateTokenRequest(BaseModel):
    username: str
    token_name: str
    ttl_days: int = 30


class RevokeTokenRequest(BaseModel):
    username: str


@router.get("/{username}")
async def list_agent_access(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    service = get_agent_access_service()
    return {
        "success": True,
        "tokens": service.list_tokens(db, username),
        "bindings": service.sync_default_bindings(db, username),
        "login_policy": {
            "web_login_source": "教务系统登录",
            "agent_rule": "外部 Agent 不直接登录教务系统，只复用 Web 端完成的绑定与授权状态",
        },
    }


@router.post("/tokens")
async def create_agent_token(payload: CreateTokenRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    service = get_agent_access_service()
    created = service.create_token(
        db=db,
        owner_username=payload.username,
        token_name=payload.token_name,
        ttl_days=payload.ttl_days,
    )
    return {"success": True, "token": created}


@router.delete("/tokens/{token_id}")
async def revoke_agent_token(token_id: int, payload: RevokeTokenRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    ok = get_agent_access_service().revoke_token(db, payload.username, token_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Token 不存在")
    return {"success": True}
