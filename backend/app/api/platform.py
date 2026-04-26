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
                "input_schema": (row.metadata_json or {}).get("input_schema", {}),
                "tools": row.tools or [],
                "mode": (row.metadata_json or {}).get("mode", "rule"),
                "compatibility_level": (row.metadata_json or {}).get("compatibility_level", "direct"),
                "compatibility_notes": (row.metadata_json or {}).get("compatibility_notes", []),
                "capabilities": (row.metadata_json or {}).get("capabilities", []),
                "execution_boundary": (row.metadata_json or {}).get("execution_boundary", "hosted_web"),
                "execution_boundary_notes": (row.metadata_json or {}).get("execution_boundary_notes", []),
                "web_enabled": (row.metadata_json or {}).get("web_enabled", True),
                "always_on": (row.metadata_json or {}).get("always_on", False),
                "source_type": row.source_type,
                "source_ref": row.source_ref,
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
                "source_type": row.source_type,
                "source_ref": row.source_ref,
                "transport": (row.metadata_json or {}).get("transport", "python" if row.kind == "python" else "http"),
                "compatibility_level": (row.metadata_json or {}).get("compatibility_level", "direct"),
                "compatibility_notes": (row.metadata_json or {}).get("compatibility_notes", []),
                "capabilities": (row.metadata_json or {}).get("capabilities", []),
                "execution_boundary": (row.metadata_json or {}).get("execution_boundary", "hosted_web"),
                "execution_boundary_notes": (row.metadata_json or {}).get("execution_boundary_notes", []),
                "web_enabled": (row.metadata_json or {}).get("web_enabled", True),
                "service_scope": (row.metadata_json or {}).get("service_scope", "web_internal_service"),
            }
            for row in rows
        ],
    }
