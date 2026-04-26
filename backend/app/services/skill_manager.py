"""
Skill 管理器（YAML 声明式）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import re
import time
import yaml
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse


REQUIRED_FIELDS = {"name", "version", "description", "tools"}
ALLOWED_IMPORT_HOSTS = {"raw.githubusercontent.com", "github.com"}
MAX_SKILL_BYTES = 256 * 1024
DEFAULT_IMPORT_TIMEOUT = 20
COMMON_SKILL_MANIFESTS = (
    "skill.yaml",
    "skill.yml",
    "skills.yaml",
    "skills.yml",
    "manifest.yaml",
    "manifest.yml",
)
COMMON_SKILL_GUIDES = (
    "SKILL.md",
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "docs/SKILL.md",
    "docs/README.md",
    "prompts/SKILL.md",
)
GUIDE_PROMPT_LIMIT = 12_000
KNOWN_SKILL_TOOL_CAPABILITIES = {
    "query_schedule": "schedule.query",
    "query_grades": "grade.query",
    "query_exam_schedule": "exam.query",
    "query_training_plan": "training_plan.query",
    "query_academic_progress": "academic_progress.query",
    "query_personal_info": "personal_info.query",
    "query_weather": "weather.query",
}
KEYWORD_CAPABILITY_HINTS = {
    "weather.query": ["weather", "forecast", "temperature", "rain", "wttr", "天气", "气温", "降雨", "预报"],
}


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
        if not isinstance(config.get("tools"), list):
            raise ValueError("tools 必须是数组")
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

    @staticmethod
    def _save_skill_config(target: Path, config: Dict[str, Any]) -> None:
        target.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    @staticmethod
    def _sanitize_skill_name(name: str) -> str:
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(name or "").strip()).strip("-_.")
        return safe_name or "imported-skill"

    def upload_skill(self, owner: str, yaml_content: str) -> Dict[str, Any]:
        config = self._parse_and_validate(yaml_content)
        self._validate(config)
        config.setdefault("enabled", True)
        config.setdefault("source_type", "yaml")
        config.setdefault("source_ref", "")
        config.setdefault("created_at", int(time.time()))
        config["updated_at"] = int(time.time())
        config = self._apply_skill_metadata(config)

        skill_name = str(config["name"]).strip()
        target = self._owner_dir(owner) / f"{skill_name}.yaml"
        self._save_skill_config(target, config)
        return {
            "owner": owner,
            "name": skill_name,
            "path": str(target),
            "mode": config.get("mode", "rule"),
            "compatibility_level": config.get("compatibility_level", "direct"),
            "compatibility_notes": config.get("compatibility_notes", []) or [],
            "capabilities": config.get("capabilities", []) or [],
        }

    def import_skill_from_text(
        self,
        owner: str,
        content: str,
        source_type: str,
        source_ref: str,
        file_name: str = "",
    ) -> Dict[str, Any]:
        text = (content or "").strip()
        if not text:
            raise ValueError("Skill 内容不能为空")

        lower_name = str(file_name or source_ref or "").strip().lower()
        if lower_name.endswith((".md", ".txt")):
            return self._save_repo_doc_skill_from_text(owner, source_ref or file_name or "uploaded-skill", text, file_name=file_name)

        try:
            saved = self.upload_skill(owner, text)
            skill = self.get_skill(owner, saved["name"]) or {}
            skill["source_type"] = source_type
            skill["source_ref"] = source_ref
            target = self._owner_dir(owner) / f"{saved['name']}.yaml"
            self._save_skill_config(target, skill)
            saved["source_type"] = source_type
            saved["source_ref"] = source_ref
            return saved
        except ValueError:
            if lower_name.endswith((".md", ".txt")):
                return self._save_repo_doc_skill_from_text(owner, source_ref or file_name or "uploaded-skill", text, file_name=file_name)
            raise

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

    @staticmethod
    def _infer_capabilities(config: Dict[str, Any]) -> List[str]:
        capabilities = []
        tools = config.get("tools") or []
        declared = config.get("capabilities")
        if isinstance(declared, list):
            for item in declared:
                text = str(item or "").strip()
                if text:
                    capabilities.append(text)
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            name = str(tool.get("name", "")).strip()
            if name in KNOWN_SKILL_TOOL_CAPABILITIES:
                capabilities.append(KNOWN_SKILL_TOOL_CAPABILITIES[name])

        capability_source = " ".join(
            [
                str(config.get("name", "") or ""),
                str(config.get("description", "") or ""),
                str(config.get("prompt", "") or "")[:2400],
                str(config.get("source_ref", "") or ""),
            ]
        ).lower()
        for capability, keywords in KEYWORD_CAPABILITY_HINTS.items():
            if any(keyword in capability_source for keyword in keywords):
                capabilities.append(capability)
        return list(dict.fromkeys(capabilities))

    def _apply_skill_metadata(self, config: Dict[str, Any]) -> Dict[str, Any]:
        classified = self._classify_skill_config(config)
        normalized = dict(config)
        normalized["mode"] = classified["mode"]
        normalized["compatibility_level"] = classified["compatibility_level"]
        normalized["compatibility_notes"] = classified["compatibility_notes"]
        normalized["capabilities"] = classified["capabilities"]
        return normalized

    def _classify_skill_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        source_type = str(config.get("source_type", "yaml")).strip() or "yaml"
        triggers = [str(item).strip() for item in (config.get("triggers") or []) if str(item).strip()]
        prompt = str(config.get("prompt", "") or "").strip()
        always_on = bool(config.get("always_on", False))
        tools = [item for item in (config.get("tools") or []) if isinstance(item, dict)]
        tool_names = [str(item.get("name", "")).strip() for item in tools if str(item.get("name", "")).strip()]
        capabilities = self._infer_capabilities(config)
        known_tools = [name for name in tool_names if name in KNOWN_SKILL_TOOL_CAPABILITIES]
        unknown_tools = [name for name in tool_names if name not in KNOWN_SKILL_TOOL_CAPABILITIES]
        notes: List[str] = []

        if source_type == "repo_doc":
            notes.append("仓库文档型 Skill，仅做规则/提示词注入，不直接调用工具")
            if always_on:
                notes.append("当前为 always_on，会持续参与系统提示词构建")
            if capabilities:
                notes.append(f"已从文档语义中识别能力标签: {', '.join(capabilities[:4])}")
                notes.append("如果平台存在同名 capability 的真实工具，可与该规则型 Skill 协同使用")
            return {
                "mode": "rule",
                "compatibility_level": "rule_only",
                "compatibility_notes": notes,
                "capabilities": capabilities,
            }

        if not tool_names:
            if triggers:
                notes.append(f"未声明工具，依赖触发词生效: {', '.join(triggers[:4])}")
            if prompt or always_on:
                notes.append("存在规则内容，可作为轻量规则型 Skill 使用")
            if notes:
                if capabilities:
                    notes.append(f"已识别能力标签: {', '.join(capabilities[:4])}")
                return {
                    "mode": "rule",
                    "compatibility_level": "rule_only",
                    "compatibility_notes": notes,
                    "capabilities": capabilities,
                }
            return {
                "mode": "rule",
                "compatibility_level": "incompatible",
                "compatibility_notes": ["既没有工具，也没有可注入规则或触发条件，当前运行时无法发挥作用"],
                "capabilities": [],
            }

        if capabilities:
            notes.append(f"已识别 {len(capabilities)} 个平台能力: {', '.join(capabilities[:4])}")
        if known_tools:
            notes.append(f"可直接识别的工具: {', '.join(known_tools[:4])}")
        if unknown_tools:
            notes.append(f"未映射到当前平台能力的工具: {', '.join(unknown_tools[:4])}")

        if unknown_tools:
            notes.append("结构可导入，但要想真正执行这些工具，需要补 tool name -> capability/runtime 映射")
            return {
                "mode": "tool",
                "compatibility_level": "adapted",
                "compatibility_notes": notes,
                "capabilities": capabilities,
            }

        return {
            "mode": "tool",
            "compatibility_level": "direct",
            "compatibility_notes": notes or ["工具名与当前运行时映射兼容，可直接进入编排和调用链路"],
            "capabilities": capabilities,
        }

    def validate_skill_yaml(self, yaml_content: str) -> Dict[str, Any]:
        config = self._parse_and_validate(yaml_content)
        config = self._apply_skill_metadata(config)
        return {
            "name": str(config.get("name", "")).strip(),
            "version": str(config.get("version", "")).strip(),
            "description": str(config.get("description", "")).strip(),
            "tools_count": len(config.get("tools", [])),
            "triggers": config.get("triggers", []),
            "input_schema": config.get("input_schema") or {},
            "mode": config.get("mode", "rule"),
            "compatibility_level": config.get("compatibility_level", "direct"),
            "compatibility_notes": config.get("compatibility_notes", []) or [],
            "capabilities": config.get("capabilities", []) or [],
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

    @staticmethod
    def _github_repo_candidates(url: str) -> List[str]:
        u = (url or "").strip().rstrip("/")
        if "github.com/" not in u:
            return []
        if "/blob/" in u or "raw.githubusercontent.com" in u:
            return []
        parts = u.split("github.com/", 1)[1].split("/")
        if len(parts) < 2:
            return []
        org, repo = parts[0], parts[1].removesuffix(".git")
        branches = ["main", "master"]
        candidates: List[str] = []
        for branch in branches:
            for manifest in COMMON_SKILL_MANIFESTS:
                candidates.append(f"https://raw.githubusercontent.com/{org}/{repo}/{branch}/{manifest}")
                candidates.append(f"https://raw.githubusercontent.com/{org}/{repo}/{branch}/skills/{manifest}")
                candidates.append(f"https://raw.githubusercontent.com/{org}/{repo}/{branch}/manifests/{manifest}")
        return candidates

    @staticmethod
    def _github_repo_guide_candidates(url: str) -> List[str]:
        u = (url or "").strip().rstrip("/")
        if "github.com/" not in u:
            return []
        if "/blob/" in u or "raw.githubusercontent.com" in u:
            return []
        parts = u.split("github.com/", 1)[1].split("/")
        if len(parts) < 2:
            return []
        org, repo = parts[0], parts[1].removesuffix(".git")
        branches = ["main", "master"]
        candidates: List[str] = []
        for branch in branches:
            for filename in COMMON_SKILL_GUIDES:
                candidates.append(f"https://raw.githubusercontent.com/{org}/{repo}/{branch}/{filename}")
        return candidates

    @staticmethod
    def _github_repo_meta(url: str) -> Dict[str, str]:
        u = (url or "").strip().rstrip("/")
        if "github.com/" not in u:
            return {"org": "", "repo": "", "name": ""}
        parts = u.split("github.com/", 1)[1].split("/")
        if len(parts) < 2:
            return {"org": "", "repo": "", "name": ""}
        org, repo = parts[0], parts[1].removesuffix(".git")
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", repo).strip("-_.") or "imported-skill"
        return {"org": org, "repo": repo, "name": safe_name}

    @staticmethod
    def _extract_guide_description(content: str, fallback: str) -> str:
        for line in (content or "").splitlines():
            text = line.strip().lstrip("#").strip()
            if len(text) >= 8:
                return text[:160]
        return fallback

    @staticmethod
    def _extract_guide_prompt(content: str) -> str:
        text = (content or "").strip()
        if not text:
            return ""
        return text[:GUIDE_PROMPT_LIMIT]

    def _save_repo_doc_skill(
        self,
        owner: str,
        source_url: str,
        source_ref: str,
        content: str,
    ) -> Dict[str, Any]:
        repo_meta = self._github_repo_meta(source_url)
        skill_name = repo_meta["name"]
        description = self._extract_guide_description(content, f"{repo_meta['repo']} 导入的仓库型 Skill")
        prompt = self._extract_guide_prompt(content)
        config = {
            "name": skill_name,
            "version": "repo",
            "description": description,
            "triggers": [],
            "tools": [],
            "enabled": True,
            "always_on": True,
            "source_type": "repo_doc",
            "source_ref": source_ref,
            "mode": "rule",
            "compatibility_level": "rule_only",
            "compatibility_notes": ["来自 README/SKILL.md 等规则文档，仅做提示词注入，不直接调用工具"],
            "capabilities": [],
            "prompt": prompt,
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        }
        config = self._apply_skill_metadata(config)
        target = self._owner_dir(owner) / f"{skill_name}.yaml"
        self._save_skill_config(target, config)
        return {
            "owner": owner,
            "name": skill_name,
            "path": str(target),
            "source_type": "repo_doc",
            "mode": config.get("mode", "rule"),
            "compatibility_level": config.get("compatibility_level", "rule_only"),
            "compatibility_notes": config.get("compatibility_notes", []) or [],
            "capabilities": config.get("capabilities", []) or [],
        }

    def _save_repo_doc_skill_from_text(
        self,
        owner: str,
        source_ref: str,
        content: str,
        file_name: str = "",
    ) -> Dict[str, Any]:
        normalized_name = self._sanitize_skill_name(Path(file_name or source_ref or "imported-skill").stem)
        description = self._extract_guide_description(content, f"{normalized_name} 导入的文档型 Skill")
        prompt = self._extract_guide_prompt(content)
        config = {
            "name": normalized_name,
            "version": "repo",
            "description": description,
            "triggers": [],
            "tools": [],
            "enabled": True,
            "always_on": True,
            "source_type": "repo_doc",
            "source_ref": source_ref,
            "mode": "rule",
            "compatibility_level": "rule_only",
            "compatibility_notes": ["来自 SKILL.md/README.md 等规则文档，仅做提示词注入，不直接调用工具"],
            "capabilities": [],
            "prompt": prompt,
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        }
        config = self._apply_skill_metadata(config)
        target = self._owner_dir(owner) / f"{normalized_name}.yaml"
        self._save_skill_config(target, config)
        return {
            "owner": owner,
            "name": normalized_name,
            "path": str(target),
            "source_type": "repo_doc",
            "mode": config.get("mode", "rule"),
            "compatibility_level": config.get("compatibility_level", "rule_only"),
            "compatibility_notes": config.get("compatibility_notes", []) or [],
            "capabilities": config.get("capabilities", []) or [],
        }

    @staticmethod
    def _build_session() -> requests.Session:
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=1.2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def import_skill_from_url(self, owner: str, url: str, timeout: int = DEFAULT_IMPORT_TIMEOUT) -> Dict[str, Any]:
        normalized = self._normalize_raw_url(url)
        if not normalized.startswith("http://") and not normalized.startswith("https://"):
            raise ValueError("仅支持 http/https URL")
        manifest_candidates = [normalized, *self._github_repo_candidates(normalized)]
        guide_candidates = self._github_repo_guide_candidates(normalized)
        candidates = [*manifest_candidates, *guide_candidates]
        seen = set()
        deduped_candidates = []
        for item in candidates:
            if item in seen:
                continue
            seen.add(item)
            deduped_candidates.append(item)

        session = self._build_session()
        headers = {"User-Agent": "campus-ai-skill-importer/1.0"}
        last_error = "未知错误"

        for candidate in deduped_candidates:
            parsed = urlparse(candidate)
            if (parsed.hostname or "").lower() not in ALLOWED_IMPORT_HOSTS:
                continue
            try:
                resp = session.get(candidate, timeout=timeout, headers=headers)
                if resp.status_code != 200:
                    last_error = f"{candidate} -> HTTP {resp.status_code}"
                    continue

                content_length = resp.headers.get("Content-Length")
                if content_length:
                    try:
                        if int(content_length) > MAX_SKILL_BYTES:
                            last_error = f"{candidate} -> Skill 文件过大（超过 256KB）"
                            continue
                    except Exception:
                        pass

                content = resp.text or ""
                if len(content.encode("utf-8")) > MAX_SKILL_BYTES:
                    last_error = f"{candidate} -> Skill 文件过大（超过 256KB）"
                    continue
                if not content.strip():
                    last_error = f"{candidate} -> Skill 内容为空"
                    continue
                if candidate.endswith((".md", ".txt")):
                    return self._save_repo_doc_skill(owner, normalized, candidate, content)
                saved = self.upload_skill(owner, content)
                skill = self.get_skill(owner, saved["name"]) or {}
                skill["source_type"] = "github_repo" if candidate != normalized and "raw.githubusercontent.com" in candidate else "url"
                skill["source_ref"] = candidate
                target = self._owner_dir(owner) / f"{saved['name']}.yaml"
                self._save_skill_config(target, skill)
                saved["source_type"] = skill["source_type"]
                saved["source_ref"] = candidate
                return saved
            except requests.RequestException as exc:
                last_error = f"{candidate} -> {exc}"
                continue

        raise ValueError(f"导入失败，未找到可用的 Skill manifest。最后错误: {last_error}")

    def list_skills(self, owner: str) -> List[Dict[str, Any]]:
        owner_dir = self._owner_dir(owner)
        result: List[Dict[str, Any]] = []
        for f in owner_dir.glob("*.yaml"):
            try:
                config = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                config = self._apply_skill_metadata(config)
                result.append(
                    {
                        "name": config.get("name", f.stem),
                        "version": config.get("version", ""),
                        "description": config.get("description", ""),
                        "enabled": bool(config.get("enabled", True)),
                        "always_on": bool(config.get("always_on", False)),
                        "triggers": config.get("triggers", []),
                        "input_schema": config.get("input_schema", {}) or {},
                        "tools": config.get("tools", []),
                        "source_type": config.get("source_type", "yaml") or "yaml",
                        "source_ref": config.get("source_ref", "") or "",
                        "mode": config.get("mode", "tool" if config.get("tools") else "rule") or "rule",
                        "compatibility_level": config.get("compatibility_level", "direct") or "direct",
                        "compatibility_notes": config.get("compatibility_notes", []) or [],
                        "capabilities": config.get("capabilities", []) or [],
                        "prompt": config.get("prompt", "") or "",
                        "guidance_excerpt": (str(config.get("prompt", "")).strip()[:360] if config.get("prompt") else ""),
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
        config = self._apply_skill_metadata(config)
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
        config = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        return self._apply_skill_metadata(config)


_skill_manager_singleton: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    global _skill_manager_singleton
    if _skill_manager_singleton is None:
        _skill_manager_singleton = SkillManager()
    return _skill_manager_singleton
