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

    if isinstance(payload, list):
        tools = payload
    else:
        tools = payload.get("tools") if isinstance(payload, dict) else None
    if not isinstance(tools, list) or not tools:
        raise HTTPException(status_code=400, detail="配置格式错误：缺少 tools 数组")

    # 基础校验
    valid_tools = []
    for it in tools:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name", "")).strip()
        kind = str(it.get("kind", "python")).strip().lower() or "python"
        if not name:
            continue
        if kind == "python":
            if not str(it.get("module_path", "")).strip() or not str(it.get("func_name", "")).strip():
                continue
        elif kind == "http":
            if not str(it.get("url", "")).strip():
                continue
        else:
            continue
        valid_tools.append(it)

    if not valid_tools:
        raise HTTPException(status_code=400, detail="无有效工具配置")

    cfg = Path(__file__).resolve().parents[1] / "mcp" / "external_tools.json"
    existing = {}
    if cfg.exists():
        try:
            existing = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing_tools = existing.get("tools") if isinstance(existing, dict) else None
    if not isinstance(existing_tools, list):
        existing_tools = []

    by_name = {str(t.get("name", "")).strip(): t for t in existing_tools if isinstance(t, dict)}
    for t in valid_tools:
        by_name[str(t.get("name", "")).strip()] = t

    merged_tools = [v for k, v in by_name.items() if k]
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"tools": merged_tools}, ensure_ascii=False, indent=2), encoding="utf-8")

    registry = reload_mcp_registry()
    return {
        "success": True,
        "imported": len(valid_tools),
        "total_tools": len(registry.list_tools()),
        "config_file": str(cfg),
    }
