from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class EducationData(Base):
    """教务数据模型（存储向量化前的原始数据）"""
    __tablename__ = "education_data"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    
    # 数据类型
    data_type = Column(String(50), nullable=False, comment="数据类型: grade/schedule/course/info")
    
    # 数据内容
    title = Column(String(255), nullable=True, comment="标题")
    content = Column(Text, nullable=False, comment="内容")
    raw_data = Column(JSON, nullable=True, comment="原始JSON数据")
    
    # 向量化状态
    is_vectorized = Column(Boolean, default=False, comment="是否已向量化")
    vector_id = Column(String(100), nullable=True, comment="Milvus中的向量ID")
    
    # 元数据
    semester = Column(String(50), nullable=True, comment="学期")
    academic_year = Column(String(20), nullable=True, comment="学年")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
