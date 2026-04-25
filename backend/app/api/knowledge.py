"""
知识库 API。

目标：
- 将知识库读接口从 workspace CRUD 中拆出
- 让前端以“知识库引擎”口径读取文档、统计、检索
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.models import get_db
from app.security import enforce_username_isolation
from app.services.workspace_knowledge import get_workspace_knowledge_service

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


@router.get("/{username}/{workspace_id}")
async def get_workspace_knowledge(username: str, workspace_id: int, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc = get_workspace_knowledge_service()
    try:
        overview = svc.get_workspace_knowledge_overview(db, username, workspace_id)
        return {"success": True, **overview}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识库读取失败: {e}")


@router.get("/{username}/{workspace_id}/stats")
async def get_workspace_knowledge_stats(username: str, workspace_id: int, http_request: Request, db: Session = Depends(get_db)):
    enforce_username_isolation(http_request, username)
    svc = get_workspace_knowledge_service()
    try:
        overview = svc.get_workspace_knowledge_overview(db, username, workspace_id)
        return {"success": True, "workspace": overview["workspace"], "stats": overview["stats"]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识库统计读取失败: {e}")


@router.get("/{username}/{workspace_id}/documents/{document_id}/chunks")
async def get_document_chunks(
    username: str,
    workspace_id: int,
    document_id: int,
    http_request: Request,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    svc = get_workspace_knowledge_service()
    try:
        chunks = svc.list_document_chunks(db, username, workspace_id, document_id)
        return {"success": True, "chunks": chunks}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档片段读取失败: {e}")


@router.delete("/{username}/{workspace_id}/documents/{document_id}")
async def delete_document(
    username: str,
    workspace_id: int,
    document_id: int,
    http_request: Request,
    db: Session = Depends(get_db),
):
    enforce_username_isolation(http_request, username)
    svc = get_workspace_knowledge_service()
    try:
        result = svc.delete_document(db, username, workspace_id, document_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档删除失败: {e}")
