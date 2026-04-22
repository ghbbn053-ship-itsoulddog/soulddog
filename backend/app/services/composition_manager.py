"""
Composition 管理器（Openclaw 风格）：
按 owner 维护 skill + mcp 的可组合配置。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from app.services.skill_manager import get_skill_manager


class CompositionManager:
    def __init__(self, base_dir: str = "backend/data/composition"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _owner_file(self, owner: str) -> Path:
        safe = (owner or "system").strip() or "system"
        return self.base_dir / f"{safe}.json"

    @staticmethod
    def _default_profile() -> Dict[str, Any]:
        return {
            "skills": {"entries": {}},
            "mcp": {"entries": {}, "order": []},
            "updated_at": int(time.time()),
        }

    def get_profile(self, owner: str) -> Dict[str, Any]:
        f = self._owner_file(owner)
        if not f.exists():
            return self._default_profile()
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return self._default_profile()

    def save_profile(self, owner: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        f = self._owner_file(owner)
        profile = profile or {}
        profile.setdefault("skills", {"entries": {}})
        profile.setdefault("mcp", {"entries": {}, "order": []})
        profile["updated_at"] = int(time.time())
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        return profile

    def set_skill_enabled(self, owner: str, skill_name: str, enabled: bool, priority: int = 50) -> Dict[str, Any]:
        p = self.get_profile(owner)
        skills = p.setdefault("skills", {}).setdefault("entries", {})
        item = skills.get(skill_name) or {}
        item["enabled"] = bool(enabled)
        item["priority"] = int(priority)
        skills[skill_name] = item
        return self.save_profile(owner, p)

    def set_mcp_enabled(self, owner: str, tool_name: str, enabled: bool, weight: int = 50) -> Dict[str, Any]:
        p = self.get_profile(owner)
        mcp = p.setdefault("mcp", {})
        entries = mcp.setdefault("entries", {})
        item = entries.get(tool_name) or {}
        item["enabled"] = bool(enabled)
        item["weight"] = int(weight)
        entries[tool_name] = item
        order = mcp.setdefault("order", [])
        if tool_name not in order:
            order.append(tool_name)
        return self.save_profile(owner, p)

    def reorder_mcp(self, owner: str, order: List[str]) -> Dict[str, Any]:
        p = self.get_profile(owner)
        mcp = p.setdefault("mcp", {})
        mcp["order"] = [str(x).strip() for x in (order or []) if str(x).strip()]
        return self.save_profile(owner, p)

    def is_mcp_tool_enabled(self, owner: str, tool_name: str) -> bool:
        p = self.get_profile(owner)
        item = ((p.get("mcp") or {}).get("entries") or {}).get(tool_name)
        if item is None:
            return True
        return bool(item.get("enabled", True))

    def filter_skill_names(self, owner: str, names: List[str]) -> List[str]:
        p = self.get_profile(owner)
        entries = ((p.get("skills") or {}).get("entries") or {})
        out = []
        for n in names:
            conf = entries.get(n)
            if conf is None or bool(conf.get("enabled", True)):
                out.append(n)
        return out

    def sorted_mcp_tools(self, owner: str, tool_names: List[str]) -> List[str]:
        p = self.get_profile(owner)
        mcp = p.get("mcp") or {}
        entries = mcp.get("entries") or {}
        order = mcp.get("order") or []
        allowed = [n for n in tool_names if self.is_mcp_tool_enabled(owner, n)]
        order_idx = {name: i for i, name in enumerate(order)}

        def _key(name: str):
            cfg = entries.get(name) or {}
            weight = int(cfg.get("weight", 50))
            idx = order_idx.get(name, 10_000)
            return (-weight, idx, name)

        allowed.sort(key=_key)
        return allowed

    def resolved(self, owner: str) -> Dict[str, Any]:
        from app.services.mcp_registry import get_mcp_registry

        skills = get_skill_manager().list_skills(owner)
        skill_names = [str(s.get("name", "")).strip() for s in skills if str(s.get("name", "")).strip()]
        filtered_skills = self.filter_skill_names(owner, skill_names)

        mcp_tools = get_mcp_registry().list_tools()
        mcp_names = [str(t.get("name", "")).strip() for t in mcp_tools if str(t.get("name", "")).strip()]
        sorted_mcp = self.sorted_mcp_tools(owner, mcp_names)

        return {
            "owner": owner,
            "skills": filtered_skills,
            "all_skills": skill_names,
            "mcp_tools": sorted_mcp,
            "all_mcp_tools": mcp_names,
            "profile": self.get_profile(owner),
        }


_composition_manager_singleton: CompositionManager | None = None


def get_composition_manager() -> CompositionManager:
    global _composition_manager_singleton
    if _composition_manager_singleton is None:
        _composition_manager_singleton = CompositionManager()
    return _composition_manager_singleton
