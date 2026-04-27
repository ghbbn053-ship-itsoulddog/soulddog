"""
MCP HTTP API - 通过HTTP提供MCP服务
允许远程调用MCP工具，支持Web端和其他客户端
"""

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, Any
import logging
import json
from pathlib import Path

from app.services import get_mcp_registry
from app.services.mcp_registry import reload_mcp_registry
from app.services.mcp_manager import get_mcp_manager
from app.models import get_db
from sqlalchemy.orm import Session
from app.security_agent import resolve_agent_identity
from app.security import enforce_username_isolation
from app.services.agent_access import get_agent_access_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["MCP"])


class MCPToolRequest(BaseModel):
    """MCP工具调用请求"""
    username: str
    params: dict = {}


class MCPToolResponse(BaseModel):
    """MCP工具调用响应"""
    success: bool
    tool: str
    result: str
    error: Optional[str] = None


class MCPImportUrlRequest(BaseModel):
    username: str
    url: str


class MCPToolToggleRequest(BaseModel):
    username: str
    enabled: bool


class MCPToolDeleteRequest(BaseModel):
    username: str


EDUCATION_CAPABILITY_PREFIXES = (
    "grade.",
    "schedule.",
    "academic_progress.",
    "training_plan.",
    "exam.",
    "personal_info.",
)


def _tool_boundary(item: dict) -> str:
    return str(item.get("execution_boundary") or "").strip() or (
        "remote_service" if item.get("kind") == "http" else "hosted_web"
    )


def _tool_scope(item: dict) -> str:
    return str(item.get("service_scope") or "").strip() or (
        "shared_remote_service" if item.get("kind") == "http" else "web_internal_service"
    )


def _resolve_call_identity(
    http_request: Request,
    db: Session,
    requested_username: str,
    tool_meta: dict,
) -> tuple[str, str]:
    agent_identity = resolve_agent_identity(http_request, db)
    if agent_identity:
        owner_username = str(agent_identity.get("owner_username") or "").strip()
        if not owner_username:
            raise HTTPException(status_code=401, detail="Agent Token 无法解析所属用户")

        allowed_boundaries = set(
            (((agent_identity.get("scope_json") or {}).get("mcp") or {}).get("allowed_boundaries") or [])
        )
        boundary = _tool_boundary(tool_meta)
        if allowed_boundaries and boundary not in allowed_boundaries:
            raise HTTPException(status_code=403, detail=f"当前 Agent Token 无权调用 {boundary} 类型能力")

        capabilities = tool_meta.get("capabilities") or []
        service_scope = _tool_scope(tool_meta)
        if service_scope == "web_internal_service" or any(
            str(capability).startswith(EDUCATION_CAPABILITY_PREFIXES) for capability in capabilities
        ):
            if not get_agent_access_service().has_active_binding(db, owner_username, "education"):
                raise HTTPException(status_code=403, detail="教务服务绑定未激活，请先在 Web 端重新完成教务系统登录")

        return owner_username, "agent"

    enforce_username_isolation(http_request, requested_username)
    return requested_username, "web"


def _sanitize_agent_params(http_request: Request, db: Session, params: Optional[dict[str, Any]]) -> dict[str, Any]:
    sanitized = dict(params or {})
    if resolve_agent_identity(http_request, db):
        sanitized.pop("username", None)
    return sanitized


def _sanitize_agent_schema(http_request: Request, db: Session, schema: dict[str, Any]) -> dict[str, Any]:
    if not resolve_agent_identity(http_request, db):
        return schema

    input_schema = dict(schema.get("inputSchema") or {})
    properties = dict(input_schema.get("properties") or {})
    properties.pop("username", None)

    required = [
        item for item in list(input_schema.get("required") or [])
        if item != "username"
    ]

    input_schema["properties"] = properties
    input_schema["required"] = required
    sanitized = dict(schema)
    sanitized["inputSchema"] = input_schema
    return sanitized


