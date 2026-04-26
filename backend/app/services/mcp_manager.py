"""
MCP 对象管理器：
- 按 owner 管理可导入的 MCP tool manifests
- 支持文件 / URL / GitHub 仓库导入
- 为 MCP registry 提供声明式对象来源
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


MAX_MCP_BYTES = 512 * 1024
COMMON_MCP_MANIFESTS = (
    "mcp.json",
    "mcp.tools.json",
    "tools.json",
    "external_tools.json",
    "manifest.json",
    "manifests/mcp.json",
    "manifests/tools.json",
    "mcp/manifest.json",
)


class MCPManager:
    def __init__(self, base_dir: str = "backend/data/mcp_manifests"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _owner_file(self, owner: str) -> Path:
        safe = (owner or "system").strip() or "system"
        return self.base_dir / f"{safe}.json"

    def _load_owner_tools(self, owner: str) -> List[Dict[str, Any]]:
        path = self._owner_file(owner)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            tools = payload.get("tools") if isinstance(payload, dict) else None
            if isinstance(tools, list):
                return [item for item in tools if isinstance(item, dict)]
        except Exception:
            return []
        return []

    def _save_owner_tools(self, owner: str, tools: List[Dict[str, Any]]) -> None:
        path = self._owner_file(owner)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"tools": tools, "updated_at": int(time.time())}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _normalize_blob_raw_url(url: str) -> str:
        u = (url or "").strip()
        if "raw.githubusercontent.com" in u:
            return u
        if "github.com" in u and "/blob/" in u:
            parts = u.split("github.com/", 1)[1].split("/")
            if len(parts) >= 5 and parts[2] == "blob":
                org, repo, _blob, branch = parts[:4]
                tail = "/".join(parts[4:])
                return f"https://raw.githubusercontent.com/{org}/{repo.removesuffix('.git')}/{branch}/{tail}"
        return u

    @staticmethod
    def _github_repo_candidates(url: str) -> List[str]:
        u = (url or "").strip().rstrip("/")
        if "github.com/" not in u or "/blob/" in u or "raw.githubusercontent.com" in u:
            return []
        parts = u.split("github.com/", 1)[1].split("/")
        if len(parts) < 2:
            return []
        org, repo = parts[0], parts[1].removesuffix(".git")
        candidates: List[str] = []
        for branch in ("main", "master"):
            for filename in COMMON_MCP_MANIFESTS:
                candidates.append(f"https://raw.githubusercontent.com/{org}/{repo}/{branch}/{filename}")
        return candidates

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

    @staticmethod
    def _parse_payload(content: str) -> List[Dict[str, Any]]:
        try:
            payload = json.loads(content)
        except Exception as exc:
            raise ValueError(f"JSON 解析失败: {exc}")
        if isinstance(payload, list):
            tools = payload
        else:
            tools = payload.get("tools") if isinstance(payload, dict) else None
        if not isinstance(tools, list) or not tools:
            raise ValueError("配置格式错误：缺少 tools 数组")
        return [item for item in tools if isinstance(item, dict)]

    @staticmethod
    def _validate_tool_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        name = str(item.get("name", "")).strip()
        kind = str(item.get("kind", "python")).strip().lower() or "python"
        if not name:
            return None
        if kind == "python":
            if not str(item.get("module_path", "")).strip() or not str(item.get("func_name", "")).strip():
                return None
        elif kind == "http":
            if not str(item.get("url", "")).strip():
                return None
        else:
            return None
        normalized = dict(item)
        normalized["name"] = name
        normalized["kind"] = kind
        normalized["enabled"] = bool(item.get("enabled", True))
        return normalized

    def import_tools(self, owner: str, tools: List[Dict[str, Any]], source_type: str, source_ref: str) -> Dict[str, Any]:
        existing = self._load_owner_tools(owner)
        by_name = {
            str(item.get("name", "")).strip(): item
            for item in existing
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        }
        imported = 0
        for raw in tools:
            item = self._validate_tool_item(raw)
            if item is None:
                continue
            item["owner_username"] = owner
            item["source_type"] = source_type
            item["source_ref"] = source_ref
            item["updated_at"] = int(time.time())
            by_name[item["name"]] = item
            imported += 1
        merged = [value for key, value in by_name.items() if key]
        self._save_owner_tools(owner, merged)
        return {"imported": imported, "total": len(merged)}

    def import_from_content(self, owner: str, content: str, source_type: str, source_ref: str) -> Dict[str, Any]:
        tools = self._parse_payload(content)
        result = self.import_tools(owner, tools, source_type=source_type, source_ref=source_ref)
        return {"tools": self.list_tools(owner), **result}

    def import_from_url(self, owner: str, url: str, timeout: int = 20) -> Dict[str, Any]:
        normalized = self._normalize_blob_raw_url(url)
        candidates = [normalized, *self._github_repo_candidates(normalized)]
        seen = set()
        session = self._build_session()
        last_error = "未知错误"
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            try:
                resp = session.get(candidate, timeout=timeout, headers={"User-Agent": "campus-ai-mcp-importer/1.0"})
                if resp.status_code != 200:
                    last_error = f"{candidate} -> HTTP {resp.status_code}"
                    continue
                content = resp.text or ""
                if len(content.encode("utf-8")) > MAX_MCP_BYTES:
                    last_error = f"{candidate} -> 配置文件过大"
                    continue
                return self.import_from_content(
                    owner,
                    content,
                    source_type="github_repo" if candidate != normalized and "raw.githubusercontent.com" in candidate else "url",
                    source_ref=candidate,
                )
            except Exception as exc:
                last_error = f"{candidate} -> {exc}"
                continue
        raise ValueError(f"MCP 导入失败，未找到可用配置。最后错误: {last_error}")

    def list_tools(self, owner: str) -> List[Dict[str, Any]]:
        items = self._load_owner_tools(owner)
        result: List[Dict[str, Any]] = []
        for item in items:
            result.append(
                {
                    "name": str(item.get("name", "")).strip(),
                    "description": str(item.get("description", "")).strip(),
                    "kind": str(item.get("kind", "python")).strip().lower() or "python",
                    "parameters": item.get("parameters") or {},
                    "enabled": bool(item.get("enabled", True)),
                    "source_type": item.get("source_type", "file"),
                    "source_ref": item.get("source_ref", ""),
                    "owner_username": item.get("owner_username", owner),
                    "module_path": item.get("module_path", ""),
                    "func_name": item.get("func_name", ""),
                    "url": item.get("url", ""),
                    "updated_at": item.get("updated_at"),
                }
            )
        result.sort(key=lambda x: x.get("name", ""))
        return result

    def list_all_tools(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for file in self.base_dir.glob("*.json"):
            owner = file.stem
            out.extend(self.list_tools(owner))
        return out

    def set_enabled(self, owner: str, tool_name: str, enabled: bool) -> Dict[str, Any]:
        items = self._load_owner_tools(owner)
        found = False
        for item in items:
            if str(item.get("name", "")).strip() == tool_name:
                item["enabled"] = bool(enabled)
                item["updated_at"] = int(time.time())
                found = True
                break
        if not found:
            raise FileNotFoundError("MCP 工具不存在")
        self._save_owner_tools(owner, items)
        return {"name": tool_name, "enabled": bool(enabled)}

    def delete(self, owner: str, tool_name: str) -> bool:
        items = self._load_owner_tools(owner)
        kept = [item for item in items if str(item.get("name", "")).strip() != tool_name]
        if len(kept) == len(items):
            return False
        self._save_owner_tools(owner, kept)
        return True


_mcp_manager_singleton: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    global _mcp_manager_singleton
    if _mcp_manager_singleton is None:
        _mcp_manager_singleton = MCPManager()
    return _mcp_manager_singleton
