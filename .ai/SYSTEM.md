# 系统约束（AI 编程工具必读）

> **更新权限**: 仅用户可修改，AI 不可自动更改
> **最后更新**: 2026-04-13

---

## 📦 技术栈锚点

```
N16/FAPI/PG/Redis/Milvus/MinIO/Qwen/MCP
```

**展开说明**:
- **N16**: Next.js 16.1.1 (App Router, React 19.2.3, TypeScript 5, Shadcn/UI, Tailwind CSS 4)
- **FAPI**: FastAPI 0.115.6 (Python 3.11+, 8000端口, Uvicorn 0.32.1, --reload)
- **PG**: PostgreSQL 15 (SQLAlchemy ORM, campus_ai 数据库, 5432端口)
- **Redis**: Redis 7 (缓存+Session存储, 6379端口)
- **Milvus**: Milvus v2.4.1 (向量数据库, text-embedding-v2, 19530端口)
- **MinIO**: MinIO (对象存储, 9000/9001端口)
- **Qwen**: 阿里云千问 (qwen-plus, DashScope SDK, 流式SSE输出)
- **MCP**: MCP 1.6.0 (Model Context Protocol, HTTP模式)

---

## 🚨 绝对规则（违反将导致错误）

1. **包管理**: 前端仅使用 `pnpm`，后端仅使用 `pip`，**严禁 npm/yarn**
2. **注释语言**: 所有代码注释**必须使用中文**
3. **文件创建**: **严禁自动创建新文件**（除非用户明确要求）
4. **文档生成**: **严禁自动生成 .md 文档**（除非用户明确要求）
5. **环境变量**: **严禁修改 .env 文件**（需用户确认）
6. **代码风格**: **先理解现有代码再修改**，不要覆盖用户的代码
7. **调试策略**: 优先添加日志，不要直接修改核心逻辑

---

## 🏗️ 核心架构决策

### 1. 后端路由模块化
```python
# backend/main.py 已拆分为：
- app/api/auth_sync.py      # 认证与数据同步
- app/api/education.py      # 教务查询
- app/api/options.py        # 选项接口
- app/api/chat.py           # 聊天API（流式SSE）
- app/api/mcp.py            # MCP HTTP接口
- app/core/runtime.py       # 运行时配置
- app/core/config.py        # 环境变量
```

### 2. 服务器选择策略
```python
# 根据学号自动分配教务系统服务器（14台内网服务器）
server_index = int(username) % 14
```

### 3. Session 管理
- **当前**: `auth_session_id` 服务端会话强绑定 username
- **隔离**: `enforce_username_isolation()` 防止A学号请求B学号数据
- **存储**: session_store.py (Redis + 内存)

### 4. 爬虫策略
- **编码**: UTF-8优先，失败回退GB18030 (`_fix_encoding()`)
- **Session校验**: `_check_session_valid()` 检测是否被踢回登录页
- **HTML基准**: `.qoder/教务系统源代码/` 目录（9个真实HTML文件）
- **深度爬取**: 树形爬取，保存HTML源码用于调试

### 5. 聊天API策略
- **优先级**: 工具调用(Function Calling) > RAG兜底 > 直接对话
- **流式输出**: SSE (Server-Sent Events)，前端节流防闪烁
- **失败兜底**: 流式失败时自动回退非流式响应
- **会话记忆**: PostgreSQL持久化，最近5轮对话历史

### 6. 向量化方案
- **Milvus Collection**: `campus_ai`
- **Embedding 模型**: 千问 `text-embedding-v2`
- **数据隔离**: 按 user_id + data_type + semester 过滤
- **待优化**: RAG精准化（二阶段硬过滤）

### 7. 部署模式
- **开发**: Docker Compose (7容器: postgres/redis/etcd/minio/milvus/frontend/backend)
- **生产**: docker-compose.prod.yml + Nginx网关代理
- **热重载**: 代码修改只需 `docker compose restart`，无需 `--build`
- **端口**: 前端5000，后端8000，Milvus 19530，PostgreSQL 5432，Redis 6379

---

## 📁 关键文件路径

