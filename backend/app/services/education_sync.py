"""
教务数据同步服务（登录后后台爬取 + 手动同步）。
"""

import time

from scraper import JwxtScraper
from app.core.runtime import logger, session_store, DB_AVAILABLE, data_processor, get_db, User


def auto_crawl_and_store(username: str, session, server_url: str):
    """
    登录成功后的后台任务：自动爬取全部教务数据并存储
    1. 爬取全部数据
    2. 存入 PostgreSQL
    3. 向量化存入 Milvus
    """
    session_store.set_sync_status(username, {"status": "syncing", "message": "正在爬取教务数据...", "timestamp": time.time()})

    try:
        logger.info(f"【自动爬取】开始为用户 {username} 爬取数据")

        # 1. 爬取全部数据
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_all_data_for_vectorization()

        if not result.get("success"):
            session_store.set_sync_status(username, {"status": "failed", "message": "爬取数据失败", "timestamp": time.time()})
            logger.error(f"【自动爬取】用户 {username} 爬取失败")
            return

        raw_data = result["data"]
        logger.info(f"【自动爬取】用户 {username} 数据爬取完成")

        session_store.set_sync_status(username, {"status": "syncing", "message": "正在存储数据...", "timestamp": time.time()})

        # 2. 存入 PostgreSQL
        if DB_AVAILABLE:
            db = next(get_db())
            try:
                data_processor.process_and_store(username, raw_data, db)

                # 获取 user_id 用于向量化
                user = db.query(User).filter(User.username == username).first()
                user_id = user.id if user else None
            finally:
                db.close()

            # 3. 向量化存入 Milvus
            if user_id:
                session_store.set_sync_status(username, {"status": "syncing", "message": "正在向量化数据...", "timestamp": time.time()})
                data_processor.vectorize_and_store(user_id, username, raw_data)

        session_store.set_sync_status(username, {"status": "completed", "message": "数据同步完成", "timestamp": time.time()})
        logger.info(f"【自动爬取】用户 {username} 全部完成")

    except Exception as e:
        session_store.set_sync_status(username, {"status": "failed", "message": f"同步失败: {str(e)}", "timestamp": time.time()})
        logger.error(f"【自动爬取】用户 {username} 异常: {e}")


def ensure_user_session(username: str):
    """
    获取用户的 session 和 server_url
    返回: (session, server_url) 或抛出 HTTPException
    """
    from fastapi import HTTPException

    user_data = session_store.get_user_session(username)
    if not user_data:
        logger.warning(f"【Session】用户 {username} 未登录")
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    session = user_data["session"]
    server_url = user_data["server_url"]
    logger.info(f"【Session】用户 {username} - 服务器: {server_url}")
    return session, server_url

