"""
教务缓存读取服务
职责：
1. 从 PostgreSQL EducationData 读取缓存化教务数据
2. 从 EducationSyncSnapshot / SessionStore 读取新鲜度与刷新状态
3. 提供 cache-first API 统一口径
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.runtime import session_store
from app.models import EducationData, EducationSyncSnapshot, User
from app.services.education_normalizer import build_payload_from_education_data_record


@dataclass
class EducationCacheBundle:
    user: User
    education_data: Optional[EducationData]
    snapshot: Optional[EducationSyncSnapshot]


class EducationCacheService:
    FRESH_DAYS = 7
    STALE_DAYS = 14

    def get_bundle(self, db: Session, username: str) -> Optional[EducationCacheBundle]:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None

        education_data = db.query(EducationData).filter(EducationData.user_id == user.id).first()
        snapshot = (
            db.query(EducationSyncSnapshot)
            .filter(
                EducationSyncSnapshot.user_id == user.id,
                EducationSyncSnapshot.status == "success",
                EducationSyncSnapshot.is_active == True,
            )
            .order_by(EducationSyncSnapshot.created_at.desc())
            .first()
        )
        return EducationCacheBundle(user=user, education_data=education_data, snapshot=snapshot)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _as_utc(self, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def get_cached_at(self, bundle: EducationCacheBundle) -> Optional[datetime]:
        if bundle.education_data and bundle.education_data.last_updated:
            return self._as_utc(bundle.education_data.last_updated)
        if bundle.snapshot and bundle.snapshot.created_at:
            return self._as_utc(bundle.snapshot.created_at)
        return None

    def get_freshness(self, cached_at: Optional[datetime]) -> str:
        if not cached_at:
            return "none"
        delta_days = max(0.0, (self._now() - cached_at).total_seconds() / 86400)
        if delta_days < self.FRESH_DAYS:
            return "fresh"
        if delta_days < self.STALE_DAYS:
            return "stale"
        return "outdated"

    def build_status(self, bundle: Optional[EducationCacheBundle], username: str) -> Dict[str, Any]:
        sync_status = session_store.get_sync_status(username) or {}
        cached_at = self.get_cached_at(bundle) if bundle else None
        freshness = self.get_freshness(cached_at)

        active_snapshot = bundle.snapshot if bundle else None
        has_cache = bool(bundle and bundle.education_data)

        return {
            "success": has_cache,
            "has_cache": has_cache,
            "freshness": freshness,
            "cached_at": cached_at.isoformat() if cached_at else None,
            "sync": sync_status or {"status": "none", "message": "未开始同步"},
            "snapshot": {
                "sync_key": active_snapshot.sync_key if active_snapshot else None,
                "status": active_snapshot.status if active_snapshot else None,
                "schema_version": active_snapshot.schema_version if active_snapshot else None,
                "summary": active_snapshot.summary if active_snapshot else {},
                "created_at": active_snapshot.created_at.isoformat() if active_snapshot and active_snapshot.created_at else None,
            },
        }

    def build_payload(self, bundle: EducationCacheBundle) -> Dict[str, Any]:
        if not bundle.education_data:
            return {}

        normalized = build_payload_from_education_data_record(bundle.education_data)
        return {
            "个人信息": normalized.get("个人信息", {}),
            "成绩信息": normalized.get("成绩信息", {}),
            "课表信息": normalized.get("课表信息", {}),
            "培养方案": normalized.get("培养方案", {}),
            "学业进度": normalized.get("学业进度", {}),
            "考试安排": normalized.get("考试安排", {}),
            "执行计划": bundle.education_data.execution_plan or {},
            "选课信息": normalized.get("选课信息", bundle.education_data.course_selection or {}),
        }

    def response_for_key(self, bundle: Optional[EducationCacheBundle], username: str, key: str) -> Dict[str, Any]:
        status = self.build_status(bundle, username)
        if not bundle or not bundle.education_data:
            return {
                "success": False,
                "error": "no_cached_data",
                "message": "暂无缓存数据，请先登录同步",
                "freshness": status["freshness"],
                "cached_at": status["cached_at"],
                "status": status,
            }

        payload = self.build_payload(bundle)
        data = payload.get(key)
        if data is None:
            data = {} if key in {"个人信息", "培养方案", "学业进度", "执行计划", "选课信息"} else []

        return {
            "success": True,
            "data": data,
            "freshness": status["freshness"],
            "cached_at": status["cached_at"],
            "status": status,
        }


education_cache_service = EducationCacheService()


def get_education_cache_service() -> EducationCacheService:
    return education_cache_service
