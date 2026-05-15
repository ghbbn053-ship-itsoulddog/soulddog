"""
GitHub Intake API
一键触发自动扫描/分析/克隆报告。
"""

from __future__ import annotations

import json
import subprocess
import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime
from time import perf_counter
import os
import shutil
import threading
import time
import hashlib

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.observability import (
    INTAKE_TASK_ENQUEUED_TOTAL,
    INTAKE_TASK_STARTED_TOTAL,
    INTAKE_TASK_FINISHED_TOTAL,
    INTAKE_TASK_DURATION,
    INTAKE_QUEUE_SIZE,
    INTAKE_RUNNING_SIZE,
)

router = APIRouter(prefix="/api/intake", tags=["GitHub Intake"])
_TASK_LOCK = threading.Lock()
_WORKER_LOCK = threading.Lock()
_WORKER_THREADS: list[threading.Thread] = []
_RUN_PROCS: dict[str, subprocess.Popen] = {}
_RUN_PROCS_LOCK = threading.Lock()
_WORKER_COUNT = max(1, int(os.getenv("INTAKE_WORKERS", "2")))
_CIRCUIT_LOCK = threading.Lock()
_CIRCUIT: dict[str, dict] = {}


def _resolve_owner(request: Request | None) -> str:
    if request is None:
        raise HTTPException(status_code=401, detail="未检测到登录会话，请重新登录")
    auth_session_id = request.cookies.get("auth_session_id")
    app_obj = request.scope.get("app")
    session_store = getattr(getattr(app_obj, "state", None), "session_store", None) if app_obj else None
    if auth_session_id and session_store:
        auth_payload = session_store.get_auth_session(auth_session_id)
        if auth_payload and auth_payload.get("username"):
            return str(auth_payload.get("username"))
    raise HTTPException(status_code=401, detail="未检测到有效登录会话，请重新登录")


def _assert_task_owner(task: dict, owner: str):
    if str(task.get("owner", "")) != owner:
        raise HTTPException(status_code=403, detail="无权访问该任务")


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
    timeout_sec: int = 600
    idempotency_key: str | None = None
    priority: str = "normal"
    max_retries: int = 2
    retry_backoff_base_sec: int = 5


class RetryRequest(BaseModel):
    auto_start: bool = True


class PipelineCancelled(Exception):
    pass


def _priority_value(priority: str) -> int:
    p = (priority or "normal").strip().lower()
    return {"high": 3, "normal": 2, "low": 1}.get(p, 2)


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


def _runs_db_path(root: Path) -> Path:
    return root / "backend" / "data" / "intake" / "runs.sqlite"


