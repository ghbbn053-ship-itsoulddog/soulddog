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


class IntakePipelineRequest(BaseModel):
    per_topic: int = 6
    clone_top: int = 2
    integrate_top: int = 8
    no_clone: bool = True
    update_repo_list: bool = True
    auto_enable: bool = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _run_script(root: Path, cmd: list[str], timeout: int, name: str) -> dict:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail=f"{name} 执行超时")
    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"{name} 失败: {(proc.stderr or proc.stdout or '').strip()[:500]}",
        )
    return {"stdout": (proc.stdout or "").strip(), "stderr": (proc.stderr or "").strip()}


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

    result = _run_script(root, cmd, timeout=180, name="autopilot")

    report_json = root / "docs" / "github-intake" / "autopilot-report.json"
    report_md = root / "docs" / "github-intake" / "autopilot-report.md"
    return {
        "success": True,
        "stdout": result["stdout"],
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


@router.post("/generate-mcp-tools")
async def generate_mcp_tools_from_report():
    root = _repo_root()
    script = root / "scripts" / "generate_mcp_external_tools.py"
    if not script.exists():
        raise HTTPException(status_code=404, detail="generate_mcp_external_tools 脚本不存在")
    result = _run_script(root, ["python", str(script)], timeout=120, name="generate_mcp_external_tools")

    generated = root / "backend" / "app" / "mcp" / "external_tools.generated.json"
    return {
        "success": True,
        "stdout": result["stdout"],
        "generated_file": str(generated),
    }


@router.post("/probe-mcp-tools")
async def probe_generated_mcp_tools(auto_enable: bool = False):
    root = _repo_root()
    script = root / "scripts" / "probe_mcp_external_tools.py"
    if not script.exists():
        raise HTTPException(status_code=404, detail="probe_mcp_external_tools 脚本不存在")
    cmd = ["python", str(script)]
    if auto_enable:
        cmd.append("--auto-enable")
    result = _run_script(root, cmd, timeout=120, name="probe_mcp_external_tools")
    return {"success": True, "summary": result["stdout"]}


@router.post("/enrich-mcp-tools")
async def enrich_generated_mcp_tools():
    root = _repo_root()
    script = root / "scripts" / "enrich_mcp_external_tools.py"
    if not script.exists():
        raise HTTPException(status_code=404, detail="enrich_mcp_external_tools 脚本不存在")
    result = _run_script(root, ["python", str(script)], timeout=120, name="enrich_mcp_external_tools")
    return {"success": True, "summary": result["stdout"]}


@router.post("/pipeline")
async def run_pipeline(payload: IntakePipelineRequest):
    """
    全自动接入流水线：
    run -> generate -> enrich -> probe -> mcp reload
    """
    root = _repo_root()

    # 1) autopilot
    autopilot_script = root / "scripts" / "github_autopilot.py"
    if not autopilot_script.exists():
        raise HTTPException(status_code=404, detail="github_autopilot 脚本不存在")
    run_cmd = [
        "python",
        str(autopilot_script),
        "--per-topic",
        str(payload.per_topic),
        "--clone-top",
        str(payload.clone_top),
        "--integrate-top",
        str(payload.integrate_top),
    ]
    if payload.no_clone:
        run_cmd.append("--no-clone")
    if payload.update_repo_list:
        run_cmd.append("--update-repo-list")
    step_run = _run_script(root, run_cmd, timeout=240, name="autopilot")

    # 2) generate
    step_generate = _run_script(
        root,
        ["python", str(root / "scripts" / "generate_mcp_external_tools.py")],
        timeout=120,
        name="generate_mcp_external_tools",
    )

    # 3) enrich
    step_enrich = _run_script(
        root,
        ["python", str(root / "scripts" / "enrich_mcp_external_tools.py")],
        timeout=120,
        name="enrich_mcp_external_tools",
    )

    # 4) probe
    probe_cmd = ["python", str(root / "scripts" / "probe_mcp_external_tools.py")]
    if payload.auto_enable:
        probe_cmd.append("--auto-enable")
    step_probe = _run_script(root, probe_cmd, timeout=120, name="probe_mcp_external_tools")

    # 5) mcp reload（在本进程内执行，确保后端生效）
    from app.services.mcp_registry import reload_mcp_registry

    registry = reload_mcp_registry()
    tools = registry.list_tools()

    return {
        "success": True,
        "steps": {
            "run": step_run["stdout"],
            "generate": step_generate["stdout"],
            "enrich": step_enrich["stdout"],
            "probe": step_probe["stdout"],
            "reload_count": len(tools),
        },
        "paths": {
            "report_json": str(root / "docs" / "github-intake" / "autopilot-report.json"),
            "generated_tools": str(root / "backend" / "app" / "mcp" / "external_tools.generated.json"),
        },
    }
