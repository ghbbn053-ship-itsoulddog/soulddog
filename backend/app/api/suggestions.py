from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import get_db
from app.security import enforce_username_isolation
from app.services.suggestions import get_suggestion_service

router = APIRouter(prefix="/api/suggestions", tags=["AI建议"])


class SuggestionActionRequest(BaseModel):
    username: str


class SuggestionScanRequest(BaseModel):
    username: str
    workspace_id: int


@router.get("/{workspace_id}")
async def list_suggestions(workspace_id: int, username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc = get_suggestion_service()
    try:
        suggestions = svc.scan_workspace(db, username, workspace_id)
        reminders = svc.get_reminders(db, username, workspace_id)
        return {"success": True, "suggestions": suggestions, "reminders": reminders}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"建议读取失败: {e}")


@router.post("/{workspace_id}/accept")
async def accept_suggestion(
    workspace_id: int,
    suggestion_id: int,
    payload: SuggestionActionRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, payload.username)
    svc = get_suggestion_service()
    try:
        return svc.accept(db, payload.username, workspace_id, suggestion_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"接受建议失败: {e}")


@router.post("/{workspace_id}/dismiss")
async def dismiss_suggestion(
    workspace_id: int,
    suggestion_id: int,
    payload: SuggestionActionRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, payload.username)
    svc = get_suggestion_service()
    try:
        return svc.dismiss(db, payload.username, workspace_id, suggestion_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"忽略建议失败: {e}")


@router.post("/scan")
async def scan_suggestions(payload: SuggestionScanRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    svc = get_suggestion_service()
    try:
        suggestions = svc.scan_workspace(db, payload.username, payload.workspace_id)
        reminders = svc.get_reminders(db, payload.username, payload.workspace_id)
        return {"success": True, "suggestions": suggestions, "reminders": reminders}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"建议扫描失败: {e}")
