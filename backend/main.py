"""
教务系统 AI 助手 - 后端 API 入口
职责：应用装配、路由注册、基础健康检查。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import time

from app.core.runtime import DB_AVAILABLE, create_tables, logger, session_store
from app.core.observability import (
    HTTP_REQUEST_TOTAL,
    HTTP_REQUEST_DURATION,
    new_trace_id,
    set_trace_id,
)
from app.api import chat
from app.api import mcp as mcp_router
from app.api.auth_sync import router as auth_sync_router
from app.api.education import router as education_router
from app.api.options import router as options_router
from app.api.models import router as models_router
from app.api.skills import router as skills_router
from app.api.agents import router as agents_router
from app.api.intake import router as intake_router
from app.api.composition import router as composition_router

app = FastAPI(title="教务系统 AI 助手 API", version="1.0.0")
app.state.session_store = session_store

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:5000",
        "http://192.168.88.100:5000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_and_metrics_middleware(request, call_next):
    trace_id = request.headers.get("x-trace-id") or new_trace_id()
    request.state.trace_id = trace_id
    set_trace_id(trace_id)
    t0 = time.perf_counter()
    path = request.url.path
    method = request.method
    try:
        response = await call_next(request)
    except Exception:
        elapsed = time.perf_counter() - t0
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(elapsed)
        HTTP_REQUEST_TOTAL.labels(method=method, path=path, status="500").inc()
        raise
    elapsed = time.perf_counter() - t0
    status = str(getattr(response, "status_code", 200))
    response.headers["x-trace-id"] = trace_id
    HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(elapsed)
    HTTP_REQUEST_TOTAL.labels(method=method, path=path, status=status).inc()
    return response

# 业务路由
app.include_router(auth_sync_router)
app.include_router(education_router)
app.include_router(options_router)
app.include_router(models_router)
app.include_router(skills_router)
app.include_router(agents_router)
app.include_router(intake_router)
app.include_router(composition_router)
app.include_router(chat.router)
app.include_router(mcp_router.router)


@app.on_event("startup")
async def startup_event():
    """App 启动时自动创建数据库表"""
    if DB_AVAILABLE:
        try:
            create_tables()
            logger.info("✅ 数据库表创建/检查完成")
        except Exception as e:
            logger.error(f"❌ 数据库表创建失败: {e}")
    else:
        logger.warning("⚠️ 数据库模块不可用，跳过建表")
    try:
        from app.api.intake import _repo_root, _ensure_runs_db, _ensure_worker

        root = _repo_root()
        _ensure_runs_db(root)
        _ensure_worker(root)
        logger.info("✅ Intake worker 与 runs.sqlite 已初始化")
    except Exception as e:
        logger.error(f"❌ Intake 初始化失败: {e}")


@app.get("/")
async def root():
    return {
        "message": "教务系统 AI 助手 API",
        "version": "1.0.0",
        "docs": "/api - 查看完整 API 列表",
        "endpoints": {
            "captcha": "/api/captcha - 获取验证码",
            "login": "/api/login - 登录",
            "chat": "/api/chat/send - AI对话",
            "mcp": "/api/mcp/tools - MCP工具",
            "health": "/api/health - 健康检查",
        },
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api")
async def api_list():
    return {
        "message": "教务系统 AI 助手 API 列表",
        "apis": {
            "验证码": "/api/captcha - 获取验证码",
            "登录": "/api/login - 登录",
            "个人信息": "/api/user/info?username=xxx",
            "学籍卡片": "/api/user/card?username=xxx",
            "成绩查询": "/api/grades?username=xxx",
            "所有成绩": "/api/grades/all?username=xxx",
            "课表查询": "/api/schedule?username=xxx&semester=2024-2025-2",
            "我的培养方案": "/api/training-plan/my?username=xxx",
            "学业进度": "/api/academic-progress?username=xxx",
            "考试安排": "/api/exam-schedule?username=xxx&semester=2024-2025-1",
            "教师查询": "/api/teacher/search?name=xxx",
            "课程查询": "/api/course/search?course_name=xxx",
            "选课信息": "/api/course-selection?username=xxx",
            "执行计划": "/api/execution-plan?username=xxx",
            "所有数据": "/api/all-data?username=xxx - 用于向量化/RAG",
            "选项查询": {
                "院系列表": "/api/options/departments",
                "学期列表": "/api/options/semesters",
                "当前学期": "/api/options/current-semester",
                "课程选项": "/api/options/course",
                "课表选项": "/api/options/schedule",
                "成绩选项": "/api/options/grade",
                "所有选项": "/api/options/all",
            },
            "健康检查": "/api/health",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
