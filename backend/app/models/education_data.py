"""
教务数据模型 - 存储爬虫抓取的数据
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Float, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base


class EducationData(Base):
    """教务数据表 - 存储学生所有教务信息"""
    __tablename__ = "education_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # 个人信息（JSON格式）
    personal_info = Column(JSON, default=dict, comment="个人信息")
    
    # 成绩数据
    grades = Column(JSON, default=list, comment="成绩列表")
    grade_stats = Column(JSON, default=dict, comment="成绩统计")
    
    # 课表数据
    schedule = Column(JSON, default=list, comment="课表")
    
    # 培养方案
    training_plan = Column(JSON, default=dict, comment="培养方案")
    
    # 学业进度
    academic_progress = Column(JSON, default=dict, comment="学业进度")
    
    # 考试安排
    exam_schedule = Column(JSON, default=list, comment="考试安排")
    
    # 执行计划
    execution_plan = Column(JSON, default=dict, comment="执行计划")
    
    # 选课信息
    course_selection = Column(JSON, default=dict, comment="选课信息")
    
    # 数据更新时间
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="education_data")


class EducationSyncSnapshot(Base):
    """教务同步快照表 - 保留每次同步的原始/标准化结果与状态"""
    __tablename__ = "education_sync_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True, comment="学号冗余")
    sync_key = Column(String(64), nullable=False, unique=True, index=True, comment="本次同步唯一键")
    schema_version = Column(String(20), nullable=False, default="v2", comment="数据契约版本")
    status = Column(String(20), nullable=False, default="pending", comment="pending/success/failed")
    sync_source = Column(String(50), nullable=False, default="auto_login", comment="auto_login/manual/tool_refresh")
    is_active = Column(Boolean, nullable=False, default=False, comment="是否当前激活快照")
    crawl_success = Column(Boolean, nullable=False, default=False)
    store_success = Column(Boolean, nullable=False, default=False)
    vector_success = Column(Boolean, nullable=False, default=False)
    summary = Column(JSON, default=dict, comment="计数摘要")
    raw_payload = Column(JSON, default=dict, comment="原始爬取数据")
    normalized_payload = Column(JSON, default=dict, comment="标准化数据")
    error_message = Column(Text, nullable=True, comment="失败信息")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Grade(Base):
    """成绩明细表（可选，用于更详细的查询）"""
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 课程信息
    semester = Column(String(50), nullable=False, comment="开课学期")
    course_code = Column(String(50), nullable=False, comment="课程代码")
    course_name = Column(String(200), nullable=False, comment="课程名称")
    course_nature = Column(String(100), nullable=True, comment="课程性质")
    credit = Column(Float, nullable=False, comment="学分")
    
    # 成绩信息
    usual_score = Column(String(20), nullable=True, comment="平时成绩")
    exam_score = Column(String(20), nullable=True, comment="期末成绩")
    final_score = Column(String(20), nullable=False, comment="总评成绩")
    gpa = Column(Float, nullable=True, comment="绩点")
    
    # 是否通过
    is_passed = Column(String(10), nullable=True, comment="是否通过")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Course(Base):
    """课程表（用于课表和选课信息）"""
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 课程基本信息
    semester = Column(String(50), nullable=False, comment="学期")
    course_code = Column(String(50), nullable=False, comment="课程代码")
    course_name = Column(String(200), nullable=False, comment="课程名称")
    credit = Column(Float, nullable=False, comment="学分")
    
    # 上课时间和地点
    weekday = Column(String(20), nullable=True, comment="星期")
    period = Column(String(50), nullable=True, comment="节次")
    weeks = Column(String(100), nullable=True, comment="周次")
    classroom = Column(String(200), nullable=True, comment="教室")
    
    # 教师
    teacher = Column(String(100), nullable=True, comment="教师")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
