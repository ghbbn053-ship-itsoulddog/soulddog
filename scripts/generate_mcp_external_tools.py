#!/usr/bin/env python3
"""
根据 autopilot 报告生成 MCP 外部工具模板：
- 输出: backend/app/mcp/external_tools.generated.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "github-intake" / "autopilot-report.json"
OUT = ROOT / "backend" / "app" / "mcp" / "external_tools.generated.json"


def sanitize(name: str) -> str:
    x = (name or "").strip().lower().replace("/", "_").replace("-", "_")
    x = re.sub(r"[^a-z0-9_]", "_", x)
    return re.sub(r"_+", "_", x).strip("_")


def pick_candidates(recs: List[Dict], limit: int = 10) -> List[Dict]:
    out = []
    for r in recs:
        repo = str(r.get("repo", "")).strip()
        if not repo:
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out


def build_tool(repo: str, topic: str, idx: int) -> Dict:
    safe = sanitize(repo)
    return {
        "name": f"ext_{safe}_{idx}",
        "description": f"Generated MCP external tool stub for {repo}",
        "kind": "http",
        "method": "POST",
        "url": "http://localhost:8787/mcp/call",
        "timeout": 12,
        "enabled": False,
        "metadata": {
            "source_repo": repo,
            "topic": topic,
            "note": "请替换为真实外部服务地址后启用",
        },
        "parameters": {
            "username": {"type": "string", "required": True, "description": "学号"},
            "payload": {"type": "object", "required": False, "description": "透传参数"},
        },
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "学号"},
                "payload": {"type": "object", "description": "透传参数"},
            },
            "required": ["username"],
        },
    }


def main():
    if not REPORT.exists():
        raise SystemExit(f"report not found: {REPORT}")
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    recs = data.get("integration_recommendations") or []
    picks = pick_candidates(recs, limit=12)

    tools = []
    for i, p in enumerate(picks, 1):
        repo = str(p.get("repo", "")).strip()
        topic = str(p.get("topic", "")).strip()
        tools.append(build_tool(repo, topic, i))

    payload = {
        "generated_from": str(REPORT),
        "tools": tools,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated: {OUT}")
    print(f"tools: {len(tools)}")


if __name__ == "__main__":
    main()
