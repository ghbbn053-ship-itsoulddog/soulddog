"""
教务数据快照/审计辅助。
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Dict, Optional

from app.services.education_normalizer import normalize_education_payload, summarize_education_payload


SCHEMA_VERSION = "v2"


def build_sync_key(username: str, normalized_payload: Dict) -> str:
    payload = json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(f"{username}|{SCHEMA_VERSION}|{payload}".encode("utf-8")).hexdigest()
    # sync_key 需要代表一次“批次同步”，而不是仅代表内容哈希；
    # 否则内容完全相同的再次同步会撞唯一约束，导致快照无法落库。
    return f"{digest[:48]}{int(time.time() * 1000):016x}"


def build_snapshot_payload(raw_payload: Dict) -> Dict:
    normalized = normalize_education_payload(raw_payload)
    summary = summarize_education_payload(normalized)
    return {
        "schema_version": SCHEMA_VERSION,
        "normalized_payload": normalized,
        "summary": summary,
    }


def payload_is_effectively_empty(normalized_payload: Dict) -> bool:
    summary = summarize_education_payload(normalized_payload)
    has_personal = bool(normalized_payload.get("个人信息"))
    has_training = bool(normalized_payload.get("培养方案"))
    has_progress = bool(normalized_payload.get("学业进度"))
    return not (
        has_personal
        or has_training
        or has_progress
        or summary.get("成绩数量", 0) > 0
        or summary.get("课表数量", 0) > 0
        or summary.get("考试数量", 0) > 0
    )


def normalize_sync_error(message: Optional[str]) -> str:
    msg = (message or "").strip()
    return msg[:2000] if msg else "unknown sync failure"
