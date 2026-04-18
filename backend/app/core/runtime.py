"""
后端运行时单例与可选依赖探测。
"""

import logging

from app.services.session_store import get_session_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

session_store = get_session_store()

try:
    from app.models import create_tables, get_db, User, EducationData
    from app.services.data_processor import data_processor

    DB_AVAILABLE = True
except Exception as e:
    DB_AVAILABLE = False
    create_tables = None
    get_db = None
    User = None
    EducationData = None
    data_processor = None
    logger.warning(f"⚠️ 数据库模块未启用: {e}")

