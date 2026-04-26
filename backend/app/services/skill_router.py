"""
Skill 路由服务：
将用户问题映射到启用的 skills，并生成可注入模型的上下文提示。
"""

from __future__ import annotations

from typing import Dict, List

from app.services.composition_manager import get_composition_manager
from app.services.skill_manager import get_skill_manager


def match_enabled_skills(owner: str, question: str, max_match: int = 3) -> List[Dict]:
    manager = get_skill_manager()
    skills = manager.list_skills(owner)
    comp = get_composition_manager()
    q = (question or "").strip().lower()
    if not q:
        return []

    matched: List[Dict] = []
    always_on: List[Dict] = []
    for s in skills:
        if not s.get("enabled", True):
            continue
        name = str(s.get("name", "")).strip()
        if name and name not in comp.filter_skill_names(owner, [name]):
            continue
        if bool(s.get("always_on")) and str(s.get("prompt", "")).strip():
            always_on.append(s)
            continue
        triggers = [str(t).strip() for t in (s.get("triggers") or []) if str(t).strip()]
        if not triggers:
            continue
        if any(t.lower() in q for t in triggers):
            matched.append(s)
        if len(matched) >= max_match:
            break
    combined = matched + [item for item in always_on if item not in matched]
    return combined[: max_match + len(always_on)]


def explain_skill_matches(owner: str, question: str, max_match: int = 3) -> List[Dict]:
    matched = match_enabled_skills(owner, question, max_match=max_match)
    out: List[Dict] = []
    q = (question or "").strip().lower()
    for s in matched:
        triggers = [str(t).strip() for t in (s.get("triggers") or []) if str(t).strip()]
        matched_triggers = [t for t in triggers if t.lower() in q]
        out.append(
            {
                "name": s.get("name", "unknown"),
                "mode": s.get("mode", "rule"),
                "source_type": s.get("source_type", "yaml"),
                "compatibility_level": s.get("compatibility_level", "direct"),
                "capabilities": s.get("capabilities", []) or [],
                "always_on": bool(s.get("always_on", False)),
                "matched_triggers": matched_triggers,
                "has_tools": bool(s.get("tools")),
                "tools": [
                    str(t.get("name", "")).strip()
                    for t in (s.get("tools") or [])
                    if isinstance(t, dict) and str(t.get("name", "")).strip()
                ],
            }
        )
    return out


def build_skill_prompt_hint(owner: str, question: str, max_match: int = 3) -> str:
    matched = match_enabled_skills(owner, question, max_match=max_match)
    if not matched:
        return ""

    lines = ["【技能路由提示】本轮可用的已启用 Skill 如下，请优先遵循其中规则，并结合对应工具回答："]
    for s in matched:
        tools = ", ".join(
            str(t.get("name", "")).strip()
            for t in (s.get("tools") or [])
            if isinstance(t, dict) and str(t.get("name", "")).strip()
        ) or "无"
        triggers = ", ".join(str(t) for t in (s.get("triggers") or [])[:5]) or "无"
        desc = str(s.get("description", "")).strip() or "无描述"
        source_type = str(s.get("source_type", "yaml")).strip() or "yaml"
        lines.append(f"- {s.get('name', 'unknown')} ({source_type}): {desc}; triggers=[{triggers}]; tools=[{tools}]")
        prompt = str(s.get("prompt", "")).strip()
        if prompt:
            lines.append("  规则摘录：")
            lines.append(prompt[:1600])
    return "\n".join(lines)
