"""
会话存储服务
Redis 可用时使用 Redis 持久化；不可用时回退到内存。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

import requests

try:
    import redis
except Exception:  # pragma: no cover
    redis = None


logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self):
        self.redis_available = False
        self._redis = None

        # 内存兜底
        self._user_sessions: Dict[str, Dict[str, Any]] = {}
        self._captcha_sessions: Dict[str, Dict[str, Any]] = {}
        self._sync_status: Dict[str, Dict[str, Any]] = {}
        self._auth_sessions: Dict[str, Dict[str, Any]] = {}
        self._model_preferences: Dict[str, Dict[str, Any]] = {}
        self._workspace_preferences: Dict[str, Dict[str, Any]] = {}

        self._connect_redis()

    def _connect_redis(self):
        if redis is None:
            logger.warning("⚠️ redis 包不可用，使用内存会话存储")
            return
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        try:
            self._redis = redis.Redis(host=host, port=port, decode_responses=True)
            self._redis.ping()
            self.redis_available = True
            logger.info(f"✅ SessionStore 使用 Redis: {host}:{port}")
        except Exception as e:
            self.redis_available = False
            self._redis = None
            logger.warning(f"⚠️ Redis 不可用，回退内存会话存储: {e}")

    @staticmethod
    def _serialize_session(session: requests.Session) -> Dict[str, Any]:
        return {
            "cookies": requests.utils.dict_from_cookiejar(session.cookies),
            "headers": dict(session.headers),
        }

    @staticmethod
    def _deserialize_session(payload: Dict[str, Any]) -> requests.Session:
        s = requests.Session()
        headers = payload.get("headers", {})
        if isinstance(headers, dict):
            s.headers.update(headers)
        cookies = payload.get("cookies", {})
        if isinstance(cookies, dict):
            s.cookies = requests.utils.cookiejar_from_dict(cookies)
        return s

    def _redis_set_json(self, key: str, value: Dict[str, Any], ttl: int):
        if not self.redis_available:
            return
        self._redis.setex(key, ttl, json.dumps(value, ensure_ascii=False))

    def _redis_get_json(self, key: str) -> Optional[Dict[str, Any]]:
        if not self.redis_available:
            return None
        raw = self._redis.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def _redis_del(self, key: str):
        if self.redis_available:
            self._redis.delete(key)

    # ===== Captcha Session =====
    def set_captcha_session(self, captcha_session_id: str, session: requests.Session, ttl: int = 300):
        payload = {
            "session": self._serialize_session(session),
            "created_at": time.time(),
        }
        if self.redis_available:
            self._redis_set_json(f"captcha:{captcha_session_id}", payload, ttl)
        else:
            self._captcha_sessions[captcha_session_id] = payload

    def pop_captcha_session(self, captcha_session_id: str) -> Optional[requests.Session]:
        if self.redis_available:
            key = f"captcha:{captcha_session_id}"
            payload = self._redis_get_json(key)
            self._redis_del(key)
            if not payload:
                return None
            return self._deserialize_session(payload.get("session", {}))

        payload = self._captcha_sessions.pop(captcha_session_id, None)
        if not payload:
            return None
        return self._deserialize_session(payload.get("session", {}))

    def list_captcha_ids(self):
        if self.redis_available:
            keys = self._redis.keys("captcha:*")
            return [k.split("captcha:", 1)[1] for k in keys]
        return list(self._captcha_sessions.keys())

    # ===== User Session =====
    def set_user_session(self, username: str, session: requests.Session, server_url: str, ttl: int = 24 * 3600):
        payload = {
            "server_url": server_url,
            "session": self._serialize_session(session),
            "updated_at": time.time(),
        }
        if self.redis_available:
            self._redis_set_json(f"user_session:{username}", payload, ttl)
        else:
            self._user_sessions[username] = payload

    def get_user_session(self, username: str) -> Optional[Dict[str, Any]]:
        if self.redis_available:
            payload = self._redis_get_json(f"user_session:{username}")
            if not payload:
                return None
            return {
                "server_url": payload.get("server_url", ""),
                "session": self._deserialize_session(payload.get("session", {})),
            }

        payload = self._user_sessions.get(username)
        if not payload:
            return None
        return {
            "server_url": payload.get("server_url", ""),
            "session": self._deserialize_session(payload.get("session", {})),
        }

    def list_usernames(self):
        if self.redis_available:
            keys = self._redis.keys("user_session:*")
            return [k.split("user_session:", 1)[1] for k in keys]
        return list(self._user_sessions.keys())

    # ===== Sync Status =====
    def set_sync_status(self, username: str, status: Dict[str, Any], ttl: int = 6 * 3600):
        if self.redis_available:
            self._redis_set_json(f"sync_status:{username}", status, ttl)
        else:
            self._sync_status[username] = status

    def get_sync_status(self, username: str) -> Optional[Dict[str, Any]]:
        if self.redis_available:
            return self._redis_get_json(f"sync_status:{username}")
        return self._sync_status.get(username)

    # ===== Auth Session =====
    def set_auth_session(self, auth_session_id: str, username: str, user_id: Optional[int] = None, ttl: int = 24 * 3600):
        payload = {
            "username": username,
            "user_id": user_id,
            "updated_at": time.time(),
        }
        if self.redis_available:
            self._redis_set_json(f"auth_session:{auth_session_id}", payload, ttl)
        else:
            self._auth_sessions[auth_session_id] = payload

    def get_auth_session(self, auth_session_id: str) -> Optional[Dict[str, Any]]:
        if self.redis_available:
            return self._redis_get_json(f"auth_session:{auth_session_id}")
        return self._auth_sessions.get(auth_session_id)

    def delete_auth_session(self, auth_session_id: str):
        if self.redis_available:
            self._redis_del(f"auth_session:{auth_session_id}")
            return
        self._auth_sessions.pop(auth_session_id, None)

    # ===== Model Preferences =====
    def set_user_model_preference(self, username: str, preference: Dict[str, Any], ttl: int = 30 * 24 * 3600):
        old = self.get_user_model_preference(username) or {}
        api_key = preference.get("api_key")
        # 传 null/未传 => 保留旧值；传空字符串 => 清空
        if api_key is None:
            api_key = old.get("api_key", "")
        payload = {
            "provider": preference.get("provider", "qwen"),
            "model": preference.get("model", ""),
            "api_base": preference.get("api_base", old.get("api_base", "")),
            "api_key": api_key,
            "reasoning_mode": preference.get("reasoning_mode", old.get("reasoning_mode", "standard")),
            "show_thinking": bool(preference.get("show_thinking", old.get("show_thinking", False))),
            "updated_at": time.time(),
        }
        if self.redis_available:
            self._redis_set_json(f"model_pref:{username}", payload, ttl)
        else:
            self._model_preferences[username] = payload

    def get_user_model_preference(self, username: str) -> Optional[Dict[str, Any]]:
        if self.redis_available:
            return self._redis_get_json(f"model_pref:{username}")
        return self._model_preferences.get(username)

    # ===== Workspace Preferences =====
    def set_user_workspace_preference(self, username: str, preference: Dict[str, Any], ttl: int = 30 * 24 * 3600):
        payload = {
            "workspace_id": preference.get("workspace_id"),
            "workspace_name": preference.get("workspace_name", ""),
            "updated_at": time.time(),
        }
        if self.redis_available:
            self._redis_set_json(f"workspace_pref:{username}", payload, ttl)
        else:
            self._workspace_preferences[username] = payload

    def get_user_workspace_preference(self, username: str) -> Optional[Dict[str, Any]]:
        if self.redis_available:
            return self._redis_get_json(f"workspace_pref:{username}")
        return self._workspace_preferences.get(username)


_session_store_singleton: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """
    返回进程级 SessionStore 单例。
    用于避免 main/mcp/chat 之间互相导入导致的循环依赖。
    """
    global _session_store_singleton
    if _session_store_singleton is None:
        _session_store_singleton = SessionStore()
    return _session_store_singleton