def _ensure_runs_db(root: Path):
    db = _runs_db_path(root)
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS task_runs (
              run_id TEXT PRIMARY KEY,
              owner TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              status TEXT NOT NULL,
              priority INTEGER NOT NULL DEFAULT 2,
              priority_label TEXT NOT NULL DEFAULT 'normal',
              next_run_at TEXT,
              idempotency_key TEXT,
              fingerprint TEXT,
              retries INTEGER NOT NULL DEFAULT 0,
              max_retries INTEGER NOT NULL DEFAULT 0,
              retry_backoff_base_sec INTEGER NOT NULL DEFAULT 5,
              timeout_sec INTEGER NOT NULL DEFAULT 600,
              cancel_requested INTEGER NOT NULL DEFAULT 0,
              cancel_requested_at TEXT,
              started_at TEXT,
              finished_at TEXT,
              cancelled_at TEXT,
              duration_ms INTEGER,
              reload_count INTEGER,
              error TEXT,
              last_error TEXT,
              snapshot TEXT,
              params_json TEXT
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_status ON task_runs(status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_created_at ON task_runs(created_at)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_priority_next ON task_runs(priority, next_run_at, created_at)")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS task_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id TEXT NOT NULL,
              ts TEXT NOT NULL,
              level TEXT NOT NULL,
              stage TEXT NOT NULL,
              message TEXT NOT NULL
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_task_logs_run_id_id ON task_logs(run_id, id)")
        con.commit()
    finally:
        con.close()


def _db_conn(root: Path) -> sqlite3.Connection:
    _ensure_runs_db(root)
    con = sqlite3.connect(str(_runs_db_path(root)))
    con.row_factory = sqlite3.Row
    return con


def _append_history(root: Path, record: dict):
    hp = _history_path(root)
    hp.parent.mkdir(parents=True, exist_ok=True)
    with hp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_history(root: Path, limit: int = 20, owner: str | None = None) -> list[dict]:
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
            item = json.loads(line)
        except Exception:
            continue
        if owner and str(item.get("owner", "")) != owner:
            continue
        rows.append(item)
        if len(rows) >= max(1, limit):
            break
    return rows


def _row_to_task(row: sqlite3.Row) -> dict:
    params = {}
    try:
        params = json.loads(row["params_json"] or "{}")
    except Exception:
        params = {}
    return {
        "run_id": row["run_id"],
        "owner": row["owner"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "status": row["status"],
        "priority": row["priority_label"],
        "next_run_at": row["next_run_at"] or "",
        "idempotency_key": row["idempotency_key"] or "",
        "fingerprint": row["fingerprint"] or "",
        "retries": int(row["retries"] or 0),
        "max_retries": int(row["max_retries"] or 0),
        "retry_backoff_base_sec": int(row["retry_backoff_base_sec"] or 5),
        "timeout_sec": int(row["timeout_sec"] or 600),
        "cancel_requested": bool(row["cancel_requested"] or 0),
        "cancel_requested_at": row["cancel_requested_at"] or "",
        "started_at": row["started_at"] or "",
        "finished_at": row["finished_at"] or "",
        "cancelled_at": row["cancelled_at"] or "",
        "duration_ms": row["duration_ms"],
        "reload_count": row["reload_count"],
        "error": row["error"] or "",
        "last_error": row["last_error"] or "",
        "snapshot": row["snapshot"] or "",
        "params": params,
    }


def _read_tasks(root: Path) -> list[dict]:
    with _TASK_LOCK:
        con = _db_conn(root)
        try:
            rows = con.execute("SELECT * FROM task_runs ORDER BY created_at DESC LIMIT 500").fetchall()
            return [_row_to_task(r) for r in rows]
        finally:
            con.close()


def _write_tasks(root: Path, items: list[dict]):
    for item in items:
        if isinstance(item, dict):
            _upsert_task(root, item)


def _upsert_task(root: Path, task: dict):
    run_id = str(task.get("run_id", "")).strip()
    if not run_id:
        return
    with _TASK_LOCK:
        con = _db_conn(root)
        try:
            existing = con.execute("SELECT * FROM task_runs WHERE run_id=?", (run_id,)).fetchone()
            if existing:
                old = _row_to_task(existing)
                merged = {**old, **task}
            else:
                merged = task
            now = datetime.now().isoformat(timespec="seconds")
            params_json = json.dumps(merged.get("params") or {}, ensure_ascii=False)
            con.execute(
                """
                INSERT OR REPLACE INTO task_runs(
                  run_id, owner, created_at, updated_at, status, priority, priority_label, next_run_at,
                  idempotency_key, fingerprint, retries, max_retries, retry_backoff_base_sec, timeout_sec,
                  cancel_requested, cancel_requested_at, started_at, finished_at, cancelled_at, duration_ms,
                  reload_count, error, last_error, snapshot, params_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    str(merged.get("owner", "system")),
                    str(merged.get("created_at", now)),
                    now,
                    str(merged.get("status", "queued")),
                    int(_priority_value(str(merged.get("priority", "normal")))),
                    str(merged.get("priority", "normal")),
                    str(merged.get("next_run_at", "")) or None,
                    str(merged.get("idempotency_key", "")) or None,
                    str(merged.get("fingerprint", "")) or None,
                    int(merged.get("retries", 0) or 0),
                    int(merged.get("max_retries", 0) or 0),
                    int(merged.get("retry_backoff_base_sec", 5) or 5),
                    int(merged.get("timeout_sec", 600) or 600),
                    1 if bool(merged.get("cancel_requested", False)) else 0,
                    str(merged.get("cancel_requested_at", "")) or None,
                    str(merged.get("started_at", "")) or None,
                    str(merged.get("finished_at", "")) or None,
                    str(merged.get("cancelled_at", "")) or None,
                    merged.get("duration_ms"),
                    merged.get("reload_count"),
                    str(merged.get("error", "")) or None,
                    str(merged.get("last_error", "")) or None,
                    str(merged.get("snapshot", "")) or None,
                    params_json,
                ),
            )
            con.commit()
        finally:
            con.close()


def _append_task_log(root: Path, run_id: str, level: str, stage: str, message: str):
    if not run_id:
        return
    con = _db_conn(root)
    try:
        con.execute(
            "INSERT INTO task_logs(run_id, ts, level, stage, message) VALUES(?,?,?,?,?)",
            (run_id, datetime.now().isoformat(timespec="seconds"), level, stage, message[:2000]),
        )
        con.commit()
    finally:
        con.close()


def _read_task_logs(root: Path, run_id: str, after_id: int = 0, limit: int = 200) -> list[dict]:
    con = _db_conn(root)
    try:
        rows = con.execute(
            "SELECT id, run_id, ts, level, stage, message FROM task_logs WHERE run_id=? AND id>? ORDER BY id ASC LIMIT ?",
            (run_id, int(after_id), max(1, int(limit))),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _claim_next_task(root: Path) -> dict | None:
    with _TASK_LOCK:
        con = _db_conn(root)
        try:
            now_iso = datetime.now().isoformat(timespec="seconds")
            row = con.execute(
                """
                SELECT * FROM task_runs
                WHERE status='queued' AND (next_run_at IS NULL OR next_run_at='' OR next_run_at<=?)
                ORDER BY priority DESC, COALESCE(next_run_at, created_at) ASC, created_at ASC
                LIMIT 1
                """,
                (now_iso,),
            ).fetchone()
            if not row:
                return None
            run_id = str(row["run_id"])
            con.execute("UPDATE task_runs SET status='claimed', updated_at=? WHERE run_id=?", (now_iso, run_id))
            con.commit()
            claimed = con.execute("SELECT * FROM task_runs WHERE run_id=?", (run_id,)).fetchone()
            return _row_to_task(claimed) if claimed else None
        finally:
            con.close()


def _next_queued_task(root: Path) -> dict | None:
    tasks = _read_tasks(root)
    queued = [t for t in tasks if str(t.get("status", "")) == "queued"]
    if not queued:
        return None
    now = datetime.now().timestamp()
    runnable: list[dict] = []
    for t in queued:
        next_run_at = str(t.get("next_run_at", "")).strip()
        if not next_run_at:
            runnable.append(t)
            continue
        try:
            ts = datetime.fromisoformat(next_run_at).timestamp()
        except Exception:
            ts = now
        if ts <= now:
            runnable.append(t)
    if not runnable:
        return None
    runnable.sort(
        key=lambda x: (
            -_priority_value(str(x.get("priority", "normal"))),
            str(x.get("next_run_at", "") or x.get("created_at", "")),
            str(x.get("created_at", "")),
        )
    )
    return runnable[0]


def _queued_count(root: Path) -> int:
    return sum(1 for t in _read_tasks(root) if str(t.get("status", "")) in {"queued", "claimed"})


def _running_count(root: Path) -> int:
    return sum(1 for t in _read_tasks(root) if str(t.get("status", "")) == "running")


def _get_task(root: Path, run_id: str) -> dict | None:
    for t in _read_tasks(root):
        if str(t.get("run_id", "")) == run_id:
            return t
    return None


def _payload_fingerprint(payload: IntakePipelineRequest) -> str:
    data = payload.model_dump()
    data.pop("idempotency_key", None)
    text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _find_recent_duplicate(root: Path, *, owner: str, idempotency_key: str | None, fingerprint: str) -> dict | None:
    now = datetime.now().timestamp()
    for t in _read_tasks(root):
        if str(t.get("owner", "")) != owner:
            continue
        status = str(t.get("status", ""))
        if status not in {"queued", "running", "retry_wait"}:
            continue
        created_at = str(t.get("created_at", ""))
        try:
            ts = datetime.fromisoformat(created_at).timestamp()
        except Exception:
            ts = now
        if now - ts > 600:
            continue
        if idempotency_key and str(t.get("idempotency_key", "")) == idempotency_key:
            return t
        if str(t.get("fingerprint", "")) == fingerprint:
            return t
    return None


def _is_cancelled(root: Path, run_id: str) -> bool:
    task = _get_task(root, run_id)
    if not task:
        return True
    return bool(task.get("cancel_requested"))


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


def _run_pipeline_task(root: Path, run_id: str):
    task = _get_task(root, run_id)
    if not task:
        return
    if str(task.get("status", "")) not in {"queued", "claimed", "running"}:
        return
    params = task.get("params") or {}
    payload = IntakePipelineRequest(**params)
    started_at = datetime.now().isoformat(timespec="seconds")
    t0 = perf_counter()

    _write_state(
        root,
        {
            "running": True,
            "run_id": run_id,
            "started_at": started_at,
            "status": "running",
        },
    )
    _upsert_task(
        root,
        {
            **task,
            "status": "running",
            "started_at": started_at,
            "next_run_at": "",
            "cancelled_at": "",
            "cancel_requested": bool(task.get("cancel_requested", False)),
        },
    )
    INTAKE_TASK_STARTED_TOTAL.inc()
    INTAKE_RUNNING_SIZE.set(_running_count(root))
    INTAKE_QUEUE_SIZE.set(_queued_count(root))
    _append_task_log(root, run_id, "info", "pipeline", "task started")

    try:
        result = _execute_pipeline(root, payload, run_id, started_at)
        _append_history(
            root,
            {
                "run_id": run_id,
                "owner": str(task.get("owner", "")),
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
                **task,
                "status": "success",
                "started_at": started_at,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "duration_ms": result["duration_ms"],
                "reload_count": result["steps"]["reload_count"],
                "error": "",
            },
        )
        _release_lock(root, run_id=run_id, ok=True)
        _append_task_log(root, run_id, "info", "pipeline", "task success")
        INTAKE_TASK_FINISHED_TOTAL.labels(outcome="success").inc()
        INTAKE_TASK_DURATION.labels(outcome="success").observe(max(0.001, (perf_counter() - t0)))
    except PipelineCancelled:
        total_ms = int((perf_counter() - t0) * 1000)
        _append_history(
            root,
            {
                "run_id": run_id,
                "owner": str(task.get("owner", "")),
                "started_at": started_at,
                "duration_ms": total_ms,
                "params": payload.model_dump(),
                "success": False,
                "error": "cancelled",
            },
        )
        _upsert_task(
            root,
            {
                **task,
                "status": "cancelled",
                "started_at": started_at,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "cancelled_at": datetime.now().isoformat(timespec="seconds"),
                "duration_ms": total_ms,
                "error": "cancelled",
            },
        )
        _release_lock(root, run_id=run_id, ok=False, error="cancelled")
        _append_task_log(root, run_id, "warn", "pipeline", "task cancelled")
        INTAKE_TASK_FINISHED_TOTAL.labels(outcome="cancelled").inc()
        INTAKE_TASK_DURATION.labels(outcome="cancelled").observe(max(0.001, (perf_counter() - t0)))
    except Exception as e:
        total_ms = int((perf_counter() - t0) * 1000)
        retries = int(task.get("retries", 0))
        max_retries = int(task.get("max_retries", 0))
        backoff_base = int(task.get("retry_backoff_base_sec", 5))
        can_retry = retries < max_retries
        if can_retry:
            next_retry = retries + 1
            backoff_sec = max(1, backoff_base) * (2 ** retries)
            next_run_at = datetime.fromtimestamp(time.time() + backoff_sec).isoformat(timespec="seconds")
            _upsert_task(
                root,
                {
                    **task,
                    "status": "queued",
                    "started_at": started_at,
                    "duration_ms": total_ms,
                    "error": str(e),
                    "retries": next_retry,
                    "last_error": str(e),
                    "next_run_at": next_run_at,
                    "last_failed_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            _append_task_log(root, run_id, "warn", "pipeline", f"retry scheduled #{next_retry} in {backoff_sec}s: {e}")
            _release_lock(root, run_id=run_id, ok=False, error=f"retry scheduled in {backoff_sec}s")
            INTAKE_RUNNING_SIZE.set(_running_count(root))
            INTAKE_QUEUE_SIZE.set(_queued_count(root))
            return

        _append_history(
            root,
            {
                "run_id": run_id,
                "owner": str(task.get("owner", "")),
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
                **task,
                "status": "failed",
                "started_at": started_at,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "duration_ms": total_ms,
                "error": str(e),
                "last_error": str(e),
            },
        )
        _release_lock(root, run_id=run_id, ok=False, error=str(e))
        _append_task_log(root, run_id, "error", "pipeline", f"task failed: {e}")
        INTAKE_TASK_FINISHED_TOTAL.labels(outcome="failed").inc()
        INTAKE_TASK_DURATION.labels(outcome="failed").observe(max(0.001, (perf_counter() - t0)))
    finally:
        INTAKE_RUNNING_SIZE.set(_running_count(root))
        INTAKE_QUEUE_SIZE.set(_queued_count(root))


def _worker_loop(root: Path):
    while True:
        task = _claim_next_task(root)
        if not task:
            time.sleep(0.5)
            continue
        run_id = str(task.get("run_id", "")).strip()
        if not run_id:
            _upsert_task(
                root,
                {
                    **task,
                    "status": "failed",
                    "error": "invalid run_id",
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            continue
        if bool(task.get("cancel_requested")):
            _upsert_task(
                root,
                {
                    **task,
                    "status": "cancelled",
                    "cancelled_at": datetime.now().isoformat(timespec="seconds"),
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "error": "cancelled before start",
                },
            )
            continue
        _run_pipeline_task(root, run_id)


def _ensure_worker(root: Path):
    global _WORKER_THREADS
    with _WORKER_LOCK:
        alive = [t for t in _WORKER_THREADS if t.is_alive()]
        _WORKER_THREADS = alive
        need = _WORKER_COUNT - len(_WORKER_THREADS)
        for i in range(max(0, need)):
            t = threading.Thread(
                target=_worker_loop,
                args=(root,),
                daemon=True,
                name=f"intake-pipeline-worker-{len(_WORKER_THREADS) + i + 1}",
            )
            t.start()
            _WORKER_THREADS.append(t)


def _run_script(root: Path, cmd: list[str], timeout: int, name: str, *, run_id: str | None = None) -> dict:
    t0 = perf_counter()
    proc: subprocess.Popen | None = None
    stdout = ""
    stderr = ""
    circuit_key = str(cmd[0]) if cmd else name
    with _CIRCUIT_LOCK:
        c = _CIRCUIT.get(circuit_key, {"fails": 0, "opened_until": 0.0})
        if c.get("opened_until", 0.0) > time.time():
            raise HTTPException(status_code=503, detail=f"{name} 熔断中，请稍后重试")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if run_id:
            with _RUN_PROCS_LOCK:
                _RUN_PROCS[run_id] = proc
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
        with _CIRCUIT_LOCK:
            c = _CIRCUIT.get(circuit_key, {"fails": 0, "opened_until": 0.0})
            c["fails"] = int(c.get("fails", 0)) + 1
            if c["fails"] >= 3:
                c["opened_until"] = time.time() + 60
            _CIRCUIT[circuit_key] = c
        raise HTTPException(status_code=504, detail=f"{name} 执行超时")
    finally:
        if run_id:
            with _RUN_PROCS_LOCK:
                _RUN_PROCS.pop(run_id, None)

    if run_id and _is_cancelled(root, run_id):
        raise PipelineCancelled("任务已取消")

    if not proc or proc.returncode != 0:
        with _CIRCUIT_LOCK:
            c = _CIRCUIT.get(circuit_key, {"fails": 0, "opened_until": 0.0})
            c["fails"] = int(c.get("fails", 0)) + 1
            if c["fails"] >= 3:
                c["opened_until"] = time.time() + 60
            _CIRCUIT[circuit_key] = c
        raise HTTPException(
            status_code=500,
            detail=f"{name} 失败: {(stderr or stdout or '').strip()[:500]}",
        )
    with _CIRCUIT_LOCK:
        _CIRCUIT[circuit_key] = {"fails": 0, "opened_until": 0.0}
    return {
        "stdout": (stdout or "").strip(),
        "stderr": (stderr or "").strip(),
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
    deadline = t_pipeline + max(60, int(payload.timeout_sec))

    def step_timeout() -> int:
        remain = int(deadline - perf_counter())
        if remain <= 0:
            raise HTTPException(status_code=504, detail="pipeline 任务总超时")
        return remain

    def ensure_not_cancelled():
        if _is_cancelled(root, run_id):
            raise PipelineCancelled("任务已取消")

    ensure_not_cancelled()
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
    _append_task_log(root, run_id, "info", "autopilot", "starting autopilot script")
    step_run = _run_script(root, run_cmd, timeout=min(240, step_timeout()), name="autopilot", run_id=run_id)
    _append_task_log(root, run_id, "info", "autopilot", "autopilot done")
    ensure_not_cancelled()

    # 2) generate
    step_generate = _run_script(
        root,
        ["python", str(root / "scripts" / "generate_mcp_external_tools.py")],
        timeout=min(120, step_timeout()),
        name="generate_mcp_external_tools",
        run_id=run_id,
    )
    _append_task_log(root, run_id, "info", "generate", "generate done")
    ensure_not_cancelled()

    # 3) enrich
    step_enrich = _run_script(
        root,
        ["python", str(root / "scripts" / "enrich_mcp_external_tools.py")],
        timeout=min(120, step_timeout()),
        name="enrich_mcp_external_tools",
        run_id=run_id,
    )
    _append_task_log(root, run_id, "info", "enrich", "enrich done")
    ensure_not_cancelled()

    # 4) probe
    probe_cmd = ["python", str(root / "scripts" / "probe_mcp_external_tools.py")]
    if payload.auto_enable:
        probe_cmd.append("--auto-enable")
    step_probe = _run_script(root, probe_cmd, timeout=min(120, step_timeout()), name="probe_mcp_external_tools", run_id=run_id)
    _append_task_log(root, run_id, "info", "probe", "probe done")
    ensure_not_cancelled()

    # 5) mcp reload（在本进程内执行，确保后端生效）
    from app.services.mcp_registry import reload_mcp_registry

    registry = reload_mcp_registry()
    tools = registry.list_tools()
    _append_task_log(root, run_id, "info", "reload", f"registry reloaded, tools={len(tools)}")
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
async def run_autopilot(payload: IntakeRunRequest, http_request: Request):
    _resolve_owner(http_request)
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
async def get_autopilot_report(http_request: Request):
    _resolve_owner(http_request)
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
async def generate_mcp_tools_from_report(http_request: Request):
    _resolve_owner(http_request)
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
async def probe_generated_mcp_tools(auto_enable: bool = False, http_request: Request = None):
    _resolve_owner(http_request)
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
async def enrich_generated_mcp_tools(http_request: Request):
    _resolve_owner(http_request)
    root = _repo_root()
    script = root / "scripts" / "enrich_mcp_external_tools.py"
    if not script.exists():
        raise HTTPException(status_code=404, detail="enrich_mcp_external_tools 脚本不存在")
    result = _run_script(root, ["python", str(script)], timeout=120, name="enrich_mcp_external_tools")
    return {"success": True, "summary": result["stdout"]}


@router.post("/pipeline")
async def run_pipeline(payload: IntakePipelineRequest, http_request: Request):
    """
    全自动接入流水线（异步）：
    入队后由后台 worker 串行执行，避免接口长时间阻塞。
    """
    root = _repo_root()
    owner = _resolve_owner(http_request)
    priority = (payload.priority or "normal").strip().lower()
    if priority not in {"high", "normal", "low"}:
        priority = "normal"
    fingerprint = _payload_fingerprint(payload)
    duplicate = _find_recent_duplicate(
        root,
        owner=owner,
        idempotency_key=(payload.idempotency_key or "").strip() or None,
        fingerprint=fingerprint,
    )
    if duplicate:
        return {
            "success": True,
            "queued": True,
            "deduplicated": True,
            "run_id": duplicate.get("run_id"),
            "status": duplicate.get("status"),
            "queue_size": _queued_count(root),
            "running_count": _running_count(root),
        }

    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}_{int(time.time() * 1000) % 100000}"
    created_at = datetime.now().isoformat(timespec="seconds")
    snapshot = _create_snapshot(root, run_id)
    _upsert_task(
        root,
        {
            "run_id": run_id,
            "created_at": created_at,
            "status": "queued",
            "params": payload.model_dump(),
            "snapshot": str(snapshot),
            "owner": owner,
            "fingerprint": fingerprint,
            "idempotency_key": (payload.idempotency_key or "").strip(),
            "timeout_sec": int(payload.timeout_sec),
            "priority": priority,
            "max_retries": max(0, int(payload.max_retries)),
            "retry_backoff_base_sec": max(1, int(payload.retry_backoff_base_sec)),
            "retries": 0,
            "cancel_requested": False,
        },
    )
    INTAKE_TASK_ENQUEUED_TOTAL.inc()
    INTAKE_QUEUE_SIZE.set(_queued_count(root))
    INTAKE_RUNNING_SIZE.set(_running_count(root))
    _append_task_log(root, run_id, "info", "queue", f"enqueued by owner={owner}, priority={priority}")
    _ensure_worker(root)
    return {
        "success": True,
        "queued": True,
        "run_id": run_id,
        "status": "queued",
        "created_at": created_at,
        "queue_size": _queued_count(root),
        "running_count": _running_count(root),
        "priority": priority,
    }


@router.get("/pipeline/history")
async def get_pipeline_history(limit: int = 20, http_request: Request = None):
    root = _repo_root()
    owner = _resolve_owner(http_request)
    rows = _read_history(root, limit=limit, owner=owner)
    return {"success": True, "count": len(rows), "items": rows}


@router.get("/pipeline/latest")
async def get_pipeline_latest(http_request: Request):
    root = _repo_root()
    owner = _resolve_owner(http_request)
    rows = _read_history(root, limit=1, owner=owner)
    if not rows:
        raise HTTPException(status_code=404, detail="暂无 pipeline 运行记录")
    return {"success": True, "item": rows[0]}


@router.get("/pipeline/state")
async def get_pipeline_state(http_request: Request):
    root = _repo_root()
    owner = _resolve_owner(http_request)
    with _WORKER_LOCK:
        workers_alive = len([t for t in _WORKER_THREADS if t.is_alive()])
    owner_tasks = [t for t in _read_tasks(root) if str(t.get("owner", "")) == owner]
    owner_running = sum(1 for t in owner_tasks if str(t.get("status", "")) == "running")
    owner_queue = sum(1 for t in owner_tasks if str(t.get("status", "")) in {"queued", "claimed"})
    latest_owner_task = owner_tasks[0] if owner_tasks else None
    return {
        "success": True,
        "state": {
            **_read_state(root),
            "owner": owner,
            "latest_owner_run_id": latest_owner_task.get("run_id") if latest_owner_task else "",
        },
        "queue_size": owner_queue,
        "running_count": owner_running,
        "worker_count": _WORKER_COUNT,
        "workers_alive": workers_alive,
    }


@router.post("/pipeline/unlock")
async def force_unlock_pipeline(http_request: Request):
    root = _repo_root()
    owner = _resolve_owner(http_request)
    state = _read_state(root)
    if not state.get("running"):
        return {"success": True, "message": "pipeline 未锁定", "state": state}
    run_id = str(state.get("run_id", "")).strip()
    if run_id:
        task = _get_task(root, run_id)
        if task:
            _assert_task_owner(task, owner)
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
async def list_pipeline_tasks(limit: int = 30, http_request: Request = None):
    root = _repo_root()
    owner = _resolve_owner(http_request)
    items = [t for t in _read_tasks(root) if str(t.get("owner", "")) == owner][: max(1, limit)]
    return {"success": True, "count": len(items), "items": items}


@router.get("/pipeline/tasks/{run_id}")
async def get_pipeline_task(run_id: str, http_request: Request):
    root = _repo_root()
    owner = _resolve_owner(http_request)
    task = _get_task(root, run_id)
    if not task:
        raise HTTPException(status_code=404, detail="task 不存在")
    _assert_task_owner(task, owner)
    return {"success": True, "item": task}


@router.post("/pipeline/tasks/{run_id}/retry")
async def retry_pipeline_task(run_id: str, payload: RetryRequest, http_request: Request):
    root = _repo_root()
    owner = _resolve_owner(http_request)
    task = _get_task(root, run_id)
    if not task:
        raise HTTPException(status_code=404, detail="task 不存在")
    _assert_task_owner(task, owner)
    params = task.get("params") or {}
    req = IntakePipelineRequest(**params)
    if not payload.auto_start:
        return {"success": True, "message": "retry 参数已校验", "params": req.model_dump()}
    req.idempotency_key = f"retry-{run_id}-{int(time.time())}"
    return await run_pipeline(req, http_request)


@router.post("/pipeline/tasks/{run_id}/cancel")
async def cancel_pipeline_task(run_id: str, http_request: Request):
    root = _repo_root()
    owner = _resolve_owner(http_request)
    task = _get_task(root, run_id)
    if not task:
        raise HTTPException(status_code=404, detail="task 不存在")
    _assert_task_owner(task, owner)
    status = str(task.get("status", ""))
    if status in {"success", "failed", "cancelled"}:
        return {"success": True, "message": f"任务已结束：{status}", "item": task}

    task["cancel_requested"] = True
    task["cancel_requested_at"] = datetime.now().isoformat(timespec="seconds")
    _upsert_task(root, task)

    if status == "running":
        with _RUN_PROCS_LOCK:
            proc = _RUN_PROCS.get(run_id)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
    _append_task_log(root, run_id, "warn", "cancel", f"cancel requested by owner={owner}")

    return {"success": True, "message": "已请求取消", "run_id": run_id}


@router.post("/pipeline/tasks/{run_id}/rollback")
async def rollback_pipeline_task(run_id: str, http_request: Request):
    root = _repo_root()
    owner = _resolve_owner(http_request)
    task = _get_task(root, run_id)
    if not task:
        raise HTTPException(status_code=404, detail="task 不存在")
    _assert_task_owner(task, owner)
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


@router.get("/pipeline/tasks/{run_id}/logs")
async def get_pipeline_task_logs(run_id: str, after_id: int = 0, limit: int = 200, http_request: Request = None):
    root = _repo_root()
    owner = _resolve_owner(http_request)
    task = _get_task(root, run_id)
    if not task:
        raise HTTPException(status_code=404, detail="task 不存在")
    _assert_task_owner(task, owner)
    items = _read_task_logs(root, run_id, after_id=after_id, limit=limit)
    return {"success": True, "count": len(items), "items": items}


@router.get("/pipeline/tasks/{run_id}/logs/stream")
async def stream_pipeline_task_logs(run_id: str, http_request: Request):
    root = _repo_root()
    owner = _resolve_owner(http_request)
    task = _get_task(root, run_id)
    if not task:
        raise HTTPException(status_code=404, detail="task 不存在")
    _assert_task_owner(task, owner)

    async def event_gen():
        last_id = 0
        idle_round = 0
        while True:
            rows = _read_task_logs(root, run_id, after_id=last_id, limit=100)
            if rows:
                idle_round = 0
                for r in rows:
                    last_id = int(r.get("id", last_id))
                    yield f"data: {json.dumps(r, ensure_ascii=False)}\n\n"
            else:
                idle_round += 1
                yield "data: {\"ping\":true}\n\n"
            current = _get_task(root, run_id)
            if current and str(current.get("status", "")) in {"success", "failed", "cancelled"} and idle_round >= 2:
                break
            await asyncio.sleep(1.0)
        yield "data: {\"done\":true}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
