"""
Platform MCP Agent Bridge

用途：
- 作为外部 Agent（OpenClaw / Claude Desktop / 其他支持 MCP 的客户端）的本地 stdio MCP server
- 不直接登录教务系统
- 通过平台下发的 Agent Token 复用 Web 端已经完成的授权状态

环境变量：
- SOULDDOG_API_BASE: 平台后端基地址，例如 http://127.0.0.1:8000
- SOULDDOG_AGENT_TOKEN: 平台签发的 Agent Access Token
- SOULDDOG_MCP_SERVER_NAME: 可选，自定义 MCP server 名称
- SOULDDOG_VERIFY_TLS: 可选，true/false，默认 true
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import requests

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions


def _env_required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量 {name}")
    return value


def _bool_env(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


class PlatformMCPBridge:
    def __init__(self) -> None:
        self.api_base = _env_required("SOULDDOG_API_BASE").rstrip("/")
        self.agent_token = _env_required("SOULDDOG_AGENT_TOKEN")
        self.server_name = (os.getenv("SOULDDOG_MCP_SERVER_NAME") or "soulddog-platform").strip() or "soulddog-platform"
        self.verify_tls = _bool_env("SOULDDOG_VERIFY_TLS", True)
        self._http = requests.Session()
        self._http.headers.update(
            {
                "Authorization": f"Bearer {self.agent_token}",
                "Accept": "application/json",
                "User-Agent": "soulddog-mcp-agent-bridge/1.0",
            }
        )

    def _get_json(self, path: str) -> dict[str, Any]:
        resp = self._http.get(f"{self.api_base}{path}", timeout=20, verify=self.verify_tls)
        resp.raise_for_status()
        return resp.json()

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._http.post(f"{self.api_base}{path}", json=payload, timeout=60, verify=self.verify_tls)
        resp.raise_for_status()
        return resp.json()

    async def fetch_catalog(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_json, "/api/mcp/agent/catalog")

    async def fetch_tool_schema(self, tool_name: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_json, f"/api/mcp/tools/{tool_name}/schema")

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        payload = {"username": "", "params": arguments or {}}
        return await asyncio.to_thread(self._post_json, f"/api/mcp/tools/{tool_name}", payload)


bridge = PlatformMCPBridge()
server = Server("soulddog-platform-bridge")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    catalog = await bridge.fetch_catalog()
    tools = catalog.get("visible_tools") or []
    result: list[types.Tool] = []
    for item in tools:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        schema_payload = await bridge.fetch_tool_schema(name)
        input_schema = schema_payload.get("inputSchema") or {
            "type": "object",
            "properties": {},
        }
        result.append(
            types.Tool(
                name=name,
                description=str(item.get("description", "")).strip() or name,
                inputSchema=input_schema,
            )
        )
    return result


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> types.CallToolResult:
    payload = await bridge.call_tool(name, arguments or {})
    if not payload.get("success", False):
        message = str(payload.get("error") or "工具调用失败")
        return types.CallToolResult(
            isError=True,
            content=[types.TextContent(type="text", text=message)],
            structuredContent={"success": False, "tool": name, "error": message},
        )

    raw_result = payload.get("result")
    text_result = raw_result if isinstance(raw_result, str) else json.dumps(raw_result, ensure_ascii=False)
    structured: dict[str, Any] = {"success": True, "tool": name, "result": raw_result}
    if isinstance(raw_result, str):
        try:
            structured["parsed_result"] = json.loads(raw_result)
        except Exception:
            pass

    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text_result)],
        structuredContent=structured,
    )


async def run() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=bridge.server_name,
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(run())
