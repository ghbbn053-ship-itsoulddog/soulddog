# 平台重规划执行方案（基于 PLATFORM_UPGRADE_GUIDE）

更新时间：2026-04-21  
目标：将当前“教务问答应用”升级为“可扩展校园 Agent 平台”

## 1. 当前基线（已具备）
- 后端：FastAPI + PostgreSQL + Redis + Milvus
- 前端：Next.js 16 + React 19 + shadcn/ui
- 已有能力：教务爬虫、MCP工具暴露、SSE流式聊天、会话隔离
- 当前痛点：模型单一、工具编排硬编码、生态扩展弱、开发/生产链路不统一

## 2. 升级总目标（分阶段）
1. 模型层解耦：引入统一模型提供层（LiteLLM Provider）
2. 工具层平台化：MCP Registry + Skill Registry（配置驱动）
3. 编排层升级：Router + Domain Agent（先轻量、后LangGraph）
4. 交付层完善：技能市场页、模型选择器、运维与观测标准

## 3. 分期路线图

### Phase A（1-2周）：平台内核抽象
- A1：新增 `model_provider.py`，封装统一 chat/chat_stream/tool-call 接口
- A2：保留 `qwen_service.py` 作为 provider 适配器（不破坏现网）
- A3：新增 `mcp_registry.py`，实现工具注册、发现、调用入口
- A4：把 chat API 调用路径从“直连服务”改为“经 provider + registry”

验收标准：
- 单元测试覆盖 provider fallback 路径
- SSE 功能回归通过
- 不改变现有 `/api/chat/*` 对外协议

### Phase B（2-3周）：Skill 系统落地
- B1：新增 `skills/` 目录与 YAML 规范
- B2：实现 `skill_manager.py`（解析、校验、启停）
- B3：新增 Skill API：上传/列表/启停/删除
- B4：前端新增 Skill 管理页面（先管理台，后市场）

验收标准：
- 可上传一个示例技能并被 chat 路由识别
- 技能启停可实时生效

### Phase C（2-3周）：多 Agent 编排
- C1：先实现轻量 Router（意图分类 + 工具路由）
- C2：拆分 `AcademicAgent` / `GeneralAgent`
- C3：引入 LangGraph（可开关）
- C4：对接可观测埋点（trace_id, first_token_ms, tool_latency_ms）

验收标准：
- 至少两类 Agent 可稳定协作
- 关键链路指标可查

### Phase D（持续）：生态与产品化
- D1：MCP 安装源与版本管理
- D2：Skill Marketplace 基础能力（搜索/安装）
- D3：文档、SDK、贡献规范

## 4. 目录重构目标（不一次性大改）
- backend/app/services/
  - `model_provider.py`（新增）
  - `providers/`（新增，qwen/litellm/ollama）
  - `mcp_registry.py`（新增）
  - `skill_manager.py`（新增）
- backend/app/agents/
  - `router.py`（新增）
  - `academic_agent.py`（新增）
  - `general_agent.py`（新增）
- backend/app/api/
  - `skills.py`（新增）
  - `models.py`（可选新增）
- frontend/src/app/
  - `skills/page.tsx`（新增）
  - `settings/models/page.tsx`（新增）

## 5. 架构原则（长期）
- 向后兼容优先：先包裹、再替换，避免重写导致回归
- 接口稳定优先：对外 API 不轻易变
- 配置驱动优先：Skill/MCP/Model 均通过配置注册
- 观测先行：每次改造同步补 trace/log 指标

## 6. 风险与规避
- 风险1：抽象过度导致速度变慢  
  规避：先最小可用 Provider/Registry，再逐步泛化
- 风险2：SSE 回归  
  规避：将流式链路加入回归清单，强制 smoke test
- 风险3：Skill 安全  
  规避：YAML 声明式 + 工具白名单 + 参数校验

## 7. 本周执行目标（启动批次）
- 完成 Phase A 的 A1+A2：模型层抽象与现网兼容接入
- 产出对应测试与迁移文档

## 8. 已完成落地（2026-04-21）
- 统一模型层已接入主链路：
  - `MODEL_PROVIDER=qwen|litellm`（默认 qwen）
  - `chat/send/send-stream` 已改为统一 provider 调用
- MCP 注册中心已接入：
  - `/api/mcp/tools`
  - `/api/mcp/tools/{tool}`
  - `/api/mcp/tools/{tool}/schema`
- 平台管理接口已上线：
  - 模型管理：`/api/models/available`、`/api/models/preference/*`
  - Skill 管理：`/api/skills/*`
- 前端页面已上线：
  - `/settings/models` 模型切换
  - `/skills` Skill 上传与启停
