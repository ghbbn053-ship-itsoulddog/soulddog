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
    provider_label: Optional[str] = None
    model: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    reasoning_mode: Optional[str] = "standard"
    show_thinking: Optional[bool] = False


PROVIDER_CATALOG = [
    {
        "provider": "qwen",
        "display_name": "通义千问",
        "category": "official",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo"],
        "default_model": os.getenv("QWEN_MODEL", "qwen-plus"),
        "supports_custom_endpoint": False,
        "supports_custom_model": False,
        "supports_reasoning": False,
        "preset_api_base": "",
        "endpoint_hint": "平台内置直连，无需单独填写",
    },
    {
        "provider": "openai_compatible",
        "display_name": "OpenAI 兼容",
        "category": "compatible",
        "models": ["gpt-4.1-mini", "gpt-4o", "claude-3-7-sonnet", "deepseek-chat", "qwen-max"],
        "default_model": os.getenv("LITELLM_MODEL", "gpt-4.1-mini"),
        "supports_custom_endpoint": True,
        "supports_custom_model": True,
        "supports_reasoning": True,
        "preset_api_base": "https://api.openai.com/v1",
        "endpoint_hint": "适合官方 OpenAI 或任何兼容 /v1/chat/completions 的服务",
    },
    {
        "provider": "openrouter",
        "display_name": "OpenRouter",
        "category": "compatible",
        "models": ["openai/gpt-4.1-mini", "anthropic/claude-3.7-sonnet", "deepseek/deepseek-chat", "google/gemini-2.5-pro-preview"],
        "default_model": "openai/gpt-4.1-mini",
        "supports_custom_endpoint": True,
        "supports_custom_model": True,
        "supports_reasoning": True,
        "preset_api_base": "https://openrouter.ai/api/v1",
        "endpoint_hint": "统一接多厂商模型，模型名通常带厂商前缀",
    },
    {
        "provider": "siliconflow",
        "display_name": "SiliconFlow",
        "category": "compatible",
        "models": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct", "meta-llama/Llama-3.3-70B-Instruct"],
        "default_model": "deepseek-ai/DeepSeek-V3",
        "supports_custom_endpoint": True,
        "supports_custom_model": True,
        "supports_reasoning": True,
        "preset_api_base": "https://api.siliconflow.cn/v1",
        "endpoint_hint": "国内常见 OpenAI 兼容接入方式",
    },
    {
        "provider": "deepseek",
        "display_name": "DeepSeek",
        "category": "compatible",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
        "supports_custom_endpoint": True,
        "supports_custom_model": True,
        "supports_reasoning": True,
        "preset_api_base": "https://api.deepseek.com/v1",
        "endpoint_hint": "官方 DeepSeek API",
    },
    {
        "provider": "ollama",
        "display_name": "Ollama",
        "category": "local",
        "models": ["llama3.1:8b", "qwen2.5:7b", "deepseek-r1:8b", "mistral:7b"],
        "default_model": "llama3.1:8b",
        "supports_custom_endpoint": True,
        "supports_custom_model": True,
        "supports_reasoning": False,
        "preset_api_base": "http://127.0.0.1:11434/v1",
        "endpoint_hint": "本地模型，通常通过 OpenAI 兼容插件层接入",
    },
]


def _provider_alias_to_runtime(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized == "qwen":
        return "qwen"
    return "litellm"


def _find_provider(provider: str) -> dict | None:
    normalized = (provider or "").strip().lower()
    for item in PROVIDER_CATALOG:
        if item["provider"] == normalized:
            return item
    return None


@router.get("/available")
async def get_available_models():
    return {
        "success": True,
        "providers": PROVIDER_CATALOG,
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
            "provider_label": "通义千问",
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
        "provider_label": pref.get("provider_label") or pref.get("provider", "qwen"),
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
    provider_meta = _find_provider(provider)
    if provider_meta is None:
        raise HTTPException(status_code=400, detail="provider 不在支持列表内")
    runtime_provider = _provider_alias_to_runtime(provider)

    model_name = (payload.model or "").strip()
    if not model_name:
        model_name = str(provider_meta.get("default_model") or "").strip()

    session_store.set_user_model_preference(
        payload.username,
        {
            "provider": provider,
            "runtime_provider": runtime_provider,
            "provider_label": payload.provider_label or provider_meta.get("display_name") or provider,
            "model": model_name,
            "api_base": (payload.api_base or str(provider_meta.get("preset_api_base") or "")).strip(),
            "api_key": payload.api_key if payload.api_key is not None else None,
            "reasoning_mode": (payload.reasoning_mode or "standard").strip().lower(),
            "show_thinking": bool(payload.show_thinking),
        },
    )

    return {"success": True, "provider": provider, "runtime_provider": runtime_provider, "model": model_name}
