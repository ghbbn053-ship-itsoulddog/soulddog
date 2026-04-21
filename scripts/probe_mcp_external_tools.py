#!/usr/bin/env python3
"""
探测 generated MCP 外部 HTTP 工具可达性，并可自动启用可达工具。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import requests


ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "backend" / "app" / "mcp" / "external_tools.generated.json"


def probe(url: str, timeout: int) -> bool:
    try:
        resp = requests.options(url, timeout=timeout)
        if resp.status_code < 500:
            return True
    except Exception:
        pass
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.status_code < 500
    except Exception:
        return False


def run(auto_enable: bool) -> Dict:
    if not CFG.exists():
        raise SystemExit(f"config not found: {CFG}")
    data = json.loads(CFG.read_text(encoding="utf-8"))
    tools: List[Dict] = data.get("tools") or []
    checked = 0
    alive = 0
    for t in tools:
        if str(t.get("kind", "")).lower() != "http":
            continue
        checked += 1
        url = str(t.get("url", "")).strip()
        timeout = int(t.get("timeout", 8) or 8)
        ok = bool(url) and probe(url, timeout=timeout)
        t["health"] = {"alive": ok}
        if auto_enable and ok:
            t["enabled"] = True
        alive += 1 if ok else 0
    data["probe_summary"] = {"checked": checked, "alive": alive}
    CFG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data["probe_summary"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-enable", action="store_true")
    args = parser.parse_args()
    summary = run(auto_enable=args.auto_enable)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
