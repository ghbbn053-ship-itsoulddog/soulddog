# 教务系统 AI 助手 - AI 协作上下文 v2.6

> **本文档专供 AI 开发工具（Qoder、Codex、Cursor 等）使用**
> **最后更新**: 2026-04-13
> **指纹**: GDUFE-JWXT-AI-v2.6

---

## 🎯 项目一句话定位

**广东财经大学教务系统智能助手**：通过爬虫抓取教务数据 + 阿里云千问 AI + RAG 向量检索，为学生提供自然语言问答服务。

---

## 📦 技术栈锚点

```
前端: Next.js 16 + React 19 + TypeScript 5 + Shadcn/UI + Tailwind CSS 4
后端: FastAPI + Python 3.8 + SQLAlchemy + BeautifulSoup4
数据库: PostgreSQL (关系数据) + Milvus v2.4.1 (向量检索)
AI服务: 阿里云千问 qwen-plus + DashScope SDK
部署: Docker Compose (3容器: frontend/backend/milvus)
包管理: pnpm (前端) / pip (后端) - 严禁使用 npm/yarn
```

---

## 📊 项目进度状态

### ✅ 已完成 (70%)
- **用户认证**: 验证码登录、多服务器智能选择（学号%14）、Session管理
- **数据爬虫**: 9类数据爬取（个人信息、成绩、课表、培养方案、学业进度、考试安排、教师查询、课程查询、选课信息）
- **后端API**: 15+ RESTful 接口（`/api/login`, `/api/grades`, `/api/schedule` 等）
- **前端页面**: 登录页、Dashboard、成绩查询页
- **AI服务**: 千问集成、RAG架构代码、Embedding生成

### 🚧 开发中 (20%)
- **AI问答前端**: chat组件已创建，未对接后端 `/api/chat/send`
- **向量数据库**: Milvus已部署，数据向量化逻辑未完成
- **个人信息页**: `/profile` 路由已创建，页面未实现
- **课表页**: 数据显示"即将推出"

### ⏳ 待开发 (10%)
- Redis缓存层
- 流式响应（SSE）
- 对话历史持久化
- 生产环境部署优化

---

## 🏗️ 核心架构决策（不可随意修改）

1. **服务器选择**: 根据学号 `int(username) % 14` 分配教务系统服务器（14台内网服务器）
2. **Session管理**: 当前使用内存存储（`SESSIONS` dict），生产环境需切换 Redis
3. **爬虫策略**: 深度优先爬取，保存HTML源码用于调试（`backend/html/` 目录）
4. **向量化方案**: Milvus Collection `campus_ai`，使用千问 `text-embedding-v2` 模型
5. **API转发**: 前端通过 `http://localhost:8000` 调用后端（开发环境），生产环境使用 Nginx 反向代理
6. **热重载**: 代码修改只需 `docker compose restart`，无需 `--build`（volume挂载）

---

## 🚨 绝对规则（违反将导致错误）

1. **包管理**: 前端仅使用 `pnpm`，后端仅使用 `pip`，严禁 npm/yarn
2. **注释语言**: 所有代码注释必须使用中文
3. **文件创建**: 严禁自动创建新文件（除非用户明确要求）
4. **文档生成**: 严禁自动生成 .md 文档（除非用户明确要求）
5. **环境变量**: 严禁修改 `.env` 文件（需用户确认）
6. **代码风格**: 先理解现有代码再修改，不要覆盖用户的代码
7. **调试策略**: 优先添加日志，不要直接修改核心逻辑

---

## 📁 关键文件路径

```
项目根目录/
├── src/app/                    # 前端页面（Next.js App Router）
│   ├── page.tsx                # 登录页
│   ├── dashboard/page.tsx      # Dashboard
│   ├── grades/page.tsx         # 成绩查询
│   ├── profile/page.tsx        # 个人信息（待实现）
│   └── chat/page.tsx           # AI问答（待对接）
├── backend/
│   ├── main.py                 # FastAPI主程序（8000端口）
│   ├── scraper.py              # 爬虫核心（JwxtScraper类，1220行）
│   ├── education_options.py    # 教务选项查询工具
│   ├── app/api/chat.py         # AI对话API
│   ├── app/services/qwen_service.py  # 千问服务
│   └── app/models/             # SQLAlchemy模型
├── .ai/                        # AI上下文文档（本目录）
└── docker-compose.yml          # 容器编排
```

---

## 🔑 核心业务逻辑

### 登录流程
```
用户输入学号密码验证码 
  → 后端根据学号选择服务器（学号%14）
  → 使用验证码Session发送登录请求
  → 登录成功保存Session到SESSIONS[username]
  → 返回前端，存储到localStorage
```

### 数据爬取流程
```
用户请求数据（如成绩）
  → 后端检查SESSIONS[username]是否存在
  → JwxtScraper使用Session访问教务系统
  → BeautifulSoup解析HTML
  → 返回JSON数据
  → （未来）同步到Milvus向量化
```

### AI问答流程（待实现）
```
用户提问
  → 前端发送问题到 /api/chat/send
  → 后端从Milvus检索相关教务数据（RAG）
  → 构建Prompt：系统提示 + 检索数据 + 用户问题
  → 调用千问API
  → 返回AI回答（未来支持SSE流式）
```

---

## 🐛 已知问题与陷阱

1. **URL双斜杠**: 教务系统URL拼接易产生 `//` 导致404（如 `base_url + /jsxsd/`）
2. **HTML编码**: 教务系统使用GBK编码，需 `response.encoding = 'gbk'`
3. **Session过期**: 验证码Session一次性使用，登录后立即删除
4. **课表解析**: `kbcontent1`（简略版）和 `kbcontent`（详细版）需配合使用
5. **培养方案**: 表格结构复杂，需处理rowspan合并单元格

---

## 📝 AI协作工作流

### 任务开始前
1. 读取本文件了解项目全貌
2. 读取 `.ai/CURRENT-TASK.md` 了解当前任务
3. 使用 `search_codebase` 理解相关代码
4. 确认用户意图，不要自行假设

### 任务进行中
1. 小步修改，每步说明原因
2. 复杂改动分步进行，等待用户确认
3. 优先使用现有代码模式，不要引入新范式

### 任务完成后
1. 更新 `.ai/CURRENT-TASK.md` 进度
2. 生成简短变更摘要（≤200字）
3. 等待用户确认后再提交

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

## 📞 交接指南（给下一个AI）

如果你是新接手的AI（Codex、Cursor等）：

1. **必读文件**:
   - 本文件（`.ai/AI-CONTEXT.md`）
   - `.ai/CURRENT-TASK.md`（当前任务）
   - `AGENTS.md`（项目规范）

2. **快速上手**:
   - 运行 `docker compose ps` 检查容器状态
   - 访问 `http://localhost:5000` 测试前端
   - 访问 `http://localhost:8000/api/health` 测试后端

3. **不要做**:
   - ❌ 不要修改 `.env` 文件
   - ❌ 不要改变项目结构
   - ❌ 不要覆盖用户代码
   - ❌ 不要自动生成文档

4. **优先做**:
   - ✅ 先理解现有代码
   - ✅ 小步修改，等待确认
   - ✅ 使用中文注释
   - ✅ 遵循现有代码风格

---

**文档版本**: v2.6  
**维护者**: 项目开发者  
**更新策略**: 仅在重大变更时手动更新（AI不可自动修改）
