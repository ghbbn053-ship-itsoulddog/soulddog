"""
Skill 管理器（YAML 声明式）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import time
import yaml
import requests
from urllib.parse import urlparse


REQUIRED_FIELDS = {"name", "version", "description", "tools"}
ALLOWED_IMPORT_HOSTS = {"raw.githubusercontent.com", "github.com"}
MAX_SKILL_BYTES = 256 * 1024


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
        input_schema = config.get("input_schema")
        if input_schema is not None:
            if not isinstance(input_schema, dict):
                raise ValueError("input_schema 必须是对象")
            schema_type = str(input_schema.get("type", "")).strip().lower()
            if schema_type and schema_type != "object":
                raise ValueError("input_schema.type 当前仅支持 object")
            props = input_schema.get("properties", {})
            if props is not None and not isinstance(props, dict):
                raise ValueError("input_schema.properties 必须是对象")
            required = input_schema.get("required", [])
            if required is not None and not isinstance(required, list):
                raise ValueError("input_schema.required 必须是数组")
        for tool in config["tools"]:
            if not isinstance(tool, dict) or "name" not in tool:
                raise ValueError("每个 tool 必须是对象且包含 name")

    def upload_skill(self, owner: str, yaml_content: str) -> Dict[str, Any]:
        config = self._parse_and_validate(yaml_content)
        self._validate(config)
        config.setdefault("enabled", True)
        config.setdefault("created_at", int(time.time()))
        config["updated_at"] = int(time.time())

        skill_name = str(config["name"]).strip()
        target = self._owner_dir(owner) / f"{skill_name}.yaml"
        target.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return {"owner": owner, "name": skill_name, "path": str(target)}

    def _parse_and_validate(self, yaml_content: str) -> Dict[str, Any]:
        if not (yaml_content or "").strip():
            raise ValueError("YAML 内容不能为空")
        try:
            config = yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 格式错误: {e}")
        if not isinstance(config, dict):
            raise ValueError("YAML 根节点必须是对象")
        self._validate(config)
        return config

    def validate_skill_yaml(self, yaml_content: str) -> Dict[str, Any]:
        config = self._parse_and_validate(yaml_content)
        return {
            "name": str(config.get("name", "")).strip(),
            "version": str(config.get("version", "")).strip(),
            "description": str(config.get("description", "")).strip(),
            "tools_count": len(config.get("tools", [])),
            "triggers": config.get("triggers", []),
            "input_schema": config.get("input_schema") or {},
        }

    @staticmethod
    def _normalize_raw_url(url: str) -> str:
        """
        支持常见 GitHub 链接自动转 raw。
        - https://github.com/<org>/<repo>/blob/<branch>/path/to/file.yaml
        -> https://raw.githubusercontent.com/<org>/<repo>/<branch>/path/to/file.yaml
        """
        u = (url or "").strip()
        if "raw.githubusercontent.com" in u:
            return u
        if "github.com" in u and "/blob/" in u:
            parts = u.split("github.com/", 1)[1].split("/")
            if len(parts) >= 5 and parts[2] == "blob":
                org, repo, _blob, branch = parts[:4]
                tail = "/".join(parts[4:])
                return f"https://raw.githubusercontent.com/{org}/{repo}/{branch}/{tail}"
        return u

    def import_skill_from_url(self, owner: str, url: str, timeout: int = 12) -> Dict[str, Any]:
        raw_url = self._normalize_raw_url(url)
        if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            raise ValueError("仅支持 http/https URL")
        parsed = urlparse(raw_url)
        if (parsed.hostname or "").lower() not in ALLOWED_IMPORT_HOSTS:
            raise ValueError("仅允许从 GitHub 官方域名导入")

        resp = requests.get(
            raw_url,
            timeout=timeout,
            headers={"User-Agent": "campus-ai-skill-importer/1.0"},
        )
        if resp.status_code != 200:
            raise ValueError(f"下载 Skill 失败: HTTP {resp.status_code}")

        content_length = resp.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > MAX_SKILL_BYTES:
                    raise ValueError("Skill 文件过大（超过 256KB）")
            except ValueError:
                raise
            except Exception:
                pass

        content = resp.text or ""
        if len(content.encode("utf-8")) > MAX_SKILL_BYTES:
            raise ValueError("Skill 文件过大（超过 256KB）")
        if not content.strip():
            raise ValueError("Skill 内容为空")
        return self.upload_skill(owner, content)

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
                        "input_schema": config.get("input_schema", {}) or {},
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
