"""
模型模块
"""

from app.models.base import Base, engine, get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.models.education_data import EducationData, EducationSyncSnapshot, Grade, Course
from app.models.platform import (
    Workspace,
    KnowledgeSource,
    KnowledgeDocument,
    KnowledgeChunk,
    KnowledgeRelation,
)

# 创建所有表
def create_tables():
    Base.metadata.create_all(bind=engine)

__all__ = [
    "Base",
    "engine",
    "get_db",
    "create_tables",
    "User",
    "Conversation",
    "Message",
    "EducationData",
    "EducationSyncSnapshot",
    "Grade",
    "Course",
    "Workspace",
    "KnowledgeSource",
    "KnowledgeDocument",
    "KnowledgeChunk",
    "KnowledgeRelation",
]
