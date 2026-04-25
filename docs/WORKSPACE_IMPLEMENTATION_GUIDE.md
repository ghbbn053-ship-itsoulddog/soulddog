# AI学习工作台 - 前后端实现说明

> 基于现有架构升级，从"问答工具"到"AI Agent学习助手"  
> 创建时间：2026-04-20  
> 更新时间：2026-04-22  
> 参考：`.qoder/交接工作日志.md` + `PLATFORM_UPGRADE_GUIDE.md`

---

## 一、项目背景

### 现状（已完成）
- ✅ 后端路由模块化（auth_sync/education/options/chat/mcp/models/skills/composition/intake）
- ✅ 统一模型层（model_provider.py）
- ✅ MCP注册中心（mcp_registry.py）
- ✅ Skill管理器（skill_manager.py + skill_router.py）
- ✅ 组合编排（composition_manager.py）
- ✅ 异步任务队列（intake.py + SQLite持久化）
- ✅ 可观测性（observability.py + Prometheus）
- ✅ 聊天流式输出 + 思考流 + 模型切换

### 目标（本次升级）
- 🎯 双模式架构（快速会话 + AI Agent工作区）
- 🎯 知识库可视化（替代知识图谱）
- 🎯 AI主动推送（定时提醒+建议）
- 🎯 文件上传与检索
- 🎯 学习状态追踪
- 🎯 工作区管理（CRUD）
- 🎯 首页课表卡片（PostgreSQL缓存秒开）
- 🎯 教务数据缓存读取优化（降低99%登录频率）
- 🎯 完整课表页面（周视图+学期切换）
- 🎯 智能数据刷新系统（JSESSIONID检测+AI引导登录）
- 🎯 AI智能过期提醒（数据新鲜度感知）

---

## 二、后端实现清单

### 2.1 新增API模块

#### **模块1：工作区管理**
**文件**: `backend/app/api/workspaces.py`

**接口清单**:
```
GET    /api/workspaces/{username}              # 获取用户工作区列表
POST   /api/workspaces                         # 创建工作区
GET    /api/workspaces/{workspace_id}          # 获取工作区详情
PUT    /api/workspaces/{workspace_id}          # 更新工作区
DELETE /api/workspaces/{workspace_id}          # 删除工作区
POST   /api/workspaces/{workspace_id}/archive  # 归档工作区
```

**请求/响应示例**:
```python
# 创建工作区
POST /api/workspaces
{
  "username": "2021001",
  "name": "高数学习",
  "description": "高等数学系统复习",
  "enabled_skills": ["skill_grades", "skill_graph", "skill_plan"],
  "connected_mcp": ["mcp_jwxt", "mcp_files"]
}

# 响应
{
  "workspace_id": "ws_001",
  "name": "高数学习",
  "created_at": "2026-04-20T10:00:00",
  "status": "active"
}
```

---

#### **模块2：知识库管理**
**文件**: `backend/app/api/knowledge_base.py`

**接口清单**:
```
GET    /api/knowledge/{workspace_id}           # 获取知识库
POST   /api/knowledge/{workspace_id}/upload    # 上传文件
POST   /api/knowledge/{workspace_id}/extract   # 提取知识点
GET    /api/knowledge/{workspace_id}/stats     # 知识库统计
DELETE /api/knowledge/{workspace_id}/{file_id} # 删除文件
```

**数据模型**:
```python
class KnowledgeFile(BaseModel):
    file_id: str
    filename: str
    file_type: str  # ppt/pdf/docx/md
    chunks_count: int  # 分块数
    uploaded_at: datetime
    parsed: bool

class KnowledgeChunk(BaseModel):
    chunk_id: str
    file_id: str
    content: str
    embedding: List[float]  # 向量
    cite_count: int  # 引用次数
```

---

#### **模块3：学习状态**
**文件**: `backend/app/api/learning_status.py`

**接口清单**:
```
GET    /api/status/{workspace_id}              # 获取学习状态
POST   /api/status/{workspace_id}/log          # 记录学习行为
GET    /api/status/{workspace_id}/stats        # 统计数据
```

**统计维度**:
- 学习时长（今日/本周/总计）
- 提问次数
- 对话引用知识点数
- 文件上传数
- 连续学习天数

---

#### **模块4：文件管理**
**文件**: `backend/app/api/files.py`

**接口清单**:
```
POST   /api/files/{workspace_id}/upload        # 上传文件
GET    /api/files/{workspace_id}               # 文件列表
GET    /api/files/{workspace_id}/{file_id}     # 文件详情
DELETE /api/files/{workspace_id}/{file_id}     # 删除文件
POST   /api/files/{workspace_id}/{file_id}/parse # 解析文件
GET    /api/files/{workspace_id}/{file_id}/download # 下载文件
```

**支持格式**:
- PPT/PPTX（演示文稿）
- PDF（文档）
- DOCX（Word）
- MD（Markdown）
- TXT（纯文本）

---

#### **模块5：AI建议与提醒**
**文件**: `backend/app/api/suggestions.py`

**接口清单**:
```
GET    /api/suggestions/{workspace_id}         # 获取建议列表
POST   /api/suggestions/{workspace_id}/accept  # 接受建议
POST   /api/suggestions/{workspace_id}/dismiss # 忽略建议
POST   /api/suggestions/scan                   # 触发扫描（定时任务）
```

**建议类型**:
```python
class SuggestionType(str, Enum):
    EXAM_REMINDER = "exam_reminder"  # 考试提醒
    CLASS_REMINDER = "class_reminder"  # 上课提醒
    STUDY_PLAN = "study_plan"  # 学习建议
    KNOWLEDGE_GAP = "knowledge_gap"  # 知识薄弱点
    REVIEW_REMINDER = "review_reminder"  # 复习提醒
```

---

#### **模块6：缓存数据查询**
**文件**: `backend/app/api/education_cache.py`

**设计原则**: 所有教务数据查询优先读PostgreSQL缓存，不依赖JSESSIONID，秒级响应。

**接口清单**:
```
GET    /api/schedule/db                   # 读取缓存课表
GET    /api/grades/db                      # 读取缓存成绩
GET    /api/exam-schedule/db               # 读取缓存考试安排
GET    /api/user/info/db                   # 读取缓存个人信息
GET    /api/training-plan/my/db            # 读取缓存培养方案
GET    /api/academic-progress/db           # 读取缓存学业进度
GET    /api/execution-plan/db              # 读取缓存执行计划
GET    /api/education/status               # 查询数据缓存状态（新鲜度）
```

**响应格式（统一）**:
```python
# 成功响应
{
  "success": True,
  "data": { ... },           # 具体数据
  "cached_at": "2026-04-22T10:00:00",  # 缓存时间
  "freshness": "fresh"       # fresh / stale / outdated
}

# 无数据响应
{
  "success": False,
  "error": "no_cached_data",
  "message": "暂无缓存数据，请先登录同步"
}
```

**数据新鲜度判定逻辑**:
```python
def get_data_freshness(cached_at: datetime) -> str:
    days = (datetime.utcnow() - cached_at).days
    if days < 7:
        return "fresh"      # 🟢 新鲜
    elif days < 14:
        return "stale"      # 🟡 可能过期
    else:
        return "outdated"   # 🔴 已过期
```

**保留原API**: `/api/schedule`、`/api/grades` 等实时爬取API全部保留，向后兼容。

---

#### **模块7：数据刷新**
**文件**: `backend/app/api/education_refresh.py`

**接口清单**:
```
POST   /api/refresh                        # 手动刷新所有教务数据
POST   /api/refresh/check                  # 检查JSESSIONID是否有效
GET    /api/refresh/progress               # 查询刷新进度
```

**刷新流程**:
```
用户点击刷新
     ↓
POST /api/refresh/check（检测JSESSIONID）
     ↓
┌──────┴──────┐
有效          无效
│             │
↓             ↓
后台爬取     返回 {need_login: true}
     ↓             ↓
更新PG       AI引导重新登录
     ↓             ↓
返回完成     登录成功→自动爬取→更新PG
```

