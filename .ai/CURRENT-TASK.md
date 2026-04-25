# 当前任务

> **更新**: AI 可更新进度，用户确认任务变更
> **最后更新**: 2026-04-13

---

## 📋 当前任务

**上下文工程框架初始化** ✅ 已完成（基于真实代码）

---

## 📊 项目整体进度

### ✅ 已完成 (85%)
- 用户认证系统（验证码登录、多服务器选择）
- 数据爬虫（9类数据，1563行，编码自动识别）
- 后端 API 模块化（5个路由文件 + 核心配置）
- 聊天系统（流式SSE、Function Calling、RAG兜底、会话记忆）
- 安全隔离（`auth_session_id` 强绑定、`enforce_username_isolation()`）
- 前端聊天界面（774行，Markdown渲染，节流防闪烁）
- MCP HTTP 接口
- 开发/生产双部署方案
- **上下文工程文档体系**（刚完成）

### 🚧 开发中 (10%)
- **RAG精准化（二阶段）**
  - 向量检索强过滤：`user_id + data_type + semester`
  - 降低“牛头不对马嘴”
- **统一可观测性**
  - `send-stream` 添加 trace_id、首token耗时、fallback计数
- **MCP产品化**
  - 标准工具schema、鉴权、限流、部署说明

### ⏳ 待优化 (5%)
- 聊天页轻微周期性闪烁（已显著降低，未完全归零）
- 教务查询工具调用偶发超时/断流体验优化
- 生产环境全量测试

---

## 🎯 下一步任务（按优先级）

**来自交接工作日志（2026-04-18）**：

1. **RAG精准化（二阶段）** 🔥 优先级最高
   - 向量检索强过滤：`user_id + data_type + semester`
   - 降低“牛头不对马嘴”
   - 相关文件：`backend/app/services/vector_store.py`

2. **统一可观测性**
   - `send-stream` 添加 trace_id、首token耗时、fallback计数
   - 相关文件：`backend/app/api/chat.py`

3. **MCP产品化**
   - 提供标准工具schema、鉴权、限流、部署说明
   - 相关文件：`backend/app/api/mcp.py`

4. **闪烁完全修复**
   - 聊天页轻微周期性闪烁归零
   - 相关文件：`frontend/src/app/chat/page.tsx`

---

## 🚫 阻塞点

- 无（按交接工作日志计划推进）

---

## 📝 相关文件

- `.qoder/交接工作日志.md` - AI接任日志（2026-04-18更新）
- `.qoder/项目结构.txt` - 完整项目文档（280行）
- `.qoder/教务系统源代码/` - 真实HTML基准（9个文件）
- `.ai/AI-CONTEXT.md` - 项目完整上下文
- `.ai/SYSTEM.md` - 系统约束
- `.ai/FINGERPRINT.md` - 项目指纹
- `docs/CONTEXT-ENGINEERING-STRATEGY.md` - 项目上下文策略
- `.ai/CONTEXT-ENGINEERING-FOR-AI-TOOLS.md` - AI 工具上下文指南

---

## 💡 备注

上下文工程框架已初始化完成，基于真实代码状态：
- ✅ 项目指纹（FINGERPRINT.md）- v3.0, 85%进度
- ✅ 系统约束（SYSTEM.md）- 10条已知问题，7条架构决策
- ✅ 当前任务（CURRENT-TASK.md）- 按交接日志计划
- ✅ 完整项目上下文（AI-CONTEXT.md）
- ✅ 上下文工程策略文档（2份）
- ✅ 自动化脚本（ai-context.ps1, update-session.ps1）

**下一步**: 按交接工作日志计划，开始 RAG精准化（二阶段）
