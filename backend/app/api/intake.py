"""
GitHub Intake API
一键触发自动扫描/分析/克隆报告。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from datetime import datetime
from time import perf_counter
import os
import shutil

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


class RetryRequest(BaseModel):
    auto_start: bool = True


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _history_path(root: Path) -> Path:
    return root / "docs" / "github-intake" / "pipeline-history.jsonl"


def _state_path(root: Path) -> Path:
    return root / "docs" / "github-intake" / "pipeline-state.json"


def _tasks_path(root: Path) -> Path:
    return root / "docs" / "github-intake" / "pipeline-tasks.json"


def _snapshots_dir(root: Path) -> Path:
    return root / "docs" / "github-intake" / "snapshots"


def _append_history(root: Path, record: dict):
    hp = _history_path(root)
    hp.parent.mkdir(parents=True, exist_ok=True)
    with hp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_history(root: Path, limit: int = 20) -> list[dict]:
    hp = _history_path(root)
    if not hp.exists():
        return []
    lines = hp.read_text(encoding="utf-8", errors="ignore").splitlines()
    rows = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
        if len(rows) >= max(1, limit):
            break
    return rows


def _read_tasks(root: Path) -> list[dict]:
    tp = _tasks_path(root)
    if not tp.exists():
        return []
    try:
        data = json.loads(tp.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def _write_tasks(root: Path, items: list[dict]):
    tp = _tasks_path(root)
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _upsert_task(root: Path, task: dict):
    tasks = _read_tasks(root)
    by_id = {str(t.get("run_id", "")): t for t in tasks if isinstance(t, dict)}
    by_id[str(task.get("run_id", ""))] = task
    merged = [v for k, v in by_id.items() if k]
    merged.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    _write_tasks(root, merged)


def _get_task(root: Path, run_id: str) -> dict | None:
    for t in _read_tasks(root):
        if str(t.get("run_id", "")) == run_id:
            return t
    return None


def _read_state(root: Path) -> dict:
    sp = _state_path(root)
    if not sp.exists():
        return {"running": False}
    try:
        return json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return {"running": False}


def _write_state(root: Path, state: dict):
    sp = _state_path(root)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _acquire_lock(root: Path) -> dict:
    state = _read_state(root)
    if state.get("running"):
        raise HTTPException(status_code=409, detail="pipeline 正在运行中")
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    new_state = {
        "running": True,
        "run_id": run_id,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "status": "running",
    }
    _write_state(root, new_state)
    return new_state


def _release_lock(root: Path, run_id: str, ok: bool, error: str = ""):
    now = datetime.now().isoformat(timespec="seconds")
    _write_state(
        root,
        {
            "running": False,
            "run_id": run_id,
            "finished_at": now,
            "status": "success" if ok else "failed",
            "error": error,
        },
    )


def _run_script(root: Path, cmd: list[str], timeout: int, name: str) -> dict:
    t0 = perf_counter()
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
    return {
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "elapsed_ms": int((perf_counter() - t0) * 1000),
    }


def _create_snapshot(root: Path, run_id: str) -> Path:
    snap = _snapshots_dir(root) / run_id
    snap.mkdir(parents=True, exist_ok=True)
    files = [
        root / "backend" / "app" / "mcp" / "external_tools.generated.json",
        root / "backend" / "app" / "mcp" / "external_tools.json",
        root / "docs" / "github-intake" / "autopilot-report.json",
        root / "docs" / "github-intake" / "autopilot-report.md",
        root / "docs" / "github-intake" / "repos.txt",
    ]
    for f in files:
        if f.exists():
            rel = f.relative_to(root)
            dst = snap / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    return snap


def _restore_snapshot(root: Path, run_id: str) -> dict:
    snap = _snapshots_dir(root) / run_id
    if not snap.exists():
        raise HTTPException(status_code=404, detail=f"snapshot 不存在: {run_id}")
    restored = 0
    for p in snap.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(snap)
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
        restored += 1
    return {"restored_files": restored, "snapshot": str(snap)}


def _execute_pipeline(root: Path, payload: IntakePipelineRequest, run_id: str, started_at: str) -> dict:
    t_pipeline = perf_counter()
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
    total_ms = int((perf_counter() - t_pipeline) * 1000)

    return {
        "success": True,
        "run_id": run_id,
        "started_at": started_at,
        "duration_ms": total_ms,
        "steps": {
            "run": step_run["stdout"],
            "generate": step_generate["stdout"],
            "enrich": step_enrich["stdout"],
            "probe": step_probe["stdout"],
            "reload_count": len(tools),
            "timing_ms": {
                "run": step_run["elapsed_ms"],
                "generate": step_generate["elapsed_ms"],
                "enrich": step_enrich["elapsed_ms"],
                "probe": step_probe["elapsed_ms"],
            },
        },
        "paths": {
            "report_json": str(root / "docs" / "github-intake" / "autopilot-report.json"),
            "generated_tools": str(root / "backend" / "app" / "mcp" / "external_tools.generated.json"),
        },
    }


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
    t0 = perf_counter()
    lock = _acquire_lock(root)
    run_id = lock["run_id"]
    started_at = datetime.now().isoformat(timespec="seconds")
    snapshot = _create_snapshot(root, run_id)
    _upsert_task(
        root,
        {
            "run_id": run_id,
            "created_at": started_at,
            "status": "running",
            "params": payload.model_dump(),
            "snapshot": str(snapshot),
        },
    )
    try:
        result = _execute_pipeline(root, payload, run_id, started_at)

        _append_history(
            root,
            {
                "run_id": run_id,
                "started_at": started_at,
                "duration_ms": result["duration_ms"],
                "params": payload.model_dump(),
                "reload_count": result["steps"]["reload_count"],
                "timing_ms": result["steps"]["timing_ms"],
                "success": True,
            },
        )
        _upsert_task(
            root,
            {
                "run_id": run_id,
                "created_at": started_at,
                "status": "success",
                "params": payload.model_dump(),
                "snapshot": str(snapshot),
                "duration_ms": result["duration_ms"],
                "reload_count": result["steps"]["reload_count"],
            },
        )
        _release_lock(root, run_id=run_id, ok=True)
        return result
    except Exception as e:
        total_ms = int((perf_counter() - t0) * 1000)
        _append_history(
            root,
            {
                "run_id": run_id,
                "started_at": started_at,
                "duration_ms": total_ms,
                "params": payload.model_dump(),
                "success": False,
                "error": str(e),
            },
        )
        _upsert_task(
            root,
            {
                "run_id": run_id,
                "created_at": started_at,
                "status": "failed",
                "params": payload.model_dump(),
                "snapshot": str(snapshot),
                "error": str(e),
            },
        )
        _release_lock(root, run_id=run_id, ok=False, error=str(e))
        raise


@router.get("/pipeline/history")
async def get_pipeline_history(limit: int = 20):
    root = _repo_root()
    rows = _read_history(root, limit=limit)
    return {"success": True, "count": len(rows), "items": rows}


@router.get("/pipeline/latest")
async def get_pipeline_latest():
    root = _repo_root()
    rows = _read_history(root, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="暂无 pipeline 运行记录")
    return {"success": True, "item": rows[0]}


@router.get("/pipeline/state")
async def get_pipeline_state():
    root = _repo_root()
    return {"success": True, "state": _read_state(root)}


@router.post("/pipeline/unlock")
async def force_unlock_pipeline():
    root = _repo_root()
    state = _read_state(root)
    if not state.get("running"):
        return {"success": True, "message": "pipeline 未锁定", "state": state}
    _write_state(
        root,
        {
            "running": False,
            "run_id": state.get("run_id", ""),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "status": "force_unlocked",
            "error": "manual unlock",
        },
    )
    return {"success": True, "message": "pipeline 已强制解锁", "state": _read_state(root)}


@router.get("/pipeline/tasks")
async def list_pipeline_tasks(limit: int = 30):
    root = _repo_root()
    items = _read_tasks(root)[: max(1, limit)]
    return {"success": True, "count": len(items), "items": items}


@router.get("/pipeline/tasks/{run_id}")
async def get_pipeline_task(run_id: str):
    root = _repo_root()
    task = _get_task(root, run_id)
    if not task:
        raise HTTPException(status_code=404, detail="task 不存在")
    return {"success": True, "item": task}


@router.post("/pipeline/tasks/{run_id}/retry")
async def retry_pipeline_task(run_id: str, payload: RetryRequest):
    root = _repo_root()
    task = _get_task(root, run_id)
    if not task:
        raise HTTPException(status_code=404, detail="task 不存在")
    params = task.get("params") or {}
    req = IntakePipelineRequest(**params)
    if not payload.auto_start:
        return {"success": True, "message": "retry 参数已校验", "params": req.model_dump()}
    return await run_pipeline(req)


@router.post("/pipeline/tasks/{run_id}/rollback")
async def rollback_pipeline_task(run_id: str):
    root = _repo_root()
    task = _get_task(root, run_id)
    if not task:
        raise HTTPException(status_code=404, detail="task 不存在")
    snapshot = str(task.get("snapshot", "")).strip()
    if not snapshot:
        raise HTTPException(status_code=400, detail="task 无 snapshot 信息")
    snap_dir = Path(snapshot)
    if not snap_dir.exists():
        raise HTTPException(status_code=404, detail="snapshot 目录不存在")
    # snapshot 路径基于 run_id，直接恢复
    restored = _restore_snapshot(root, run_id)
    from app.services.mcp_registry import reload_mcp_registry

    registry = reload_mcp_registry()
    return {
        "success": True,
        "restored": restored,
        "reloaded_tools": len(registry.list_tools()),
    }
