"""
统一模型提供层（Model-Agnostic）。

Phase A 目标：
1) 保持现网行为不变（默认走 QwenService）
2) 预留 LiteLLM 接入能力（可选）
3) 对上层暴露统一接口，便于后续多模型切换
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Generator, Any


logger = logging.getLogger(__name__)


class BaseProvider:
    available: bool = False

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict[str, Any]:
        raise NotImplementedError

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        education_context: str = "",
    ) -> Generator[str, None, None]:
        raise NotImplementedError

    def chat_stream_events(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        education_context: str = "",
        reasoning_mode: str = "standard",
        show_thinking: bool = False,
    ) -> Generator[Dict[str, str], None, None]:
        # 默认实现：仅输出答案片段
        for chunk in self.chat_stream(messages, temperature=temperature, education_context=education_context):
            if chunk:
                yield {"type": "content", "content": chunk}

    def chat_with_tools(self, messages: List[Dict], tools_context: Optional[Dict] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def chat_with_rag(
        self,
        question: str,
        context: List[Dict],
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def generate_embedding(self, text: str) -> List[float]:
        raise NotImplementedError


class QwenProvider(BaseProvider):
    """Qwen 适配器（兼容现有实现）。"""

    def __init__(self, model: Optional[str] = None):
        from app.services.qwen_service import get_qwen_service

        self._svc = get_qwen_service()
        if model:
            setattr(self._svc, "model", model)
        self.available = bool(getattr(self._svc, "available", False))

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict[str, Any]:
        return self._svc.chat(messages, temperature=temperature)

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        education_context: str = "",
    ) -> Generator[str, None, None]:
        yield from self._svc.chat_stream(messages, temperature=temperature, education_context=education_context)

    def chat_with_tools(self, messages: List[Dict], tools_context: Optional[Dict] = None) -> Dict[str, Any]:
        return self._svc.chat_with_tools(messages, tools_context=tools_context)

    def chat_with_rag(
        self,
        question: str,
        context: List[Dict],
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        return self._svc.chat_with_rag(
            question=question,
            context=context,
            conversation_history=conversation_history,
        )

    def generate_embedding(self, text: str) -> List[float]:
        return self._svc.generate_embedding(text)


class LiteLLMProvider(BaseProvider):
    """
    LiteLLM 适配器（先支持 chat/chat_stream）。
    工具调用与RAG暂通过统一层回退到 QwenProvider。
    """

    def __init__(self, model: Optional[str] = None, api_base: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.getenv("LITELLM_MODEL", os.getenv("QWEN_MODEL", "qwen-plus"))
        self.api_key = api_key or os.getenv("LITELLM_API_KEY") or os.getenv("QWEN_API_KEY")
        self.api_base = api_base or os.getenv("LITELLM_API_BASE")
        self._completion = None
        self.available = False

        try:
            from litellm import completion

            self._completion = completion
            self.available = True
        except Exception as e:
            logger.warning(f"LiteLLM 不可用，回退默认模型提供层: {e}")
            self.available = False

    def _build_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"model": self.model}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
            kwargs["base_url"] = self.api_base
        return kwargs

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict[str, Any]:
        if not self.available or self._completion is None:
            return {"success": False, "message": "LiteLLM 未就绪"}
        try:
            kwargs = self._build_kwargs()
            resp = self._completion(messages=messages, temperature=temperature, stream=False, **kwargs)
            content = resp.choices[0].message.content or ""
            usage = getattr(resp, "usage", None)
            return {
                "success": True,
                "content": content,
                "usage": {
                    "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                    "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                    "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
                },
            }
        except Exception as e:
            logger.error(f"LiteLLM chat 失败: {e}")
            return {"success": False, "message": f"LiteLLM chat 失败: {e}"}

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        education_context: str = "",
    ) -> Generator[str, None, None]:
        if not self.available or self._completion is None:
            yield "[LiteLLM 未就绪]"
            return

        stream_messages = messages
        if education_context:
            system_ctx = {
                "role": "system",
                "content": (
                    "以下是当前可用的事实与知识，请据此回答用户问题。\n"
                    "回答自然直接，不要机械复述“根据以上数据”。\n"
                    "没有依据就明确说无法确认，不要补虚构细节。\n\n"
                    f"{education_context}"
                ),
            }
            stream_messages = [system_ctx] + messages

        try:
            kwargs = self._build_kwargs()
            resp = self._completion(messages=stream_messages, temperature=temperature, stream=True, **kwargs)
            for chunk in resp:
                try:
                    delta = chunk.choices[0].delta
                    text = getattr(delta, "content", None) or ""
                    if text:
                        yield text
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"LiteLLM chat_stream 失败: {e}")
            yield f"[异常: {e}]"

    def chat_stream_events(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        education_context: str = "",
        reasoning_mode: str = "standard",
        show_thinking: bool = False,
    ) -> Generator[Dict[str, str], None, None]:
        if not self.available or self._completion is None:
            yield {"type": "content", "content": "[LiteLLM 未就绪]"}
            return

        stream_messages = messages
        if education_context:
            system_ctx = {
                "role": "system",
                "content": (
                    "以下是当前可用的事实与知识，请据此回答用户问题。\n"
                    "回答自然直接，不要机械复述“根据以上数据”。\n"
                    "没有依据就明确说无法确认，不要补虚构细节。\n\n"
                    f"{education_context}"
                ),
            }
            stream_messages = [system_ctx] + messages

        try:
            kwargs = self._build_kwargs()
            # 简单推理模式参数（兼容支持该字段的后端；不支持会被忽略）
            if reasoning_mode in {"thinking", "deep"}:
                kwargs["reasoning_effort"] = "high" if reasoning_mode == "deep" else "medium"
            resp = self._completion(messages=stream_messages, temperature=temperature, stream=True, **kwargs)
            for chunk in resp:
                try:
                    delta = chunk.choices[0].delta
                    think = getattr(delta, "reasoning_content", None) or ""
                    text = getattr(delta, "content", None) or ""
                    if show_thinking and think:
                        yield {"type": "thinking", "content": think}
                    if text:
                        yield {"type": "content", "content": text}
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"LiteLLM chat_stream_events 失败: {e}")
            yield {"type": "content", "content": f"[异常: {e}]"}

    def chat_with_tools(self, messages: List[Dict], tools_context: Optional[Dict] = None) -> Dict[str, Any]:
        return {"success": False, "message": "LiteLLM Provider 尚未实现工具调用编排"}

    def chat_with_rag(
        self,
        question: str,
        context: List[Dict],
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        return {"success": False, "message": "LiteLLM Provider 尚未实现 RAG 组合逻辑"}

    def generate_embedding(self, text: str) -> List[float]:
        return []


class UnifiedModelProvider(BaseProvider):
    """
    统一模型层：
    - 主 Provider 由 MODEL_PROVIDER 决定（默认 qwen）
    - 主 Provider 失败时自动回退 QwenProvider（保证可用性）
    """

    def __init__(
        self,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        provider_name = (provider_name or os.getenv("MODEL_PROVIDER", "qwen")).strip().lower()
        self.provider_name = provider_name
        self.primary: BaseProvider
        self.fallback: BaseProvider = QwenProvider(model=model if provider_name == "qwen" else None)

        if provider_name == "litellm":
            self.primary = LiteLLMProvider(model=model, api_base=api_base, api_key=api_key)
        else:
            self.primary = self.fallback

        self.available = bool(getattr(self.primary, "available", False) or getattr(self.fallback, "available", False))

        logger.info(
            "ModelProvider 初始化完成: primary=%s available=%s fallback_available=%s",
            self.provider_name,
            getattr(self.primary, "available", False),
            getattr(self.fallback, "available", False),
        )

    def _fallback_result(self, result: Dict[str, Any], call_name: str, *args, **kwargs):
        if result and result.get("success"):
            return result
        if self.primary is self.fallback:
            return result
        logger.warning("ModelProvider %s 失败，回退 QwenProvider", call_name)
        return getattr(self.fallback, call_name)(*args, **kwargs)

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict[str, Any]:
        result = self.primary.chat(messages, temperature=temperature)
        return self._fallback_result(result, "chat", messages, temperature=temperature)

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        education_context: str = "",
    ) -> Generator[str, None, None]:
        try:
            yielded = False
            for chunk in self.primary.chat_stream(messages, temperature=temperature, education_context=education_context):
                yielded = True
                yield chunk
            if yielded or self.primary is self.fallback:
                return
        except Exception as e:
            logger.warning(f"ModelProvider chat_stream 主通道异常，回退Qwen: {e}")

        yield from self.fallback.chat_stream(messages, temperature=temperature, education_context=education_context)

    def chat_stream_events(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        education_context: str = "",
        reasoning_mode: str = "standard",
        show_thinking: bool = False,
    ) -> Generator[Dict[str, str], None, None]:
        try:
            yielded = False
            if hasattr(self.primary, "chat_stream_events"):
                for event in self.primary.chat_stream_events(
                    messages,
                    temperature=temperature,
                    education_context=education_context,
                    reasoning_mode=reasoning_mode,
                    show_thinking=show_thinking,
                ):
                    yielded = True
                    yield event
            else:
                for chunk in self.primary.chat_stream(messages, temperature=temperature, education_context=education_context):
                    yielded = True
                    if chunk:
                        yield {"type": "content", "content": chunk}
            if yielded or self.primary is self.fallback:
                return
        except Exception as e:
            logger.warning(f"ModelProvider chat_stream_events 主通道异常，回退Qwen: {e}")

        # Qwen 当前无 thinking 事件，作为 content 回退
        for chunk in self.fallback.chat_stream(messages, temperature=temperature, education_context=education_context):
            if chunk:
                yield {"type": "content", "content": chunk}

    def chat_with_tools(self, messages: List[Dict], tools_context: Optional[Dict] = None) -> Dict[str, Any]:
        result = self.primary.chat_with_tools(messages, tools_context=tools_context)
        return self._fallback_result(result, "chat_with_tools", messages, tools_context=tools_context)

    def chat_with_rag(
        self,
        question: str,
        context: List[Dict],
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        result = self.primary.chat_with_rag(question, context, conversation_history=conversation_history)
        return self._fallback_result(
            result,
            "chat_with_rag",
            question,
            context,
            conversation_history=conversation_history,
        )

    def generate_embedding(self, text: str) -> List[float]:
        emb = self.primary.generate_embedding(text)
        if emb:
            return emb
        if self.primary is self.fallback:
            return emb
        return self.fallback.generate_embedding(text)


_model_provider_singleton: Optional[UnifiedModelProvider] = None


def get_model_provider() -> UnifiedModelProvider:
    global _model_provider_singleton
    if _model_provider_singleton is None:
        _model_provider_singleton = UnifiedModelProvider()
    return _model_provider_singleton


def reset_model_provider():
    global _model_provider_singleton
    _model_provider_singleton = None


def get_model_provider_for_user(username: str, session_store) -> UnifiedModelProvider:
    """
    按用户偏好创建 provider（避免全局环境变量污染）。
    """
    pref = session_store.get_user_model_preference(username) if session_store else None
    if not pref:
        return get_model_provider()
    provider = (pref.get("provider") or "qwen").strip().lower()
    model = (pref.get("model") or "").strip() or None
    api_base = (pref.get("api_base") or "").strip() or None
    api_key = (pref.get("api_key") or "").strip() or None
    return UnifiedModelProvider(provider_name=provider, model=model, api_base=api_base, api_key=api_key)
