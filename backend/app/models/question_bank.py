"""
学习辅助数据模型：
- 个人题库
- 题目复盘记录
- 学习活动日志
- 浏览器侧自动化任务
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.models.base import Base


class LearningQuestion(Base):
    __tablename__ = "learning_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_username = Column(String(50), nullable=False, index=True, comment="题目归属用户")
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True, index=True, comment="关联工作区")
    platform_name = Column(String(50), nullable=False, default="chaoxing", comment="来源平台")
    course_name = Column(String(200), nullable=True, comment="课程名称")
    chapter_name = Column(String(200), nullable=True, comment="章节名称")
    title = Column(Text, nullable=False, comment="题目标题")
    question_type = Column(String(20), nullable=False, default="unknown", comment="single/multiple/blank/judge/essay")
    options_json = Column(JSON, default=list, comment="题目选项")
    answer_json = Column(JSON, default=list, comment="参考答案，仅用户自行整理")
    explanation_text = Column(Text, nullable=True, comment="解析与思路")
    source = Column(String(20), nullable=False, default="manual", comment="manual/ai/import")
    verified_status = Column(String(20), nullable=False, default="draft", comment="draft/reviewed/verified")
    tags_json = Column(JSON, default=list, comment="标签")
    usage_count = Column(Integer, nullable=False, default=0, comment="复用次数")
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(50), nullable=True, comment="记录创建者")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_learning_question_owner_platform", "owner_username", "platform_name"),
        Index("idx_learning_question_owner_workspace", "owner_username", "workspace_id"),
        Index("idx_learning_question_verified", "owner_username", "verified_status"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "owner_username": self.owner_username,
            "workspace_id": self.workspace_id,
            "platform_name": self.platform_name,
            "course_name": self.course_name,
            "chapter_name": self.chapter_name,
            "title": self.title,
            "question_type": self.question_type,
            "options": self.options_json or [],
            "answer": self.answer_json or [],
            "explanation": self.explanation_text or "",
            "source": self.source,
            "verified_status": self.verified_status,
            "tags": self.tags_json or [],
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LearningQuestionAttempt(Base):
    __tablename__ = "learning_question_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_username = Column(String(50), nullable=False, index=True, comment="记录所属用户")
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True, index=True)
    question_id = Column(Integer, ForeignKey("learning_questions.id"), nullable=False, index=True)
    submitted_answer_json = Column(JSON, default=list, comment="用户提交的答案")
    result_status = Column(String(20), nullable=False, default="unknown", comment="correct/incorrect/needs_review/unknown")
    note = Column(Text, nullable=True, comment="复盘备注")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_learning_attempt_owner_question", "owner_username", "question_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "owner_username": self.owner_username,
            "workspace_id": self.workspace_id,
            "question_id": self.question_id,
            "submitted_answer": self.submitted_answer_json or [],
            "result_status": self.result_status,
            "note": self.note or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LearningActivity(Base):
    __tablename__ = "learning_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_username = Column(String(50), nullable=False, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True, index=True)
    platform_name = Column(String(50), nullable=False, default="chaoxing")
    activity_type = Column(String(50), nullable=False, default="study_note", comment="study_note/course_sync/review/question_capture")
    title = Column(String(255), nullable=False)
    course_name = Column(String(200), nullable=True)
    chapter_name = Column(String(200), nullable=True)
    status = Column(String(20), nullable=False, default="recorded", comment="recorded/doing/done/blocked")
    detail_text = Column(Text, nullable=True)
    meta_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_learning_activity_owner_platform", "owner_username", "platform_name"),
        Index("idx_learning_activity_owner_workspace", "owner_username", "workspace_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "owner_username": self.owner_username,
            "workspace_id": self.workspace_id,
            "platform_name": self.platform_name,
            "activity_type": self.activity_type,
            "title": self.title,
            "course_name": self.course_name,
            "chapter_name": self.chapter_name,
            "status": self.status,
            "detail": self.detail_text or "",
            "meta": self.meta_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LearningStudyMemory(Base):
    __tablename__ = "learning_study_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_username = Column(String(50), nullable=False, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True, index=True)
    course_name = Column(String(200), nullable=True)
    question_text = Column(Text, nullable=False)
    question_summary = Column(String(300), nullable=False)
    question_type = Column(String(40), nullable=False, default="general")
    knowledge_points_json = Column(JSON, default=list)
    status = Column(String(20), nullable=False, default="unresolved")
    answer_summary = Column(Text, nullable=True)
    source_refs_json = Column(JSON, default=dict)
    importance = Column(Integer, nullable=False, default=3)
    question_fingerprint = Column(String(64), nullable=False, index=True)
    conversation_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_learning_memory_owner_workspace_status", "owner_username", "workspace_id", "status"),
        Index("idx_learning_memory_owner_workspace_course", "owner_username", "workspace_id", "course_name"),
        Index("idx_learning_memory_owner_fingerprint", "owner_username", "question_fingerprint"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "owner_username": self.owner_username,
            "workspace_id": self.workspace_id,
            "course_name": self.course_name or "",
            "question_text": self.question_text,
            "question_summary": self.question_summary,
            "question_type": self.question_type,
            "knowledge_points": self.knowledge_points_json or [],
            "status": self.status,
            "answer_summary": self.answer_summary or "",
            "source_refs": self.source_refs_json or {},
            "importance": self.importance,
            "conversation_id": self.conversation_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LearningAutomationTask(Base):
    __tablename__ = "learning_automation_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_username = Column(String(50), nullable=False, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True, index=True)
    platform_name = Column(String(50), nullable=False, default="chaoxing")
    task_name = Column(String(255), nullable=False)
    course_name = Column(String(255), nullable=True)
    course_url = Column(Text, nullable=False)
    start_url = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending", comment="pending/running/paused/completed/failed/stopped")
    runner_token = Column(String(120), nullable=False, unique=True, index=True)
    automation_options_json = Column(JSON, default=dict)
    runner_meta_json = Column(JSON, default=dict)
    last_stage = Column(String(80), nullable=True)
    last_url = Column(Text, nullable=True)
    last_message = Column(Text, nullable=True)
    last_ping_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_learning_automation_task_owner_workspace", "owner_username", "workspace_id"),
        Index("idx_learning_automation_task_owner_status", "owner_username", "status"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "owner_username": self.owner_username,
            "workspace_id": self.workspace_id,
            "platform_name": self.platform_name,
            "task_name": self.task_name,
            "course_name": self.course_name,
            "course_url": self.course_url,
            "start_url": self.start_url,
            "status": self.status,
            "runner_token": self.runner_token,
            "automation_options": self.automation_options_json or {},
            "runner_meta": self.runner_meta_json or {},
            "last_stage": self.last_stage,
            "last_url": self.last_url,
            "last_message": self.last_message,
            "last_ping_at": self.last_ping_at.isoformat() if self.last_ping_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LearningAutomationEvent(Base):
    __tablename__ = "learning_automation_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("learning_automation_tasks.id"), nullable=False, index=True)
    owner_username = Column(String(50), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, default="log")
    level = Column(String(20), nullable=False, default="info")
    stage = Column(String(80), nullable=True)
    message = Column(Text, nullable=False)
    current_url = Column(Text, nullable=True)
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_learning_automation_event_task_created", "task_id", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "owner_username": self.owner_username,
            "event_type": self.event_type,
            "level": self.level,
            "stage": self.stage,
            "message": self.message,
            "current_url": self.current_url,
            "payload": self.payload_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
