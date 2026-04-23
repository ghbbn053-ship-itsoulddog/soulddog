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
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    reasoning_mode: Optional[str] = "standard"
    show_thinking: Optional[bool] = False


@router.get("/available")
async def get_available_models():
    return {
        "success": True,
        "providers": [
            {
                "provider": "qwen",
                "models": ["qwen-plus", "qwen-max", "qwen-turbo"],
                "default_model": os.getenv("QWEN_MODEL", "qwen-plus"),
                "supports_custom_endpoint": False,
                "supports_reasoning": False,
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
                "supports_custom_endpoint": True,
                "supports_reasoning": True,
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
        return {
            "success": True,
            "provider": "qwen",
            "model": os.getenv("QWEN_MODEL", "qwen-plus"),
            "api_base": "",
            "api_key_masked": "",
            "reasoning_mode": "standard",
            "show_thinking": False,
        }
    api_key = pref.get("api_key") or ""
    masked = ""
    if api_key:
        masked = f"{api_key[:4]}***{api_key[-4:]}" if len(api_key) >= 8 else "***"
    return {
        "success": True,
        "provider": pref.get("provider", "qwen"),
        "model": pref.get("model") or os.getenv("QWEN_MODEL", "qwen-plus"),
        "api_base": pref.get("api_base", ""),
        "api_key_masked": masked,
        "reasoning_mode": pref.get("reasoning_mode", "standard"),
        "show_thinking": bool(pref.get("show_thinking", False)),
    }


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
        {
            "provider": provider,
            "model": model_name,
            "api_base": (payload.api_base or "").strip(),
            "api_key": payload.api_key if payload.api_key is not None else None,
            "reasoning_mode": (payload.reasoning_mode or "standard").strip().lower(),
            "show_thinking": bool(payload.show_thinking),
        },
    )

    return {"success": True, "provider": provider, "model": model_name}
