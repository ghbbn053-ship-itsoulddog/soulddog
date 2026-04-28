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
import re
from datetime import datetime
from typing import Any, Dict, List

from education_options import EducationOptions
from app.services import get_model_provider_for_user
from app.core.runtime import get_db
from app.services.composition_manager import get_composition_manager
from app.services.mcp_registry import get_mcp_registry
from app.services.platform_registry import get_platform_registry_service
from app.services.workspace_knowledge import get_workspace_knowledge_service

logger = logging.getLogger(__name__)


class AgentRuntimeService:
    async def build_chat_runtime_context(
        self,
        username: str,
        message: str,
        session_store,
        workspace_id: int | None = None,
    ) -> Dict[str, Any]:
        runtime_context = self._build_runtime_context(username, message, session_store, workspace_id=workspace_id)
        tool_context, tool_trace = await self._build_tool_context(username, message, runtime_context)
        if tool_context:
            runtime_context["tool_results"] = tool_context
        return {
            "runtime_context": runtime_context,
            "system_context": self._render_runtime_context(runtime_context),
            "tool_results": tool_context,
            "tool_trace": tool_trace,
        }

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

    async def run(self, username: str, message: str, framework: str, session_store, workspace_id: int | None = None) -> Dict[str, Any]:
        fw = (framework or "openai_agents").strip().lower()
        prepared = await self.build_chat_runtime_context(username, message, session_store, workspace_id=workspace_id)
        runtime_context = prepared["runtime_context"]
        tool_trace = prepared["tool_trace"]
        system_context = prepared["system_context"]
        if fw == "openai_agents":
            result = self._run_openai_agents(message, system_context)
            if result.get("success"):
                result["tool_trace"] = tool_trace
                return result
            logger.warning("openai_agents 不可用，降级统一模型层: %s", result.get("message"))
            return self._fallback_chat(username, message, session_store, fw, result.get("message", ""), system_context, tool_trace)

        if fw == "langgraph":
            result = self._run_langgraph(message, system_context)
            if result.get("success"):
                result["tool_trace"] = tool_trace
                return result
            logger.warning("langgraph 不可用或执行失败，降级统一模型层: %s", result.get("message"))
            return self._fallback_chat(username, message, session_store, fw, result.get("message", ""), system_context, tool_trace)

        return self._fallback_chat(username, message, session_store, fw, "未知 framework", system_context, tool_trace)

    @staticmethod
    def _has_openai_agents() -> bool:
        return importlib.util.find_spec("agents") is not None

    @staticmethod
    def _has_langgraph() -> bool:
        return importlib.util.find_spec("langgraph") is not None

    def _build_runtime_context(self, username: str, message: str, session_store, workspace_id: int | None = None) -> Dict[str, Any]:
        db = None
        try:
            db = next(get_db())
            workspace_svc = get_workspace_knowledge_service()
            platform_svc = get_platform_registry_service()
            composition = get_composition_manager().resolved(username)
            workspaces = workspace_svc.list_workspaces(db, username)
            context: Dict[str, Any] = {
                "workspace": None,
                "knowledge_hits": [],
                "skills": [],
                "mcp_tools": [],
                "composition": composition,
                "tool_results": [],
                "time_context": {
                    **EducationOptions.get_time_context(),
                    "now_label": datetime.now().strftime("%Y-%m-%d"),
                },
            }
            selected_id = workspace_id
            if selected_id is None and session_store:
                pref = session_store.get_user_workspace_preference(username) or {}
                selected_id = pref.get("workspace_id")
            if workspaces:
                workspace = next((item for item in workspaces if item.id == selected_id), None) or workspaces[0]
                context["workspace"] = {
                    "id": workspace.id,
                    "name": workspace.name,
                    "slug": workspace.slug,
                }
                context["knowledge_hits"] = workspace_svc.search_workspace(db, username, workspace.id, message, top_k=4)

            skills = platform_svc.list_skills(db, username)
            enabled_skill_names = set(composition.get("skills", []) or [])
            context["skills"] = [
                {
                    "name": skill.name,
                    "description": skill.description or "",
                    "triggers": skill.triggers or [],
                    "enabled": skill.name in enabled_skill_names,
                    "tools": skill.tools or [],
                    "mode": (skill.metadata_json or {}).get("mode", "rule"),
                    "source_type": skill.source_type,
                    "compatibility_level": (skill.metadata_json or {}).get("compatibility_level", "direct"),
                    "compatibility_notes": (skill.metadata_json or {}).get("compatibility_notes", []) or [],
                    "always_on": bool((skill.metadata_json or {}).get("always_on", False)),
                    "capabilities": (skill.metadata_json or {}).get("capabilities", []) or [],
                }
                for skill in skills
                if skill.name in enabled_skill_names
            ]

            mcp_tools = platform_svc.list_mcp_tools(db, username)
            enabled_mcp_names = set(composition.get("mcp_tools", []) or [])
            context["mcp_tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "kind": tool.kind,
                    "enabled": tool.name in enabled_mcp_names,
                    "parameters": (tool.tool_schema or {}).get("parameters", {}),
                    "transport": (tool.metadata_json or {}).get("transport", "python" if tool.kind == "python" else "http"),
                    "source_type": tool.source_type,
                    "compatibility_level": (tool.metadata_json or {}).get("compatibility_level", "direct"),
                    "compatibility_notes": (tool.metadata_json or {}).get("compatibility_notes", []) or [],
                    "capabilities": (tool.metadata_json or {}).get("capabilities", []) or [],
                }
                for tool in mcp_tools
                if tool.name in enabled_mcp_names
            ]
            return context
        except Exception as e:
            logger.warning("AgentRuntime 平台上下文加载失败: %s", e)
            return {
                "workspace": None,
                "knowledge_hits": [],
                "skills": [],
                "mcp_tools": [],
                "composition": {},
                "tool_results": [],
            }
        finally:
            if db:
                db.close()

    @staticmethod
    def _extract_candidate_values(message: str) -> Dict[str, str]:
        semester_match = re.search(r"(20\d{2}-20\d{2}-[12])", message or "")
        week_match = re.search(r"(第?\s*\d{1,2}\s*周)", message or "")
        numeric_match = re.findall(r"\d{4,}", message or "")
        resolved_semester = ""
        try:
            resolved_semester = str(EducationOptions.resolve_semester_reference(message or "") or "").strip()
        except Exception:
            resolved_semester = ""

        lowered = (message or "").lower()
        values: Dict[str, str] = {}
        if semester_match:
            values["semester"] = semester_match.group(1)
        elif resolved_semester:
            values["semester"] = resolved_semester
        if week_match:
            values["week"] = re.sub(r"\s+", "", week_match.group(1))
        elif any(token in lowered for token in ["本周", "这周", "当前周"]):
            values["week"] = "本周"
        if numeric_match:
            values["numeric"] = numeric_match[0]
        return values

    def _map_tool_params(self, message: str, tool_name: str) -> Dict[str, Any]:
        registry = get_mcp_registry()
        schema = registry.get_tool_schema(tool_name) or {}
        props = ((schema.get("inputSchema") or {}).get("properties") or {})
        candidates = self._extract_candidate_values(message)
        params: Dict[str, Any] = {}

        for key in props.keys():
            lowered = str(key).strip().lower()
            if lowered in {"semester", "term", "xnxq"} and candidates.get("semester"):
                params[key] = candidates["semester"]
            elif lowered in {"week", "week_no"} and candidates.get("week"):
                params[key] = candidates["week"]
            elif lowered in {"student_id", "xh"} and candidates.get("numeric"):
                params[key] = candidates["numeric"]
            elif lowered in {"location", "city", "place"}:
                msg = (message or "").strip()
                if msg:
                    location = re.sub(r"^(查(一下)?|查询|看看|帮我查(一下)?|帮我看看)\s*", "", msg)
                    location = re.sub(r"(天气|温度|气温|降雨|预报)", "", location).strip(" ，,。？?")
                    if location:
                        params[key] = location
        return params

    async def _build_tool_context(self, username: str, message: str, runtime_context: Dict[str, Any]) -> tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
        registry = get_mcp_registry()
        skills = runtime_context.get("skills") or []
        enabled_tools = runtime_context.get("mcp_tools") or []
        capability_to_tools: Dict[str, List[str]] = {}
        for tool in enabled_tools:
            tool_name = str(tool.get("name", "")).strip()
            if not tool_name:
                continue
            for capability in tool.get("capabilities") or []:
                cap = str(capability or "").strip()
                if not cap:
                    continue
                capability_to_tools.setdefault(cap, [])
                if tool_name not in capability_to_tools[cap]:
                    capability_to_tools[cap].append(tool_name)
        results: List[Dict[str, str]] = []
        traces: List[Dict[str, Any]] = []
        tried_tools = set()
        execution_candidates: List[Dict[str, Any]] = []

        for skill in skills:
            candidate_tools: List[str] = []
            tool_defs = skill.get("tools") or []
            for tool_def in tool_defs:
                if not isinstance(tool_def, dict):
                    continue
                tool_name = str(tool_def.get("name", "")).strip()
                if tool_name:
                    candidate_tools.append(tool_name)

            for capability in skill.get("capabilities") or []:
                cap = str(capability or "").strip()
                if not cap:
                    continue
                for tool_name in capability_to_tools.get(cap, []):
                    if tool_name not in candidate_tools:
                        candidate_tools.append(tool_name)

            if candidate_tools:
                execution_candidates.append(
                    {
                        "skill": str(skill.get("name", "")).strip() or "unknown",
                        "capabilities": skill.get("capabilities") or [],
                        "tools": candidate_tools,
                    }
                )

        if not execution_candidates:
            for tool in enabled_tools:
                tool_name = str(tool.get("name", "")).strip()
                if not tool_name:
                    continue
                execution_candidates.append(
                    {
                        "skill": "composition",
                        "capabilities": tool.get("capabilities") or [],
                        "tools": [tool_name],
                    }
                )

        for candidate in execution_candidates:
            skill_name = candidate.get("skill", "unknown")
            for tool_name in candidate.get("tools") or []:
                if not tool_name or tool_name in tried_tools or not registry.has_tool(tool_name):
                    continue
                tried_tools.add(tool_name)
                mapped_params = self._map_tool_params(message, tool_name)
                try:
                    output = await registry.call_tool(tool_name, username, mapped_params)
                except Exception as e:
                    logger.warning("AgentRuntime 工具预调用失败 %s: %s", tool_name, e)
                    traces.append(
                        {
                            "skill": skill_name,
                            "tool": tool_name,
                            "params": mapped_params,
                            "status": "failed",
                            "error": str(e),
                        }
                    )
                    continue

                rendered = str(output or "").strip()
                if not rendered:
                    traces.append(
                        {
                            "skill": skill_name,
                            "tool": tool_name,
                            "params": mapped_params,
                            "status": "empty",
                        }
                    )
                    continue
                traces.append(
                    {
                        "skill": skill_name,
                        "tool": tool_name,
                        "params": mapped_params,
                        "status": "success",
                    }
                )
                results.append(
                    {
                        "skill": skill_name,
                        "tool": tool_name,
                        "content": rendered[:2400],
                    }
                )
                if len(results) >= 3:
                    return results, traces
        return results, traces

    @staticmethod
    def _render_runtime_context(runtime_context: Dict[str, Any]) -> str:
        workspace = runtime_context.get("workspace") or {}
        knowledge_hits = runtime_context.get("knowledge_hits") or []
        skills = runtime_context.get("skills") or []
        mcp_tools = runtime_context.get("mcp_tools") or []
        tool_results = runtime_context.get("tool_results") or []
        time_context = runtime_context.get("time_context") or {}
        sections: List[str] = []

        if time_context:
            sections.append(
                "当前时间上下文："
                f"今天={time_context.get('today', '')}；"
                f"当前学期={time_context.get('current_semester', '')}；"
                f"上学期={time_context.get('previous_semester', '')}；"
                f"下学期={time_context.get('next_semester', '')}"
            )

        if workspace:
            sections.append(
                "当前工作区："
                f"{workspace.get('name', '未命名')} "
                f"(id={workspace.get('id')}, slug={workspace.get('slug', '')})"
            )

        if skills:
            lines = [
                f"- {item.get('name')} [{item.get('mode', 'rule')}/{item.get('compatibility_level', 'direct')}]: {item.get('description') or '无描述'}"
                + (f" | source={item.get('source_type')}" if item.get("source_type") else "")
                + (f" | capabilities={','.join(item.get('capabilities') or [])}" if item.get("capabilities") else "")
                + (f" | triggers={','.join(item.get('triggers') or [])}" if item.get("triggers") else "")
                for item in skills
            ]
            sections.append("当前启用 Skills：\n" + "\n".join(lines))

        if mcp_tools:
            lines = [
                f"- {item.get('name')} ({item.get('kind', 'unknown')}/{item.get('transport', 'unknown')})"
                f" [{item.get('compatibility_level', 'direct')}]: {item.get('description') or '无描述'}"
                + (f" | capabilities={','.join(item.get('capabilities') or [])}" if item.get("capabilities") else "")
                for item in mcp_tools
            ]
            sections.append("当前启用 MCP 工具：\n" + "\n".join(lines))

        if knowledge_hits:
            lines = [
                f"[{idx}] {item.get('title', '未知标题')}: {item.get('content', '')}"
                for idx, item in enumerate(knowledge_hits, start=1)
            ]
            sections.append("工作区相关知识：\n" + "\n".join(lines))

        if tool_results:
            lines = [
                f"[skill={item.get('skill')} tool={item.get('tool')}]\n{item.get('content')}"
                for item in tool_results
            ]
            sections.append("预调用工具结果：\n" + "\n\n".join(lines))

        return "\n\n".join(section for section in sections if section).strip()

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
    def _fallback_chat(username: str, message: str, session_store, framework: str, reason: str, workspace_context: str = "", tool_trace: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
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
                "tool_trace": tool_trace or [],
            }
        return {
            "success": False,
            "message": result.get("message", "模型服务不可用"),
            "framework": f"{framework}:fallback_model_provider",
            "fallback_reason": reason,
            "tool_trace": tool_trace or [],
        }


_agent_runtime_singleton: AgentRuntimeService | None = None


def get_agent_runtime() -> AgentRuntimeService:
    global _agent_runtime_singleton
    if _agent_runtime_singleton is None:
        _agent_runtime_singleton = AgentRuntimeService()
    return _agent_runtime_singleton
