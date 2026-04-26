"""
Composition API:
按用户管理 skill + mcp 的自由拼接配置。
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.security import enforce_username_isolation
from app.services.composition_manager import get_composition_manager
from app.core.runtime import get_db
from app.services.skill_manager import get_skill_manager
from app.services.mcp_manager import get_mcp_manager
from app.services.platform_registry import get_platform_registry_service

router = APIRouter(prefix="/api/composition", tags=["Composition"])


class SkillComposeRequest(BaseModel):
    username: str
    skill_name: str
    enabled: bool
    priority: int = 50


class MCPComposeRequest(BaseModel):
    username: str
    tool_name: str
    enabled: bool
    weight: int = 50


class MCPReorderRequest(BaseModel):
    username: str
    order: List[str]


@router.get("/{username}")
async def get_composition(username: str, http_request: Request):
    enforce_username_isolation(http_request, username)
    manager = get_composition_manager()
    return {"success": True, "data": manager.resolved(username)}


@router.post("/skills")
async def set_skill_compose(payload: SkillComposeRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    skill = get_skill_manager().get_skill(payload.username, payload.skill_name)
    if payload.enabled and skill and not bool(skill.get("web_enabled", True)):
        raise HTTPException(
            status_code=400,
            detail=f"Skill '{payload.skill_name}' 属于 {skill.get('execution_boundary', 'agent_local_only')}，不能直接在 Web 平台启用",
        )
    manager = get_composition_manager()
    profile = manager.set_skill_enabled(payload.username, payload.skill_name, payload.enabled, payload.priority)
    return {"success": True, "profile": profile}


@router.post("/mcp")
async def set_mcp_compose(payload: MCPComposeRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    tool = next((item for item in get_mcp_manager().list_tools(payload.username) if item.get("name") == payload.tool_name), None)
    if payload.enabled:
        web_enabled = None
        execution_boundary = "agent_local_only"
        if tool:
            web_enabled = bool(tool.get("web_enabled", True))
            execution_boundary = str(tool.get("execution_boundary", execution_boundary))
        else:
            db = next(get_db())
            try:
                record = next(
                    (row for row in get_platform_registry_service().list_mcp_tools(db, payload.username) if row.name == payload.tool_name),
                    None,
                )
                if record:
                    web_enabled = bool((record.metadata_json or {}).get("web_enabled", True))
                    execution_boundary = str((record.metadata_json or {}).get("execution_boundary", execution_boundary))
            finally:
                db.close()
        if web_enabled is False:
            raise HTTPException(
                status_code=400,
                detail=f"MCP '{payload.tool_name}' 属于 {execution_boundary}，不能直接在 Web 平台启用",
            )
    manager = get_composition_manager()
    profile = manager.set_mcp_enabled(payload.username, payload.tool_name, payload.enabled, payload.weight)
    return {"success": True, "profile": profile}


@router.post("/mcp/reorder")
async def reorder_mcp(payload: MCPReorderRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    manager = get_composition_manager()
    profile = manager.reorder_mcp(payload.username, payload.order)
    return {"success": True, "profile": profile}