@router.get("/service-catalog")
async def service_catalog():
    """
    平台托管能力目录：
    - Web 平台内部能力
    - 可对外提供给 OpenClaw / Claude Desktop / 其他 Agent 的远程能力
    """
    registry = get_mcp_registry()
    tools = registry.list_tools()
    hosted_web_tools = [item for item in tools if _tool_boundary(item) == "hosted_web"]
    remote_tools = [item for item in tools if _tool_boundary(item) == "remote_service"]
    agent_local_only = [item for item in tools if _tool_boundary(item) == "agent_local_only"]
    return {
        "success": True,
        "service_positioning": {
            "web_platform": "面向 Web 用户的托管知识库与对话平台，只调用平台可托管远程能力",
            "agent_integration": "面向 OpenClaw / Claude Desktop / 其他 Agent 的远程能力服务目录",
        },
        "recommended_split": {
            "hosted_web_tools": len(hosted_web_tools),
            "remote_agent_services": len(remote_tools),
            "agent_local_only": len(agent_local_only),
        },
        "groups": {
            "hosted_web": hosted_web_tools,
            "remote_service": remote_tools,
            "agent_local_only": agent_local_only,
        },
        "remote_mcp_entrypoints": [
            {
                "name": "education-mcp-http",
                "description": "通过平台 HTTP API 暴露教务类能力，供外部 Agent 复用",
                "entry": "/api/mcp/tools/{tool_name}",
                "tool_schema": "/api/mcp/tools/{tool_name}/schema",
            },
            {
                "name": "education-mcp-stdio",
                "description": "本仓库内置 stdio MCP server，适合本地 Agent 或受控环境接入",
                "entry": "python backend/mcp_server.py",
            },
        ],
        "tools": tools,
    }


@router.get("/agent/catalog")
async def agent_catalog(request: Request, db: Session = Depends(get_db)):
    identity = resolve_agent_identity(request, db)
    if not identity:
        raise HTTPException(status_code=401, detail="缺少有效的 Agent Access Token")

    registry = get_mcp_registry()
    tools = registry.list_tools()
    allowed_boundaries = set((((identity.get("scope_json") or {}).get("mcp") or {}).get("allowed_boundaries") or []))
    if not allowed_boundaries:
        allowed_boundaries = {"hosted_web", "remote_service"}

    visible_tools = [
        item
        for item in tools
        if _tool_boundary(item) in allowed_boundaries and item.get("capabilities")
    ]
    return {
        "success": True,
        "owner_username": identity.get("owner_username"),
        "token_name": identity.get("token_name"),
        "visible_tools": visible_tools,
        "message": "外部 Agent 不直接登录教务系统，只复用 Web 端用户完成的绑定与授权状态",
    }


@router.get("/tools/{tool_name}/probe")
async def probe_tool(tool_name: str, username: Optional[str] = None, http_request: Request = None):
    """
    轻量探测单个工具是否具备上线条件。
    - 不做真正业务调用
    - 只判断 transport / 配置完备性 / 适用边界
    """
    registry = get_mcp_registry()
    meta = registry.get_tool_meta(tool_name)
    if not meta:
        raise HTTPException(status_code=404, detail="工具不存在")

    if username:
        enforce_username_isolation(http_request, username)

    boundary = _tool_boundary(meta)
    scope = _tool_scope(meta)
    transport = str(meta.get("transport") or meta.get("kind") or "unknown")
    kind = str(meta.get("kind") or "unknown")
    checks: list[dict[str, Any]] = []

    if boundary == "agent_local_only":
        checks.append({"name": "boundary", "ok": False, "detail": "该能力依赖本地 Agent / 本地进程，不适合作为 Web 托管能力开放"})
    else:
        checks.append({"name": "boundary", "ok": True, "detail": f"适用边界：{boundary}"})

    if kind == "python":
        checks.append(
            {
                "name": "runtime_entry",
                "ok": bool(meta.get("module_path")) and bool(meta.get("func_name")),
                "detail": f"module={meta.get('module_path') or '-'} func={meta.get('func_name') or '-'}",
            }
        )
    elif kind in {"http", "streamable_http", "sse"}:
        checks.append(
            {
                "name": "endpoint",
                "ok": bool(meta.get("url")),
                "detail": f"url={meta.get('url') or '-'}",
            }
        )
    elif kind in {"stdio", "command"}:
        checks.append(
            {
                "name": "command",
                "ok": bool(meta.get("command")) and bool(meta.get("tool_name")),
                "detail": f"command={meta.get('command') or '-'} tool={meta.get('tool_name') or '-'}",
            }
        )
    else:
        checks.append({"name": "kind", "ok": False, "detail": f"当前 kind={kind} 不在受支持范围内"})

    checks.append(
        {
            "name": "capabilities",
            "ok": bool(meta.get("capabilities")),
            "detail": f"capabilities={(meta.get('capabilities') or [])}",
        }
    )

    ready = all(item["ok"] for item in checks)
    return {
        "success": True,
        "tool": tool_name,
        "ready": ready,
        "boundary": boundary,
        "service_scope": scope,
        "transport": transport,
        "kind": kind,
        "checks": checks,
        "meta": meta,
    }


@router.get("/tools")
async def list_tools(username: Optional[str] = None, http_request: Request = None):
    """列出所有可用的MCP工具"""
    registry = get_mcp_registry()
    if registry is None:
        return {"success": False, "tools": [], "error": "MCP registry 不可用"}
    imported = []
    if username:
        enforce_username_isolation(http_request, username)
        imported = get_mcp_manager().list_tools(username)
    return {
        "success": True,
        "tools": registry.list_tools(),
        "imported_tools": imported,
    }


