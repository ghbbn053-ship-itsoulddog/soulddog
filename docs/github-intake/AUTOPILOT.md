# GitHub Autopilot（全自动拿来主义）

自动流程：
1. 读取项目需求文档（`PLATFORM_UPGRADE_GUIDE.md`、`.qoder/项目结构.txt`）
2. 自动提取主题（multi-agent / mcp / rag / workflow / evaluation / skill-plugin）
3. 搜索 GitHub 高星且近期活跃仓库
4. 自动评分排序（星数 + 更新时效 + 语言/许可证）
5. 自动克隆 Top N 到 `vendor/autopilot/`
6. 生成可融入路径建议报告

## 运行命令
```bash
python scripts/github_autopilot.py --per-topic 8 --clone-top 4 --integrate-top 8 --update-repo-list
```

仅生成报告，不克隆：
```bash
python scripts/github_autopilot.py --no-clone
```

## 产物
- `docs/github-intake/autopilot-report.md`
- `docs/github-intake/autopilot-report.json`
- `docs/github-intake/repos.txt`（可选自动更新）

## MCP 自动接入链路
1. 生成 MCP 外部工具模板：
```bash
python scripts/generate_mcp_external_tools.py
```
2. 探测工具可达性（只探测）：
```bash
python scripts/probe_mcp_external_tools.py
```
3. 探测并自动启用可达工具：
```bash
python scripts/probe_mcp_external_tools.py --auto-enable
```

4. 从 `vendor/autopilot` 提取端点线索并回填 URL：
```bash
python scripts/enrich_mcp_external_tools.py
```

## 一键全自动流水线（API）
`POST /api/intake/pipeline`

执行顺序：
1. `github_autopilot.py`
2. `generate_mcp_external_tools.py`
3. `enrich_mcp_external_tools.py`
4. `probe_mcp_external_tools.py`
5. 后端进程内 `reload_mcp_registry()`

说明：
- 该接口已升级为“异步入队”模式，调用后立即返回 `run_id` 与 `queue_size`
- 后端 worker 串行消费队列，避免请求长时间阻塞
- 运行状态通过 `GET /api/intake/pipeline/state` 与 `GET /api/intake/pipeline/tasks` 轮询

## 运行记录查询（API）
- `GET /api/intake/pipeline/history?limit=20`
- `GET /api/intake/pipeline/latest`
- `GET /api/intake/pipeline/state`
- `GET /api/intake/pipeline/tasks?limit=30`
- `GET /api/intake/pipeline/tasks/{run_id}`

任务控制（API）：
- `POST /api/intake/pipeline/tasks/{run_id}/retry`
- `POST /api/intake/pipeline/tasks/{run_id}/cancel`
- `POST /api/intake/pipeline/tasks/{run_id}/rollback`
- `POST /api/intake/pipeline/unlock`

可靠性增强：
- `POST /api/intake/pipeline` 支持 `idempotency_key`，用于幂等去重
- `POST /api/intake/pipeline` 支持 `timeout_sec`，用于任务总超时预算
- `POST /api/intake/pipeline` 支持 `priority=high|normal|low`
- `POST /api/intake/pipeline` 支持自动重试：`max_retries` + `retry_backoff_base_sec`
- 对 `queued/running` 任务可请求取消；running 时会终止当前子进程

记录文件：
- `docs/github-intake/pipeline-history.jsonl`
- `docs/github-intake/pipeline-tasks.json`
- `docs/github-intake/snapshots/<run_id>/...`

## Openclaw 对齐（2026-04）
- 参考 `E:/Openclaw/tasks/runs.sqlite` 结构，接入本项目 `backend/data/intake/runs.sqlite`
- 任务主表：`task_runs`（owner/status/priority/retry/timeout/cancel 等）
- 日志表：`task_logs`（按 run_id + 自增 id 拉流）
- 支持实时日志接口：
  - `GET /api/intake/pipeline/tasks/{run_id}/logs`
  - `GET /api/intake/pipeline/tasks/{run_id}/logs/stream`（SSE）

## Skill + MCP 自由拼接（Composition）
- 新增用户组合配置（参考 Openclaw 配置式拼接思路）：
  - `GET /api/composition/{username}`
  - `POST /api/composition/skills`
  - `POST /api/composition/mcp`
  - `POST /api/composition/mcp/reorder`
- 作用：
  - 控制 skill 是否生效（路由阶段）
  - 控制 mcp 工具是否可调用（执行阶段）
  - 定义 mcp 工具排序与权重
