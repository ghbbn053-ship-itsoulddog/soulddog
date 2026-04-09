"""
模型模块
"""

from app.models.base import Base, engine, get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.models.education_data import EducationData, Grade, Course

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
    "Grade",
    "Course",
]
