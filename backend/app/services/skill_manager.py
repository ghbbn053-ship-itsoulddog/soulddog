"""
Skill 管理器（YAML 声明式）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import time
import yaml


REQUIRED_FIELDS = {"name", "version", "description", "tools"}


@dataclass
class SkillRecord:
    owner: str
    file_path: Path
    config: Dict[str, Any]


class SkillManager:
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def _owner_dir(self, owner: str) -> Path:
        d = self.skills_dir / owner
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _validate(self, config: Dict[str, Any]):
        missing = [f for f in REQUIRED_FIELDS if f not in config]
        if missing:
            raise ValueError(f"Skill 缺少必填字段: {', '.join(missing)}")
        if not isinstance(config.get("tools"), list) or not config["tools"]:
            raise ValueError("tools 必须为非空数组")
        if not isinstance(config.get("name"), str) or not config["name"].strip():
            raise ValueError("name 必须为非空字符串")
        for tool in config["tools"]:
            if not isinstance(tool, dict) or "name" not in tool:
                raise ValueError("每个 tool 必须是对象且包含 name")

    def upload_skill(self, owner: str, yaml_content: str) -> Dict[str, Any]:
        config = yaml.safe_load(yaml_content) or {}
        self._validate(config)
        config.setdefault("enabled", True)
        config.setdefault("created_at", int(time.time()))
        config["updated_at"] = int(time.time())

        skill_name = str(config["name"]).strip()
        target = self._owner_dir(owner) / f"{skill_name}.yaml"
        target.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return {"owner": owner, "name": skill_name, "path": str(target)}

    def list_skills(self, owner: str) -> List[Dict[str, Any]]:
        owner_dir = self._owner_dir(owner)
        result: List[Dict[str, Any]] = []
        for f in owner_dir.glob("*.yaml"):
            try:
                config = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                result.append(
                    {
                        "name": config.get("name", f.stem),
                        "version": config.get("version", ""),
                        "description": config.get("description", ""),
                        "enabled": bool(config.get("enabled", True)),
                        "triggers": config.get("triggers", []),
                        "tools": config.get("tools", []),
                        "updated_at": config.get("updated_at"),
                    }
                )
            except Exception:
                continue
        result.sort(key=lambda x: x.get("name", ""))
        return result

    def set_enabled(self, owner: str, skill_name: str, enabled: bool) -> Dict[str, Any]:
        f = self._owner_dir(owner) / f"{skill_name}.yaml"
        if not f.exists():
            raise FileNotFoundError("skill 不存在")
        config = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        config["enabled"] = bool(enabled)
        config["updated_at"] = int(time.time())
        f.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return {"name": skill_name, "enabled": bool(enabled)}

    def delete_skill(self, owner: str, skill_name: str) -> bool:
        f = self._owner_dir(owner) / f"{skill_name}.yaml"
        if not f.exists():
            return False
        f.unlink()
        return True

    def get_skill(self, owner: str, skill_name: str) -> Optional[Dict[str, Any]]:
        f = self._owner_dir(owner) / f"{skill_name}.yaml"
        if not f.exists():
            return None
        return yaml.safe_load(f.read_text(encoding="utf-8")) or {}


_skill_manager_singleton: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    global _skill_manager_singleton
    if _skill_manager_singleton is None:
        _skill_manager_singleton = SkillManager()
    return _skill_manager_singleton

