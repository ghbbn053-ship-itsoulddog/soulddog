"""
Skill 路由服务：
将用户问题映射到启用的 skills，并生成可注入模型的上下文提示。
"""

from __future__ import annotations

from typing import Dict, List

from app.services.skill_manager import get_skill_manager


def match_enabled_skills(owner: str, question: str, max_match: int = 3) -> List[Dict]:
    manager = get_skill_manager()
    skills = manager.list_skills(owner)
    q = (question or "").strip().lower()
    if not q:
        return []

    matched: List[Dict] = []
    for s in skills:
        if not s.get("enabled", True):
            continue
        triggers = [str(t).strip() for t in (s.get("triggers") or []) if str(t).strip()]
        if not triggers:
            continue
        if any(t.lower() in q for t in triggers):
            matched.append(s)
        if len(matched) >= max_match:
            break
    return matched


def build_skill_prompt_hint(owner: str, question: str, max_match: int = 3) -> str:
    matched = match_enabled_skills(owner, question, max_match=max_match)
    if not matched:
        return ""

    lines = ["【技能路由提示】本轮问题命中以下已启用技能，请优先结合对应工具回答："]
    for s in matched:
        tools = ", ".join(
            str(t.get("name", "")).strip()
            for t in (s.get("tools") or [])
            if isinstance(t, dict) and str(t.get("name", "")).strip()
        ) or "无"
        triggers = ", ".join(str(t) for t in (s.get("triggers") or [])[:5]) or "无"
        desc = str(s.get("description", "")).strip() or "无描述"
        lines.append(f"- {s.get('name', 'unknown')}: {desc}; triggers=[{triggers}]; tools=[{tools}]")
    return "\n".join(lines)
