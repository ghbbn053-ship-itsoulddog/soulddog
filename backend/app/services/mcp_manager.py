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
    ".mcp.json",
    ".mcp/config.json",
    ".cursor/mcp.json",
    ".vscode/mcp.json",
    "manifests/mcp.json",
    "manifests/tools.json",
    "mcp/manifest.json",
)
KNOWN_MCP_CAPABILITIES = {
    "query_schedule": "schedule.query",
    "query_grades": "grade.query",
    "query_exam_schedule": "exam.query",
    "query_training_plan": "training_plan.query",
    "query_academic_progress": "academic_progress.query",
    "query_personal_info": "personal_info.query",
    "query_weather": "weather.query",
}


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
    def _coerce_server_entry(name: str, raw: Dict[str, Any]) -> Dict[str, Any]:
        server = dict(raw)
        normalized_name = str(name or server.get("name", "")).strip()
        transport = str(server.get("transport", "")).strip().lower()
        command = str(server.get("command", "")).strip()
        url = str(server.get("url", "") or server.get("endpoint", "")).strip()

        if not transport:
            if command:
                transport = "stdio"
            elif url:
                transport = "http"
            else:
                transport = "unknown"

        kind = str(server.get("kind", "")).strip().lower()
        if not kind:
            if transport in {"stdio", "command"}:
                kind = "stdio"
            elif transport in {"sse"}:
                kind = "sse"
            elif transport == "streamable_http":
                kind = "streamable_http"
            elif transport == "http":
                kind = "http"
            else:
                kind = transport or "unknown"

        item: Dict[str, Any] = {
            "name": normalized_name,
            "description": str(server.get("description", "")).strip() or f"Imported MCP server: {normalized_name}",
            "kind": kind,
            "transport": transport,
            "enabled": bool(server.get("enabled", True)),
            "capabilities": server.get("capabilities") or [],
            "parameters": server.get("parameters") or {},
        }

        if url:
            item["url"] = url
        if command:
            item["command"] = command
        if isinstance(server.get("args"), list):
            item["args"] = server.get("args")
        if isinstance(server.get("env"), dict):
            item["env"] = server.get("env")
        if isinstance(server.get("headers"), dict):
            item["headers"] = server.get("headers")
        if str(server.get("cwd", "")).strip():
            item["cwd"] = str(server.get("cwd", "")).strip()
        if str(server.get("module_path", "")).strip():
            item["module_path"] = str(server.get("module_path", "")).strip()
        if str(server.get("func_name", "")).strip():
            item["func_name"] = str(server.get("func_name", "")).strip()
        return item

    @classmethod
    def _parse_openclaw_skill_payload(cls, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        mcp_servers = payload.get("mcpServers")
        declared_tools = payload.get("tools")
        if not isinstance(mcp_servers, dict) or not isinstance(declared_tools, list) or not declared_tools:
            return []

        tools: List[Dict[str, Any]] = []
        capabilities_map = payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else {}
        for server_name, raw_server in mcp_servers.items():
            if not isinstance(raw_server, dict):
                continue
            base = cls._coerce_server_entry(server_name, raw_server)
            disabled = bool(raw_server.get("disabled", False))
            for tool_name in declared_tools:
                tool_text = str(tool_name or "").strip()
                if not tool_text:
                    continue
                capability_list: List[str] = []
                description = ""
                for capability_key, capability_meta in capabilities_map.items():
                    if not isinstance(capability_meta, dict):
                        continue
                    bound_tool = str(capability_meta.get("tool", "")).strip()
                    if bound_tool == tool_text:
                        capability_list.append(str(capability_key).strip())
                        if not description:
                            description = str(capability_meta.get("description", "")).strip()
                item = dict(base)
                item["name"] = tool_text
                item["tool_name"] = tool_text
                item["description"] = description or f"MCP tool from server {server_name}: {tool_text}"
                item["enabled"] = not disabled
                if capability_list:
                    item["capabilities"] = capability_list
                item["source_format"] = "openclaw_skill"
                tools.append(item)
        return tools

    @classmethod
    def _parse_payload(cls, content: str) -> List[Dict[str, Any]]:
        try:
            payload = json.loads(content)
        except Exception as exc:
            raise ValueError(f"JSON 解析失败: {exc}")
        if isinstance(payload, list):
            tools = payload
        else:
            tools = None
            if isinstance(payload, dict):
                openclaw_tools = cls._parse_openclaw_skill_payload(payload)
                if openclaw_tools:
                    tools = openclaw_tools
                if isinstance(payload.get("tools"), list):
                    tools = tools or payload.get("tools")
                elif isinstance(payload.get("mcpServers"), dict):
                    tools = tools or [cls._coerce_server_entry(name, item) for name, item in payload.get("mcpServers", {}).items() if isinstance(item, dict)]
                elif isinstance(payload.get("servers"), dict):
                    tools = tools or [cls._coerce_server_entry(name, item) for name, item in payload.get("servers", {}).items() if isinstance(item, dict)]
                elif isinstance(payload.get("mcp_servers"), dict):
                    tools = tools or [cls._coerce_server_entry(name, item) for name, item in payload.get("mcp_servers", {}).items() if isinstance(item, dict)]
        if not isinstance(tools, list) or not tools:
            raise ValueError("配置格式错误：缺少 tools 数组，或缺少 mcpServers/servers 映射")
        return [item for item in tools if isinstance(item, dict)]

    @staticmethod
    def _validate_tool_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        name = str(item.get("name", "")).strip()
        kind = str(item.get("kind", "python")).strip().lower() or "python"
        if not name:
            return None
        if kind == "python":
            if not str(item.get("module_path", "")).strip() or not str(item.get("func_name", "")).strip():
                normalized = dict(item)
                normalized["name"] = name
                normalized["kind"] = kind
                normalized["enabled"] = bool(item.get("enabled", True))
                normalized.setdefault("transport", "python")
                return MCPManager._apply_tool_metadata(normalized)
        elif kind == "http":
            if not str(item.get("url", "")).strip():
                normalized = dict(item)
                normalized["name"] = name
                normalized["kind"] = kind
                normalized["enabled"] = bool(item.get("enabled", True))
                normalized.setdefault("transport", "http")
                return MCPManager._apply_tool_metadata(normalized)
        normalized = dict(item)
        normalized["name"] = name
        normalized["kind"] = kind
        normalized["enabled"] = bool(item.get("enabled", True))
        normalized.setdefault("transport", "python" if kind == "python" else ("http" if kind == "http" else kind))
        normalized = MCPManager._apply_tool_metadata(normalized)
        return normalized

    @staticmethod
    def _infer_capabilities(item: Dict[str, Any]) -> List[str]:
        capabilities: List[str] = []
        declared = item.get("capabilities")
        if isinstance(declared, list):
            for value in declared:
                text = str(value or "").strip()
                if text:
                    capabilities.append(text)
        name = str(item.get("name", "")).strip()
        capability = KNOWN_MCP_CAPABILITIES.get(name)
        if capability:
            capabilities.append(capability)
        return list(dict.fromkeys(capabilities))

    @staticmethod
    def _apply_tool_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
        classified = MCPManager._classify_tool_item(item)
        normalized = dict(item)
        normalized["transport"] = str(item.get("transport", "python" if item.get("kind") == "python" else "http")).strip().lower() or (
            "python" if item.get("kind") == "python" else "http"
        )
        normalized["compatibility_level"] = classified["compatibility_level"]
        normalized["compatibility_notes"] = classified["compatibility_notes"]
        normalized["capabilities"] = classified["capabilities"]
        return normalized

    @staticmethod
    def _classify_tool_item(item: Dict[str, Any]) -> Dict[str, Any]:
        name = str(item.get("name", "")).strip()
        kind = str(item.get("kind", "python")).strip().lower() or "python"
        transport = str(item.get("transport", "python" if kind == "python" else "http")).strip().lower() or (
            "python" if kind == "python" else "http"
        )
        capabilities = MCPManager._infer_capabilities(item)
        notes: List[str] = []

        if kind not in {"python", "http"}:
            if kind in {"stdio", "command"}:
                command = str(item.get("command", "")).strip()
                notes = ["检测到 stdio MCP server 配置"]
                if command:
                    notes.append(f"command: {command}")
                tool_name = str(item.get("tool_name", "")).strip()
                if tool_name:
                    notes.append(f"tool: {tool_name}")
                notes.append("已接入 stdio MCP runtime；前提是本机安装了 mcp SDK 且目标 server 能正常启动")
                return {
                    "compatibility_level": "direct" if tool_name and command else "adapted",
                    "compatibility_notes": notes,
                    "capabilities": capabilities,
                }
            if kind in {"sse", "streamable_http"}:
                url = str(item.get("url", "") or item.get("endpoint", "")).strip()
                notes = [f"检测到 {kind} MCP server 配置"]
                if url:
                    notes.append(f"endpoint: {url}")
                tool_name = str(item.get("tool_name", "")).strip()
                if tool_name:
                    notes.append(f"tool: {tool_name}")
                notes.append("已接入远程 MCP client；前提是目标 endpoint 支持标准 MCP 握手与 tool 调用")
                return {
                    "compatibility_level": "direct" if tool_name and url else "adapted",
                    "compatibility_notes": notes,
                    "capabilities": capabilities,
                }
            return {
                "compatibility_level": "incompatible",
                "compatibility_notes": [f"当前仅支持 python/http 两类 MCP，收到不支持的 kind: {kind}"],
                "capabilities": capabilities,
            }

        if kind == "python":
            module_path = str(item.get("module_path", "")).strip()
            func_name = str(item.get("func_name", "")).strip()
            if not module_path or not func_name:
                return {
                    "compatibility_level": "incompatible",
                    "compatibility_notes": ["python MCP 缺少 module_path 或 func_name，当前运行时无法执行"],
                    "capabilities": capabilities,
                }
            notes.append(f"python 入口: {module_path}:{func_name}")
        else:
            url = str(item.get("url", "")).strip()
            if not url:
                return {
                    "compatibility_level": "incompatible",
                    "compatibility_notes": ["http MCP 缺少 url，当前运行时无法执行"],
                    "capabilities": capabilities,
                }
            notes.append(f"http 入口: {url}")

        if transport not in {"python", "http"}:
            notes.append(f"transport={transport} 不在当前标准传输集中，已按 {kind} 兼容处理")

        if capabilities:
            notes.append(f"已识别平台能力: {', '.join(capabilities[:4])}")
            return {
                "compatibility_level": "direct",
                "compatibility_notes": notes,
                "capabilities": capabilities,
            }

        if name:
            notes.append(f"工具 {name} 结构可导入，但未映射到平台 capability")
        notes.append("当前可作为对象管理和编排项存在，真正调用前需要补能力映射或工具路由规则")
        return {
            "compatibility_level": "adapted",
            "compatibility_notes": notes,
            "capabilities": capabilities,
        }

    @staticmethod
    def _build_import_summary(items: List[Dict[str, Any]]) -> Dict[str, int]:
        summary = {"direct": 0, "adapted": 0, "rule_only": 0, "incompatible": 0}
        for item in items:
            level = str(item.get("compatibility_level", "")).strip().lower()
            if level in summary:
                summary[level] += 1
        return summary

    def import_tools(self, owner: str, tools: List[Dict[str, Any]], source_type: str, source_ref: str) -> Dict[str, Any]:
        existing = self._load_owner_tools(owner)
        by_name = {
            str(item.get("name", "")).strip(): item
            for item in existing
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        }
        imported = 0
        imported_items: List[Dict[str, Any]] = []
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
            imported_items.append(item)
        merged = [value for key, value in by_name.items() if key]
        self._save_owner_tools(owner, merged)
        return {
            "imported": imported,
            "total": len(merged),
            "items": imported_items,
            "summary": self._build_import_summary(imported_items),
        }

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
            item = self._apply_tool_metadata(item)
            result.append(
                {
                    "name": str(item.get("name", "")).strip(),
                    "description": str(item.get("description", "")).strip(),
                    "kind": str(item.get("kind", "python")).strip().lower() or "python",
                    "parameters": item.get("parameters") or {},
                    "enabled": bool(item.get("enabled", True)),
                    "source_type": item.get("source_type", "file"),
                    "source_ref": item.get("source_ref", ""),
                    "transport": item.get("transport", "python" if item.get("kind") == "python" else "http"),
                    "compatibility_level": item.get("compatibility_level", "direct"),
                    "compatibility_notes": item.get("compatibility_notes", []) or [],
                    "capabilities": item.get("capabilities", []) or [],
                    "owner_username": item.get("owner_username", owner),
                    "module_path": item.get("module_path", ""),
                    "func_name": item.get("func_name", ""),
                    "url": item.get("url", ""),
                    "command": item.get("command", ""),
                    "args": item.get("args", []) or [],
                    "env": item.get("env", {}) or {},
                    "cwd": item.get("cwd", ""),
                    "headers": item.get("headers", {}) or {},
                    "tool_name": item.get("tool_name", ""),
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
