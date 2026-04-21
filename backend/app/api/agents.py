"""
Agent Runtime API
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.security import enforce_username_isolation
from app.services.agent_runtime import get_agent_runtime

router = APIRouter(prefix="/api/agents", tags=["Agent Runtime"])


class AgentRunRequest(BaseModel):
    username: str
    framework: str = "openai_agents"
    message: str


@router.get("/frameworks")
async def list_frameworks():
    runtime = get_agent_runtime()
    return {"success": True, "frameworks": runtime.available_frameworks()}


@router.post("/run")
async def run_agent(payload: AgentRunRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)
    runtime = get_agent_runtime()
    session_store = getattr(http_request.app.state, "session_store", None)
    result = runtime.run(
        username=payload.username,
        message=payload.message,
        framework=payload.framework,
        session_store=session_store,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "agent 运行失败"))
    return {"success": True, **result}
