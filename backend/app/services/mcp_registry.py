"""
MCP 工具注册中心（最小可用版）。

目标：
- 消除 api 层硬编码工具映射
- 提供统一 list/schema/call 接口
- 为后续社区MCP动态安装预留扩展点
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


@dataclass
class MCPToolSpec:
    name: str
    description: str
    module_path: str
    func_name: str
    parameters: Dict[str, Any]
    input_schema: Optional[Dict[str, Any]] = None


class MCPRegistry:
    def __init__(self):
        self._tools: Dict[str, MCPToolSpec] = {}
        self._register_builtin_tools()

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

    def list_tools(self) -> List[Dict[str, Any]]:
        tools = []
        for spec in self._tools.values():
            tools.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
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
        module = importlib.import_module(spec.module_path)
        func = getattr(module, spec.func_name)

        merged = {"username": username}
        if params:
            merged.update(params)
        return await func(**merged)


_mcp_registry_singleton: Optional[MCPRegistry] = None


def get_mcp_registry() -> MCPRegistry:
    global _mcp_registry_singleton
    if _mcp_registry_singleton is None:
        _mcp_registry_singleton = MCPRegistry()
    return _mcp_registry_singleton

