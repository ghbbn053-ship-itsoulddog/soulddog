# Phase A 任务板（平台内核抽象）

目标：在不破坏现有聊天/流式能力的前提下，完成模型层与工具层抽象。

## A1. 统一模型提供层
- 文件：
  - `backend/app/services/model_provider.py`（新增）
  - `backend/app/services/providers/qwen_provider.py`（新增）
  - `backend/app/services/providers/litellm_provider.py`（新增，先占位可用）
- 产出：
  - `chat(messages)`
  - `chat_stream(messages)`
  - `chat_with_tools(messages, tools_context)`
- 验收：
  - 默认仍走 Qwen（行为不变）
  - provider 异常时可回退并给出可观测日志

## A2. Chat API 接入 Provider
- 文件：
  - `backend/app/api/chat.py`
  - `backend/app/services/__init__.py`
- 产出：
  - 将现有对 `qwen_service` 直接调用改为 `model_provider`
- 验收：
  - `/api/chat/send` 与 `/api/chat/send-stream` 返回结构不变
  - 回归“工具调用 + SSE + fallback”

## A3. MCP Registry 最小版
- 文件：
  - `backend/app/services/mcp_registry.py`（新增）
  - `backend/app/api/mcp.py`（改造）
- 产出：
  - 统一 `register/list/call` 接口
- 验收：
  - 现有6个教务工具全部可列出与调用

## A4. 测试与观测
- 文件：
  - `backend/tests/test_model_provider.py`（新增）
  - `backend/tests/test_mcp_registry.py`（新增）
  - `backend/app/api/chat.py`（增加 trace 字段日志）
- 验收：
  - `python -m py_compile` 全通过
  - 核心测试通过

## 当前进度（2026-04-21）
- [x] A1 完成：`model_provider.py` + `LiteLLM` 兼容入口
- [x] A2 完成：`chat.py` 切换到统一模型层
- [x] A3 完成：`mcp_registry.py` + `mcp.py` 改造
- [x] 补充：模型管理 API（`/api/models/*`）
- [x] 补充：Skill 管理 API（`/api/skills/*`）
- [x] 补充：前端模型设置页 + Skills 管理页
- [x] 补充：Skills 支持 GitHub URL 导入（含基础安全约束）
- [x] 补充：Skill 路由器抽象（chat 脱耦）+ Skill YAML 校验 API
- [ ] 后续：按 Phase B 增强 Skill 安全策略与市场能力

## Linux 验证命令
```bash
git pull origin main
docker compose -f docker-compose.yml restart backend frontend
docker compose -f docker-compose.yml logs -f backend frontend
```
