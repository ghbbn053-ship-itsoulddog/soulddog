"""
Agent 运行时服务（框架可插拔）。

当前策略：
- 主推荐：OpenAI Agents SDK（高活跃、轻量、MCP友好）
- 兼容入口：LangGraph（高星、生产编排能力强）
"""

from __future__ import annotations

import importlib.util
import logging
import os
from typing import Any, Dict, List

from app.services import get_model_provider_for_user

logger = logging.getLogger(__name__)


class AgentRuntimeService:
    def available_frameworks(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "openai_agents",
                "name": "OpenAI Agents SDK",
                "recommended": True,
                "available": self._has_openai_agents(),
                "requires": ["openai-agents", "OPENAI_API_KEY"],
            },
            {
                "id": "langgraph",
                "name": "LangGraph",
                "recommended": False,
                "available": self._has_langgraph(),
                "requires": ["langgraph"],
            },
        ]

    def run(self, username: str, message: str, framework: str, session_store) -> Dict[str, Any]:
        fw = (framework or "openai_agents").strip().lower()
        if fw == "openai_agents":
            result = self._run_openai_agents(message)
            if result.get("success"):
                return result
            logger.warning("openai_agents 不可用，降级统一模型层: %s", result.get("message"))
            return self._fallback_chat(username, message, session_store, fw, result.get("message", ""))

        if fw == "langgraph":
            result = self._run_langgraph_placeholder(message)
            if result.get("success"):
                return result
            logger.warning("langgraph 未启用实现，降级统一模型层: %s", result.get("message"))
            return self._fallback_chat(username, message, session_store, fw, result.get("message", ""))

        return self._fallback_chat(username, message, session_store, fw, "未知 framework")

    @staticmethod
    def _has_openai_agents() -> bool:
        return importlib.util.find_spec("agents") is not None

    @staticmethod
    def _has_langgraph() -> bool:
        return importlib.util.find_spec("langgraph") is not None

    def _run_openai_agents(self, message: str) -> Dict[str, Any]:
        if not self._has_openai_agents():
            return {"success": False, "message": "openai-agents 未安装"}
        if not os.getenv("OPENAI_API_KEY"):
            return {"success": False, "message": "OPENAI_API_KEY 未配置"}
        try:
            from agents import Agent, Runner  # type: ignore

            agent = Agent(
                name="CampusRouter",
                instructions=(
                    "你是校园AI助手，优先准确、简洁回答。"
                    "涉及具体教务数据时明确指出需要调用本系统工具链。"
                ),
            )

            run_sync = getattr(Runner, "run_sync", None)
            if callable(run_sync):
                result = run_sync(agent, input=message)
            else:
                return {"success": False, "message": "openai-agents 版本不兼容：缺少 Runner.run_sync"}

            final_output = getattr(result, "final_output", None)
            content = str(final_output or "").strip()
            if not content:
                content = "本轮 Agent 未返回有效内容。"

            return {
                "success": True,
                "content": content,
                "framework": "openai_agents",
                "usage": {},
            }
        except Exception as e:
            return {"success": False, "message": f"openai_agents 运行失败: {e}"}

    def _run_langgraph_placeholder(self, message: str) -> Dict[str, Any]:
        if not self._has_langgraph():
            return {"success": False, "message": "langgraph 未安装"}
        # 占位：当前先确认依赖可用并保留接入位，不破坏现有链路。
        return {"success": False, "message": "langgraph 运行图尚未启用，已回退统一模型层"}

    @staticmethod
    def _fallback_chat(username: str, message: str, session_store, framework: str, reason: str) -> Dict[str, Any]:
        model_svc = get_model_provider_for_user(username, session_store)
        result = model_svc.chat([{"role": "user", "content": message}])
        if result.get("success"):
            return {
                "success": True,
                "content": result.get("content", ""),
                "framework": f"{framework}:fallback_model_provider",
                "fallback_reason": reason,
                "usage": result.get("usage", {}),
            }
        return {
            "success": False,
            "message": result.get("message", "模型服务不可用"),
            "framework": f"{framework}:fallback_model_provider",
            "fallback_reason": reason,
        }


_agent_runtime_singleton: AgentRuntimeService | None = None


def get_agent_runtime() -> AgentRuntimeService:
    global _agent_runtime_singleton
    if _agent_runtime_singleton is None:
        _agent_runtime_singleton = AgentRuntimeService()
    return _agent_runtime_singleton
