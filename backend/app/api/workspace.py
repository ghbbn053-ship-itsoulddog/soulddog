"""
工作区 / 知识库 API。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import get_db
from app.security import enforce_username_isolation
from app.services.learning_assistant import get_learning_assistant_service
from app.services.learning_status import get_learning_status_service
from app.services.workspace_knowledge import get_workspace_knowledge_service

router = APIRouter(prefix="/api/workspace", tags=["工作区知识库"])


class WorkspaceCreateRequest(BaseModel):
    username: str
    name: str
    description: Optional[str] = ""


class TextIngestRequest(BaseModel):
    username: str
    workspace_id: int
    filename: str
    content: str
    authority_level: Optional[str] = "user"


class WorkspaceSearchRequest(BaseModel):
    username: str
    workspace_id: int
    query: str
    top_k: Optional[int] = 8


@router.get("/{username}")
async def list_workspaces(username: str, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc = get_workspace_knowledge_service()
    items = svc.list_workspaces(db, username)
    learning_svc = get_learning_assistant_service()
    status_svc = get_learning_status_service()
    workspace_ids = [item.id for item in items]
    memory_briefs = learning_svc.get_workspace_memory_briefs(db, username, workspace_ids)
    status_briefs = status_svc.get_workspace_status_briefs(db, username, workspace_ids)
    workspaces = []
    for item in items:
        learning_summary = memory_briefs.get(item.id) or {}
        learning_status = status_briefs.get(item.id) or {}
        recommended_followup = learning_summary.get("recommended_followup") or None
        workspaces.append(
            {
                "id": item.id,
                "slug": item.slug,
                "name": item.name,
                "description": item.description,
                "is_default": item.is_default,
                "learning_summary": {
                    "unresolved": int(learning_summary.get("unresolved") or 0),
                    "resolved": int(learning_summary.get("resolved") or 0),
                    "review_priority": learning_summary.get("review_priority") or [],
                    "recommended_followup": recommended_followup,
                    "prompt_strategy_rank": learning_summary.get("prompt_strategy_rank") or [],
                },
                "status_summary": {
                    "today_minutes": int((learning_status or {}).get("today_minutes") or 0),
                    "today_prompts": int((learning_status or {}).get("today_prompts") or 0),
                    "documents": int((learning_status or {}).get("documents") or 0),
                },
            }
        )
    return {
        "success": True,
        "workspaces": workspaces,
    }


@router.get("/{username}/detail/{workspace_id}")
async def workspace_detail(username: str, workspace_id: int, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc = get_workspace_knowledge_service()
    items = svc.list_workspaces(db, username)
    workspace = next((item for item in items if item.id == workspace_id), None)
    if not workspace:
        raise HTTPException(status_code=404, detail="工作区不存在")

    docs = svc.list_documents(db, username, workspace_id=workspace_id)
    graph = svc.get_workspace_graph(db, username, workspace_id)
    return {
        "success": True,
        "workspace": {
            "id": workspace.id,
            "slug": workspace.slug,
            "name": workspace.name,
            "description": workspace.description,
            "is_default": workspace.is_default,
        },
        "stats": {
            "documents": len(docs),
            "graph_nodes": len(graph.get("nodes", [])),
            "graph_edges": len(graph.get("edges", [])),
        },
        "graph": graph,
    }


@router.post("")
async def create_workspace(payload: WorkspaceCreateRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    svc = get_workspace_knowledge_service()
    workspace = svc.create_workspace(db, payload.username, payload.name, payload.description or "")
    return {
        "success": True,
        "workspace": {
            "id": workspace.id,
            "slug": workspace.slug,
            "name": workspace.name,
            "description": workspace.description,
            "is_default": workspace.is_default,
        },
    }


@router.get("/{username}/documents")
async def list_documents(
    username: str,
    workspace_id: Optional[int] = None,
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    svc = get_workspace_knowledge_service()
    docs = svc.list_documents(db, username, workspace_id=workspace_id)
    return {
        "success": True,
        "documents": [
            {
                "id": doc.id,
                "workspace_id": doc.workspace_id,
                "title": doc.title,
                "doc_type": doc.doc_type,
                "summary": doc.summary,
                "status": doc.status,
                "token_estimate": doc.token_estimate,
                "metadata": doc.metadata_json or {},
            }
            for doc in docs
        ],
    }


@router.post("/documents/text")
async def ingest_text_document(payload: TextIngestRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    svc = get_workspace_knowledge_service()
    try:
        doc = svc.ingest_text_document(
            db,
            owner_username=payload.username,
            workspace_id=payload.workspace_id,
            filename=payload.filename,
            content_text=payload.content,
            source_type="manual",
            authority_level=payload.authority_level or "user",
        )
        return {"success": True, "document_id": doc.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文本入库失败: {e}")


@router.post("/documents/upload")
async def upload_document(
    username: str = Form(...),
    workspace_id: int = Form(...),
    authority_level: str = Form("user"),
    document_file: UploadFile = File(...),
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    svc = get_workspace_knowledge_service()
    filename = Path(document_file.filename or "upload.txt").name
    raw = await document_file.read()

    try:
        doc = svc.ingest_uploaded_document(
            db,
            owner_username=username,
            workspace_id=workspace_id,
            filename=filename,
            raw_bytes=raw,
            source_type="upload",
            mime_type=document_file.content_type,
            authority_level=authority_level,
        )
        return {"success": True, "document_id": doc.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件入库失败: {e}")


@router.get("/{username}/graph/{workspace_id}")
async def workspace_graph(username: str, workspace_id: int, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc = get_workspace_knowledge_service()
    try:
        graph = svc.get_workspace_graph(db, username, workspace_id)
        return {"success": True, "graph": graph}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图谱获取失败: {e}")


@router.post("/search")
async def workspace_search(payload: WorkspaceSearchRequest, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, payload.username)
    svc = get_workspace_knowledge_service()
    try:
        results = svc.search_workspace(
            db,
            owner_username=payload.username,
            workspace_id=payload.workspace_id,
            query=payload.query,
            top_k=max(1, min(int(payload.top_k or 8), 20)),
        )
        return {"success": True, "results": results}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {e}")