**刷新进度响应**:
```python
{
  "status": "in_progress",     # pending / in_progress / completed / failed
  "progress": {
    "personal_info": "done",
    "schedule": "done",
    "grades": "in_progress",   # 正在爬取
    "academic_progress": "pending",
    "exam_schedule": "pending",
    "training_plan": "pending"
  },
  "started_at": "2026-04-22T10:00:00",
  "estimated_remaining": 15    # 预计剩余秒数
}
```

---

#### **模块8：AI过期提醒**
**文件**: `backend/app/api/chat.py`（在现有对话流中增强）

**接口**: 复用 `/api/send-stream`，在构建上下文时增加数据新鲜度检测。

**提醒逻辑**:
```python
def _should_remind_data_outdated(edu_data: EducationData) -> dict:
    """
    判断是否应该提醒用户数据过期
    - > 14天：强烈建议刷新
    - 7-14天：温和提醒
    - < 7天：不提醒
    """
    days = (datetime.utcnow() - edu_data.last_updated).days
    if days > 14:
        return {"should_remind": True, "level": "strong", "days": days}
    elif days > 7:
        return {"should_remind": True, "level": "gentle", "days": days}
    return {"should_remind": False}
```

**AI对话中的提醒方式**:
```
用户："我今天下午有课吗？"

AI检测到缓存数据10天未更新，在回答后附加：
"我这里的课表数据是10天前更新的，可能不是最新的。
建议点击「刷新数据」按钮更新课表。
如果提示需要登录，重新登录即可自动同步。"
```

---

### 2.2 新增服务层模块

#### **服务1：工作区管理器**
**文件**: `backend/app/services/workspace_manager.py`

**核心功能**:
- 工作区CRUD
- 工作区配置管理（启用哪些Skill/MCP）
- 工作区数据隔离（按user_id + workspace_id）
- 工作区归档/恢复

---

#### **服务2：知识库引擎**
**文件**: `backend/app/services/knowledge_engine.py`

**核心功能**:
- 文件解析（PPT/PDF/DOCX）
- 文本分块
- 向量化存储（Milvus）
- 对话时检索相关片段
- 知识点提取
- 引用追踪

**技术实现**:
```python
class KnowledgeEngine:
    def parse_file(self, file_path: str) -> List[str]:
        """解析文件，提取文本"""
        # PPT/PDF/DOCX解析
        pass
    
    def chunk_text(self, text: str) -> List[str]:
        """文本分块"""
        # 按语义分块
        pass
    
    def search(self, query: str, top_k: int = 5) -> List[Chunk]:
        """检索相关知识"""
        # Milvus向量检索
        pass
```

---

#### **服务3：学习分析器**
**文件**: `backend/app/services/learning_analytics.py`

**核心功能**:
- 学习行为分析
- 学习时长统计
- 提问模式分析
- 连续学习天数计算
- 学习状态评估

---

#### **服务4：文件解析器**
**文件**: `backend/app/services/file_parser.py`

**核心功能**:
- PPT解析（提取文字/图片）
- PDF解析（提取文字/表格）
- 知识点提取
- 自动生成知识卡片

**依赖库**:
```
python-pptx（PPT解析）
PyPDF2（PDF解析）
pdfplumber（PDF表格提取）
```

---

#### **服务5：AI建议引擎**
**文件**: `backend/app/services/suggestion_engine.py`

**核心功能**:
- 定时扫描学生数据（课表/考试/成绩）
- 规则引擎（IF-THEN）
- LLM生成个性化建议
- 优先级排序
- 弹窗推送

---

#### **服务6：数据刷新服务**
**文件**: `backend/app/services/data_refresh.py`

**核心功能**:
- JSESSIONID有效性检测（请求教务系统轻量接口判断）
- 后台异步刷新爬取
- 刷新进度追踪（存Redis）
- 刷新失败重试（最多3次）
- 刷新完成后自动更新PostgreSQL + Milvus

**技术实现**:
```python
class DataRefreshService:
    async def check_session_valid(self, username: str) -> dict:
        """检查教务系统session是否有效"""
        # 尝试请求教务系统轻量接口
        # 返回 {"valid": True/False, "reason": "..."}

    async def refresh_all_data(self, username: str) -> dict:
        """刷新所有教务数据"""
        # 1. 获取有效session
        # 2. 爬取全部数据
        # 3. 更新PostgreSQL
        # 4. 更新Milvus
        # 5. 记录刷新时间到Redis

    async def get_refresh_progress(self, username: str) -> dict:
        """获取刷新进度"""
        # 从Redis读取进度信息
```

---

### 2.3 Redis缓存策略调整

#### **TTL优化**

| 缓存类型 | Key格式 | 优化前TTL | 优化后TTL | 说明 |
|---------|---------|----------|----------|------|
| 用户会话 | `user_session:{username}` | 24小时 | **7天** | 延长教务系统session缓存 |
| 认证会话 | `auth_session:{auth_session_id}` | 24小时 | **30天** | AI对话/工作区长期有效 |
| 数据更新时间 | `data_updated:{username}` | 无 | **新增** | 记录最后同步时间戳 |
| 刷新进度 | `refresh_progress:{username}` | 无 | **新增** | 刷新进度临时存储，TTL=5分钟 |

#### **数据更新时间Key**
```python
# 在 education_sync.py 的 auto_crawl_and_store 中新增
redis.setex(f"data_updated:{username}", 30 * 86400, datetime.utcnow().isoformat())
```

#### **新鲜度查询API**
```python
@router.get("/api/education/status")
async def get_education_status(username: str):
    """查询数据缓存状态"""
    # 1. 从Redis读取 data_updated:{username}
    # 2. 从PostgreSQL读取 education_data.last_updated
    # 3. 计算新鲜度
    # 4. 返回状态
```

---

### 2.4 数据库模型扩展

**文件**: `backend/app/models/`

#### **新增模型**:

```python
# workspace.py
class Workspace(Base):
    __tablename__ = "workspaces"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    config = Column(JSON)  # 启用的Skill/MCP
    status = Column(String, default="active")
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

# knowledge_base.py
class KnowledgeFile(Base):
    __tablename__ = "knowledge_files"
    
    id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String)
    file_size = Column(Integer)
    storage_path = Column(String)
    chunks_count = Column(Integer, default=0)
    parsed = Column(Boolean, default=False)
    created_at = Column(DateTime)

class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    
    id = Column(String, primary_key=True)
    file_id = Column(String, nullable=False)
    workspace_id = Column(String, nullable=False)
    content = Column(Text)
    cite_count = Column(Integer, default=0)
    created_at = Column(DateTime)

# learning_status.py
class LearningLog(Base):
    __tablename__ = "learning_logs"
    
    id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    action = Column(String)  # view/ask/upload
    duration = Column(Integer)  # 秒
    metadata = Column(JSON)
    created_at = Column(DateTime)

# file.py
class WorkspaceFile(Base):
    __tablename__ = "workspace_files"
    
    id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String)
    file_size = Column(Integer)
    storage_path = Column(String)
    parsed = Column(Boolean, default=False)
    created_at = Column(DateTime)

# suggestion.py
class Suggestion(Base):
    __tablename__ = "suggestions"
    
    id = Column(String, primary_key=True)
    workspace_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    type = Column(String)
    content = Column(Text)
    priority = Column(String)  # high/medium/low
    status = Column(String, default="pending")  # pending/accepted/dismissed
    created_at = Column(DateTime)
```

---

### 2.5 路由注册

**文件**: `backend/main.py`

