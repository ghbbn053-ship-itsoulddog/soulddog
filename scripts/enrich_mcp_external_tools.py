#!/usr/bin/env python3
"""
从 vendor/autopilot 克隆仓库中提取 API 端点线索，回填 generated MCP 工具配置。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "backend" / "app" / "mcp" / "external_tools.generated.json"
VENDOR = ROOT / "vendor" / "autopilot"


URL_RE = re.compile(r"(https?://[^\s'\"<>)]+)")
LOCAL_RE = re.compile(r"(http://localhost:\d{2,5}[^\s'\"<>)]*)", re.IGNORECASE)
FASTAPI_RE = re.compile(r"uvicorn\s+[^\s]+\s+--port\s+(\d{2,5})", re.IGNORECASE)


def repo_dir_from_source(repo: str) -> Path:
    return VENDOR / repo.replace("/", "__")


def read_candidates(repo_dir: Path) -> List[str]:
    candidates: List[str] = []
    if not repo_dir.exists():
        return candidates
    files = []
    for name in ["README.md", "readme.md", "README.MD", "docker-compose.yml", "docker-compose.yaml"]:
        p = repo_dir / name
        if p.exists():
            files.append(p)
    if not files:
        files = list(repo_dir.glob("README*"))[:3]

    for f in files[:8]:
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        candidates.extend(URL_RE.findall(txt))
        candidates.extend(LOCAL_RE.findall(txt))
        for m in FASTAPI_RE.findall(txt):
            candidates.append(f"http://localhost:{m}/")
    return candidates


def choose_best(candidates: List[str]) -> Tuple[str, str]:
    if not candidates:
        return "http://localhost:8787/mcp/call", "no_endpoint_detected"
    rank = []
    for c in candidates:
        s = c.strip().rstrip(".,)")
        score = 0
        lc = s.lower()
        if "localhost" in lc:
            score += 4
        if "/mcp" in lc:
            score += 4
        if "127.0.0.1" in lc:
            score += 3
        if "/api" in lc:
            score += 2
        if "http://localhost" in lc:
            score += 1
        rank.append((score, s))
    rank.sort(key=lambda x: x[0], reverse=True)
    best = rank[0][1]
    # 规范化成可调用路径倾向
    if best.endswith("/"):
        best = best + "mcp/call"
    return best, "detected_from_vendor"


def main():
    if not CFG.exists():
        raise SystemExit(f"config not found: {CFG}")
    data = json.loads(CFG.read_text(encoding="utf-8"))
    tools: List[Dict] = data.get("tools") or []
    changed = 0
    for t in tools:
        meta = t.get("metadata") or {}
        source_repo = str(meta.get("source_repo", "")).strip()
        if not source_repo:
            continue
        repo_dir = repo_dir_from_source(source_repo)
        candidates = read_candidates(repo_dir)
        best, note = choose_best(candidates)
        old = str(t.get("url", "")).strip()
        if best and best != old:
            t["url"] = best
            changed += 1
        meta["enrich_note"] = note
        meta["vendor_repo_dir"] = str(repo_dir)
        t["metadata"] = meta
    data["enrich_summary"] = {"changed": changed, "total": len(tools)}
    CFG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data["enrich_summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
