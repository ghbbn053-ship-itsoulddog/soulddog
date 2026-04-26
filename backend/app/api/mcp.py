"""
MCP HTTP API - 通过HTTP提供MCP服务
允许远程调用MCP工具，支持Web端和其他客户端
"""

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, Any
import logging
import json
from pathlib import Path

from app.services import get_mcp_registry
from app.services.mcp_registry import reload_mcp_registry
from app.services.mcp_manager import get_mcp_manager
from app.security import enforce_username_isolation

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
async def call_tool(tool_name: str, request: MCPToolRequest):
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
        result = await registry.call_tool(tool_name, request.username, request.params)
        
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
async def get_tool_schema(tool_name: str):
    """获取工具的JSON Schema"""
    registry = get_mcp_registry()
    if registry is None:
        raise HTTPException(status_code=503, detail="MCP registry 不可用")

    if not registry.has_tool(tool_name):
        raise HTTPException(status_code=404, detail="工具不存在")

    schema = registry.get_tool_schema(tool_name)
    return schema or {"error": "Schema not found"}


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
