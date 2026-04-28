"""
学习辅助题库 API
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import get_db
from app.security import enforce_username_isolation
from app.services.learning_assistant import get_learning_assistant_service

router = APIRouter(prefix="/api/chaoxing/question-bank", tags=["learning-question-bank"])


class SearchQuestionRequest(BaseModel):
    username: str
    workspace_id: Optional[int] = None
    query: str
    limit: Optional[int] = 20


class SaveQuestionRequest(BaseModel):
    username: str
    workspace_id: Optional[int] = None
    platform_name: Optional[str] = "chaoxing"
    course_name: Optional[str] = ""
    chapter_name: Optional[str] = ""
    title: str
    question_type: str
    options: List[str] = []
    answer: List[str] = []
    explanation: Optional[str] = ""
    source: Optional[str] = "manual"
    verified_status: Optional[str] = "draft"
    tags: List[str] = []
    created_by: Optional[str] = None


class AnalyzeQuestionRequest(BaseModel):
    username: str
    course_name: Optional[str] = ""
    title: str
    question_type: str
    options: List[str] = []


class AttemptQuestionRequest(BaseModel):
    username: str
    workspace_id: Optional[int] = None
    question_id: int
    submitted_answer: List[str] = []
    result_status: Optional[str] = "unknown"
    note: Optional[str] = ""


@router.post("/search")
async def search_questions(payload: SearchQuestionRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    rows = get_learning_assistant_service().list_questions(
        db,
        payload.username,
        workspace_id=payload.workspace_id,
        limit=int(payload.limit or 20),
        query=payload.query or "",
    )
    return {"success": True, "items": [item.to_dict() for item in rows]}


@router.get("/list")
async def list_questions(
    username: str,
    workspace_id: Optional[int] = None,
    limit: int = 50,
    query: str = "",
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    rows = get_learning_assistant_service().list_questions(
        db,
        username,
        workspace_id=workspace_id,
        limit=limit,
        query=query,
    )
    return {"success": True, "questions": [item.to_dict() for item in rows], "total": len(rows)}


@router.post("/save")
async def save_question(payload: SaveQuestionRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    if not (payload.title or "").strip():
        raise HTTPException(status_code=400, detail="title 不能为空")
    row = get_learning_assistant_service().save_question(
        db,
        owner_username=payload.username,
        workspace_id=payload.workspace_id,
        platform_name=payload.platform_name or "chaoxing",
        course_name=payload.course_name or "",
        chapter_name=payload.chapter_name or "",
        title=payload.title,
        question_type=payload.question_type,
        options=payload.options or [],
        answer=payload.answer or [],
        explanation=payload.explanation or "",
        source=payload.source or "manual",
        verified_status=payload.verified_status or "draft",
        tags=payload.tags or [],
        created_by=payload.created_by or payload.username,
    )
    return {"success": True, "question": row.to_dict()}


@router.post("/analyze")
async def analyze_question(payload: AnalyzeQuestionRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    if not (payload.title or "").strip():
        raise HTTPException(status_code=400, detail="title 不能为空")
    result = get_learning_assistant_service().analyze_question(
        payload.username,
        title=payload.title,
        question_type=payload.question_type,
        options=payload.options or [],
        course_name=payload.course_name or "",
    )
    return {"success": True, **result}


@router.post("/attempt")
async def record_attempt(payload: AttemptQuestionRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    try:
        row = get_learning_assistant_service().log_attempt(
            db,
            owner_username=payload.username,
            workspace_id=payload.workspace_id,
            question_id=payload.question_id,
            submitted_answer=payload.submitted_answer or [],
            result_status=payload.result_status or "unknown",
            note=payload.note or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"success": True, "attempt": row.to_dict()}
