"""
MCP 工具注册中心（最小可用版）。

目标：
- 消除 api 层硬编码工具映射
- 提供统一 list/schema/call 接口
- 为后续社区MCP动态安装预留扩展点
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import requests
from app.services.mcp_manager import get_mcp_manager
from app.services.mcp_manager import KNOWN_MCP_CAPABILITIES
from app.services.mcp_runtime import get_mcp_runtime


@dataclass
class MCPToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    module_path: str = ""
    func_name: str = ""
    input_schema: Optional[Dict[str, Any]] = None
    kind: str = "python"  # python | http
    method: str = "POST"
    url: str = ""
    timeout: int = 12
    transport: str = "python"
    source_type: str = "registry"
    source_ref: str = "mcp_registry"
    compatibility_level: str = "direct"
    compatibility_notes: Optional[List[str]] = None
    capabilities: Optional[List[str]] = None
    owner_username: str = "system"
    command: str = ""
    args: Optional[List[str]] = None
    env: Optional[Dict[str, Any]] = None
    cwd: str = ""
    headers: Optional[Dict[str, Any]] = None
    tool_name: str = ""
    execution_boundary: str = "hosted_web"
    execution_boundary_notes: Optional[List[str]] = None
    web_enabled: bool = True
    service_scope: str = "web_internal_service"


class MCPRegistry:
    def __init__(self):
        self._tools: Dict[str, MCPToolSpec] = {}
        self._register_builtin_tools()
        self._load_external_tools()

    def _register_builtin_tools(self):
        self.register(
            MCPToolSpec(
                name="query_grades",
                description="查询学生成绩；可指定学期，不传则默认当前学期",
                module_path="app.mcp.tools",
                func_name="query_grades",
                parameters={
                    "username": {"type": "string", "required": True, "description": "学号"},
                    "semester": {"type": "string", "required": False, "description": "学期，如2024-2025-1；不传默认当前学期"},
                },
                input_schema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "description": "学号"},
                        "semester": {"type": "string", "description": "学期，如2024-2025-1；不传默认当前学期"},
                    },
                    "required": ["username"],
                },
                capabilities=["grade.query"],
            )
        )
        self.register(
            MCPToolSpec(
                name="query_schedule",
                description="查询课程表；可指定学期，不传则默认当前学期",
                module_path="app.mcp.tools",
                func_name="query_schedule",
                parameters={
                    "username": {"type": "string", "required": True, "description": "学号"},
                    "semester": {"type": "string", "required": False, "description": "学期；不传默认当前学期"},
                },
                input_schema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "description": "学号"},
                        "semester": {"type": "string", "description": "学期；不传默认当前学期"},
                    },
                    "required": ["username"],
                },
                capabilities=["schedule.query"],
            )
        )
        self.register(
            MCPToolSpec(
                name="query_academic_progress",
                description="查询学业进度和学分情况，默认返回当前账号最近同步的进度数据",
                module_path="app.mcp.tools",
                func_name="query_academic_progress",
                parameters={"username": {"type": "string", "required": True, "description": "学号"}},
                capabilities=["academic_progress.query"],
            )
        )
        self.register(
            MCPToolSpec(
                name="query_training_plan",
                description="查询培养方案，默认返回当前账号最近同步的培养方案",
                module_path="app.mcp.tools",
                func_name="query_training_plan",
                parameters={"username": {"type": "string", "required": True, "description": "学号"}},
                capabilities=["training_plan.query"],
            )
        )
        self.register(
            MCPToolSpec(
                name="query_exam_schedule",
                description="查询考试安排；可指定学期，不传则默认当前学期",
                module_path="app.mcp.tools",
                func_name="query_exam_schedule",
                parameters={
                    "username": {"type": "string", "required": True, "description": "学号"},
                    "semester": {"type": "string", "required": False, "description": "学期；不传默认当前学期"},
                },
                capabilities=["exam.query"],
            )
        )
        self.register(
            MCPToolSpec(
                name="query_personal_info",
                description="查询个人基本信息",
                module_path="app.mcp.tools",
                func_name="query_personal_info",
                parameters={"username": {"type": "string", "required": True, "description": "学号"}},
                capabilities=["personal_info.query"],
            )
        )
        self.register(
            MCPToolSpec(
                name="query_weather",
                description="查询指定地点天气",
                module_path="app.mcp.tools",
                func_name="query_weather",
                parameters={
                    "username": {"type": "string", "required": True, "description": "学号"},
                    "location": {"type": "string", "required": True, "description": "地点，如佛山、广州、北京"},
                },
                input_schema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "description": "学号"},
                        "location": {"type": "string", "description": "地点，如佛山、广州、北京"},
                    },
                    "required": ["username", "location"],
                },
                capabilities=["weather.query"],
            )
        )

    def register(self, spec: MCPToolSpec):
        self._tools[spec.name] = spec

    def _load_external_tools(self):
        """
        从声明式配置加载外部工具（拿来主义接入位）：
        - backend/app/mcp/external_tools.json
        - backend/app/mcp/external_tools.generated.json
        - backend/data/mcp_manifests/*.json
        """
        base = Path(__file__).resolve().parents[1] / "mcp"
        for filename in ["external_tools.json", "external_tools.generated.json"]:
            config_path = base / filename
            if not config_path.exists():
                continue
            try:
                payload = json.loads(config_path.read_text(encoding="utf-8"))
                items = payload.get("tools") or []
                for it in items:
                    if it.get("enabled", True) is False:
                        continue
                    name = str(it.get("name", "")).strip()
                    kind = str(it.get("kind", "python")).strip().lower() or "python"
                    module_path = str(it.get("module_path", "")).strip()
                    func_name = str(it.get("func_name", "")).strip()
                    if not name:
                        continue
                    if kind == "python" and (not module_path or not func_name):
                        continue
                    if kind == "http" and not str(it.get("url", "")).strip():
                        continue
                    spec = MCPToolSpec(
                        name=name,
                        description=str(it.get("description", "")).strip() or f"External tool: {name}",
                        module_path=module_path,
                        func_name=func_name,
                        parameters=it.get("parameters") or {},
                        input_schema=it.get("input_schema"),
                        kind=kind,
                        method=str(it.get("method", "POST")).strip().upper() or "POST",
                        url=str(it.get("url", "")).strip(),
                        timeout=int(it.get("timeout", 12) or 12),
                        transport=str(it.get("transport", kind)).strip().lower() or kind,
                        source_type=str(it.get("source_type", "registry")).strip() or "registry",
                        source_ref=str(it.get("source_ref", str(config_path))).strip() or str(config_path),
                        compatibility_level=str(it.get("compatibility_level", "direct")).strip() or "direct",
                        compatibility_notes=it.get("compatibility_notes") or [],
                        capabilities=it.get("capabilities") or ([KNOWN_MCP_CAPABILITIES[name]] if name in KNOWN_MCP_CAPABILITIES else []),
                        owner_username=str(it.get("owner_username", "system")).strip() or "system",
                        command=str(it.get("command", "")).strip(),
                        args=it.get("args") or [],
                        env=it.get("env") or {},
                        cwd=str(it.get("cwd", "")).strip(),
                        headers=it.get("headers") or {},
                        tool_name=str(it.get("tool_name", "")).strip() or name,
                        execution_boundary=str(it.get("execution_boundary", "hosted_web")).strip() or "hosted_web",
                        execution_boundary_notes=it.get("execution_boundary_notes") or [],
                        web_enabled=bool(it.get("web_enabled", True)),
                        service_scope=str(it.get("service_scope", "web_internal_service")).strip() or "web_internal_service",
                    )
                    self.register(spec)
            except Exception:
                # 外部配置失败不影响内置工具可用性
                continue

        # 用户/平台导入的 MCP 对象
        try:
            imported_items = get_mcp_manager().list_all_tools()
            for it in imported_items:
                if it.get("enabled", True) is False:
                    continue
                name = str(it.get("name", "")).strip()
                kind = str(it.get("kind", "python")).strip().lower() or "python"
                module_path = str(it.get("module_path", "")).strip()
                func_name = str(it.get("func_name", "")).strip()
                if not name:
                    continue
                if kind == "python" and (not module_path or not func_name):
                    continue
                if kind == "http" and not str(it.get("url", "")).strip():
                    continue
                self.register(
                    MCPToolSpec(
                        name=name,
                        description=str(it.get("description", "")).strip() or f"Imported MCP tool: {name}",
                        module_path=module_path,
                        func_name=func_name,
                        parameters=it.get("parameters") or {},
                        input_schema=it.get("input_schema"),
                        kind=kind,
                        method=str(it.get("method", "POST")).strip().upper() or "POST",
                        url=str(it.get("url", "")).strip(),
                        timeout=int(it.get("timeout", 12) or 12),
                        transport=str(it.get("transport", kind)).strip().lower() or kind,
                        source_type=str(it.get("source_type", "registry")).strip() or "registry",
                        source_ref=str(it.get("source_ref", "mcp_registry")).strip() or "mcp_registry",
                        compatibility_level=str(it.get("compatibility_level", "direct")).strip() or "direct",
                        compatibility_notes=it.get("compatibility_notes") or [],
                        capabilities=it.get("capabilities") or ([KNOWN_MCP_CAPABILITIES[name]] if name in KNOWN_MCP_CAPABILITIES else []),
                        owner_username=str(it.get("owner_username", "system")).strip() or "system",
                        command=str(it.get("command", "")).strip(),
                        args=it.get("args") or [],
                        env=it.get("env") or {},
                        cwd=str(it.get("cwd", "")).strip(),
                        headers=it.get("headers") or {},
                        tool_name=str(it.get("tool_name", "")).strip() or name,
                        execution_boundary=str(it.get("execution_boundary", "hosted_web")).strip() or "hosted_web",
                        execution_boundary_notes=it.get("execution_boundary_notes") or [],
                        web_enabled=bool(it.get("web_enabled", True)),
                        service_scope=str(it.get("service_scope", "web_internal_service")).strip() or "web_internal_service",
                    )
                )
        except Exception:
            pass

    def list_tools(self) -> List[Dict[str, Any]]:
        tools = []
        for spec in self._tools.values():
            tools.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                    "kind": spec.kind,
                    "transport": spec.transport,
                    "source_type": spec.source_type,
                    "source_ref": spec.source_ref,
                    "compatibility_level": spec.compatibility_level,
                    "compatibility_notes": spec.compatibility_notes or [],
                    "capabilities": spec.capabilities or [],
                    "owner_username": spec.owner_username,
                    "command": spec.command,
                    "args": spec.args or [],
                    "env": spec.env or {},
                    "cwd": spec.cwd,
                    "headers": spec.headers or {},
                    "tool_name": spec.tool_name or spec.name,
                    "execution_boundary": getattr(spec, "execution_boundary", None),
                    "execution_boundary_notes": getattr(spec, "execution_boundary_notes", None) or [],
                    "web_enabled": getattr(spec, "web_enabled", True),
                    "service_scope": getattr(spec, "service_scope", None),
                }
            )
        return tools

    def get_tool_meta(self, name: str) -> Optional[Dict[str, Any]]:
        spec = self._tools.get(name)
        if not spec:
            return None
        return {
            "name": spec.name,
            "description": spec.description,
            "kind": spec.kind,
            "transport": spec.transport,
            "source_type": spec.source_type,
            "source_ref": spec.source_ref,
            "compatibility_level": spec.compatibility_level,
            "compatibility_notes": spec.compatibility_notes or [],
            "capabilities": spec.capabilities or [],
            "owner_username": spec.owner_username,
            "command": spec.command,
            "args": spec.args or [],
            "env": spec.env or {},
            "cwd": spec.cwd,
            "headers": spec.headers or {},
            "tool_name": spec.tool_name or spec.name,
            "parameters": spec.parameters,
            "input_schema": spec.input_schema,
            "execution_boundary": getattr(spec, "execution_boundary", None),
            "execution_boundary_notes": getattr(spec, "execution_boundary_notes", None) or [],
            "web_enabled": getattr(spec, "web_enabled", True),
            "service_scope": getattr(spec, "service_scope", None),
        }

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def get_tool_schema(self, name: str) -> Optional[Dict[str, Any]]:
        spec = self._tools.get(name)
        if not spec:
            return None
        if spec.input_schema:
            return {
                "name": spec.name,
                "description": spec.description,
                "inputSchema": spec.input_schema,
            }
        return {
            "name": spec.name,
            "description": spec.description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    key: {"type": val.get("type", "string"), "description": val.get("description", "")}
                    for key, val in spec.parameters.items()
                },
                "required": [k for k, v in spec.parameters.items() if v.get("required")],
            },
        }

    @staticmethod
    def _merge_call_params(username: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        merged: Dict[str, Any] = {"username": username}
        if not params:
            return merged

        sanitized = dict(params)
        sanitized.pop("username", None)
        merged.update(sanitized)
        return merged

    async def call_tool(self, name: str, username: str, params: Optional[Dict[str, Any]] = None) -> str:
        if not self.has_tool(name):
            raise ValueError(f"工具 '{name}' 不存在")
        from app.services.composition_manager import get_composition_manager

        comp = get_composition_manager()
        if not comp.is_mcp_tool_enabled(username, name):
            raise ValueError(f"工具 '{name}' 在当前组合中已禁用")
        spec = self._tools[name]
        merged = self._merge_call_params(username, params)
        if spec.kind in {"stdio", "sse", "streamable_http", "command"}:
            return await get_mcp_runtime().call_tool(spec, merged)
        if spec.kind not in {"python", "http"}:
            raise ValueError(f"工具 '{name}' 当前为 {spec.kind} 类型，尚未接入真实运行时")
        if spec.kind == "http":
            return self._call_http_tool(spec, merged)
        module = importlib.import_module(spec.module_path)
        func = getattr(module, spec.func_name)
        return await func(**merged)

    @staticmethod
    def _call_http_tool(spec: MCPToolSpec, payload: Dict[str, Any]) -> str:
        if not spec.url:
            raise ValueError(f"HTTP 工具 '{spec.name}' 缺少 url 配置")
        method = (spec.method or "POST").upper()
        try:
            if method == "GET":
                resp = requests.get(spec.url, params=payload, timeout=spec.timeout)
            else:
                resp = requests.request(method, spec.url, json=payload, timeout=spec.timeout)
            if resp.status_code >= 400:
                raise ValueError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "application/json" in ctype:
                return json.dumps(resp.json(), ensure_ascii=False)
            return resp.text
        except Exception as e:
            raise ValueError(f"HTTP 工具调用失败: {e}")


_mcp_registry_singleton: Optional[MCPRegistry] = None


def get_mcp_registry() -> MCPRegistry:
    global _mcp_registry_singleton
    if _mcp_registry_singleton is None:
        _mcp_registry_singleton = MCPRegistry()
    return _mcp_registry_singleton


def reload_mcp_registry() -> MCPRegistry:
    global _mcp_registry_singleton
    _mcp_registry_singleton = MCPRegistry()
    return _mcp_registry_singleton
