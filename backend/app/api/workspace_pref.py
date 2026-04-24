"""
工作区偏好 API。
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.runtime import session_store
from app.security import enforce_username_isolation

router = APIRouter(prefix="/api/workspace-preference", tags=["工作区偏好"])


class WorkspacePreferenceRequest(BaseModel):
    username: str
    workspace_id: int
    workspace_name: str = ""


@router.get("/{username}")
async def get_workspace_preference(username: str, http_request: Request):
    enforce_username_isolation(http_request, username)
    pref = session_store.get_user_workspace_preference(username) or {}
    return {
        "success": True,
        "workspace_id": pref.get("workspace_id"),
        "workspace_name": pref.get("workspace_name", ""),
    }


@router.post("")
async def set_workspace_preference(payload: WorkspacePreferenceRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    session_store.set_user_workspace_preference(
        payload.username,
        {
            "workspace_id": payload.workspace_id,
            "workspace_name": payload.workspace_name,
        },
    )
    return {"success": True}
