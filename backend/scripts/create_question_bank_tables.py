"""
创建学习辅助相关数据库表
运行: python create_question_bank_tables.py
"""

import os
import sys

from sqlalchemy import inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.base import engine
from app.models.question_bank import (
    LearningActivity,
    LearningAutomationEvent,
    LearningAutomationTask,
    LearningQuestion,
    LearningQuestionAttempt,
)
from app.models.chaoxing_qr_session import ChaoxingQrSession


def create_tables():
    print("📚 开始创建学习辅助相关表...")
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    targets = [
        ("learning_questions", LearningQuestion),
        ("learning_question_attempts", LearningQuestionAttempt),
        ("learning_activities", LearningActivity),
        ("learning_automation_tasks", LearningAutomationTask),
        ("learning_automation_events", LearningAutomationEvent),
        ("chaoxing_qr_sessions", ChaoxingQrSession),
    ]
    for table_name, model in targets:
        if table_name in existing_tables:
            print(f"⚠️  {table_name} 已存在，跳过创建")
            continue
        print(f"✅ 创建 {table_name} ...")
        model.__table__.create(engine)
        print(f"✅ {table_name} 创建成功")
    print("\n🎉 学习辅助表创建完成")


if __name__ == "__main__":
    create_tables()
