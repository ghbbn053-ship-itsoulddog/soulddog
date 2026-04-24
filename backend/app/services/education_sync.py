"""
教务数据同步服务（登录后后台爬取 + 手动同步）。
"""

import time

from scraper import JwxtScraper
from app.core.runtime import logger, session_store, DB_AVAILABLE, data_processor, get_db, User
from app.models import EducationSyncSnapshot
from app.services.education_audit import (
    build_snapshot_payload,
    build_sync_key,
    normalize_sync_error,
    payload_is_effectively_empty,
)


def auto_crawl_and_store(username: str, session, server_url: str):
    """
    登录成功后的后台任务：自动爬取全部教务数据并存储
    1. 爬取全部数据
    2. 存入 PostgreSQL
    3. 向量化存入 Milvus
    """
    session_store.set_sync_status(username, {"status": "syncing", "message": "正在爬取教务数据...", "timestamp": time.time()})

    db = None
    snapshot = None
    try:
        logger.info(f"【自动爬取】开始为用户 {username} 爬取数据")

        if DB_AVAILABLE:
            db = next(get_db())
            user = db.query(User).filter(User.username == username).first()
            if not user:
                user = User(username=username)
                db.add(user)
                db.commit()
                db.refresh(user)
            snapshot = EducationSyncSnapshot(
                user_id=user.id,
                username=username,
                sync_key=f"pending-{username}-{int(time.time() * 1000)}",
                sync_source="auto_login",
                status="pending",
            )
            db.add(snapshot)
            db.commit()
            db.refresh(snapshot)

        # 1. 爬取全部数据
        scraper = JwxtScraper(session, server_url)
        result = scraper.get_all_data_for_vectorization()

        if not result.get("success"):
            if db and snapshot:
                snapshot.status = "failed"
                snapshot.error_message = normalize_sync_error(result.get("message"))
                db.commit()
            session_store.set_sync_status(username, {"status": "failed", "message": "爬取数据失败", "timestamp": time.time()})
            logger.error(f"【自动爬取】用户 {username} 爬取失败")
            return

        raw_data = result["data"]
        snapshot_payload = build_snapshot_payload(raw_data)
        normalized_payload = snapshot_payload["normalized_payload"]
        summary = snapshot_payload["summary"]
        sync_key = build_sync_key(username, normalized_payload)

        if payload_is_effectively_empty(normalized_payload):
            if db and snapshot:
                snapshot.sync_key = sync_key
                snapshot.raw_payload = raw_data
                snapshot.normalized_payload = normalized_payload
                snapshot.summary = summary
                snapshot.status = "failed"
                snapshot.crawl_success = False
                snapshot.error_message = "normalized payload is empty"
                db.commit()
            session_store.set_sync_status(username, {"status": "failed", "message": "爬取结果为空", "timestamp": time.time()})
            logger.error(f"【自动爬取】用户 {username} 结果为空")
            return

        if db and snapshot:
            snapshot.sync_key = sync_key
            snapshot.raw_payload = raw_data
            snapshot.normalized_payload = normalized_payload
            snapshot.summary = summary
            snapshot.crawl_success = True
            db.commit()

        logger.info(f"【自动爬取】用户 {username} 数据爬取完成")

        session_store.set_sync_status(username, {"status": "syncing", "message": "正在存储数据...", "timestamp": time.time()})

        # 2. 存入 PostgreSQL
        if DB_AVAILABLE:
            if not db:
                db = next(get_db())

            store_ok = data_processor.process_and_store(username, raw_data, db)
            if not store_ok:
                if snapshot:
                    snapshot.status = "failed"
                    snapshot.store_success = False
                    snapshot.error_message = "process_and_store failed"
                    db.commit()
                session_store.set_sync_status(username, {"status": "failed", "message": "结构化存储失败", "timestamp": time.time()})
                logger.error(f"【自动爬取】用户 {username} 存储失败")
                return

            # 获取 user_id 用于向量化
            user = db.query(User).filter(User.username == username).first()
            user_id = user.id if user else None
            if snapshot:
                snapshot.user_id = user_id or snapshot.user_id
                snapshot.store_success = True
                db.commit()

            # 3. 向量化存入 Milvus
            if user_id:
                session_store.set_sync_status(username, {"status": "syncing", "message": "正在向量化数据...", "timestamp": time.time()})
                vector_ok = data_processor.vectorize_and_store(
                    user_id,
                    username,
                    raw_data,
                    sync_key=sync_key,
                    schema_version=snapshot.schema_version if snapshot else None,
                )
                if snapshot:
                    snapshot.vector_success = bool(vector_ok)
                    snapshot.status = "success" if vector_ok else "failed"
                    snapshot.error_message = None if vector_ok else "vectorize_and_store failed"
                    if vector_ok:
                        db.query(EducationSyncSnapshot).filter(
                            EducationSyncSnapshot.username == username,
                            EducationSyncSnapshot.id != snapshot.id,
                        ).update({"is_active": False}, synchronize_session=False)
                        snapshot.is_active = True
                    db.commit()
                if not vector_ok:
                    session_store.set_sync_status(username, {"status": "failed", "message": "向量化失败", "timestamp": time.time()})
                    logger.error(f"【自动爬取】用户 {username} 向量化失败")
                    return
            else:
                if snapshot:
                    snapshot.status = "failed"
                    snapshot.error_message = "user_id not found after store"
                    db.commit()
                session_store.set_sync_status(username, {"status": "failed", "message": "用户标识异常", "timestamp": time.time()})
                logger.error(f"【自动爬取】用户 {username} 未找到 user_id")
                return

        session_store.set_sync_status(username, {"status": "completed", "message": "数据同步完成", "timestamp": time.time()})
        logger.info(f"【自动爬取】用户 {username} 全部完成")

    except Exception as e:
        if db and snapshot:
            snapshot.status = "failed"
            snapshot.error_message = normalize_sync_error(str(e))
            db.commit()
        session_store.set_sync_status(username, {"status": "failed", "message": f"同步失败: {str(e)}", "timestamp": time.time()})
        logger.error(f"【自动爬取】用户 {username} 异常: {e}")
    finally:
        if db:
            db.close()


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
