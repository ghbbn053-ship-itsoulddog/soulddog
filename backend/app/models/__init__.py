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
    SkillManifest,
    MCPServerManifest,
    WorkspaceSuggestion,
    AgentAccessToken,
    ExternalServiceBinding,
)
from app.models.question_bank import (
    LearningQuestion,
    LearningQuestionAttempt,
    LearningActivity,
    LearningStudyMemory,
    LearningAutomationTask,
    LearningAutomationEvent,
)
from app.models.chaoxing_qr_session import ChaoxingQrSession

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
    "SkillManifest",
    "MCPServerManifest",
    "WorkspaceSuggestion",
    "AgentAccessToken",
    "ExternalServiceBinding",
    "LearningQuestion",
    "LearningQuestionAttempt",
    "LearningActivity",
    "LearningStudyMemory",
    "LearningAutomationTask",
    "LearningAutomationEvent",
    "ChaoxingQrSession",
]
