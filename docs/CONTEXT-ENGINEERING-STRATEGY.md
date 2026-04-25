# 上下文工程策略 - AI 问答系统

> **用途**: 教务系统 AI 助手的 RAG 上下文管理策略
> **位置**: 项目核心文档，上线后指导 AI 问答行为
> **版本**: v1.0
> **创建日期**: 2026-04-13

---

## 🎯 策略目标

为 AI 问答系统构建高效的上下文管理机制，实现：
1. **Token 优化**: 减少 60%+ 的无效 Token 消耗
2. **准确性提升**: 降低 AI 幻觉率至 5% 以下
3. **响应速度**: 上下文检索时间 < 500ms
4. **个性化**: 按学号隔离数据，精准回答

---

## 📐 三层上下文架构

### 架构总览

```
用户提问
  ↓
┌─────────────────────────────────────────┐
│ Layer 1: 系统级上下文（常驻）            │
│ - AI角色定义                             │
│ - 回答规则                               │
│ - 数据使用策略                           │
│ Token: ~300                              │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ Layer 2: 用户级上下文（按需加载）        │
│ - 个人教务数据（向量检索）               │
│ - 最近查询历史                           │
│ - 学业状态摘要                           │
│ Token: ~500-1000                         │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ Layer 3: 会话级上下文（动态）            │
│ - 当前对话历史（最近5轮）                │
│ - 临时变量（学期、过滤条件）             │
│ Token: ~200-400                          │
└────────────────┬────────────────────────┘
                 ↓
         构建 Prompt → 千问 API
```

---

## 🔧 实现方案

### Layer 1: 系统级上下文（System Context）

**存储位置**: 后端配置文件 `backend/config/system_prompt.yaml`

**内容结构**:
```yaml
system_prompt: |
  你是广东财经大学的校园AI助手，专门帮助学生查询教务信息、解答学业相关问题。
  
  【核心职责】
  1. 基于提供的教务数据准确回答问题
  2. 数据不足时明确告知，不编造信息
  3. 保持友好、专业的语气
  4. 绝不泄露敏感信息（密码、身份证号等）
  
  【回答规则】
  - 直接给出答案，避免过多寒暄
  - 涉及数据时列出关键信息
  - 复杂问题分步骤解答
  - 如有需要建议查看具体页面
  
  【数据使用策略】
  - 优先使用检索到的个人数据
  - 数据冲突时以最新数据为准
  - 不确定时明确说明"数据未同步"
  
  【时间感知】
  当前学年学期: {current_semester}
  当前时间: {current_date}
```

**加载策略**:
- 每次对话固定注入（~300 tokens）
- 仅在系统更新时修改（如新学期开始）

---

### Layer 2: 用户级上下文（User Context）

**存储位置**: Milvus 向量数据库 + PostgreSQL

#### 2.1 个人教务数据（向量化）

**数据分类**:
```python
USER_CONTEXT_TYPES = {
    "personal_info": "个人信息",      # 姓名、学号、专业
    "grades": "成绩数据",            # 成绩列表、统计信息
    "schedule": "课表数据",          # 当前学期课表
    "training_plan": "培养方案",     # 课程要求、学分分布
    "academic_progress": "学业进度", # 已修/还需学分
    "exam_schedule": "考试安排",     #  upcoming exams
}
```

**向量化策略**:
```python
# 数据分块策略
CHUNKING_STRATEGY = {
    "grades": {
        "chunk_size": 5,        # 每5条成绩为一个chunk
        "overlap": 1,           # 重叠1条
        "metadata": ["semester", "course_type"]
    },
    "schedule": {
        "chunk_size": 10,       # 每10门课程为一个chunk
        "overlap": 2,
        "metadata": ["weekday", "teacher"]
    },
    "training_plan": {
        "chunk_size": 3,        # 每3个课程模块为一个chunk
        "overlap": 0,
        "metadata": ["category", "nature"]
    }
}
```

**检索策略**:
```python
# 语义检索 + 元数据过滤
def retrieve_user_context(username: str, question: str, top_k: int = 5):
    """
    检索用户相关上下文
    
    流程:
    1. 问题分类（成绩/课表/培养方案）
    2. 向量检索（Milvus similarity search）
    3. 元数据过滤（按学期、课程类型等）
    4. 重排序（re-ranker）
    5. 返回 top_k 相关上下文
    """
    pass
```

