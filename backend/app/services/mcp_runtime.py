"""
MCP 运行时适配层。

目标：
- 为导入的 stdio / sse / streamable_http MCP 对象提供真实调用入口
- 与当前 registry 保持解耦，便于后续增加缓存、探测、生命周期管理
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


class MCPRuntimeService:
    async def call_tool(self, spec, payload: Dict[str, Any]) -> str:
        transport = str(getattr(spec, "transport", "") or getattr(spec, "kind", "") or "").strip().lower()
        if transport in {"stdio", "command"}:
            return await self._call_stdio_tool(spec, payload)
        if transport == "sse":
            return await self._call_sse_tool(spec, payload)
        if transport == "streamable_http":
            return await self._call_streamable_http_tool(spec, payload)
        raise ValueError(f"暂不支持的 MCP transport: {transport or 'unknown'}")

    async def _call_stdio_tool(self, spec, payload: Dict[str, Any]) -> str:
        try:
            from mcp import ClientSession, StdioServerParameters  # type: ignore
            from mcp.client.stdio import stdio_client  # type: ignore
        except Exception as exc:
            raise ValueError(f"stdio MCP 运行时不可用，请确认已安装 mcp SDK: {exc}")

        command = str(getattr(spec, "command", "") or "").strip()
        if not command:
            raise ValueError(f"stdio MCP '{spec.name}' 缺少 command 配置")

        args = [str(item) for item in (getattr(spec, "args", None) or [])]
        env = self._build_env(getattr(spec, "env", None) or {})
        cwd = self._resolve_cwd(getattr(spec, "cwd", "") or "", getattr(spec, "source_ref", "") or "")

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env,
            cwd=str(cwd) if cwd else None,
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(self._runtime_tool_name(spec), payload)
                return self._render_tool_result(result)

    async def _call_sse_tool(self, spec, payload: Dict[str, Any]) -> str:
        try:
            from mcp import ClientSession  # type: ignore
            from mcp.client.sse import sse_client  # type: ignore
        except Exception as exc:
            raise ValueError(f"sse MCP 运行时不可用，请确认已安装 mcp SDK: {exc}")

        endpoint = str(getattr(spec, "url", "") or "").strip()
        if not endpoint:
            raise ValueError(f"sse MCP '{spec.name}' 缺少 endpoint/url 配置")

        headers = self._string_headers(getattr(spec, "headers", None) or {})
        async with sse_client(endpoint, headers=headers) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(self._runtime_tool_name(spec), payload)
                return self._render_tool_result(result)

    async def _call_streamable_http_tool(self, spec, payload: Dict[str, Any]) -> str:
        endpoint = str(getattr(spec, "url", "") or "").strip()
        if not endpoint:
            raise ValueError(f"streamable_http MCP '{spec.name}' 缺少 endpoint/url 配置")

        try:
            from mcp import ClientSession  # type: ignore
        except Exception as exc:
            raise ValueError(f"streamable_http MCP 运行时不可用，请确认已安装 mcp SDK: {exc}")

        client_factory = None
        client_import_error = None
        try:
            from mcp.client.streamable_http import streamablehttp_client as client_factory  # type: ignore
        except Exception as exc:
            client_import_error = exc
        if client_factory is None:
            try:
                from mcp.client.streamable_http import streamable_http_client as client_factory  # type: ignore
            except Exception:
                pass
        if client_factory is None:
            raise ValueError(f"streamable_http MCP client 不可用: {client_import_error}")

        headers = self._string_headers(getattr(spec, "headers", None) or {})
        async with client_factory(endpoint, headers=headers) as streams:
            if isinstance(streams, tuple):
                read_stream, write_stream = streams[0], streams[1]
            else:
                raise ValueError("streamable_http MCP client 返回了无法识别的连接对象")
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(self._runtime_tool_name(spec), payload)
                return self._render_tool_result(result)

    @staticmethod
    def _runtime_tool_name(spec) -> str:
        return str(getattr(spec, "tool_name", "") or getattr(spec, "name", "") or "").strip()

    @staticmethod
    def _string_headers(raw_headers: Dict[str, Any]) -> Dict[str, str]:
        return {
            str(key).strip(): str(value).strip()
            for key, value in (raw_headers or {}).items()
            if str(key).strip() and value is not None
        }

    @staticmethod
    def _build_env(raw_env: Dict[str, Any]) -> Dict[str, str]:
        env = dict(os.environ)
        for key, value in (raw_env or {}).items():
            key_text = str(key).strip()
            if not key_text:
                continue
            env[key_text] = str(value)
        return env

    @staticmethod
    def _resolve_cwd(raw_cwd: str, source_ref: str) -> Path | None:
        cwd_text = str(raw_cwd or "").strip()
        if not cwd_text:
            return None
        candidate = Path(cwd_text)
        if candidate.is_absolute():
            return candidate

        project_candidate = (_project_root() / candidate).resolve()
        if project_candidate.exists():
            return project_candidate

        if source_ref:
            source_path = Path(str(source_ref))
            if source_path.exists():
                source_candidate = (source_path.parent / candidate).resolve()
                if source_candidate.exists():
                    return source_candidate

        return project_candidate

    def _render_tool_result(self, result: Any) -> str:
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            rendered = self._render_content_items(result.get("content"))
            if rendered:
                return rendered
            structured = result.get("structuredContent") or result.get("structured_content")
            if structured is not None:
                return json.dumps(structured, ensure_ascii=False, indent=2)
            return json.dumps(result, ensure_ascii=False, indent=2)

        content = getattr(result, "content", None)
        rendered = self._render_content_items(content)
        if rendered:
            return rendered

        structured = getattr(result, "structuredContent", None)
        if structured is None:
            structured = getattr(result, "structured_content", None)
        if structured is not None:
            return json.dumps(structured, ensure_ascii=False, indent=2)

        data = getattr(result, "data", None)
        if data is not None:
            return json.dumps(data, ensure_ascii=False, indent=2)

        return str(result)

    def _render_content_items(self, items: Any) -> str:
        if not items:
            return ""
        if isinstance(items, (str, bytes)):
            return str(items)
        if not isinstance(items, Iterable):
            return ""

        parts = []
        for item in items:
            if item is None:
                continue
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                item_type = str(item.get("type", "")).strip().lower()
                if item_type == "text" and item.get("text") is not None:
                    parts.append(str(item.get("text")))
                    continue
                if item.get("text") is not None:
                    parts.append(str(item.get("text")))
                    continue
                if item.get("content") is not None:
                    parts.append(str(item.get("content")))
                    continue
                parts.append(json.dumps(item, ensure_ascii=False))
                continue

            item_type = str(getattr(item, "type", "") or "").strip().lower()
            text = getattr(item, "text", None)
            if item_type == "text" and text is not None:
                parts.append(str(text))
                continue
            if text is not None:
                parts.append(str(text))
                continue
            content = getattr(item, "content", None)
            if content is not None:
                parts.append(str(content))
                continue
            parts.append(str(item))
        return "\n".join(part for part in parts if str(part).strip())


_mcp_runtime_singleton: MCPRuntimeService | None = None


def get_mcp_runtime() -> MCPRuntimeService:
    global _mcp_runtime_singleton
    if _mcp_runtime_singleton is None:
        _mcp_runtime_singleton = MCPRuntimeService()
    return _mcp_runtime_singleton