**新增注册**:
```python
from app.api import workspaces, knowledge_base, learning_status, files, suggestions

app.include_router(workspaces.router, prefix="/api/workspaces", tags=["工作区"])
app.include_router(knowledge_base.router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(learning_status.router, prefix="/api/status", tags=["学习状态"])
app.include_router(files.router, prefix="/api/files", tags=["文件管理"])
app.include_router(suggestions.router, prefix="/api/suggestions", tags=["AI建议"])
app.include_router(education_cache.router, prefix="/api", tags=["教务缓存查询"])
app.include_router(education_refresh.router, prefix="/api/refresh", tags=["数据刷新"])
```

---

### 2.6 依赖更新

**文件**: `backend/requirements.txt`

**新增依赖**:
```
# 文件解析
python-pptx==0.6.23
PyPDF2==3.0.1
pdfplumber==0.10.4

# 定时任务
apscheduler==3.10.4
```

---

## 三、前端实现清单

### 3.1 页面结构

**目录**: `frontend/src/app/`

```
app/
├── page.tsx                          # 首页（全屏分割，双模式入口 + 今日课表卡片）
├── login/page.tsx                    # 登录页（保留）
├── chat/page.tsx                     # 快速会话页（改造：+模型选择+保存工作区）
├── schedule/page.tsx                 # 完整课表页（新增：周视图+学期切换）
├── workspace/
│   └── [id]/page.tsx                 # 工作区详情页（核心：三栏AI Agent布局）
├── settings/
│   ├── page.tsx                      # 设置首页
│   ├── models/page.tsx               # 模型设置（已有）
│   └── appearance/page.tsx           # 外观设置（新增）
├── skills/page.tsx                   # Skill管理（已有）
├── mcp/page.tsx                      # MCP管理（已有）
├── composition/page.tsx              # 组合编排（已有）
└── help/page.tsx                     # 帮助文档（新增）
```

**说明**：
- 工作区通过首页直接进入，无需独立列表页
- 创建工作区通过弹窗完成，无需独立页面

---

### 3.2 页面详细设计

#### **页面1：首页（Dashboard）**

**文件**: `frontend/src/app/page.tsx`

**布局（全屏分割 + 课表卡片）**:
```
┌────────┬─────────────────────────────────────────┐
│ 🎓     │                                         │
│ AI助手 │                                         │
│        │    📅 今日课表          💬 快速会话      │
│ ─────  │    ┌────────────┐   ┌────────────┐      │
│        │    │ 08:00 高数 │   │            │      │
│ 💬会话 │    │ 10:00 英语 │   │  快速对话  │      │
│        │    │ 14:00 物理 │   │            │      │
│ 🎓工作 │    │            │   │  [进入]    │      │
│        │    │ 🟢更新2h前│   │            │      │
│ ┌────┐ │    │ [🔄][📊]  │   └────────────┘      │
│ │概览│ │    └────────────┘                       │
│ │课表│ │                                         │
│ │成绩│ │    🎓 学习工作区      📊 学习状态       │
│ │培养│ │    ┌────────────┐   ┌────────────┐      │
│ │文件│ │    │ 高数学习   │   │ 今日学习    │      │
│ └────┘ │    │ 工作区     │   │ 45分钟      │      │
│        │    │  [进入]    │   │ 12提问      │      │
│ ⚙️设置 │    └────────────┘   └────────────┘      │
│ 📖帮助 │                                         │
├────────┤                                         │
│ 👤张三 │                                         │
│ 2021001│                                         │
└────────┴─────────────────────────────────────────┘
```

**今日课表卡片详情**:
```
┌──────────────────────────────────────┐
│  📅 今日课表                   [查看]│
├──────────────────────────────────────┤
│                                      │
│  08:00 - 09:40                      │
│  📘 高等数学                        │
│  📍 A101  👤 张教授                 │
│                                      │
│  10:00 - 11:40                      │
│  📗 大学英语                        │
│  📍 B203  👤 李教授                 │
│                                      │
│  14:00 - 15:40                      │
│  📙 大学物理                        │
│  📍 C305  👤 王教授                 │
│                                      │
├──────────────────────────────────────┤
│  🟢 更新于 2小时前                   │
│  [🔄 刷新]  [📊 完整课表]           │
└──────────────────────────────────────┘
```

**课表卡片数据状态指示**:

| 状态 | 显示效果 | 颜色 | 条件 |
|------|---------|------|------|
| 新鲜 | “更新于 X小时前” | 🟢 绿色 Badge | < 7天 |
| 可能过期 | “更新于 X天前 ⚠️” | 🟡 黄色 Badge | 7-14天 |
| 已过期 | “更新于 X天前 🔴” | 🔴 红色 Badge | > 14天 |
| 无数据 | “暂无课表数据” | ⚪ 灰色 Badge | 无缓存 |

**组件**:
- `TodayScheduleCard.tsx` - 首页今日课表卡片（shadcn Card + Badge + Button）
- `DataFreshnessBadge.tsx` - 数据新鲜度徽标（shadcn Badge variant）
- `ModeSelector.tsx` - 模式选择卡片（左右50%分割）
- `Sidebar.tsx` - 左侧导航栏

---

#### **页面2：快速会话页（Chat）**

**文件**: `frontend/src/app/chat/page.tsx`（改造现有）

**新增功能**:
- 模型选择器（左上）
- 模式选择器（深度思考）
- 保存到工作区按钮（左侧栏）
- 对话历史展示

**布局**:
```
┌────────┬─────────────────────────────────────────┐
│ 🎓     │  ← 返回首页         💬 快速会话         │
│ AI助手 │ ─────────────────────────────────────── │
│        │                                         │
│ ─────  │  对话历史                                │
│        │  ┌───────────────────────────────────┐  │
│ 💬会话 │  │ 👤 什么是导数？                    │  │
│        │  │ 🤖 导数是微积分的核心概念...       │  │
│ 🎓工作 │  └───────────────────────────────────┘  │
│        │                                         │
│ ┌────┐ │  ┌───────────────────────────────────┐  │
│ │保存到│ │  │ [🤖 qwen-plus ▼] [⚡ 深度思考 ▼] │  │
│ │ 工作区│ │  │                                   │  │
│ └──────┘ │  │ 你的问题...                       │  │
│          │  │                      [📎]  [发送] │  │
│ ⚙️设置 │  └───────────────────────────────────┘  │
│ 📖帮助 │                                         │
├────────┤                                         │
│ 👤张三 │                                         │
└────────┴─────────────────────────────────────────┘
```

**点击“保存到工作区”弹窗**:
```
┌─────────────────────────────────┐
│  保存到工作区                    │
├─────────────────────────────────┤
│                                 │
│  选择工作区：                     │
│  ○ 高数学习（42个知识点）        │
│  ○ 英语学习（18个知识点）        │
│  ○ 创建新工作区                  │
│                                 │
│  [取消]  [保存]                  │
│                                 │
└─────────────────────────────────┘
```

---

#### **页面3：工作区详情页（核心页面）**

**文件**: `frontend/src/app/workspace/[id]/page.tsx`

