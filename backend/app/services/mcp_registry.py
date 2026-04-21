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


class MCPRegistry:
    def __init__(self):
        self._tools: Dict[str, MCPToolSpec] = {}
        self._register_builtin_tools()
        self._load_external_tools()

    def _register_builtin_tools(self):
        self.register(
            MCPToolSpec(
                name="query_grades",
                description="查询学生成绩",
                module_path="app.mcp.tools",
                func_name="query_grades",
                parameters={
                    "username": {"type": "string", "required": True, "description": "学号"},
                    "semester": {"type": "string", "required": False, "description": "学期，如2024-2025-1"},
                },
                input_schema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "description": "学号"},
                        "semester": {"type": "string", "description": "学期，如2024-2025-1"},
                    },
                    "required": ["username"],
                },
            )
        )
        self.register(
            MCPToolSpec(
                name="query_schedule",
                description="查询课程表",
                module_path="app.mcp.tools",
                func_name="query_schedule",
                parameters={
                    "username": {"type": "string", "required": True, "description": "学号"},
                    "semester": {"type": "string", "required": False, "description": "学期"},
                },
                input_schema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "description": "学号"},
                        "semester": {"type": "string", "description": "学期"},
                    },
                    "required": ["username"],
                },
            )
        )
        self.register(
            MCPToolSpec(
                name="query_academic_progress",
                description="查询学业进度和学分情况",
                module_path="app.mcp.tools",
                func_name="query_academic_progress",
                parameters={"username": {"type": "string", "required": True, "description": "学号"}},
            )
        )
        self.register(
            MCPToolSpec(
                name="query_training_plan",
                description="查询培养方案",
                module_path="app.mcp.tools",
                func_name="query_training_plan",
                parameters={"username": {"type": "string", "required": True, "description": "学号"}},
            )
        )
        self.register(
            MCPToolSpec(
                name="query_exam_schedule",
                description="查询考试安排",
                module_path="app.mcp.tools",
                func_name="query_exam_schedule",
                parameters={
                    "username": {"type": "string", "required": True, "description": "学号"},
                    "semester": {"type": "string", "required": False, "description": "学期"},
                },
            )
        )
        self.register(
            MCPToolSpec(
                name="query_personal_info",
                description="查询个人基本信息",
                module_path="app.mcp.tools",
                func_name="query_personal_info",
                parameters={"username": {"type": "string", "required": True, "description": "学号"}},
            )
        )

    def register(self, spec: MCPToolSpec):
        self._tools[spec.name] = spec

    def _load_external_tools(self):
        """
        从声明式配置加载外部工具（拿来主义接入位）：
        - backend/app/mcp/external_tools.json
        """
        config_path = Path(__file__).resolve().parents[1] / "mcp" / "external_tools.json"
        if not config_path.exists():
            return
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            items = payload.get("tools") or []
            for it in items:
                name = str(it.get("name", "")).strip()
                module_path = str(it.get("module_path", "")).strip()
                func_name = str(it.get("func_name", "")).strip()
                if not name or not module_path or not func_name:
                    continue
                spec = MCPToolSpec(
                    name=name,
                    description=str(it.get("description", "")).strip() or f"External tool: {name}",
                    module_path=module_path,
                    func_name=func_name,
                    parameters=it.get("parameters") or {},
                    input_schema=it.get("input_schema"),
                    kind=str(it.get("kind", "python")).strip().lower() or "python",
                    method=str(it.get("method", "POST")).strip().upper() or "POST",
                    url=str(it.get("url", "")).strip(),
                    timeout=int(it.get("timeout", 12) or 12),
                )
                self.register(spec)
        except Exception:
            # 外部配置失败不影响内置工具可用性
            return

    def list_tools(self) -> List[Dict[str, Any]]:
        tools = []
        for spec in self._tools.values():
            tools.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                    "kind": spec.kind,
                }
            )
        return tools

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

    async def call_tool(self, name: str, username: str, params: Optional[Dict[str, Any]] = None) -> str:
        if not self.has_tool(name):
            raise ValueError(f"工具 '{name}' 不存在")
        spec = self._tools[name]
        merged = {"username": username}
        if params:
            merged.update(params)
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
