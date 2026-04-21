#!/usr/bin/env python3
"""
GitHub Autopilot:
1) Parse project docs for demand keywords
2) Search GitHub for matching high-star active repos
3) Score/rank repos
4) Optionally clone top repos
5) Generate integration report
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import requests


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = [
    ROOT / "PLATFORM_UPGRADE_GUIDE.md",
    ROOT / ".qoder" / "项目结构.txt",
]
OUT_DIR = ROOT / "docs" / "github-intake"
VENDOR_DIR = ROOT / "vendor" / "autopilot"

KEYWORD_MAP = {
    "multi_agent": ["multi-agent", "agent", "编排", "协作"],
    "mcp": ["mcp", "model context protocol", "tool calling", "工具调用"],
    "rag": ["rag", "vector", "embedding", "向量", "检索"],
    "workflow": ["workflow", "graph", "state machine", "工作流", "可视化"],
    "evaluation": ["eval", "benchmark", "observability", "监控", "评估"],
    "skill_plugin": ["skill", "plugin", "marketplace", "扩展", "插件"],
}

TOPIC_QUERIES = {
    "multi_agent": "multi agent framework python",
    "mcp": "model context protocol server python",
    "rag": "rag framework python",
    "workflow": "agent workflow graph python",
    "evaluation": "llm eval observability agent",
    "skill_plugin": "ai plugin framework python",
}

INTEGRATION_HINTS = {
    "multi_agent": "接入 backend/app/services/agent_runtime.py，扩展 framework 分派与路由策略",
    "mcp": "映射到 backend/app/services/mcp_registry.py，新增 registry adapter",
    "rag": "映射到 backend/app/services/vector_store.py 与检索过滤策略",
    "workflow": "映射到 langgraph 路由图，落到 backend/app/services/agent_runtime.py",
    "evaluation": "新增 trace/metrics 采集，挂到 chat/send-stream 与 agents/run",
    "skill_plugin": "映射到 backend/app/services/skill_manager.py 与 skills API",
}


@dataclass
class RepoRecord:
    topic: str
    full_name: str
    html_url: str
    description: str
    language: str
    stars: int
    forks: int
    open_issues: int
    size_kb: int
    updated_at: str
    pushed_at: str
    license: str
    score: float


def read_sources(paths: List[Path]) -> str:
    parts = []
    for p in paths:
        if p.exists():
            parts.append(p.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def detect_topics(text: str) -> List[str]:
    content = (text or "").lower()
    hits: List[Tuple[str, int]] = []
    for topic, words in KEYWORD_MAP.items():
        c = sum(1 for w in words if w.lower() in content)
        if c > 0:
            hits.append((topic, c))
    hits.sort(key=lambda x: x[1], reverse=True)
    topics = [t for t, _ in hits] or ["multi_agent", "mcp", "rag"]
    return topics[:6]


def days_since(iso_time: str) -> float:
    if not iso_time:
        return 3650.0
    dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def score_repo(item: Dict) -> float:
    stars = int(item.get("stargazers_count") or 0)
    pushed = item.get("pushed_at") or ""
    lang = (item.get("language") or "").lower()
    license_name = ((item.get("license") or {}).get("spdx_id") or "").upper()
    size_kb = int(item.get("size") or 0)

    star_score = min(1.0, math.log10(stars + 1) / 5.0)
    recency_days = days_since(pushed)
    recency_score = max(0.0, 1.0 - min(1.0, recency_days / 365.0))
    lang_score = 0.1 if lang in {"python", "typescript"} else 0.0
    license_score = 0.1 if license_name in {"MIT", "APACHE-2.0", "BSD-3-CLAUSE"} else 0.0
    size_penalty = 0.08 if size_kb > 300000 else (0.04 if size_kb > 120000 else 0.0)
    return round(star_score * 0.65 + recency_score * 0.25 + lang_score + license_score - size_penalty, 4)


def is_relevant_repo(item: Dict) -> bool:
    text = " ".join(
        [
            str(item.get("name") or ""),
            str(item.get("full_name") or ""),
            str(item.get("description") or ""),
            " ".join(item.get("topics") or []),
        ]
    ).lower()
    allow_tokens = [
        "ai",
        "agent",
        "llm",
        "mcp",
        "rag",
        "langchain",
        "langgraph",
        "workflow",
        "tool",
        "orchestr",
    ]
    deny_tokens = [
        "dictatorship",
        "awesome-",
        "leetcode",
        "interview",
        "news",
        "crawler-only",
    ]
    if any(d in text for d in deny_tokens):
        return False
    return any(a in text for a in allow_tokens)


def github_search(query: str, per_page: int = 8) -> List[Dict]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": per_page}
    headers = {"User-Agent": "campus-ai-autopilot"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code == 401 and token:
        # token 失效/权限不足时自动降级匿名请求，避免流程中断
        headers.pop("Authorization", None)
        resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json() or {}
    return payload.get("items") or []


def collect_repos(topics: List[str], per_topic: int) -> List[RepoRecord]:
    seen = set()
    rows: List[RepoRecord] = []
    for topic in topics:
        q = TOPIC_QUERIES.get(topic, topic)
        try:
            items = github_search(q, per_page=per_topic)
        except Exception:
            continue
        for it in items:
            full_name = it.get("full_name") or ""
            if not full_name or full_name in seen:
                continue
            if not is_relevant_repo(it):
                continue
            seen.add(full_name)
            rows.append(
                RepoRecord(
                    topic=topic,
                    full_name=full_name,
                    html_url=it.get("html_url") or "",
                    description=it.get("description") or "",
                    language=it.get("language") or "",
                    stars=int(it.get("stargazers_count") or 0),
                    forks=int(it.get("forks_count") or 0),
                    open_issues=int(it.get("open_issues_count") or 0),
                    size_kb=int(it.get("size") or 0),
                    updated_at=it.get("updated_at") or "",
                    pushed_at=it.get("pushed_at") or "",
                    license=((it.get("license") or {}).get("spdx_id") or ""),
                    score=score_repo(it),
                )
            )
        time.sleep(0.4)
    rows.sort(key=lambda r: (r.score, r.stars), reverse=True)
    return rows


def clone_repo(full_name: str, target: Path) -> Tuple[bool, str]:
    if target.exists():
        return True, "exists"
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{full_name}.git"
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(target)],
            check=True,
            capture_output=True,
            text=True,
        )
        return True, "cloned"
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or "").strip()[:400]
        return False, msg or "clone_failed"


def suggest_integration(rows: List[RepoRecord], top_n: int) -> List[Dict]:
    picks = rows[:top_n]
    out = []
    for r in picks:
        out.append(
            {
                "repo": r.full_name,
                "topic": r.topic,
                "score": r.score,
                "why": f"stars={r.stars}, pushed={r.pushed_at[:10]}, lang={r.language or '-'}",
                "integrate_to": INTEGRATION_HINTS.get(r.topic, "backend/app/services"),
            }
        )
    return out


def write_outputs(topics: List[str], rows: List[RepoRecord], integration: List[Dict], clones: Dict[str, Dict]):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    json_path = OUT_DIR / "autopilot-report.json"
    md_path = OUT_DIR / "autopilot-report.md"

    payload = {
        "generated_at": ts,
        "topics": topics,
        "repos": [asdict(r) for r in rows],
        "integration_recommendations": integration,
        "clone_status": clones,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# GitHub Autopilot Report",
        "",
        f"- Generated at: {ts}",
        f"- Detected topics: {', '.join(topics)}",
        "",
        "## Top Repositories",
        "",
        "| Repo | Topic | Score | Stars | Size(KB) | Pushed | License |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for r in rows[:25]:
        lines.append(
            f"| {r.full_name} | {r.topic} | {r.score:.4f} | {r.stars} | {r.size_kb} | {r.pushed_at[:10]} | {r.license or '-'} |"
        )

    lines += ["", "## Integration Recommendations", ""]
    for i, rec in enumerate(integration, 1):
        lines.append(f"{i}. `{rec['repo']}` -> {rec['integrate_to']} ({rec['why']})")

    lines += ["", "## Clone Status", ""]
    for repo, st in clones.items():
        lines.append(f"- `{repo}`: {st.get('status')} ({st.get('note', '')})")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def update_repo_list(rows: List[RepoRecord], limit: int):
    repo_txt = OUT_DIR / "repos.txt"
    repo_txt.parent.mkdir(parents=True, exist_ok=True)
    uniq = []
    seen = set()
    for r in rows:
        if r.full_name in seen:
            continue
        seen.add(r.full_name)
        uniq.append(r.full_name)
        if len(uniq) >= limit:
            break
    content = "# owner/repo (autopilot generated)\n" + "\n".join(uniq) + "\n"
    repo_txt.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-topic", type=int, default=8)
    parser.add_argument("--clone-top", type=int, default=4)
    parser.add_argument("--integrate-top", type=int, default=8)
    parser.add_argument("--no-clone", action="store_true")
    parser.add_argument("--update-repo-list", action="store_true")
    args = parser.parse_args()

    source_text = read_sources(DEFAULT_SOURCES)
    topics = detect_topics(source_text)
    repos = collect_repos(topics, per_topic=args.per_topic)
    integration = suggest_integration(repos, top_n=args.integrate_top)

    clone_result: Dict[str, Dict] = {}
    if not args.no_clone:
        for r in repos[: args.clone_top]:
            target = VENDOR_DIR / r.full_name.replace("/", "__")
            ok, note = clone_repo(r.full_name, target)
            clone_result[r.full_name] = {
                "status": "ok" if ok else "fail",
                "note": note,
                "path": str(target),
            }

    if args.update_repo_list:
        update_repo_list(repos, limit=20)

    json_path, md_path = write_outputs(topics, repos, integration, clone_result)
    print(f"[autopilot] topics={topics}")
    print(f"[autopilot] repos={len(repos)}")
    print(f"[autopilot] report={md_path}")
    print(f"[autopilot] json={json_path}")


if __name__ == "__main__":
    main()
