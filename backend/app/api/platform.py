"""
平台对象 API。
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.models import get_db
from app.security import enforce_username_isolation
from app.services.platform_registry import get_platform_registry_service

router = APIRouter(prefix="/api/platform", tags=["平台对象"])


@router.get("/{username}/skills")
async def list_platform_skills(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc = get_platform_registry_service()
    rows = svc.list_skills(db, username)
    return {
        "success": True,
        "skills": [
            {
                "id": row.id,
                "name": row.name,
                "version": row.version,
                "description": row.description,
                "enabled": row.enabled,
                "triggers": row.triggers or [],
                "tools": row.tools or [],
            }
            for row in rows
        ],
    }


@router.get("/{username}/mcp")
async def list_platform_mcp(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc = get_platform_registry_service()
    rows = svc.list_mcp_tools(db, username)
    return {
        "success": True,
        "mcp_tools": [
            {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "kind": row.kind,
                "enabled": row.enabled,
                "tool_schema": row.tool_schema or {},
            }
            for row in rows
        ],
    }
