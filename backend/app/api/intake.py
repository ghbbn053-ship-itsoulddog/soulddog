"""
GitHub Intake API
一键触发自动扫描/分析/克隆报告。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/intake", tags=["GitHub Intake"])


class IntakeRunRequest(BaseModel):
    per_topic: int = 6
    clone_top: int = 2
    integrate_top: int = 8
    no_clone: bool = True
    update_repo_list: bool = True


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@router.post("/run")
async def run_autopilot(payload: IntakeRunRequest):
    root = _repo_root()
    script = root / "scripts" / "github_autopilot.py"
    if not script.exists():
        raise HTTPException(status_code=404, detail="autopilot 脚本不存在")

    cmd = [
        "python",
        str(script),
        "--per-topic",
        str(payload.per_topic),
        "--clone-top",
        str(payload.clone_top),
        "--integrate-top",
        str(payload.integrate_top),
    ]
    if payload.no_clone:
        cmd.append("--no-clone")
    if payload.update_repo_list:
        cmd.append("--update-repo-list")

    try:
        proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="autopilot 执行超时")

    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"autopilot 失败: {(proc.stderr or proc.stdout or '').strip()[:500]}",
        )

    report_json = root / "docs" / "github-intake" / "autopilot-report.json"
    report_md = root / "docs" / "github-intake" / "autopilot-report.md"
    return {
        "success": True,
        "stdout": proc.stdout.strip(),
        "report_json": str(report_json),
        "report_md": str(report_md),
    }


@router.get("/report")
async def get_autopilot_report():
    root = _repo_root()
    report = root / "docs" / "github-intake" / "autopilot-report.json"
    if not report.exists():
        raise HTTPException(status_code=404, detail="报告不存在，请先运行 /api/intake/run")
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取报告失败: {e}")
    return {"success": True, "report": data}