#### 2.2 用户状态摘要

**生成策略**:
```python
def generate_user_summary(username: str) -> dict:
    """
    生成用户学业状态摘要（~200 tokens）
    
    返回:
    {
        "name": "张靖",
        "student_id": "24251102121",
        "major": "计算机科学与技术",
        "grade": "2024级",
        "current_semester": "2025-2026-2",
        "credits_completed": 45,
        "credits_required": 160,
        "gpa": 3.75,
        "rank": "15/120",
        "key_info": "大二下学期，进度28%，绩点优秀"
    }
    """
    pass
```

**更新频率**:
- 数据同步时更新（用户主动触发）
- 定期更新（每周一次，定时任务）

---

### Layer 3: 会话级上下文（Session Context）

**存储位置**: Redis（短期） + PostgreSQL（长期）

#### 3.1 对话历史管理

**滑动窗口策略**:
```python
class SessionContext:
    def __init__(self, max_turns: int = 5):
        self.max_turns = max_turns
        self.history = []  # 最近5轮对话
    
    def add_message(self, role: str, content: str):
        """添加消息，超出窗口自动删除"""
        self.history.append({"role": role, "content": content})
        # 保持最近 2*max_turns 条消息（user + assistant）
        if len(self.history) > self.max_turns * 2:
            self.history = self.history[-self.max_turns * 2:]
    
    def get_context(self) -> list:
        """获取会话上下文"""
        return self.history
```

**Token 控制**:
```python
# 对话历史压缩
def compress_history(history: list, max_tokens: int = 400) -> list:
    """
    压缩对话历史
    
    策略:
    1. 保留最近2轮完整对话
    2. 更早的对话生成摘要
    3. 确保总 Token < max_tokens
    """
    pass
```

#### 3.2 临时变量管理

**上下文变量**:
```python
session_variables = {
    "current_semester": "2025-2026-2",  # 当前查询学期
    "filter_course_type": "必修课",      # 课程类型过滤
    "filter_grade_range": None,          # 成绩范围过滤
    "last_query_type": "grades",         # 上次查询类型
    "pending_action": None,              # 待确认操作
}
```

**生命周期**:
- 会话开始时初始化
- 会话结束时清空
- 跨轮次保持（如同一会话内多次查询成绩）

---

## 🚀 Prompt 构建流程

### 完整流程

```python
def build_prompt(username: str, question: str, session_id: str) -> dict:
    """
    构建完整的 AI 问答 Prompt
    
    返回:
    {
        "system": Layer 1 系统上下文,
        "messages": [
            Layer 2 用户上下文,
            Layer 3 会话历史,
            {"role": "user", "content": question}
        ],
        "metadata": {
            "token_estimate": 1200,
            "context_sources": ["milvus", "redis", "postgresql"]
        }
    }
    """
    
    # 1. 加载系统上下文（Layer 1）
    system_prompt = load_system_prompt()
    
    # 2. 检索用户上下文（Layer 2）
    user_context = retrieve_user_context(username, question)
    user_summary = get_user_summary(username)
    
    # 3. 获取会话历史（Layer 3）
    session_history = get_session_history(session_id)
    
    # 4. 构建完整 Prompt
    messages = []
    
    # 注入用户摘要
    messages.append({
        "role": "system",
        "content": f"【用户信息】{user_summary}"
    })
    
    # 注入检索到的相关数据
    if user_context:
        context_text = "\n\n".join([
            f"【相关数据{i+1}】{ctx['text']}"
            for i, ctx in enumerate(user_context)
        ])
        messages.append({
            "role": "system",
            "content": f"【教务数据】\n{context_text}"
        })
    
    # 添加会话历史
    messages.extend(session_history)
    
    # 添加当前问题
    messages.append({"role": "user", "content": question})
    
    return {
        "system": system_prompt,
        "messages": messages,
        "metadata": {
            "token_estimate": estimate_tokens(system_prompt + messages),
            "context_count": len(user_context)
        }
    }
```

---

## 📊 Token 优化策略

### 优化前后对比

