# AI服务插件扩展

<cite>
**本文档引用的文件**
- [main.py](file://backend/main.py)
- [education_options.py](file://backend/education_options.py)
- [chat.py](file://backend/app/api/chat.py)
- [education.py](file://backend/app/api/education.py)
- [qwen_service.py](file://backend/app/services/qwen_service.py)
- [vector_store.py](file://backend/app/services/vector_store.py)
- [scraper.py](file://backend/scraper.py)
- [education_data.py](file://backend/app/models/education_data.py)
- [requirements.txt](file://backend/requirements.txt)
- [test_scraper.py](file://backend/test_scraper.py)
- [test_login.py](file://backend/test_login.py)
</cite>

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构概览](#架构概览)
5. [详细组件分析](#详细组件分析)
6. [依赖关系分析](#依赖关系分析)
7. [性能考虑](#性能考虑)
8. [故障排除指南](#故障排除指南)
9. [结论](#结论)

## 简介

智能教务系统AI助手是一个基于FastAPI构建的教育管理系统，集成了AI对话能力和教务数据爬取功能。该系统采用插件化架构设计，支持灵活的大语言模型集成、自定义AI工具函数扩展和教育选项查询功能的定制化。

系统的核心特色包括：
- **插件化AI架构**：支持多种大语言模型的无缝集成
- **教育选项工具体系**：提供完整的教育数据查询工具函数
- **RAG增强对话**：结合向量检索的智能问答能力
- **可扩展的数据模型**：支持多种教育数据类型的存储和查询

## 项目结构

智能教务系统采用清晰的分层架构，主要分为以下几个层次：

```mermaid
graph TB
subgraph "前端层"
FE[前端应用]
end
subgraph "后端层"
API[FastAPI应用]
ROUTER[路由管理]
end
subgraph "服务层"
QWEN[千问AI服务]
VECTOR[向量存储服务]
SCRAPER[数据爬虫服务]
end
subgraph "数据层"
DB[(数据库)]
MILVUS[(Milvus向量数据库)]
end
FE --> API
API --> ROUTER
ROUTER --> QWEN
ROUTER --> VECTOR
ROUTER --> SCRAPER
QWEN --> DB
VECTOR --> MILVUS
SCRAPER --> DB
```

**图表来源**
- [main.py:1-853](file://backend/main.py#L1-L853)
- [chat.py:1-224](file://backend/app/api/chat.py#L1-L224)

**章节来源**
- [main.py:1-853](file://backend/main.py#L1-L853)
- [requirements.txt:1-44](file://backend/requirements.txt#L1-L44)

## 核心组件

### AI服务插件架构

系统采用插件化设计，主要核心组件包括：

#### 1. EducationOptions类
教育选项查询的核心工具类，提供完整的教育数据选项管理：

```mermaid
classDiagram
class EducationOptions {
+Dict[] get_departments(include_admin, include_vocational)
+Dict get_department_by_name(name)
+Dict get_department_by_code(code)
+str[] get_grades()
+Dict[] get_semesters()
+str get_current_semester()
+Dict[] get_course_natures()
+Dict[] get_study_types()
+Dict[] get_grade_display_modes()
+Dict[] get_assessment_methods()
+Dict[] get_weekdays()
+Dict[] get_periods()
+Dict[] get_weeks()
+Dict get_all_options()
}
class OptionsTools {
+Dict[] query_departments(keyword)
+Dict[] query_semesters(include_past, include_future)
+Dict query_course_options()
+Dict query_schedule_options()
+Dict query_grade_options()
+str get_option_description(option_type, code)
}
EducationOptions --> OptionsTools : "提供数据源"
```

**图表来源**
- [education_options.py:130-420](file://backend/education_options.py#L130-L420)

#### 2. AI服务接口
系统支持多种AI服务提供商的统一接口：

```mermaid
classDiagram
class QwenService {
+str api_key
+str model
+str system_prompt
+chat(messages, temperature) Dict
+chat_with_rag(question, context, conversation_history) Dict
+generate_embedding(text) float[]
}
class VectorStore {
+str host
+str port
+str collection_name
+VectorStore()
+create_collection(dim) void
+add_documents(user_id, texts, embeddings, sources, metadatas) int[]
+search(user_id, query_embedding, top_k) Dict[]
+delete_user_data(user_id) void
+close() void
}
class ChatAPI {
+ChatRequest(BaseModel)
+ChatResponse(BaseModel)
+send_message(request) ChatResponse
+get_conversations(username) List
+get_chat_history(conversation_id) Dict
+delete_conversation(conversation_id) Dict
}
QwenService --> VectorStore : "使用向量检索"
ChatAPI --> QwenService : "调用AI服务"
ChatAPI --> VectorStore : "RAG检索"
```

**图表来源**
- [qwen_service.py:15-178](file://backend/app/services/qwen_service.py#L15-L178)
- [vector_store.py:14-164](file://backend/app/services/vector_store.py#L14-L164)
- [chat.py:18-224](file://backend/app/api/chat.py#L18-L224)

**章节来源**
- [education_options.py:130-420](file://backend/education_options.py#L130-L420)
- [qwen_service.py:15-178](file://backend/app/services/qwen_service.py#L15-L178)
- [vector_store.py:14-164](file://backend/app/services/vector_store.py#L14-L164)
- [chat.py:18-224](file://backend/app/api/chat.py#L18-L224)

## 架构概览

系统采用微服务架构，通过API网关统一对外提供服务：

```mermaid
sequenceDiagram
participant Client as "客户端"
participant API as "FastAPI应用"
participant Chat as "对话API"
participant Qwen as "千问服务"
participant Vector as "向量存储"
participant DB as "数据库"
Client->>API : POST /api/chat/send
API->>Chat : 路由到对话处理器
Chat->>Chat : 查找或创建用户
Chat->>Chat : 查找或创建对话
Chat->>Chat : 保存用户消息
Chat->>DB : 查询历史对话
Chat->>Vector : 生成查询向量
Vector->>Vector : 检索相关文档
Vector-->>Chat : 返回上下文
Chat->>Qwen : 调用AI服务
Qwen->>Qwen : 生成回答
Qwen-->>Chat : 返回AI结果
Chat->>DB : 保存AI回复
Chat-->>Client : 返回对话结果
```

**图表来源**
- [chat.py:45-154](file://backend/app/api/chat.py#L45-L154)
- [qwen_service.py:39-142](file://backend/app/services/qwen_service.py#L39-L142)
- [vector_store.py:100-142](file://backend/app/services/vector_store.py#L100-L142)

## 详细组件分析

### AI工具函数体系详解

#### 1. 院系查询工具
`query_departments`函数提供灵活的院系查询能力：

```mermaid
flowchart TD
Start([开始查询]) --> CheckKeyword{"是否有关键词?"}
CheckKeyword --> |否| GetAllDepts["获取所有院系<br/>DEPARTMENTS + ADMIN_DEPARTMENTS + VOCATIONAL_COLLEGES"]
CheckKeyword --> |是| FilterDepts["按关键词过滤"]
GetAllDepts --> ReturnAll["返回所有院系"]
FilterDepts --> CheckAdmin{"包含职能部门?"}
CheckAdmin --> |是| AddAdmin["添加职能部门"]
CheckAdmin --> |否| SkipAdmin["跳过职能部门"]
AddAdmin --> CheckVocational{"包含联合培养学院?"}
SkipAdmin --> CheckVocational
CheckVocational --> |是| AddVocational["添加联合培养学院"]
CheckVocational --> |否| SkipVocational["跳过联合培养学院"]
AddVocational --> FinalFilter["最终过滤"]
SkipVocational --> FinalFilter
FinalFilter --> ReturnResult["返回匹配结果"]
ReturnAll --> End([结束])
ReturnResult --> End
```

**图表来源**
- [education_options.py:264-287](file://backend/education_options.py#L264-L287)

#### 2. 学期查询工具
`query_semesters`函数支持灵活的学期查询策略：

```mermaid
flowchart TD
Start([开始查询]) --> GetSemesters["获取学期列表"]
GetSemesters --> GetCurrent["获取当前学期"]
GetCurrent --> CheckFlags{"查询标志?"}
CheckFlags --> |past=false & future=false| GetCurrentOnly["仅返回当前学期"]
CheckFlags --> |past=true & future=true| ReturnAll["返回所有学期"]
CheckFlags --> |past=true & future=false| ReturnPast["返回过去学期"]
CheckFlags --> |past=false & future=true| ReturnFuture["返回未来学期"]
GetCurrentOnly --> FindCurrent["查找当前学期索引"]
FindCurrent --> ReturnSingle["返回当前学期"]
ReturnAll --> End([结束])
ReturnPast --> GetFromIndex["从当前索引开始返回"]
GetFromIndex --> ReturnPastResult["返回过去学期列表"]
ReturnFuture --> GetToIndex["到当前索引结束返回"]
GetToIndex --> ReturnFutureResult["返回未来学期列表"]
ReturnSingle --> End
ReturnPastResult --> End
ReturnFutureResult --> End
```

**图表来源**
- [education_options.py:289-330](file://backend/education_options.py#L289-L330)

#### 3. 课程选项查询工具
`query_course_options`提供课程相关的完整选项体系：

| 选项类型 | 数据来源 | 用途 |
|---------|---------|------|
| 课程性质 | `COURSE_NATURES` | 必修、选修、通识等分类 |
| 修读类别 | `STUDY_TYPES` | 主修、辅修课程区分 |
| 考核方式 | `ASSESSMENT_METHODS` | 考试、考查等评估方式 |

**章节来源**
- [education_options.py:262-378](file://backend/education_options.py#L262-L378)

### 新AI模型集成指南

#### 1. 模型接口定义
要集成新的AI模型，需要实现以下接口：

```mermaid
classDiagram
class BaseAIService {
<<abstract>>
+chat(messages, temperature) Dict
+chat_with_rag(question, context, conversation_history) Dict
+generate_embedding(text) float[]
}
class NewAIService {
+api_key : str
+model : str
+system_prompt : str
+chat(messages, temperature) Dict
+chat_with_rag(question, context, conversation_history) Dict
+generate_embedding(text) float[]
}
BaseAIService <|-- NewAIService : "继承"
```

**图表来源**
- [qwen_service.py:15-178](file://backend/app/services/qwen_service.py#L15-L178)

#### 2. 配置参数
新模型的配置参数包括：

| 参数名称 | 类型 | 必需 | 默认值 | 描述 |
|---------|------|------|--------|------|
| `API_KEY` | str | 是 | - | AI服务API密钥 |
| `MODEL_NAME` | str | 否 | "qwen-plus" | 模型名称 |
| `TEMPERATURE` | float | 否 | 0.7 | 生成随机性控制 |
| `MAX_TOKENS` | int | 否 | 2048 | 最大生成tokens数 |

#### 3. 调用方式
新模型的调用遵循统一的接口规范：

```mermaid
sequenceDiagram
participant App as "应用"
participant Service as "AI服务"
participant Model as "大模型"
App->>Service : chat(messages, temperature)
Service->>Service : 构建系统提示词
Service->>Model : Generation.call(model, messages, temperature)
Model-->>Service : 返回生成结果
Service->>Service : 解析响应格式
Service-->>App : 返回标准化结果
```

**图表来源**
- [qwen_service.py:39-90](file://backend/app/services/qwen_service.py#L39-L90)

**章节来源**
- [qwen_service.py:15-178](file://backend/app/services/qwen_service.py#L15-L178)

### AI工具函数开发规范

#### 1. 输入输出格式规范

##### 统一响应格式
所有AI工具函数应返回标准化的响应格式：

```json
{
  "success": true,
  "data": {},
  "count": 0,
  "message": ""
}
```

##### 错误处理规范
- **HTTP状态码**：使用标准HTTP状态码
- **错误消息**：提供清晰的错误描述
- **异常捕获**：统一的异常处理机制

#### 2. 性能优化策略

##### 缓存机制
- **会话缓存**：短期会话数据缓存
- **静态数据缓存**：教育选项数据缓存
- **向量缓存**：RAG检索结果缓存

##### 异步处理
- **并发请求**：支持多个API请求并发处理
- **超时控制**：合理的请求超时设置
- **重试机制**：网络异常的自动重试

**章节来源**
- [chat.py:45-154](file://backend/app/api/chat.py#L45-L154)
- [main.py:132-328](file://backend/main.py#L132-L328)

### 教育选项查询功能扩展

#### 1. 新查询类型添加流程

```mermaid
flowchart TD
DefineNewType["定义新查询类型"] --> AddData["添加数据源"]
AddData --> CreateFunction["创建查询函数"]
CreateFunction --> RegisterAPI["注册API端点"]
RegisterAPI --> TestFunction["测试功能"]
TestFunction --> UpdateDocs["更新文档"]
UpdateDocs --> Deploy["部署发布"]
AddData --> AddToOptions["添加到EducationOptions"]
AddToOptions --> AddToTools["添加到工具函数"]
AddToTools --> CreateTest["创建测试用例"]
```

#### 2. 自定义选项扩展

##### 数据结构设计
```python
CUSTOM_OPTIONS = [
    {"code": "custom_code", "name": "自定义选项名称", "description": "详细描述"},
    # 更多选项...
]
```

##### 查询函数实现
```python
def query_custom_options(filter_param: str = "") -> List[Dict]:
    """AI工具：查询自定义选项
    
    Args:
        filter_param: 过滤参数
        
    Returns:
        匹配的选项列表
    """
    # 实现查询逻辑
    pass
```

**章节来源**
- [education_options.py:130-420](file://backend/education_options.py#L130-L420)

## 依赖关系分析

系统采用模块化的依赖管理，主要依赖关系如下：

```mermaid
graph TB
subgraph "核心依赖"
FASTAPI[FastAPI]
REQUESTS[requests]
BEAUTIFULSOUP[beautifulsoup4]
end
subgraph "AI服务"
DASHSCOPE[DashScope]
OPENAI[OpenAI]
LANGCHAIN[LangChain]
end
subgraph "数据存储"
PYMILVUS[Pymilvus]
REDIS[Redis]
SQLALCHEMY[SQLAlchemy]
end
subgraph "工具库"
PANDAS[pandas]
NUMPY[numpy]
DOTENV[python-dotenv]
end
FASTAPI --> REQUESTS
FASTAPI --> BEAUTIFULSOUP
FASTAPI --> DASHSCOPE
DASHSCOPE --> LANGCHAIN
PYMILVUS --> SQLALCHEMY
REDIS --> SQLALCHEMY
```

**图表来源**
- [requirements.txt:1-44](file://backend/requirements.txt#L1-L44)

**章节来源**
- [requirements.txt:1-44](file://backend/requirements.txt#L1-L44)

## 性能考虑

### 1. 缓存策略
- **短期缓存**：会话数据缓存5分钟
- **长期缓存**：教育选项数据缓存24小时
- **向量缓存**：RAG检索结果缓存1小时

### 2. 并发处理
- **异步API**：支持高并发请求处理
- **连接池**：数据库和HTTP连接池管理
- **限流控制**：防止API滥用

### 3. 内存优化
- **流式处理**：大文件下载和处理
- **分页查询**：大量数据的分页处理
- **及时释放**：及时释放不再使用的资源

## 故障排除指南

### 1. 常见问题诊断

#### 登录问题
```mermaid
flowchart TD
LoginError["登录失败"] --> CheckCaptcha["检查验证码"]
CheckCaptcha --> VerifyServer["验证服务器可用性"]
VerifyServer --> CheckSession["检查会话状态"]
CheckSession --> CheckCredentials["验证凭据"]
CheckCredentials --> CheckNetwork["检查网络连接"]
CheckNetwork --> CheckTimeout["检查超时设置"]
CheckTimeout --> ContactSupport["联系技术支持"]
```

#### AI服务问题
- **API密钥错误**：检查环境变量配置
- **模型不可用**：验证模型名称和版本
- **请求超时**：调整超时参数和重试策略

### 2. 日志监控
系统提供详细的日志记录，包括：
- **请求日志**：所有API请求的详细信息
- **错误日志**：异常和错误的完整堆栈跟踪
- **性能日志**：响应时间和资源使用情况

**章节来源**
- [main.py:132-328](file://backend/main.py#L132-L328)
- [chat.py:149-154](file://backend/app/api/chat.py#L149-L154)

## 结论

智能教务系统AI助手通过其插件化架构设计，为教育AI应用提供了高度可扩展的基础框架。系统的主要优势包括：

1. **模块化设计**：清晰的分层架构便于维护和扩展
2. **插件化AI**：支持多种大语言模型的无缝集成
3. **丰富的工具函数**：完善的教育选项查询体系
4. **RAG增强**：结合向量检索的智能问答能力
5. **性能优化**：全面的缓存和并发处理机制

该系统为后续的AI助手功能扩展奠定了坚实的基础，开发者可以根据具体需求添加新的AI模型、自定义工具函数和教育数据查询功能。