**布局（三栏，AI Agent增强）**:
```
┌────────┬─────────────────────────────────┬────────────┐
│ 🎓     │  🎓 高数学习工作区        ⚙️    │            │
│ AI助手 │ ─────────────────────────────── │            │
│        │                                 │            │
│ ─────  │  📚 知识库可视化                │  💬 AI对话 │
│        │  ┌───────────────────────────┐  │            │
│ 💬会话 │  │ ●●●    ●●●●    ●●        │  │  👤 什么是 │
│        │  │   ●●●  ●●●●●  ●●●●      │  │  导数？    │
│ 🎓工作 │  │  ●●●● ●●●●●● ●●●●●     │  │            │
│        │  │   ●●●  ●●●●●  ●●●●      │  │  🤖 导数是 │
│ ┌────┐ │  │    ●●    ●●●●    ●●      │  │  微积分... │
│ │概览│ │  │                           │  │            │
│ │课表│ │  │  [节点=知识点]            │  │  👤 那积   │
│ │成绩│ │  │  [颜色=掌握度]            │  │  分呢？    │
│ │培养│ │  │  [连线=关联]              │  │            │
│ │文件│ │  └───────────────────────────┘  │            │
│ └────┘ │                                 │            │
│        │  💡 AI建议                      │  ┌──────┐  │
│ ⚙️设置 │  "根据你的情况，建议今晚       │  │[🤖] │  │
│   ├模型│   复习积分，因为..."          │  │[⚡]  │  │
│   ├Skill│                                 │  │      │  │
│   └MCP │  [接受建议] [忽略]              │  │输入..│  │
│        │                                 │  │      │  │
│ 📖帮助 │  📚 知识库                      │  │[📎][发]││
│        │  - 高数第一章.pptx              │  └──────┘  │
│        │  - 课后习题.pdf                 │            │
│        │                                 │            │
│        │  📝 添加内容                    │            │
│        │  ┌───────────────────────────┐  │            │
│        │  │ 输入知识点或上传文件...   │  │            │
│        │  │ [📎 上传]  [添加]         │  │            │
│        │  └───────────────────────────┘  │            │
├────────┤                                 │            │
│ 📊状态 │                                 │            │
│ 45分钟 │                                 │            │
│ 12提问 │                                 │            │
│ 65%正确│                                 │            │
│ 5天连续│                                 │            │
└────────┴─────────────────────────────────┴────────────┘
```

**AI提醒弹窗（触发时）**:
```
┌─────────────────────────────────┐
│  🔔 AI提醒                       │
├─────────────────────────────────┤
│                                 │
│  🚨 紧急                         │
│                                 │
│  3天后高数期中考试               │
│  你的导数掌握度只有60%           │
│                                 │
│  建议：                          │
│  今晚复习导数（45分钟）          │
│                                 │
│  [立即开始] [稍后] [忽略]        │
│                                 │
└─────────────────────────────────┘
```

**组件清单**:
- `WorkspaceLayout.tsx` - 三栏布局容器
- `Sidebar.tsx` - 左侧导航栏
- `KnowledgeVisualization.tsx` - 知识库可视化
- `AIPanel.tsx` - 右侧AI对话区
- `AISuggestion.tsx` - AI建议组件
- `ReminderModal.tsx` - 提醒弹窗
- `FileUploader.tsx` - 文件上传
- `LearningStatus.tsx` - 学习状态展示

---

#### **页面4：完整课表页（新增）**

**文件**: `frontend/src/app/schedule/page.tsx`

**布局（周视图）**:
```
┌────────┬──────────────────────────────────────────────┐
│ 🎓     │  📅 我的课表              [🔄 刷新] [📊 统计]│
│ AI助手 │ ──────────────────────────────────────────── │
│        │  🟢 数据更新于: 2小时前                      │
│ ─────  │  ┌──┬──────┬──────┬──────┬──────┬──────┬──┐ │
│        │  │节│ 周一  │ 周二  │ 周三  │ 周四  │ 周五  │周│ │
│ 💬会话 │  ├──┼──────┼──────┼──────┼──────┼──────┼──┤ │
│        │  │1-2│ 高数 │      │ 英语 │      │ 物理 │  │ │
│ 🎓工作 │  │   │ A101 │      │ B203 │      │ C305 │  │ │
│        │  ├──┼──────┼──────┼──────┼──────┼──────┼──┤ │
│ ┌────┐ │  │3-4│      │数据结构│     │ 高数 │      │  │ │
│ │概览│ │  │   │      │ D401 │      │ A101 │      │  │ │
│ │课表│ │  ├──┼──────┼──────┼──────┼──────┼──────┼──┤ │
│ │成绩│ │  │5-6│ 体育 │      │ 物理 │      │      │  │ │
│ │培养│ │  │   │ 操场 │      │ C305 │      │      │  │ │
│ │文件│ │  └──┴──────┴──────┴──────┴──────┴──────┴──┘ │
│ └────┘ │  📍 当前周: 第8周   [◀ 上一周]  [下一周 ▶]  │
│        │  📅 学期: 2025-2026-2 [学期选择 ▼]          │
│ ⚙️设置 │                                              │
│ 📖帮助 │                                              │
├────────┤                                              │
│ 👤张三 │                                              │
└────────┴──────────────────────────────────────────────┘
```

**shadcn/ui 组件清单**:
- `Card` - 课表卡片容器、课程格子
- `Table` - 课表网格（表头+单元格）
- `Button` - 刷新、周次切换、学期选择
- `Badge` - 数据新鲜度、课程类型标签
- `Select` - 学期选择下拉框
- `Tooltip` - 课程详情悬浮提示
- `Dialog` - 课程详情弹窗
- `Progress` - 刷新进度条
- `Skeleton` - 加载骨架屏

**数据来源**: 调用 `/api/schedule/db`（PostgreSQL缓存，秒级响应）

**功能交互**:
- 周次切换：`Button` variant="outline" 左右箭头
- 学期切换：`Select` 下拉框
- 课程详情：点击课格 → `Dialog` 弹窗显示课程信息
- 刷新按钮：触发 `POST /api/refresh`，显示 `Progress` 进度条
- 数据状态：顶部 `Badge` 显示新鲜度

---

### 3.3 核心组件实现

#### **组件1：知识库可视化**

**文件**: `frontend/src/components/knowledge/KnowledgeVisualization.tsx`

**技术栈**: ReactFlow

**功能**:
- 节点渲染（知识点）
- 节点颜色（引用次数/掌握度）
- 连线显示（关联关系）
- 交互（点击/悬停/拖拽/缩放）

**Props**:
```typescript
interface KnowledgeVisualizationProps {
  workspaceId: string;
  files: KnowledgeFile[];
  chunks: KnowledgeChunk[];
  onNodeClick: (chunk: KnowledgeChunk) => void;
}
```

---

#### **组件2：文件上传**

**文件**: `frontend/src/components/workspace/FileUploader.tsx`

**技术栈**: react-dropzone

**功能**:
- 拖拽上传
- 文件类型校验
- 上传进度条
- 解析状态显示
- 文件列表管理

---

#### **组件3：AI对话面板**

**文件**: `frontend/src/components/workspace/AIPanel.tsx`

**功能**:
- 对话窗口
- 模型选择器
- 模式选择器（深度思考）
- 文件附件
- 流式输出

---

#### **组件4：AI建议**

**文件**: `frontend/src/components/workspace/AISuggestion.tsx`

**功能**:
- 建议展示
- 推荐理由
- 接受/忽略按钮
- 优先级显示

---

#### **组件5：提醒弹窗**

**文件**: `frontend/src/components/workspace/ReminderModal.tsx`

**功能**:
- 紧急提醒
- 建议展示
- 操作按钮（立即开始/稍后/忽略）
- 自动触发

---

#### **组件6：今日课表卡片**

**文件**: `frontend/src/components/home/TodayScheduleCard.tsx`

**shadcn/ui 组件组合**:
```tsx
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
```

**功能**:
- 显示今日课程列表（时间 + 课程名 + 教室 + 教师）
- 数据来源：`GET /api/schedule/db`（PostgreSQL缓存）
- 底部显示数据新鲜度 Badge
- 刷新按钮：触发 `POST /api/refresh`
- 查看完整：跳转 `/schedule` 完整课表页

**布局结构**:
```tsx
<Card className="hover:shadow-md transition-shadow duration-200">
  <CardHeader className="pb-3">
    <div className="flex items-center justify-between">
      <CardTitle className="text-lg font-semibold">📅 今日课表</CardTitle>
      <Button variant="ghost" size="sm" onClick={onViewFull}>查看</Button>
    </div>
  </CardHeader>
  <CardContent className="space-y-3">
    {/* 每门课程 */}
    <div className="flex items-start gap-3">
      <span className="text-sm text-muted-foreground whitespace-nowrap">08:00</span>
      <div>
        <p className="text-sm font-medium">高等数学</p>
        <p className="text-xs text-muted-foreground">📍 A101 · 👤 张教授</p>
      </div>
    </div>
  </CardContent>
  <CardFooter className="flex items-center justify-between pt-3 border-t">
    <DataFreshnessBadge freshness={freshness} cachedAt={cachedAt} />
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={onRefresh}>🔄 刷新</Button>
      <Button variant="outline" size="sm" onClick={onViewFull}>📊 完整课表</Button>
    </div>
  </CardFooter>
</Card>
```

