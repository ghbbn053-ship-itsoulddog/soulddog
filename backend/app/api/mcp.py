"""
MCP HTTP API - 通过HTTP提供MCP服务
允许远程调用MCP工具，支持Web端和其他客户端
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
import logging

from app.services import get_mcp_registry

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


@router.get("/tools")
async def list_tools():
    """列出所有可用的MCP工具"""
    registry = get_mcp_registry()
    if registry is None:
        return {"success": False, "tools": [], "error": "MCP registry 不可用"}
    return {
        "success": True,
        "tools": registry.list_tools(),
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
