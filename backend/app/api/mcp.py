"""
MCP HTTP API - 通过HTTP提供MCP服务
允许远程调用MCP工具，支持Web端和其他客户端
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
import logging

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


# 工具映射表
TOOLS_MAP = {
    "query_grades": "app.mcp.tools:query_grades",
    "query_schedule": "app.mcp.tools:query_schedule",
    "query_academic_progress": "app.mcp.tools:query_academic_progress",
    "query_training_plan": "app.mcp.tools:query_training_plan",
    "query_exam_schedule": "app.mcp.tools:query_exam_schedule",
    "query_personal_info": "app.mcp.tools:query_personal_info",
}


@router.get("/tools")
async def list_tools():
    """列出所有可用的MCP工具"""
    return {
        "success": True,
        "tools": [
            {
                "name": "query_grades",
                "description": "查询学生成绩",
                "parameters": {
                    "username": {"type": "string", "required": True, "description": "学号"},
                    "semester": {"type": "string", "required": False, "description": "学期，如2024-2025-1"}
                }
            },
            {
                "name": "query_schedule",
                "description": "查询课程表",
                "parameters": {
                    "username": {"type": "string", "required": True, "description": "学号"},
                    "semester": {"type": "string", "required": False, "description": "学期"}
                }
            },
            {
                "name": "query_academic_progress",
                "description": "查询学业进度和学分情况",
                "parameters": {
                    "username": {"type": "string", "required": True, "description": "学号"}
                }
            },
            {
                "name": "query_training_plan",
                "description": "查询培养方案",
                "parameters": {
                    "username": {"type": "string", "required": True, "description": "学号"}
                }
            },
            {
                "name": "query_exam_schedule",
                "description": "查询考试安排",
                "parameters": {
                    "username": {"type": "string", "required": True, "description": "学号"},
                    "semester": {"type": "string", "required": False, "description": "学期"}
                }
            },
            {
                "name": "query_personal_info",
                "description": "查询个人基本信息",
                "parameters": {
                    "username": {"type": "string", "required": True, "description": "学号"}
                }
            }
        ]
    }


@router.post("/tools/{tool_name}", response_model=MCPToolResponse)
async def call_tool(tool_name: str, request: MCPToolRequest):
    """
    调用MCP工具
    
    Args:
        tool_name: 工具名称
        request: 包含username和params的请求体
    """
    if tool_name not in TOOLS_MAP:
        raise HTTPException(
            status_code=404,
            detail=f"工具 '{tool_name}' 不存在，可用工具: {list(TOOLS_MAP.keys())}"
        )
    
    try:
        # 动态导入工具函数
        module_path, func_name = TOOLS_MAP[tool_name].split(":")
        import importlib
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        
        # 构建参数
        params = {"username": request.username}
        params.update(request.params)
        
        # 调用工具（异步）
        import asyncio
        result = await func(**params)
        
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
    if tool_name not in TOOLS_MAP:
        raise HTTPException(status_code=404, detail="工具不存在")
    
    schemas = {
        "query_grades": {
            "name": "query_grades",
            "description": "查询学生成绩",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "学号"
                    },
                    "semester": {
                        "type": "string",
                        "description": "学期，如2024-2025-1"
                    }
                },
                "required": ["username"]
            }
        },
        "query_schedule": {
            "name": "query_schedule",
            "description": "查询课程表",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "学号"
                    },
                    "semester": {
                        "type": "string",
                        "description": "学期"
                    }
                },
                "required": ["username"]
            }
        }
    }
    
    return schemas.get(tool_name, {"error": "Schema not found"})
