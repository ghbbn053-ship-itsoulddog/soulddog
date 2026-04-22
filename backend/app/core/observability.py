"""
Observability primitives:
- trace_id 上下文
- Prometheus 指标
"""

from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from prometheus_client import Counter, Gauge, Histogram

TRACE_ID_CTX: ContextVar[str] = ContextVar("trace_id", default="")


def new_trace_id() -> str:
    return uuid4().hex


def set_trace_id(trace_id: str):
    TRACE_ID_CTX.set((trace_id or "").strip())


def get_trace_id() -> str:
    v = TRACE_ID_CTX.get("")
    return v or ""


HTTP_REQUEST_TOTAL = Counter(
    "campus_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "campus_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)

INTAKE_TASK_ENQUEUED_TOTAL = Counter(
    "campus_intake_tasks_enqueued_total",
    "Total intake tasks enqueued",
)

INTAKE_TASK_STARTED_TOTAL = Counter(
    "campus_intake_tasks_started_total",
    "Total intake tasks started",
)

INTAKE_TASK_FINISHED_TOTAL = Counter(
    "campus_intake_tasks_finished_total",
    "Total intake tasks finished",
    ["outcome"],  # success | failed | cancelled
)

INTAKE_TASK_DURATION = Histogram(
    "campus_intake_task_duration_seconds",
    "Intake task duration",
    ["outcome"],
)

INTAKE_QUEUE_SIZE = Gauge(
    "campus_intake_queue_size",
    "Current intake queue size",
)

INTAKE_RUNNING_SIZE = Gauge(
    "campus_intake_running_size",
    "Current intake running task count",
)

CHAT_STREAM_REQUESTS_TOTAL = Counter(
    "campus_chat_stream_requests_total",
    "Total chat stream requests",
)

CHAT_STREAM_ABORTED_TOTAL = Counter(
    "campus_chat_stream_aborted_total",
    "Total chat stream aborted by client",
)

CHAT_STREAM_DURATION = Histogram(
    "campus_chat_stream_duration_seconds",
    "Chat stream duration",
    ["outcome"],  # success | failed | aborted
)