**空状态**（无缓存数据）:
```tsx
<Card className="hover:shadow-md transition-shadow duration-200">
  <CardContent className="flex flex-col items-center justify-center py-8">
    <Calendar className="w-12 h-12 text-muted-foreground mb-3" />
    <p className="text-sm text-muted-foreground mb-2">暂无课表数据</p>
    <Button variant="outline" size="sm" onClick={onLogin}>登录同步课表</Button>
  </CardContent>
</Card>
```

**加载状态**（骨架屏）:
```tsx
<Card>
  <CardHeader className="pb-3">
    <Skeleton className="h-6 w-24" />
  </CardHeader>
  <CardContent className="space-y-3">
    <div className="flex items-start gap-3">
      <Skeleton className="h-4 w-12" />
      <div className="space-y-1">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-3 w-28" />
      </div>
    </div>
  </CardContent>
</Card>
```

---

#### **组件7：数据新鲜度徽标**

**文件**: `frontend/src/components/home/DataFreshnessBadge.tsx`

**shadcn/ui 组件组合**:
```tsx
import { Badge } from "@/components/ui/badge"
```

**功能**: 根据数据新鲜度显示不同状态的 Badge

**实现**:
```tsx
function DataFreshnessBadge({ freshness, cachedAt }: Props) {
  const config = {
    fresh:   { label: `更新于 ${timeAgo}`, variant: "default",  className: "bg-green-100 text-green-700 hover:bg-green-100" },
    stale:   { label: `更新于 ${days}天前 ⚠️`, variant: "secondary", className: "bg-yellow-100 text-yellow-700 hover:bg-yellow-100" },
    outdated:{ label: `更新于 ${days}天前 🔴`, variant: "destructive", className: "" },
  }[freshness]
  return <Badge variant={config.variant} className={config.className}>{config.label}</Badge>
}
```

---

#### **组件8：课表周视图网格**

**文件**: `frontend/src/components/schedule/ScheduleGrid.tsx`

**shadcn/ui 组件组合**:
```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Card } from "@/components/ui/card"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
```

**功能**:
- 周视图课表网格（Table 组件）
- 每个课程格子用 Card 包裹
- 悬停显示 Tooltip 课程详情
- 点击弹出 Dialog 完整信息
- 空格子半透明显示

**课程格子样式**:
```tsx
{/* 有课的格子 */}
<Card className="p-2 cursor-pointer hover:shadow-md transition-all duration-200 border-l-4"
  style={{ borderLeftColor: courseColor }}>
  <p className="text-sm font-medium truncate">{course.name}</p>
  <p className="text-xs text-muted-foreground">{course.location}</p>
</Card>

{/* 空格子 */}
<div className="p-2 opacity-0 hover:opacity-30 transition-opacity duration-200" />
```

---

#### **组件9：刷新进度条**

**文件**: `frontend/src/components/schedule/RefreshProgress.tsx`

**shadcn/ui 组件组合**:
```tsx
import { Progress } from "@/components/ui/progress"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
```

**功能**:
- 显示当前刷新进度
- 每个数据项显示状态（done / in_progress / pending）
- 整体进度条

**布局**:
```tsx
<Card>
  <CardHeader className="pb-2">
    <CardTitle className="text-base">🔄 正在更新数据...</CardTitle>
  </CardHeader>
  <CardContent className="space-y-2">
    <div className="flex items-center gap-2">
      <Badge variant="default" className="bg-green-100 text-green-700">✓ 个人信息</Badge>
    </div>
    <div className="flex items-center gap-2">
      <Badge variant="default" className="bg-green-100 text-green-700">✓ 课表</Badge>
    </div>
    <div className="flex items-center gap-2">
      <Badge variant="secondary">⏳ 成绩 (正在爬取...)</Badge>
    </div>
    <div className="flex items-center gap-2">
      <Badge variant="outline">⏸ 学业进度</Badge>
    </div>
    <Progress value={40} className="mt-3" />
    <p className="text-xs text-muted-foreground text-right">预计还需 15 秒...</p>
  </CardContent>
</Card>
```

---

### 3.4 依赖更新

#### **色彩方案（精确色值）**

```css
:root {
  /* ========== 主色 ========== */
  --brand-primary: #3B82F6;        /* 品牌主色（蓝色） */
  --brand-hover: #2563EB;          /* 悬停态 */
  --brand-active: #1D4ED8;         /* 点击态 */
  --brand-light: #DBEAFE;          /* 浅色背景 */
  --brand-lighter: #EFF6FF;        /* 更浅色 */
  
  /* ========== 状态色 ========== */
  /* 成功 */
  --success: #10B981;
  --success-hover: #059669;
  --success-light: #D1FAE5;
  
  /* 警告 */
  --warning: #F59E0B;
  --warning-hover: #D97706;
  --warning-light: #FEF3C7;
  
  /* 错误 */
  --error: #EF4444;
  --error-hover: #DC2626;
  --error-light: #FEE2E2;
  
  /* 信息 */
  --info: #06B6D4;
  --info-hover: #0891B2;
  --info-light: #CFFAFE;
  
  /* ========== 背景色 ========== */
  --bg-primary: #F9FAFB;           /* 页面主背景 */
  --bg-card: #FFFFFF;              /* 卡片背景 */
  --bg-sidebar: #F3F4F6;           /* 侧边栏背景 */
  --bg-hover: #F9FAFB;             /* 悬停背景 */
  --bg-active: #F3F4F6;            /* 激活背景 */
  --bg-disabled: #F9FAFB;          /* 禁用背景 */
  
  /* ========== 文字色 ========== */
  --text-primary: #111827;         /* 主文字（标题） */
  --text-secondary: #6B7280;       /* 次要文字（正文） */
  --text-muted: #9CA3AF;           /* 弱化文字（提示） */
  --text-disabled: #D1D5DB;        /* 禁用文字 */
  --text-inverse: #FFFFFF;         /* 反色文字（深色背景上） */
  
  /* ========== 边框色 ========== */
  --border-light: #F3F4F6;         /* 浅色边框 */
  --border: #E5E7EB;               /* 标准边框 */
  --border-hover: #D1D5DB;         /* 悬停边框 */
  --border-focus: #3B82F6;         /* 聚焦边框 */
  --border-error: #EF4444;         /* 错误边框 */
  
  /* ========== 阴影 ========== */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
}
```

---

#### **间距系统（精确到像素）**

```css
/* ========== Tailwind 间距映射 ========== */
空间单位: 4px = 1单位

0.5 → 2px    (极小间距，图标与文字)
1   → 4px    (小组件内边距)
1.5 → 6px    (标签内边距)
2   → 8px    (标准内边距)
2.5 → 10px   (按钮内边距)
3   → 12px   (卡片内边距)
4   → 16px   (组件间距)
5   → 20px   (大组件间距)
6   → 24px   (区块间距)
8   → 32px   (大区块间距)
10  → 40px   (页面边距)
12  → 48px   (页面大间距)
16  → 64px   (页面最大间距)

/* ========== 应用场景 ========== */
按钮内边距: px-4 py-2 (16px 8px)
卡片内边距: p-6 (24px)
组件间距: gap-4 (16px)
页面边距: p-6 md:p-8 lg:p-10 (24px/32px/40px)
```

---

#### **字体规范（精确到行高）**