@router.post("/tools/{tool_name}", response_model=MCPToolResponse)
async def call_tool(tool_name: str, request: MCPToolRequest, http_request: Request, db: Session = Depends(get_db)):
    """
    调用MCP工具
    
    Args:
        tool_name: 工具名称
        request: 包含username和params的请求体
    """
    registry = get_mcp_registry()
    if registry is None:
        raise HTTPException(status_code=503, detail="MCP registry 不可用")

    if not registry.has_tool(tool_name):
        raise HTTPException(
            status_code=404,
            detail=f"工具 '{tool_name}' 不存在"
        )
    try:
        tool_meta = registry.get_tool_meta(tool_name)
        if not tool_meta:
            raise HTTPException(status_code=404, detail="工具元数据不存在")
        effective_username, _identity_type = _resolve_call_identity(http_request, db, request.username, tool_meta)
        effective_params = _sanitize_agent_params(http_request, db, request.params)
        result = await registry.call_tool(tool_name, effective_username, effective_params)
        
        return MCPToolResponse(
            success=True,
            tool=tool_name,
            result=result
        )
    
    except ValueError as e:
        return MCPToolResponse(
            success=False,
            tool=tool_name,
            result="",
            error=str(e)
        )
    except Exception as e:
        logger.error(f"调用MCP工具 {tool_name} 失败: {e}")
        return MCPToolResponse(
            success=False,
            tool=tool_name,
            result="",
            error=f"工具调用失败: {str(e)}"
        )


@router.get("/tools/{tool_name}/schema")
async def get_tool_schema(tool_name: str, http_request: Request, db: Session = Depends(get_db)):
    """获取工具的JSON Schema"""
    registry = get_mcp_registry()
    if registry is None:
        raise HTTPException(status_code=503, detail="MCP registry 不可用")

    if not registry.has_tool(tool_name):
        raise HTTPException(status_code=404, detail="工具不存在")

    schema = registry.get_tool_schema(tool_name)
    if not schema:
        return {"error": "Schema not found"}
    return _sanitize_agent_schema(http_request, db, schema)


@router.post("/tools/reload")
async def reload_tools():
    """热重载 MCP 工具配置（包括 external_tools.json）"""
    registry = reload_mcp_registry()
    return {"success": True, "tools": registry.list_tools(), "count": len(registry.list_tools())}


@router.post("/tools/import-file")
async def import_mcp_tools_file(
    username: str = Form(...),
    mcp_file: UploadFile = File(...),
    http_request: Request = None,
):
    """
    通过文件导入 MCP 外部工具配置（JSON）。
    支持文件形态：
    - {"tools":[...]}
    - [{...}, {...}]
    """
    enforce_username_isolation(http_request, username)
    filename = (mcp_file.filename or "").lower()
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="仅支持 .json 文件")
    try:
        content = (await mcp_file.read()).decode("utf-8", errors="ignore")
        payload = json.loads(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON 解析失败: {e}")
    manager = get_mcp_manager()
    result = manager.import_from_content(username, content, source_type="file", source_ref=mcp_file.filename or "upload.json")
    registry = reload_mcp_registry()
    return {
        "success": True,
        "imported": result.get("imported", 0),
        "total_tools": len(registry.list_tools()),
        "imported_tools": result.get("tools", []),
        "summary": result.get("summary", {}),
        "items": result.get("items", []),
    }


@router.post("/tools/import-url")
async def import_mcp_tools_url(payload: MCPImportUrlRequest, http_request: Request):
    """
    从 URL 导入 MCP 外部工具配置（JSON）。
    """
    enforce_username_isolation(http_request, payload.username)
    try:
        result = get_mcp_manager().import_from_url(payload.username, payload.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"URL 导入失败: {e}")
    registry = reload_mcp_registry()
    return {
        "success": True,
        "imported": result.get("imported", 0),
        "total_tools": len(registry.list_tools()),
        "imported_tools": result.get("tools", []),
        "summary": result.get("summary", {}),
        "items": result.get("items", []),
        "source": "url",
    }


@router.post("/tools/{tool_name}/enable")
async def set_mcp_enabled(tool_name: str, payload: MCPToolToggleRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    manager = get_mcp_manager()
    try:
        result = manager.set_enabled(payload.username, tool_name, payload.enabled)
        reload_mcp_registry()
        return {"success": True, "tool": result}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="MCP 工具不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {e}")


@router.delete("/tools/{tool_name}")
async def delete_mcp_tool(tool_name: str, payload: MCPToolDeleteRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    ok = get_mcp_manager().delete(payload.username, tool_name)
    if not ok:
        raise HTTPException(status_code=404, detail="MCP 工具不存在")
    reload_mcp_registry()
    return {"success": True}