| 场景 | 传统方式 | 三层策略 | 节省 |
|------|---------|---------|------|
| 简单问题（如"我的绩点"） | ~2500 tokens | ~800 tokens | 68% |
| 复杂问题（如"分析我的学业"） | ~4000 tokens | ~1500 tokens | 62% |
| 连续对话（第5轮） | ~5000 tokens | ~1800 tokens | 64% |

### 优化手段

1. **按需检索**: 仅检索与问题相关的上下文
2. **数据压缩**: 长文本生成摘要
3. **窗口限制**: 会话历史仅保留最近5轮
4. **元数据过滤**: 避免检索无关数据
5. **懒加载**: 首次不加载全量数据

---

## 🎯 上下文质量控制

### 相关性评估

```python
def evaluate_context_relevance(context: dict, question: str) -> float:
    """
    评估上下文与问题的相关性
    
    返回: 0-1 分数
    """
    # 1. 向量相似度
    similarity = cosine_similarity(context.embedding, question_embedding)
    
    # 2. 关键词匹配
    keyword_score = calculate_keyword_overlap(context, question)
    
    # 3. 时间衰减（新数据权重更高）
    time_decay = calculate_time_decay(context.timestamp)
    
    return 0.5 * similarity + 0.3 * keyword_score + 0.2 * time_decay
```

### 质量阈值

```python
CONTEXT_QUALITY_THRESHOLDS = {
    "high": 0.8,      # 高质量，直接使用
    "medium": 0.5,    # 中等质量，标注来源
    "low": 0.3,       # 低质量，提示用户
    "reject": 0.3     # 低于此阈值，不使用
}
```

---

## 🔒 安全与隐私

### 数据隔离

```python
# 严格按学号隔离数据
def get_user_data(username: str) -> dict:
    """
    确保数据隔离：
    1. Milvus 按 partition_key 隔离
    2. PostgreSQL 按 user_id 过滤
    3. Redis 按 session_key 隔离
    """
    pass
```

### 敏感信息过滤

```python
SENSITIVE_FIELDS = [
    "password",
    "id_card",
    "phone_number",
    "home_address"
]

def filter_sensitive_data(data: dict) -> dict:
    """过滤敏感字段"""
    return {k: v for k, v in data.items() if k not in SENSITIVE_FIELDS}
```

---

## 📈 监控与优化

### 关键指标

```python
CONTEXT_METRICS = {
    "retrieval_time": "< 500ms",       # 检索时间
    "token_usage": "< 2000",           # 单次对话 Token
    "context_relevance": "> 0.7",      # 上下文相关性
    "hallucination_rate": "< 5%",      # 幻觉率
    "user_satisfaction": "> 85%",      # 用户满意度
}
```

### 持续优化

1. **A/B 测试**: 不同上下文策略对比
2. **用户反馈**: 收集"有帮助/无帮助"反馈
3. **自动调优**: 根据反馈调整检索参数
4. **定期评估**: 每月评估上下文质量

---

## 📝 实施路线图

### Phase 1: 基础框架（2周）
- [ ] 实现三层上下文加载逻辑
- [ ] Milvus 向量检索集成
- [ ] 会话历史管理（Redis）
- [ ] Prompt 构建器

### Phase 2: 优化策略（2周）
- [ ] 数据分块与向量化
- [ ] 相关性评估算法
- [ ] Token 优化（压缩、摘要）
- [ ] 元数据过滤

### Phase 3: 质量提升（2周）
- [ ] 敏感信息过滤
- [ ] 上下文质量监控
- [ ] A/B 测试框架
- [ ] 用户反馈收集

### Phase 4: 生产优化（2周）
- [ ] 性能优化（缓存、并发）
- [ ] 容错机制（降级策略）
- [ ] 日志与追踪
- [ ] 文档完善

---

## 🔗 相关文件

- `backend/app/services/qwen_service.py` - AI 服务实现
- `backend/app/services/vector_store.py` - 向量存储
- `backend/app/api/chat.py` - 对话 API
- `backend/config/system_prompt.yaml` - 系统提示词配置

---

**版本**: v1.0  
**作者**: 项目开发团队  
**审核**: 待审核  
**生效日期**: 待上线