```css
/* ========== 字体系列 ========== */
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'Fira Code', 'Courier New', monospace;

/* ========== 字号与行高 ========== */
/* 标题 */
--text-xs: 0.75rem;     /* 12px */
  line-height: 1rem;    /* 16px */
  
--text-sm: 0.875rem;    /* 14px */
  line-height: 1.25rem; /* 20px */
  
--text-base: 1rem;      /* 16px */
  line-height: 1.5rem;  /* 24px */
  
--text-lg: 1.125rem;    /* 18px */
  line-height: 1.75rem; /* 28px */
  
--text-xl: 1.25rem;     /* 20px */
  line-height: 1.75rem; /* 28px */
  
--text-2xl: 1.5rem;     /* 24px */
  line-height: 2rem;    /* 32px */
  
--text-3xl: 1.875rem;   /* 30px */
  line-height: 2.25rem; /* 36px */

/* 字重 */
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;

/* ========== 应用场景 ========== */
页面标题: text-3xl font-bold (30px, 700)
卡片标题: text-xl font-semibold (20px, 600)
正文: text-base (16px, 400)
辅助文字: text-sm text-secondary (14px, 灰色)
标签: text-xs font-medium (12px, 500)
```

---

#### **圆角规范**

```css
/* ========== 圆角映射 ========== */
--radius-sm: 0.25rem;    /* 4px - 小按钮、标签 */
--radius: 0.375rem;      /* 6px - 标准组件 */
--radius-md: 0.5rem;     /* 8px - 卡片、输入框 */
--radius-lg: 0.75rem;    /* 12px - 大卡片 */
--radius-xl: 1rem;       /* 16px - 模态框 */
--radius-2xl: 1.5rem;    /* 24px - 特殊卡片 */
--radius-full: 9999px;   /* 圆形 - 头像、徽章 */

/* ========== 应用场景 ========== */
按钮: rounded-md (8px)
卡片: rounded-lg (12px)
输入框: rounded-md (8px)
头像: rounded-full (圆形)
标签: rounded-full (圆形)
```

---

#### **响应式断点（精确到设备）**

```css
/* ========== 断点定义 ========== */
/* 手机竖屏 */
@media (max-width: 640px) {
  /* 单栏布局 */
  /* 隐藏侧边栏，使用底部导航 */
  /* 字体缩小 */
  /* 间距减小 */
}

/* 手机横屏 / 小平板 */
@media (min-width: 641px) and (max-width: 768px) {
  /* 双栏布局 */
  /* 侧边栏可折叠 */
}

/* 平板 */
@media (min-width: 769px) and (max-width: 1024px) {
  /* 双栏布局（侧边栏+主内容） */
  /* AI面板可切换显示 */
}

/* 小屏幕桌面 */
@media (min-width: 1025px) and (max-width: 1280px) {
  /* 三栏布局 */
  /* 标准间距 */
}

/* 标准桌面 */
@media (min-width: 1281px) and (max-width: 1536px) {
  /* 三栏布局 */
  /* 最大宽度限制 */
  max-width: 1440px;
  margin: 0 auto;
}

/* 大屏桌面 */
@media (min-width: 1537px) {
  /* 三栏布局 */
  /* 居中显示 */
  max-width: 1600px;
  margin: 0 auto;
}
```

---

#### **组件样式规范（逐个组件）**

##### **1. 按钮样式**

```tsx
/* ========== 主要按钮 ========== */
<button className="
  px-4 py-2                    /* 内边距 16px 8px */
  bg-brand-primary             /* 背景色 #3B82F6 */
  text-white                   /* 文字白色 */
  font-medium                  /* 字重 500 */
  rounded-md                   /* 圆角 8px */
  shadow-sm                    /* 阴影 */
  hover:bg-brand-hover         /* 悬停背景 #2563EB */
  active:bg-brand-active       /* 点击背景 #1D4ED8 */
  focus:outline-none           /* 移除默认轮廓 */
  focus:ring-2                 /* 聚焦环宽度 */
  focus:ring-brand-primary     /* 聚焦环颜色 */
  focus:ring-offset-2          /* 聚焦环偏移 */
  disabled:opacity-50          /* 禁用透明度 */
  disabled:cursor-not-allowed  /* 禁用光标 */
  transition-all               /* 过渡动画 */
  duration-200                 /* 动画时长 200ms */
">
  按钮文字
</button>

/* ========== 次要按钮 ========== */
<button className="
  px-4 py-2
  bg-white                     /* 背景白色 */
  text-brand-primary           /* 文字蓝色 */
  border border-brand-primary  /* 蓝色边框 */
  font-medium
  rounded-md
  hover:bg-brand-light         /* 悬停浅蓝背景 */
  active:bg-brand-lighter
  focus:ring-2 focus:ring-brand-primary
  transition-all duration-200
">
  按钮文字
</button>

/* ========== 文字按钮 ========== */
<button className="
  px-3 py-1.5
  text-brand-primary
  font-medium
  hover:bg-brand-light
  rounded-md
  transition-all duration-200
">
  按钮文字
</button>

/* ========== 图标按钮 ========== */
<button className="
  p-2                          /* 内边距 8px */
  text-text-secondary          /* 灰色图标 */
  hover:text-text-primary      /* 悬停深色 */
  hover:bg-bg-hover            /* 悬停背景 */
  rounded-md
  transition-all duration-200
">
  <Icon />
</button>
```

---

##### **2. 卡片样式**

```tsx
/* ========== 标准卡片 ========== */
<div className="
  bg-white                     /* 白色背景 */
  rounded-lg                   /* 圆角 12px */
  shadow                       /* 标准阴影 */
  border border-border-light   /* 浅色边框 */
  p-6                          /* 内边距 24px */
  hover:shadow-md              /* 悬停阴影加深 */
  transition-shadow duration-200
">
  卡片内容
</div>

/* ========== 交互式卡片 ========== */
<div className="
  bg-white
  rounded-lg
  shadow
  border border-border-light
  p-6
  cursor-pointer               /* 鼠标指针 */
  hover:shadow-md
  hover:border-border-hover    /* 悬停边框加深 */
  hover:-translate-y-0.5       /* 悬停上移 2px */
  active:translate-y-0         /* 点击复位 */
  transition-all duration-200
">
  卡片内容
</div>

/* ========== 高亮卡片 ========== */
<div className="
  bg-brand-lighter             /* 浅蓝背景 */
  rounded-lg
  border-2 border-brand-primary /* 蓝色粗边框 */
  p-6
  shadow-md
">
  卡片内容
</div>
```

---

##### **3. 输入框样式**

```tsx
/* ========== 标准输入框 ========== */
<input className="
  w-full                       /* 宽度100% */
  px-3 py-2                    /* 内边距 12px 8px */
  bg-white
  border border-border         /* 标准边框 */
  rounded-md                   /* 圆角 8px */
  text-text-primary
  placeholder-text-muted       /* 占位符灰色 */
  focus:outline-none
  focus:ring-2                 /* 聚焦环 */
  focus:ring-brand-primary
  focus:border-transparent     /* 聚焦时边框透明 */
  disabled:bg-bg-disabled
  disabled:cursor-not-allowed
  transition-all duration-200
" />

/* ========== 错误状态 ========== */
<input className="
  ...                          /* 同上 */
  border-error                 /* 红色边框 */
  focus:ring-error             /* 聚焦环红色 */
" />

/* ========== 带图标的输入框 ========== */
<div className="relative">
  <Icon className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
  <input className="pl-10 ..." /> {/* 左边距留给图标 */}
</div>
```

---

##### **4. 标签样式**

```tsx
/* ========== 默认标签 ========== */
<span className="
  inline-flex items-center
  px-2.5 py-0.5                /* 内边距 10px 2px */
  text-xs font-medium          /* 12px 500 */
  rounded-full                 /* 圆形 */
  bg-bg-active                 /* 灰色背景 */
  text-text-secondary
">
  标签文字
</span>

/* ========== 成功标签 ========== */
<span className="
  inline-flex items-center
  px-2.5 py-0.5
  text-xs font-medium
  rounded-full
  bg-success-light             /* 浅绿背景 */
  text-success                 /* 绿色文字 */
">
  ✓ 已完成
</span>

/* ========== 警告标签 ========== */
<span className="
  inline-flex items-center
  px-2.5 py-0.5
  text-xs font-medium
  rounded-full
  bg-warning-light             /* 浅橙背景 */
  text-warning                 /* 橙色文字 */
">
  ⚠ 进行中
</span>
```

