"""
工作区知识库服务：
- 工作区管理
- 用户上传文档入库
- 文档切块和向量化
- 轻量关系抽取（Skill/MCP/文档）
"""

from __future__ import annotations

import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import User
from app.models.platform import (
    Workspace,
    KnowledgeSource,
    KnowledgeDocument,
    KnowledgeChunk,
    KnowledgeRelation,
)
from app.services import get_model_provider, get_vector_store

logger = logging.getLogger(__name__)

UPLOAD_ROOT = Path("backend/data/workspace_uploads")


def _slugify(text: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", (text or "").strip()).strip("-").lower()
    return base or "workspace"


def _normalize_text(text: str) -> str:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    lines = [line.strip() for line in raw.split("\n")]
    return "\n".join(lines).strip()


def _split_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]
    chunks: List[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


class WorkspaceKnowledgeService:
    def ensure_default_workspace(self, db: Session, owner_username: str) -> Workspace:
        workspace = (
            db.query(Workspace)
            .filter(Workspace.owner_username == owner_username, Workspace.is_default == True)
            .first()
        )
        if workspace:
            return workspace

        workspace = Workspace(
            owner_username=owner_username,
            slug="default",
            name="默认工作区",
            description="平台默认知识空间",
            is_default=True,
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        return workspace

    def list_workspaces(self, db: Session, owner_username: str) -> List[Workspace]:
        self.ensure_default_workspace(db, owner_username)
        return (
            db.query(Workspace)
            .filter(Workspace.owner_username == owner_username)
            .order_by(Workspace.is_default.desc(), Workspace.id.asc())
            .all()
        )

    def create_workspace(self, db: Session, owner_username: str, name: str, description: str = "") -> Workspace:
        self.ensure_default_workspace(db, owner_username)
        slug_seed = _slugify(name)
        slug = slug_seed
        index = 2
        while (
            db.query(Workspace)
            .filter(Workspace.owner_username == owner_username, Workspace.slug == slug)
            .first()
        ):
            slug = f"{slug_seed}-{index}"
            index += 1
        workspace = Workspace(
            owner_username=owner_username,
            slug=slug,
            name=name.strip() or "未命名工作区",
            description=(description or "").strip(),
            is_default=False,
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        return workspace

    def _owner_dir(self, owner_username: str, workspace_slug: str) -> Path:
        target = UPLOAD_ROOT / owner_username / workspace_slug
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _extract_relations(self, owner_username: str, workspace_id: int, title: str, content: str) -> List[KnowledgeRelation]:
        relations: List[KnowledgeRelation] = []
        lowered = f"{title}\n{content}".lower()
        if "skill" in lowered:
            relations.append(
                KnowledgeRelation(
                    workspace_id=workspace_id,
                    owner_username=owner_username,
                    subject_type="document",
                    subject_ref=title,
                    relation_type="mentions",
                    object_type="capability",
                    object_ref="skill",
                    confidence="medium",
                    metadata_json={},
                )
            )
        if "mcp" in lowered:
            relations.append(
                KnowledgeRelation(
                    workspace_id=workspace_id,
                    owner_username=owner_username,
                    subject_type="document",
                    subject_ref=title,
                    relation_type="mentions",
                    object_type="capability",
                    object_ref="mcp",
                    confidence="medium",
                    metadata_json={},
                )
            )
        return relations

    def ingest_text_document(
        self,
        db: Session,
        owner_username: str,
        workspace_id: int,
        filename: str,
        content_text: str,
        source_type: str = "upload",
        mime_type: Optional[str] = None,
        extra_meta: Optional[Dict] = None,
    ) -> KnowledgeDocument:
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == workspace_id, Workspace.owner_username == owner_username)
            .first()
        )
        if not workspace:
            raise ValueError("工作区不存在")

        normalized = _normalize_text(content_text)
        if not normalized:
            raise ValueError("文档内容为空")

        owner_dir = self._owner_dir(owner_username, workspace.slug)
        target_path = owner_dir / filename
        target_path.write_text(normalized, encoding="utf-8")

        detected_mime = mime_type or mimetypes.guess_type(filename)[0] or "text/plain"
        source = KnowledgeSource(
            workspace_id=workspace.id,
            owner_username=owner_username,
            source_type=source_type,
            title=filename,
            mime_type=detected_mime,
            original_filename=filename,
            storage_path=str(target_path),
            status="ready",
            authority_level="user",
            meta_json=extra_meta or {},
        )
        db.add(source)
        db.flush()

        title = Path(filename).stem or filename
        summary = normalized[:240]
        doc = KnowledgeDocument(
            workspace_id=workspace.id,
            source_id=source.id,
            owner_username=owner_username,
            title=title,
            doc_type="document",
            status="ready",
            summary=summary,
            content_text=normalized,
            token_estimate=max(1, len(normalized) // 2),
            metadata_json={
                "filename": filename,
                "source_type": source_type,
                "mime_type": detected_mime,
                **(extra_meta or {}),
            },
        )
        db.add(doc)
        db.flush()

        chunks = _split_text(normalized)
        chunk_rows: List[KnowledgeChunk] = []
        for idx, chunk in enumerate(chunks):
            chunk_rows.append(
                KnowledgeChunk(
                    document_id=doc.id,
                    workspace_id=workspace.id,
                    owner_username=owner_username,
                    chunk_index=idx,
                    title=title if idx == 0 else f"{title} #{idx + 1}",
                    content=chunk,
                    char_count=len(chunk),
                    metadata_json={"document_title": title, "filename": filename},
                )
            )
        db.add_all(chunk_rows)

        relations = self._extract_relations(owner_username, workspace.id, title, normalized)
        if relations:
            db.add_all(relations)

        db.commit()
        db.refresh(doc)

        self._vectorize_document(doc, chunk_rows)
        return doc

    def _vectorize_document(self, document: KnowledgeDocument, chunks: List[KnowledgeChunk]):
        if not chunks:
            return
        provider = get_model_provider()
        vec_store = get_vector_store()
        texts: List[str] = []
        embeddings: List[List[float]] = []
        sources: List[str] = []
        metadatas: List[Dict] = []

        for chunk in chunks:
            emb = provider.generate_embedding(chunk.content)
            if not emb:
                continue
            texts.append(chunk.content)
            embeddings.append(emb)
            sources.append(f"workspace:{document.workspace_id}:{document.title}")
            metadatas.append(
                {
                    "type": "knowledge_chunk",
                    "document_id": document.id,
                    "workspace_id": document.workspace_id,
                    "owner_username": document.owner_username,
                    "chunk_index": chunk.chunk_index,
                    "title": chunk.title,
                }
            )
        if texts and embeddings:
            user_numeric = abs(hash(document.owner_username)) % 2_000_000_000
            try:
                vec_store.add_documents(user_numeric, texts, embeddings, sources, metadatas)
            except Exception as e:
                logger.warning("工作区文档向量化失败: %s", e)

    def list_documents(self, db: Session, owner_username: str, workspace_id: Optional[int] = None) -> List[KnowledgeDocument]:
        query = db.query(KnowledgeDocument).filter(KnowledgeDocument.owner_username == owner_username)
        if workspace_id:
            query = query.filter(KnowledgeDocument.workspace_id == workspace_id)
        return query.order_by(KnowledgeDocument.id.desc()).all()

    @staticmethod
    def _fallback_search_score(query: str, text: str) -> float:
        q = (query or "").strip().lower()
        t = (text or "").strip().lower()
        if not q or not t:
            return 0.0
        if q in t:
            return min(1.0, 0.65 + (len(q) / max(len(t), 1)))
        q_terms = [term for term in re.split(r"[\s,，。；;、]+", q) if term]
        if not q_terms:
            return 0.0
        hits = sum(1 for term in q_terms if term in t)
        return hits / max(len(q_terms), 1)

    def search_workspace(
        self,
        db: Session,
        owner_username: str,
        workspace_id: int,
        query: str,
        top_k: int = 8,
    ) -> List[Dict]:
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == workspace_id, Workspace.owner_username == owner_username)
            .first()
        )
        if not workspace:
            raise ValueError("工作区不存在")

        provider = get_model_provider()
        vec_store = get_vector_store()
        query_embedding = provider.generate_embedding(query)
        user_numeric = abs(hash(owner_username)) % 2_000_000_000
        hits: List[Dict] = []

        if query_embedding:
            try:
                raw_hits = vec_store.search(user_numeric, query_embedding, top_k=top_k * 2)
                for hit in raw_hits:
                    meta = hit.get("metadata") or {}
                    if int(meta.get("workspace_id", -1)) != int(workspace_id):
                        continue
                    hits.append(
                        {
                            "document_id": meta.get("document_id"),
                            "title": meta.get("title") or hit.get("source") or "未知文档",
                            "content": hit.get("text", ""),
                            "score": float(hit.get("score", 0.0)),
                            "chunk_index": meta.get("chunk_index", 0),
                            "source": hit.get("source", ""),
                        }
                    )
                    if len(hits) >= top_k:
                        break
            except Exception as e:
                logger.warning("工作区向量检索失败，回退文本匹配: %s", e)

        if hits:
            return hits[:top_k]

        docs = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.owner_username == owner_username, KnowledgeDocument.workspace_id == workspace_id)
            .all()
        )
        scored: List[Tuple[float, KnowledgeDocument]] = []
        for doc in docs:
            score = self._fallback_search_score(query, f"{doc.title}\n{doc.summary or ''}\n{doc.content_text or ''}")
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "document_id": doc.id,
                "title": doc.title,
                "content": (doc.summary or doc.content_text or "")[:400],
                "score": float(score),
                "chunk_index": 0,
                "source": f"workspace:{workspace_id}:{doc.title}",
            }
            for score, doc in scored[:top_k]
        ]

    def get_workspace_graph(self, db: Session, owner_username: str, workspace_id: int) -> Dict:
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == workspace_id, Workspace.owner_username == owner_username)
            .first()
        )
        if not workspace:
            raise ValueError("工作区不存在")
        docs = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.workspace_id == workspace_id, KnowledgeDocument.owner_username == owner_username)
            .all()
        )
        rels = (
            db.query(KnowledgeRelation)
            .filter(KnowledgeRelation.workspace_id == workspace_id, KnowledgeRelation.owner_username == owner_username)
            .order_by(KnowledgeRelation.id.desc())
            .all()
        )
        nodes = [
            {"id": f"doc:{doc.id}", "label": doc.title, "type": doc.doc_type}
            for doc in docs
        ]
        node_ids = {node["id"] for node in nodes}
        edge_ids = set()
        edges = [
            {
                "id": f"rel:{rel.id}",
                "source": rel.subject_ref if rel.subject_ref.startswith("doc:") else f"label:{rel.subject_ref}",
                "target": rel.object_ref if rel.object_ref.startswith("doc:") else f"label:{rel.object_ref}",
                "label": rel.relation_type,
                "subject_type": rel.subject_type,
                "object_type": rel.object_type,
            }
            for rel in rels
        ]
        edge_ids.update(edge["id"] for edge in edges)

        for edge in edges:
            if edge["source"] not in node_ids:
                nodes.append({"id": edge["source"], "label": edge["source"].split(":", 1)[-1], "type": "label"})
                node_ids.add(edge["source"])
            if edge["target"] not in node_ids:
                nodes.append({"id": edge["target"], "label": edge["target"].split(":", 1)[-1], "type": "label"})
                node_ids.add(edge["target"])

        from app.services.skill_manager import get_skill_manager
        from app.services.mcp_registry import get_mcp_registry
        from app.services.composition_manager import get_composition_manager

        skill_items = get_skill_manager().list_skills(owner_username)
        mcp_items = get_mcp_registry().list_tools()
        composition = get_composition_manager().resolved(owner_username)

        for skill in skill_items:
            node_id = f"skill:{skill['name']}"
            if node_id not in node_ids:
                nodes.append({"id": node_id, "label": skill["name"], "type": "skill"})
                node_ids.add(node_id)
            edge_id = f"derived:workspace-skill:{workspace_id}:{skill['name']}"
            if edge_id not in edge_ids:
                edges.append(
                    {
                        "id": edge_id,
                        "source": f"workspace:{workspace_id}",
                        "target": node_id,
                        "label": "contains",
                        "subject_type": "workspace",
                        "object_type": "skill",
                    }
                )
                edge_ids.add(edge_id)

        for tool in mcp_items:
            tool_name = str(tool.get("name", "")).strip()
            if not tool_name:
                continue
            node_id = f"mcp:{tool_name}"
            if node_id not in node_ids:
                nodes.append({"id": node_id, "label": tool_name, "type": "mcp"})
                node_ids.add(node_id)
            edge_id = f"derived:workspace-mcp:{workspace_id}:{tool_name}"
            if edge_id not in edge_ids:
                edges.append(
                    {
                        "id": edge_id,
                        "source": f"workspace:{workspace_id}",
                        "target": node_id,
                        "label": "can_use",
                        "subject_type": "workspace",
                        "object_type": "mcp",
                    }
                )
                edge_ids.add(edge_id)

        if f"workspace:{workspace_id}" not in node_ids:
            nodes.append({"id": f"workspace:{workspace_id}", "label": workspace.name, "type": "workspace"})
            node_ids.add(f"workspace:{workspace_id}")

        for skill_name in composition.get("skills", []):
            skill_node = f"skill:{skill_name}"
            if skill_node in node_ids:
                edge_id = f"derived:enabled-skill:{workspace_id}:{skill_name}"
                if edge_id not in edge_ids:
                    edges.append(
                        {
                            "id": edge_id,
                            "source": f"workspace:{workspace_id}",
                            "target": skill_node,
                            "label": "enabled",
                            "subject_type": "workspace",
                            "object_type": "skill",
                        }
                    )
                    edge_ids.add(edge_id)

        for tool_name in composition.get("mcp_tools", []):
            tool_node = f"mcp:{tool_name}"
            if tool_node in node_ids:
                edge_id = f"derived:enabled-mcp:{workspace_id}:{tool_name}"
                if edge_id not in edge_ids:
                    edges.append(
                        {
                            "id": edge_id,
                            "source": f"workspace:{workspace_id}",
                            "target": tool_node,
                            "label": "enabled",
                            "subject_type": "workspace",
                            "object_type": "mcp",
                        }
                    )
                    edge_ids.add(edge_id)
        return {
            "workspace": {"id": workspace.id, "name": workspace.name, "slug": workspace.slug},
            "nodes": nodes,
            "edges": edges,
        }


_workspace_knowledge_singleton: Optional[WorkspaceKnowledgeService] = None


def get_workspace_knowledge_service() -> WorkspaceKnowledgeService:
    global _workspace_knowledge_singleton
    if _workspace_knowledge_singleton is None:
        _workspace_knowledge_singleton = WorkspaceKnowledgeService()
    return _workspace_knowledge_singleton
