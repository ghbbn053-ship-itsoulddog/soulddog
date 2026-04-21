"""
模型管理 API
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.runtime import session_store
from app.security import enforce_username_isolation

router = APIRouter(prefix="/api/models", tags=["模型管理"])


class ModelPreferenceRequest(BaseModel):
    username: str
    provider: str
    model: Optional[str] = None


@router.get("/available")
async def get_available_models():
    return {
        "success": True,
        "providers": [
            {
                "provider": "qwen",
                "models": ["qwen-plus", "qwen-max", "qwen-turbo"],
                "default_model": os.getenv("QWEN_MODEL", "qwen-plus"),
            },
            {
                "provider": "litellm",
                "models": [
                    "gpt-4o",
                    "claude-3-5-sonnet",
                    "deepseek-chat",
                    "qwen-max",
                    "ollama/llama3",
                ],
                "default_model": os.getenv("LITELLM_MODEL", "qwen-plus"),
            },
        ],
        "active": {
            "provider": os.getenv("MODEL_PROVIDER", "qwen"),
            "model": os.getenv("LITELLM_MODEL", os.getenv("QWEN_MODEL", "qwen-plus")),
        },
    }


@router.get("/preference/{username}")
async def get_user_model_preference(username: str, http_request: Request):
    enforce_username_isolation(http_request, username)
    pref = session_store.get_user_model_preference(username)
    if not pref:
        return {"success": True, "provider": "qwen", "model": os.getenv("QWEN_MODEL", "qwen-plus")}
    return {"success": True, **pref}


@router.post("/preference")
async def set_user_model_preference(payload: ModelPreferenceRequest, http_request: Request):
    enforce_username_isolation(http_request, payload.username)

    provider = (payload.provider or "").strip().lower()
    if provider not in {"qwen", "litellm"}:
        raise HTTPException(status_code=400, detail="provider 仅支持 qwen / litellm")

    model_name = (payload.model or "").strip()
    if not model_name:
        model_name = os.getenv("QWEN_MODEL", "qwen-plus") if provider == "qwen" else os.getenv("LITELLM_MODEL", "qwen-plus")

    session_store.set_user_model_preference(
        payload.username,
        {"provider": provider, "model": model_name},
    )

    return {"success": True, "provider": provider, "model": model_name}