---

##### **5. 进度条样式**

```tsx
/* ========== 基础进度条 ========== */
<div className="w-full bg-bg-active rounded-full h-2.5 overflow-hidden">
  <div 
    className="bg-brand-primary h-2.5 rounded-full transition-all duration-500" 
    style={{ width: '60%' }}
  />
</div>

/* ========== 带文字 ========== */
<div>
  <div className="flex justify-between mb-1">
    <span className="text-sm font-medium text-text-primary">第一章</span>
    <span className="text-sm font-medium text-text-secondary">60%</span>
  </div>
  <div className="w-full bg-bg-active rounded-full h-2.5 overflow-hidden">
    <div 
      className="bg-brand-primary h-2.5 rounded-full transition-all duration-500" 
      style={{ width: '60%' }}
    />
  </div>
</div>

/* ========== 多色进度条 ========== */
<div className="w-full bg-bg-active rounded-full h-2.5 overflow-hidden flex">
  <div className="bg-success h-2.5" style={{ width: '40%' }} />
  <div className="bg-warning h-2.5" style={{ width: '20%' }} />
  <div className="bg-error h-2.5" style={{ width: '10%' }} />
</div>
```

---

##### **6. 三栏布局样式**

```tsx
/* ========== 工作区详情页（三栏） ========== */
<div className="
  flex                         /* Flexbox布局 */
  h-screen                     /* 全屏高度 */
  bg-bg-primary                /* 浅灰背景 */
  overflow-hidden              /* 隐藏溢出 */
>
  {/* 左侧栏 20% */}
  <aside className="
    w-64                       /* 固定宽度 256px */
    bg-white                   /* 白色背景 */
    border-r border-border-light /* 右边框 */
    flex flex-col              /* 垂直布局 */
    overflow-y-auto            /* 垂直滚动 */
  ">
    左侧内容
  </aside>

  {/* 主工作区 50% */}
  <main className="
    flex-1                     /* 占据剩余空间 */
    overflow-y-auto            /* 垂直滚动 */
    p-6                        /* 内边距 24px */
  ">
    主内容
  </main>

  {/* 右侧AI面板 30% */}
  <aside className="
    w-96                       /* 固定宽度 384px */
    bg-white
    border-l border-border-light
    flex flex-col
    overflow-y-auto
  ">
    AI面板内容
  </aside>
</div>

/* ========== 响应式适配 ========== */
/* 移动端：单栏 */
@media (max-width: 768px) {
  <div className="flex flex-col">
    <main className="flex-1" />
    {/* 侧边栏隐藏，使用底部导航 */}
  </div>
}

/* 平板：双栏 */
@media (min-width: 769px) and (max-width: 1024px) {
  <div className="flex">
    <aside className="w-56" /> {/* 侧边栏缩小 */}
    <main className="flex-1" />
    {/* AI面板隐藏，可切换显示 */}
  </div>
}
```

---

##### **7. 导航菜单样式**

```tsx
/* ========== 左侧导航 ========== */
<nav className="flex flex-col gap-1 p-3">
  {/* 激活项 */}
  <a className="
    flex items-center gap-3
    px-3 py-2
    bg-brand-light             /* 浅蓝背景 */
    text-brand-primary         /* 蓝色文字 */
    font-medium
    rounded-md
  ">
    <Icon className="w-5 h-5" />
    <span>概览</span>
  </a>

  {/* 普通项 */}
  <a className="
    flex items-center gap-3
    px-3 py-2
    text-text-secondary
    hover:bg-bg-hover          /* 悬停背景 */
    hover:text-text-primary
    rounded-md
    transition-colors duration-200
  ">
    <Icon className="w-5 h-5" />
n    <span>课程</span>
  </a>
</nav>
```

---

##### **8. 空状态样式**

```tsx
/* ========== 空状态 ========== */
<div className="
  flex flex-col items-center justify-center
  py-12 px-6                   /* 垂直间距大 */
  text-center
>
  <Icon className="w-16 h-16 text-text-muted mb-4" /> {/* 大图标 */}
  <h3 className="text-lg font-medium text-text-primary mb-2">
    暂无数据
  </h3>
  <p className="text-sm text-text-secondary mb-4">
    还没有任何工作区，创建一个开始学习吧
  </p>
  <button className="px-4 py-2 bg-brand-primary text-white rounded-md">
    创建工作区
  </button>
</div>
```

---

##### **9. 加载状态样式**

```tsx
/* ========== 骨架屏 ========== */
<div className="animate-pulse space-y-4">
  <div className="h-4 bg-bg-active rounded w-3/4" />
  <div className="h-4 bg-bg-active rounded" />
  <div className="h-4 bg-bg-active rounded w-5/6" />
</div>

/* ========== 旋转加载 ========== */
<div className="flex items-center justify-center py-12">
  <div className="
    w-8 h-8
    border-4 border-border
    border-t-brand-primary
    rounded-full
    animate-spin
  " />
</div>
```

---

##### **10. 滚动条样式**

```css
/* ========== 自定义滚动条 ========== */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #D1D5DB;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #9CA3AF;
}

/* Firefox */
* {
  scrollbar-width: thin;
  scrollbar-color: #D1D5DB transparent;
}
```

---

#### **动画规范**

```css
/* ========== 过渡动画 ========== */
/* 快速动画（交互反馈） */
--transition-fast: 150ms;

/* 标准动画（状态变化） */
--transition: 200ms;

/* 慢速动画（页面切换） */
--transition-slow: 300ms;

/* 缓动函数 */
--ease-in: cubic-bezier(0.4, 0, 1, 1);
--ease-out: cubic-bezier(0, 0, 0.2, 1);
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);

/* ========== 应用场景 ========== */
按钮悬停: transition-colors duration-200
卡片悬停: transition-all duration-200
模态框: transition-opacity duration-300
页面切换: transition-transform duration-300
```

---

#### **图标规范**

```tsx
/* ========== 图标尺寸 ========== */
--icon-xs: 12px;    /* 极小图标（标签内） */
--icon-sm: 16px;    /* 小图标（按钮内） */
--icon: 20px;       /* 标准图标（导航） */
--icon-md: 24px;    /* 中等图标（标题旁） */
--icon-lg: 32px;    /* 大图标（空状态） */
--icon-xl: 48px;    /* 超大图标（欢迎页） */

/* ========== 使用示例 ========== */
<Icon className="w-4 h-4" />  {/* 16px */}
<Icon className="w-5 h-5" />  {/* 20px */}
<Icon className="w-6 h-6" />  {/* 24px */}
<Icon className="w-8 h-8" />  {/* 32px */}
```

---

#### **Tailwind配置示例**

```typescript
// tailwind.config.ts
import type { Config } from 'tailwindcss';

const config: Config = {
  theme: {
    extend: {
      colors: {
        brand: {
          primary: '#3B82F6',
          hover: '#2563EB',
          active: '#1D4ED8',
          light: '#DBEAFE',
          lighter: '#EFF6FF',
        },
        success: {
          DEFAULT: '#10B981',
          light: '#D1FAE5',
        },
        warning: {
          DEFAULT: '#F59E0B',
          light: '#FEF3C7',
        },
        error: {
          DEFAULT: '#EF4444',
          light: '#FEE2E2',
        },
      },
      borderRadius: {
        sm: '0.25rem',
        DEFAULT: '0.375rem',
        md: '0.5rem',
        lg: '0.75rem',
        xl: '1rem',
      },
      boxShadow: {
        sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        DEFAULT: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
        md: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
        lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
      },
    },
  },
};

export default config;
```

---

### 3.5 依赖更新

**文件**: `frontend/package.json`