```
项目根目录/
├── backend/
│   ├── main.py                 # FastAPI入口（装配层）
│   ├── scraper.py              # 爬虫核心（JwxtScraper类，1563行）
│   ├── app/api/
│   │   ├── auth_sync.py        # 认证与数据同步
│   │   ├── education.py        # 教务查询
│   │   ├── options.py          # 选项接口
│   │   ├── chat.py             # 聊天API（流式SSE，499行）
│   │   └── mcp.py              # MCP HTTP接口
│   ├── app/services/
│   │   ├── qwen_service.py     # 千问服务（工具调用、RAG）
│   │   ├── vector_store.py     # 向量数据库操作
│   │   ├── session_store.py    # Session管理
│   │   └── education_normalizer.py  # 数据标准化
│   ├── app/core/
│   │   ├── runtime.py          # 运行时配置
│   │   └── config.py           # 环境变量
│   ├── app/security.py         # 安全隔离
│   └── app/models/             # SQLAlchemy模型
├── frontend/src/app/
│   ├── chat/page.tsx           # 聊天界面（774行，流式渲染）
│   ├── login/page.tsx          # 登录页面
│   └── page.tsx                # 首页
├── .qoder/                     # AI协作目录
│   ├── 教务系统源代码/          # 真实HTML基准（9个文件）
│   ├── 交接工作日志.md          # AI接任日志
│   └── 项目结构.txt            # 完整项目文档
├── .ai/                        # 上下文工程文档（本目录）
├── docs/                       # 项目文档
├── docker-compose.yml          # 开发环境容器编排
└── docker-compose.prod.yml     # 生产环境容器编排
```

---

## 🐛 已知问题与陷阱

1. **URL双斜杠**: 教务系统URL拼接易产生 `//` 导致404（已在scraper.py修复：`base_url.rstrip('/') + '/'`）
2. **HTML编码**: 教务系统使用 GBK/UTF-8 混合，需 `_fix_encoding()` 自动识别
3. **Session过期**: 强智系统Session过期会返回登录页HTML，需 `_check_session_valid()` 检测
4. **流式闪烁**: 聊天页仍有轻微周期性闪烁（已节流，未完全归零）
5. **RAG精准度**: 向量检索缺少 `user_id + data_type + semester` 硬过滤（待二阶段优化）
6. **API路径重复**: `NEXT_PUBLIC_API_URL=/api` 与前端拼接可能产生 `/api/api/*`（需避免）
7. **课表解析**: `kbcontent1`（简略版）和 `kbcontent`（详细版）需配合使用
8. **培养方案**: 表格结构复杂，需处理 rowspan 合并单元格
9. **Git同步**: Linux服务器必须手动 `git pull`（Docker不会自动拉取）
10. **代理配置**: Windows推送Git需配置代理（`git config --global http.proxy http://127.0.0.1:7890`）

---

## 💡 AI 协作工作流

### 任务开始前
1. ✅ 读取本文件（`.ai/SYSTEM.md`）了解项目约束
2. ✅ 读取 `.ai/CURRENT-TASK.md` 了解当前任务
3. ✅ 使用 `search_codebase` 理解相关代码
4. ✅ 确认用户意图，**不要自行假设**

### 任务进行中
1. ✅ 小步修改，每步说明原因
2. ✅ 复杂改动分步进行，**等待用户确认**
3. ✅ 优先使用现有代码模式，不要引入新范式

### 任务完成后
1. ✅ 更新 `.ai/CURRENT-TASK.md` 进度
2. ✅ 生成简短变更摘要（≤200字）
3. ✅ **等待用户确认**后再提交

---

## 🔧 常用命令

```bash
# 前端开发
pnpm dev                    # 启动前端（5000端口）

# 后端开发
cd backend && python main.py  # 启动后端（8000端口）

# Docker
docker compose up -d         # 启动所有容器
docker compose restart       # 代码修改后重启（无需build）
docker compose down          # 停止容器

# 数据库
docker exec -it postgres psql -U postgres -d campus_ai  # 进入PostgreSQL
```

---

**文档版本**: v1.0  
**维护者**: 项目开发者  
**更新策略**: 仅用户确认后可修改
