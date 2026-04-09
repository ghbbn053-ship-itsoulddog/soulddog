"""
用户模型
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False, comment="学号")
    name = Column(String(100), nullable=True, comment="姓名")
    department = Column(String(200), nullable=True, comment="学院")
    major = Column(String(200), nullable=True, comment="专业")
    class_name = Column(String(100), nullable=True, comment="班级")
    
    # 状态
    is_active = Column(Boolean, default=True, comment="是否激活")
    last_login = Column(DateTime(timezone=True), nullable=True, comment="最后登录时间")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    education_data = relationship("EducationData", back_populates="user", cascade="all, delete-orphan")
