"""
平台核心对象模型：
- 工作区
- 知识源/文档/切片
- 轻量关系图谱
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    owner_username = Column(String(50), nullable=False, index=True, comment="当前先按学号隔离")
    slug = Column(String(100), nullable=False, comment="工作区唯一名（owner内）")
    name = Column(String(200), nullable=False, comment="工作区名称")
    description = Column(Text, nullable=True, comment="工作区描述")
    is_default = Column(Boolean, nullable=False, default=False, comment="是否默认工作区")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sources = relationship("KnowledgeSource", back_populates="workspace", cascade="all, delete-orphan")
    documents = relationship("KnowledgeDocument", back_populates="workspace", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("owner_username", "slug", name="uq_workspace_owner_slug"),
    )


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    owner_username = Column(String(50), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, comment="upload/manual/crawler/system")
    title = Column(String(255), nullable=False, comment="来源标题")
    mime_type = Column(String(120), nullable=True, comment="文件类型")
    original_filename = Column(String(255), nullable=True)
    storage_path = Column(String(500), nullable=True, comment="本地存储路径")
    status = Column(String(30), nullable=False, default="ready", comment="ready/processing/failed")
    authority_level = Column(String(30), nullable=False, default="user", comment="system/school/user")
    meta_json = Column(JSON, default=dict, comment="来源元数据")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    workspace = relationship("Workspace", back_populates="sources")
    documents = relationship("KnowledgeDocument", back_populates="source", cascade="all, delete-orphan")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("knowledge_sources.id"), nullable=False, index=True)
    owner_username = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    doc_type = Column(String(50), nullable=False, default="document", comment="document/education_snapshot/skill/mcp")
    status = Column(String(30), nullable=False, default="ready")
    summary = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True, comment="清洗后的全文")
    token_estimate = Column(Integer, nullable=False, default=0)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    workspace = relationship("Workspace", back_populates="documents")
    source = relationship("KnowledgeSource", back_populates="documents")
    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    owner_username = Column(String(50), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False, default=0)
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False, default=0)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk_doc_idx"),
    )


class KnowledgeRelation(Base):
    __tablename__ = "knowledge_relations"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    owner_username = Column(String(50), nullable=False, index=True)
    subject_type = Column(String(50), nullable=False)
    subject_ref = Column(String(255), nullable=False)
    relation_type = Column(String(50), nullable=False)
    object_type = Column(String(50), nullable=False)
    object_ref = Column(String(255), nullable=False)
    confidence = Column(String(20), nullable=False, default="high")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SkillManifest(Base):
    __tablename__ = "skill_manifests"

    id = Column(Integer, primary_key=True, index=True)
    owner_username = Column(String(50), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    version = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    triggers = Column(JSON, default=list)
    tools = Column(JSON, default=list)
    source_type = Column(String(30), nullable=False, default="yaml")
    source_ref = Column(String(500), nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("owner_username", "name", name="uq_skill_manifest_owner_name"),
    )


class MCPServerManifest(Base):
    __tablename__ = "mcp_server_manifests"

    id = Column(Integer, primary_key=True, index=True)
    owner_username = Column(String(50), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    kind = Column(String(30), nullable=False, default="python")
    enabled = Column(Boolean, nullable=False, default=True)
    tool_schema = Column(JSON, default=dict)
    source_type = Column(String(30), nullable=False, default="registry")
    source_ref = Column(String(500), nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("owner_username", "name", name="uq_mcp_manifest_owner_name"),
    )


class WorkspaceSuggestion(Base):
    __tablename__ = "workspace_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False, index=True)
    owner_username = Column(String(50), nullable=False, index=True)
    suggestion_key = Column(String(160), nullable=False, comment="建议幂等键")
    suggestion_type = Column(String(50), nullable=False, comment="exam_reminder/class_reminder/study_plan/knowledge_gap/review_reminder/data_refresh")
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    tone = Column(String(20), nullable=False, default="normal", comment="normal/warning/urgent")
    status = Column(String(20), nullable=False, default="active", comment="active/accepted/dismissed/expired")
    payload_json = Column(JSON, default=dict)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("workspace_id", "suggestion_key", name="uq_workspace_suggestion_workspace_key"),
    )
