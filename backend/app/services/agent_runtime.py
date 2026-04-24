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
from app.core.runtime import get_db
from app.services.workspace_knowledge import get_workspace_knowledge_service

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
        workspace_context = self._build_workspace_context(username, message, session_store)
        if fw == "openai_agents":
            result = self._run_openai_agents(message, workspace_context)
            if result.get("success"):
                return result
            logger.warning("openai_agents 不可用，降级统一模型层: %s", result.get("message"))
            return self._fallback_chat(username, message, session_store, fw, result.get("message", ""), workspace_context)

        if fw == "langgraph":
            result = self._run_langgraph(message, workspace_context)
            if result.get("success"):
                return result
            logger.warning("langgraph 不可用或执行失败，降级统一模型层: %s", result.get("message"))
            return self._fallback_chat(username, message, session_store, fw, result.get("message", ""), workspace_context)

        return self._fallback_chat(username, message, session_store, fw, "未知 framework", workspace_context)

    @staticmethod
    def _has_openai_agents() -> bool:
        return importlib.util.find_spec("agents") is not None

    @staticmethod
    def _has_langgraph() -> bool:
        return importlib.util.find_spec("langgraph") is not None

    def _build_workspace_context(self, username: str, message: str, session_store) -> str:
        db = None
        try:
            db = next(get_db())
            svc = get_workspace_knowledge_service()
            workspaces = svc.list_workspaces(db, username)
            if not workspaces:
                return ""
            selected_id = None
            if session_store:
                pref = session_store.get_user_workspace_preference(username) or {}
                selected_id = pref.get("workspace_id")
            workspace = next((item for item in workspaces if item.id == selected_id), None) or workspaces[0]
            hits = svc.search_workspace(db, username, workspace.id, message, top_k=4)
            if not hits:
                return ""
            return "\n".join(
                [f"[{idx}] {item.get('title', '未知标题')}: {item.get('content', '')}" for idx, item in enumerate(hits, start=1)]
            )
        except Exception as e:
            logger.warning("AgentRuntime 工作区知识加载失败: %s", e)
            return ""
        finally:
            if db:
                db.close()

    def _run_openai_agents(self, message: str, workspace_context: str = "") -> Dict[str, Any]:
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
                    f"\n\n以下是当前工作区知识摘要：\n{workspace_context}" if workspace_context else ""
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

    def _run_langgraph(self, message: str, workspace_context: str = "") -> Dict[str, Any]:
        if not self._has_langgraph():
            return {"success": False, "message": "langgraph 未安装"}
        if not os.getenv("OPENAI_API_KEY"):
            return {"success": False, "message": "OPENAI_API_KEY 未配置（langgraph 需要模型后端）"}
        try:
            from langgraph.graph import START, END, StateGraph  # type: ignore
            from langchain_openai import ChatOpenAI  # type: ignore
            from typing import TypedDict

            class GraphState(TypedDict):
                user_input: str
                output: str

            llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.2)

            def solve_node(state: GraphState) -> GraphState:
                prompt = (
                    "你是校园AI助手，回答简洁准确。"
                    "如果问题涉及具体教务数据，明确提示需要调用本系统教务工具。\\n\\n"
                    f"当前工作区知识：{workspace_context}\\n\\n"
                    f"用户问题：{state.get('user_input', '')}"
                )
                ai_msg = llm.invoke(prompt)
                content = getattr(ai_msg, "content", "") or ""
                return {"user_input": state.get("user_input", ""), "output": str(content).strip()}

            g = StateGraph(GraphState)
            g.add_node("solve", solve_node)
            g.add_edge(START, "solve")
            g.add_edge("solve", END)
            app = g.compile()

            result = app.invoke({"user_input": message, "output": ""})
            content = str(result.get("output", "")).strip() or "本轮 LangGraph 未返回有效内容。"
            return {
                "success": True,
                "content": content,
                "framework": "langgraph",
                "usage": {},
            }
        except RuntimeError as e:
            if "event loop" in str(e).lower():
                return {"success": False, "message": f"langgraph 事件循环冲突: {e}"}
            return {"success": False, "message": f"langgraph 运行失败: {e}"}
        except Exception as e:
            return {"success": False, "message": f"langgraph 运行失败: {e}"}

    @staticmethod
    def _fallback_chat(username: str, message: str, session_store, framework: str, reason: str, workspace_context: str = "") -> Dict[str, Any]:
        model_svc = get_model_provider_for_user(username, session_store)
        messages = []
        if workspace_context:
            messages.append({"role": "system", "content": f"当前工作区知识：\n{workspace_context}"})
        messages.append({"role": "user", "content": message})
        result = model_svc.chat(messages)
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
