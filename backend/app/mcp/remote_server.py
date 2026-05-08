from contextvars import ContextVar
from typing import Any, Dict

from app.models.base import SessionLocal
from app.services import get_mcp_registry
from app.services.agent_access import get_agent_access_service


EDUCATION_CAPABILITY_PREFIXES = (
    "grade.",
    "schedule.",
    "academic_progress.",
    "training_plan.",
    "exam.",
    "personal_info.",
    "course_selection.",
)

_current_identity: ContextVar[Dict[str, Any] | None] = ContextVar("remote_mcp_identity", default=None)


def _tool_scope(item: dict) -> str:
    return str(item.get("service_scope") or "").strip() or (
        "shared_remote_service" if item.get("kind") == "http" else "web_internal_service"
    )


def set_remote_mcp_identity(identity: Dict[str, Any] | None):
    return _current_identity.set(identity)


def reset_remote_mcp_identity(token) -> None:
    _current_identity.reset(token)


def _get_current_identity() -> Dict[str, Any]:
    identity = _current_identity.get()
    if not identity:
        raise ValueError("缺少有效的 Agent Access Token")
    return identity


def _get_current_username() -> str:
    identity = _get_current_identity()
    owner_username = str(identity.get("owner_username") or "").strip()
    if not owner_username:
        raise ValueError("Agent Token 无法解析所属用户")
    return owner_username


def _needs_education_binding(tool_meta: dict) -> bool:
    capabilities = tool_meta.get("capabilities") or []
    return any(str(capability).startswith(EDUCATION_CAPABILITY_PREFIXES) for capability in capabilities)


async def _call_bound_tool(tool_name: str, params: Dict[str, Any] | None = None) -> str:
    registry = get_mcp_registry()
    if not registry.has_tool(tool_name):
        raise ValueError(f"工具 '{tool_name}' 不存在")

    username = _get_current_username()
    tool_meta = registry.get_tool_meta(tool_name) or {}
    needs_education_binding = _needs_education_binding(tool_meta)
    if needs_education_binding:
        db = SessionLocal()
        try:
            if not get_agent_access_service().has_active_binding(db, username, "education"):
                raise ValueError("教务能力当前不可用：既没有有效缓存，也没有可用登录会话，请先在 Web 端同步一次教务数据")
        finally:
            db.close()

    return await registry.call_tool(tool_name, username, params or {})


def _build_remote_server():
    from mcp.server.fastmcp import FastMCP

    remote_mcp_server = FastMCP(
        "soulddog-platform-remote",
        streamable_http_path="/",
        sse_path="/",
    )

    @remote_mcp_server.tool()
    async def query_grades(semester: str = "") -> str:
        params: Dict[str, Any] = {}
        if semester:
            params["semester"] = semester
        return await _call_bound_tool("query_grades", params)

    @remote_mcp_server.tool()
    async def query_schedule(semester: str = "") -> str:
        params: Dict[str, Any] = {}
        if semester:
            params["semester"] = semester
        return await _call_bound_tool("query_schedule", params)

    @remote_mcp_server.tool()
    async def query_academic_progress() -> str:
        return await _call_bound_tool("query_academic_progress")

    @remote_mcp_server.tool()
    async def query_training_plan(semester: str = "") -> str:
        params: Dict[str, Any] = {}
        if semester:
            params["semester"] = semester
        return await _call_bound_tool("query_training_plan", params)

    @remote_mcp_server.tool()
    async def query_exam_schedule(semester: str = "") -> str:
        params: Dict[str, Any] = {}
        if semester:
            params["semester"] = semester
        return await _call_bound_tool("query_exam_schedule", params)

    @remote_mcp_server.tool()
    async def query_personal_info() -> str:
        return await _call_bound_tool("query_personal_info")

    @remote_mcp_server.tool()
    async def query_weather(location: str = "") -> str:
        params: Dict[str, Any] = {}
        if location:
            params["location"] = location
        return await _call_bound_tool("query_weather", params)

    @remote_mcp_server.tool()
    async def query_general_electives(elective_type: str = "tsk") -> str:
        params: Dict[str, Any] = {}
        if elective_type:
            params["elective_type"] = elective_type
        return await _call_bound_tool("query_general_electives", params)

    return remote_mcp_server


def create_remote_mcp_server():
    return _build_remote_server()
