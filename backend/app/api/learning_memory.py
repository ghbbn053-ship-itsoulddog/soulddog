"""
学习疑问记忆 API。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import get_db, LearningStudyMemory
from app.security import enforce_username_isolation
from app.services.learning_assistant import get_learning_assistant_service

router = APIRouter(prefix="/api/learning-memory", tags=["learning-memory"])


class UpdateMemoryStatusRequest(BaseModel):
    username: str
    status: str


@router.get("/{username}")
async def list_learning_memory(
    username: str,
    workspace_id: int | None = None,
    status: str = "",
    query: str = "",
    course_name: str = "",
    question_type: str = "",
    knowledge_point: str = "",
    limit: int = 20,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    svc = get_learning_assistant_service()
    overview = svc.get_learning_memory_overview(
        db,
        username,
        workspace_id=workspace_id,
        status=status,
        query=query,
        course_name=course_name,
        question_type=question_type,
        knowledge_point=knowledge_point,
        limit=limit,
    )
    return {"success": True, **overview}


@router.get("/{username}/summary")
async def learning_memory_summary(
    username: str,
    workspace_id: int | None = None,
    query: str = "",
    limit: int = 20,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    svc = get_learning_assistant_service()
    overview = svc.get_learning_memory_overview(
        db,
        username,
        workspace_id=workspace_id,
        status="",
        query=query,
        limit=limit,
    )
    return {"success": True, "summary": overview["summary"]}


@router.post("/{username}/{memory_id}/status")
async def update_learning_memory_status(
    username: str,
    memory_id: int,
    payload: UpdateMemoryStatusRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    svc = get_learning_assistant_service()
    try:
        row = svc.update_learning_memory_status(db, username, memory_id, payload.status)
        return {"success": True, "memory": row.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新学习疑问状态失败: {e}")


@router.get("/{username}/{memory_id}")
async def get_learning_memory_detail(
    username: str,
    memory_id: int,
    http_request: Request,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    item = (
        db.query(LearningStudyMemory)
        .filter(LearningStudyMemory.id == memory_id, LearningStudyMemory.owner_username == username)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="学习疑问不存在")
    return {"success": True, "memory": item.to_dict()}