**新增依赖**:
```json
{
  "dependencies": {
    "reactflow": "^11.10.4",
    "react-dropzone": "^14.2.3",
    "react-markdown": "^9.0.1",
    "remark-gfm": "^4.0.0"
  }
}
```

---

## 四、教务数据缓存优化（新增）

### 4.1 优化背景

**当前问题**:
- 所有教务数据查询API（`/api/schedule`、`/api/grades`等）均实时爬取教务系统
- 即使PostgreSQL已有缓存数据，查询时也不使用
- 教务系统JSESSIONID有效期仅2-5分钟，导致用户频繁登录
- 课表、培养方案等低频变更数据不应实时爬取

### 4.2 优化方案对比

| 数据类型 | 变更频率 | 优化前 | 优化后 | 说明 |
|---------|---------|-------|-------|------|
| 课表 | 学期1次 | 实时爬取 | 读缓存 | 课表基本不变 |
| 培养方案 | 学年1次 | 实时爬取 | 读缓存 | 极少变更 |
| 个人信息 | 学年1次 | 实时爬取 | 读缓存 | 极少变更 |
| 学业进度 | 学期2-3次 | 实时爬取 | 读缓存 | 低频变更 |
| 考试安排 | 考前更新 | 实时爬取 | 读缓存+可刷新 | 考前需刷新 |
| 成绩 | 学期2-3次 | 实时爬取 | 读缓存+可刷新 | 出分后需刷新 |

### 4.3 性能提升指标

| 指标 | 优化前 | 优化后 | 提升 |
|------|-------|-------|------|
| 课表查询响应时间 | 2-5秒 | <100ms | 20-50倍 |
| 成绩查询响应时间 | 2-5秒 | <100ms | 20-50倍 |
| 用户登录频率 | 每2-5分钟 | 每7-30天 | 降低99% |
| 教务系统请求次数 | 每次查询都请求 | 仅刷新时请求 | 降低95% |
| 系统可用性 | 依赖教务系统在线 | 缓存可用 | 大幅提升 |

### 4.4 向后兼容性

- ✅ 原API全部保留（`/api/schedule`、`/api/grades`等）
- ✅ 前端可选择性迁移到新API
- ✅ 数据库表结构无需改动
- ✅ 不影响现有AI对话功能
- ✅ 回滚方案：前端切换回调用原API即可恢复

---

## 五、开发阶段规划

### **Phase 1：基础架构 + 数据缓存优化（1-2周）**

**后端**:
- ✅ 工作区CRUD API
- ✅ 文件上传API
- ✅ 知识库检索API
- ✅ 学习状态统计API
- ✅ 缓存数据查询API（7个 `/api/xxx/db`）
- ✅ 数据刷新API（`/api/refresh` + 进度查询）
- ✅ Redis TTL优化（user_session 7天 / auth_session 30天）
- ✅ 数据新鲜度判定逻辑

**前端**:
- ✅ 首页（全屏分割 + 今日课表卡片）
- ✅ 快速会话页（加保存按钮）
- ✅ 工作区详情页（三栏布局）
- ✅ 文件上传组件
- ✅ 完整课表页（周视图 + 学期切换）
- ✅ 课表卡片组件（shadcn Card + Badge + Button）
- ✅ 数据新鲜度徽标组件
- ✅ 刷新进度条组件

**验收**:
- 可以创建/查看工作区
- 文件可以上传和检索
- 学习状态正常统计
- 课表秒开（< 100ms）
- 数据状态指示正确（新鲜/过期/无数据）
- 刷新功能正常（检测JSESSIONID + 进度显示）

---

### **Phase 2：AI Agent核心（2-3周）**

**前端**:
- ✅ 知识库可视化
- ✅ AI建议展示
- ✅ 提醒弹窗
- ✅ 学习状态展示

**验收**:
- AI能主动推送提醒
- 知识库可视化正常
- 建议可接受/忽略

---

### **Phase 3：教学策略 + AI智能提醒（2-3周）**

**后端**:
- ✅ 对话引导模式
- ✅ 学习路径推荐
- ✅ 可解释AI
- ✅ 薄弱点诊断
- ✅ AI智能过期提醒（对话流中检测数据新鲜度）

**前端**:
- ✅ 对话引导UI
- ✅ 学习路径展示
- ✅ 推荐理由展示
- ✅ 能力画像
- ✅ AI过期提醒提示组件

**验收**:
- AI会引导式教学
- 学习路径合理
- 推荐理由清晰
- AI在对话中提醒数据过期并引导刷新

---

## 六、技术难点与解决方案

### **难点1：知识库可视化**

**问题**: 知识点多时如何清晰展示？

**解决方案**:
1. 按文件分组展示
2. 颜色区分掌握度
3. 点击节点查看详情
4. 按需加载，避免一次性渲染过多

---

### **难点2：文件解析性能**

**问题**: 大文件解析耗时，阻塞用户操作？

**解决方案**:
1. 异步解析：上传后立即返回，后台解析
2. 进度展示：显示解析进度
3. 分块处理：大文件分块向量化

---

### **难点3：AI建议准确性**

**问题**: 如何避免推送无用建议？

**解决方案**:
1. 规则引擎：基于明确规则（考试/课表）
2. 用户反馈：接受/忽略，优化模型
3. 频率控制：同类建议不重复推送

---

## 七、验收标准

### **功能验收**

1. ✅ 工作区CRUD正常
2. ✅ 知识库可视化正常
3. ✅ 文件上传/检索正常
4. ✅ 学习状态统计准确
5. ✅ AI建议推送及时
6. ✅ 提醒弹窗正常

### **性能验收**

1. ✅ 页面加载 < 2秒
2. ✅ 知识库渲染 < 1秒（50节点）
3. ✅ 文件上传 < 5秒（10MB）
4. ✅ API响应 < 500ms

### **兼容性验收**

1. ✅ Chrome/Edge/Safari正常
2. ✅ 移动端响应式正常
3. ✅ 平板适配正常

---

## 八、后续扩展

### **Phase 5：高级功能（2-3月）**

- 多模态交互（拍照搜题/语音）
- 角色扮演学习
- 同伴匹配
- 游戏化2.0

### **Phase 6：前沿探索（3-6月）**

- 学习数字分身
- 联邦学习
- 自适应难度
- 情感智能

---

## 九、注意事项

### **基于交接文档的约束**

1. ⚠️ **不要破坏现有API**: 所有新增API使用新路径，不改旧接口
2. ⚠️ **保持auth_session_id隔离**: 所有新接口必须校验会话隔离
3. ⚠️ **避免/api/api/*路径重复**: NEXT_PUBLIC_API_URL=/api 与前端拼接要注意
4. ⚠️ **Git提交规范**: 使用路径级`git add -- <files>`，避免带入.qoder/repowiki脏改
5. ⚠️ **Docker热重载**: 代码修改后`docker compose restart`即可，无需`--build`

### **开发建议**

1. ✅ 先做Phase 1，验证架构可行
2. ✅ 每个Phase完成后提交Git
3. ✅ 写单元测试，避免回归
4. ✅ 前端组件复用，避免重复代码
5. ✅ 后端服务解耦，方便后续扩展

---

**文档版本**: v3.0  
**创建时间**: 2026-04-20  
**更新时间**: 2026-04-22  
**维护者**: AI Assistant  
**参考文档**: 
- `.qoder/交接工作日志.md`
- `PLATFORM_UPGRADE_GUIDE.md`

**更新记录**:
- v3.0 (2026-04-22): 新增教务数据缓存优化章节、首页课表卡片、完整课表页、智能刷新系统、AI过期提醒、Redis TTL优化、shadcn/ui组件详细规范
- v2.1 (2026-04-21): 精简页面结构，删除工作区列表页/创建页，工作区通过首页直接进入，创建通过弹窗完成
- v2.0 (2026-04-21): 调整为AI Agent定位，删除知识图谱/笔记系统，新增知识库可视化/AI主动推送/学习状态追踪
