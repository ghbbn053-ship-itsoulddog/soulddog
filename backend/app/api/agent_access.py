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


def _api_base_from_request(http_request: Request) -> str:
    return str(http_request.base_url).rstrip("/")


@router.get("/{username}")
async def list_agent_access(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    service = get_agent_access_service()
    api_base = _api_base_from_request(http_request)
    return {
        "success": True,
        "tokens": service.list_tokens(db, username),
        "bindings": service.sync_default_bindings(db, username),
        "login_policy": {
            "web_login_source": "教务系统登录",
            "agent_rule": "外部 Agent 不直接登录教务系统，只复用 Web 端完成的绑定与授权状态",
        },
        "agent_bridge": {
            "bridge_script": "backend/mcp_agent_bridge.py",
            "catalog_endpoint": f"{api_base}/api/mcp/agent/catalog",
            "tool_call_endpoint": f"{api_base}/api/mcp/tools/{{tool_name}}",
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


@router.get("/{username}/bootstrap")
async def get_agent_bootstrap(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    service = get_agent_access_service()
    bindings = service.sync_default_bindings(db, username)
    tokens = service.list_tokens(db, username)
    active_token = next((item for item in tokens if item.get("status") == "active"), None)
    api_base = _api_base_from_request(http_request)
    return {
        "success": True,
        "username": username,
        "bindings": bindings,
        "has_active_education_binding": any(
            item.get("service_name") == "education" and item.get("status") == "active" for item in bindings
        ),
        "recommended_flow": [
            "1. 先在 Web 端完成教务系统登录",
            "2. 创建或确认可用的 Agent Token",
            "3. 用本地 stdio bridge 接入外部 Agent",
            "4. 外部 Agent 通过平台 API 复用 Web 端授权",
        ],
        "bridge": {
            "script_path": "backend/mcp_agent_bridge.py",
            "env": {
                "SOULDDOG_API_BASE": api_base,
                "SOULDDOG_AGENT_TOKEN": "<创建后填入>",
                "SOULDDOG_MCP_SERVER_NAME": "soulddog-platform",
                "SOULDDOG_VERIFY_TLS": "true",
            },
            "claude_desktop": {
                "mcpServers": {
                    "soulddog-platform": {
                        "command": "python",
                        "args": ["backend/mcp_agent_bridge.py"],
                        "env": {
                            "SOULDDOG_API_BASE": api_base,
                            "SOULDDOG_AGENT_TOKEN": "<创建后填入>",
                        },
                    }
                }
            },
            "openclaw_skill": {
                "name": "soulddog-platform",
                "description": "Bridge to Souldog platform MCP tools using Web-managed auth",
                "tools": [
                    "query_grades",
                    "query_schedule",
                    "query_academic_progress",
                    "query_training_plan",
                    "query_exam_schedule",
                    "query_personal_info",
                    "query_weather",
                ],
                "mcpServers": {
                    "soulddog-platform": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["backend/mcp_agent_bridge.py"],
                        "env": {
                            "SOULDDOG_API_BASE": api_base,
                            "SOULDDOG_AGENT_TOKEN": "<创建后填入>",
                        },
                    }
                },
            },
        },
        "active_token_hint": {
            "token_name": active_token.get("token_name") if active_token else None,
            "token_prefix": active_token.get("token_prefix") if active_token else None,
        },
    }
