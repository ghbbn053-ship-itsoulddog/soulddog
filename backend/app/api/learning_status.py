from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.models import get_db
from app.security import enforce_username_isolation
from app.services.learning_status import get_learning_status_service

router = APIRouter(prefix="/api/status", tags=["学习状态"])


@router.get("/{workspace_id}")
async def get_learning_status(workspace_id: int, username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc = get_learning_status_service()
    try:
        data = svc.get_workspace_status(db, username, workspace_id)
        return {"success": True, **data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"学习状态读取失败: {e}")
