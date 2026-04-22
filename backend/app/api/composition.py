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
    manager = get_composition_manager()
    profile = manager.set_skill_enabled(payload.username, payload.skill_name, payload.enabled, payload.priority)
    return {"success": True, "profile": profile}


@router.post("/mcp")
async def set_mcp_compose(payload: MCPComposeRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    manager = get_composition_manager()
    profile = manager.set_mcp_enabled(payload.username, payload.tool_name, payload.enabled, payload.weight)
    return {"success": True, "profile": profile}


@router.post("/mcp/reorder")
async def reorder_mcp(payload: MCPReorderRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    manager = get_composition_manager()
    profile = manager.reorder_mcp(payload.username, payload.order)
    return {"success": True, "profile": profile}

