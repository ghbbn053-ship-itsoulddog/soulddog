# 个人信息查询API

<cite>
**本文档引用的文件**
- [backend/main.py](file://backend/main.py)
- [backend/app/api/education.py](file://backend/app/api/education.py)
- [backend/app/services/education_sync.py](file://backend/app/services/education_sync.py)
- [backend/app/security.py](file://backend/app/security.py)
- [backend/app/services/session_store.py](file://backend/app/services/session_store.py)
- [backend/scraper.py](file://backend/scraper.py)
- [backend/test_scraper.py](file://backend/test_scraper.py)
- [backend/test_login.py](file://backend/test_login.py)
- [backend/requirements.txt](file://backend/requirements.txt)
- [frontend/src/app/login/page.tsx](file://frontend/src/app/login/page.tsx)
- [frontend/src/app/chat/page.tsx](file://frontend/src/app/chat/page.tsx)
</cite>

## 更新摘要
**变更内容**
- **重大改进** 个人信息解析功能从单一的 #Top1_divLoginName 元素解析转变为双重解析策略，优先使用结构化 div.block1text 元素，同时保留降级机制以确保向后兼容性
- **新增** extract_labeled_value 函数和表格键值对提取机制，实现了结构化表格解析与正则提取的双重保障策略
- **新增** 统一的会话管理机制：所有用户数据查询API端点现在使用 ensure_user_session() 函数进行会话管理
- **新增** 增强的调试日志记录，包括详细的日志记录来改善问题诊断能力，包括URL访问跟踪、响应特征监控、内容分析等
- **新增** 严格的用户名隔离机制，确保会话安全性
- **新增** 完整的个人信息解析流程，包括学籍卡片详细信息提取

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
10. [附录](#附录)

## 简介

本项目是一个基于FastAPI开发的教务系统AI助手后端服务，主要提供个人信息查询和学籍卡片查询功能。该系统通过爬取学校教务系统的网页数据，为学生提供便捷的信息查询服务。

系统采用前后端分离架构，后端使用Python FastAPI框架，前端使用Next.js构建。核心功能包括：
- 个人信息获取接口
- 学籍卡片查询接口
- 成绩查询、课表查询等扩展功能
- 教师查询、课程查询等辅助功能

**更新** 系统现已引入统一的会话管理机制，所有用户数据查询API端点都使用 ensure_user_session() 函数确保登录和爬取操作使用同一服务器实例，提高了系统的一致性和可靠性。**新增** 系统还增强了调试能力，通过详细的日志记录来改善问题诊断，包括URL访问跟踪、响应特征监控、内容分析等。

## 项目结构

```mermaid
graph TB
subgraph "后端服务"
A[main.py - 主应用入口]
B[scraper.py - 爬虫模块]
C[education_options.py - 选项数据]
D[app/api/ - API路由]
E[app/services/ - 服务层]
F[app/models/ - 数据模型]
G[ensure_user_session() - 会话管理]
H[enforce_username_isolation - 用户名隔离]
I[日志记录系统 - 调试增强]
end
subgraph "前端应用"
J[frontend/src/app/ - Next.js应用]
K[components/ui/ - UI组件]
end
subgraph "外部系统"
L[教务系统(jwxt.gdufe.edu.cn)]
M[Redis缓存]
N[向量数据库]
O[会话存储]
end
A --> B
A --> C
A --> D
A --> E
A --> F
A --> G
A --> H
A --> I
J --> A
B --> L
A --> M
A --> N
G --> O
```

**图表来源**
- [backend/main.py:1-170](file://backend/main.py#L1-L170)
- [backend/scraper.py:1-1615](file://backend/scraper.py#L1-L1615)

**章节来源**
- [backend/main.py:1-170](file://backend/main.py#L1-L170)
- [backend/requirements.txt:1-61](file://backend/requirements.txt#L1-L61)

## 核心组件

### API路由组件

系统提供多个API端点，其中个人信息查询和学籍卡片查询是本次文档重点关注的功能：

1. **个人信息查询接口** (`/api/user/info`)
   - 方法：GET
   - 参数：username (必需)
   - 功能：获取用户的个人信息，包括姓名、学号、专业、班级等
   - **更新**：使用 ensure_user_session() 函数进行统一会话管理
   - **新增**：详细的日志记录，包括请求参数、会话状态、爬取结果等

2. **学籍卡片查询接口** (`/api/user/card`)
   - 方法：GET
   - 参数：username (必需)
   - 功能：获取详细的学籍卡片信息
   - **更新**：使用 ensure_user_session() 函数进行统一会话管理
   - **新增**：详细的日志记录，包括URL访问跟踪、响应特征监控、内容分析等

3. **验证码接口** (`/api/captcha`)
   - 方法：GET
   - 参数：username (可选)
   - 功能：获取登录验证码图片

4. **登录接口** (`/api/login`)
   - 方法：POST
   - 参数：username, password, code, captcha_session_id
   - 功能：用户身份验证
   - **新增**：增强的调试日志，包括服务器选择、响应状态码、编码检测等

**章节来源**
- [backend/app/api/education.py:15-46](file://backend/app/api/education.py#L15-L46)
- [backend/main.py:132-163](file://backend/main.py#L132-L163)

### 会话管理组件

**新增** ensure_user_session() 函数是本次更新的核心组件，提供统一的会话管理机制：

```mermaid
flowchart TD
Start([API请求到达]) --> CheckUsername["检查username参数"]
CheckUsername --> ValidateSession["调用ensure_user_session()"]
ValidateSession --> SessionExists{"会话是否存在?"}
SessionExists --> |否| Return401["返回401未登录错误"]
SessionExists --> |是| ExtractSession["提取session和server_url"]
ExtractSession --> CreateScraper["创建JwxtScraper实例"]
CreateScraper --> CallFunction["调用具体功能函数"]
CallFunction --> ParseResult["解析爬取结果"]
ParseResult --> BuildResponse["构建响应数据"]
BuildResponse --> Success["返回成功响应"]
Return401 --> End([结束])
Success --> End
```

**图表来源**
- [backend/app/services/education_sync.py:169-184](file://backend/app/services/education_sync.py#L169-L184)

**章节来源**
- [backend/app/services/education_sync.py:169-184](file://backend/app/services/education_sync.py#L169-L184)

### 爬虫组件

JwxtScraper类是系统的核心爬虫组件，负责与教务系统交互：

```mermaid
classDiagram
class JwxtScraper {
+session : requests.Session
+base_url : str
+captcha_url : str
+login_url : str
+get_captcha() bytes
+login(username, password, captcha) Dict
+get_personal_info() Dict
+get_student_card() Dict
+get_grades(params) Dict
+get_schedule(params) Dict
+get_my_training_plan() Dict
+get_academic_progress(params) Dict
}
class BeautifulSoup {
+find(tag, attrs) Tag
+find_all(tag, attrs) List
+get_text(strip) str
}
JwxtScraper --> BeautifulSoup : "使用"
```

**图表来源**
- [backend/scraper.py:1-1615](file://backend/scraper.py#L1-L1615)

**章节来源**
- [backend/scraper.py:1-200](file://backend/scraper.py#L1-L200)

## 架构概览

```mermaid
sequenceDiagram
participant Client as "客户端"
participant API as "FastAPI后端"
participant SessionMgr as "会话管理器"
participant Security as "安全检查"
participant Scraper as "JwxtScraper"
participant EduSys as "教务系统"
Client->>API : GET /api/user/info?username=...
API->>Security : enforce_username_isolation(username)
Security->>Security : 验证用户名隔离
Security-->>API : 验证通过
API->>SessionMgr : ensure_user_session(username)
SessionMgr->>SessionMgr : 验证用户会话
SessionMgr-->>API : 返回(session, server_url)
API->>Scraper : 创建JwxtScraper(session, server_url)
Scraper->>EduSys : 请求个人信息页面
EduSys-->>Scraper : 个人信息HTML
Scraper-->>API : 解析后的个人信息
API-->>Client : {success, data}
```

**图表来源**
- [backend/app/api/education.py:15-30](file://backend/app/api/education.py#L15-L30)
- [backend/app/services/education_sync.py:169-184](file://backend/app/services/education_sync.py#L169-L184)
- [backend/app/security.py:4-26](file://backend/app/security.py#L4-L26)

## 详细组件分析

### 个人信息查询接口

#### 接口规范

**端点**: `GET /api/user/info`

**请求参数**:
- `username` (必需): 学号，用于识别用户会话

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/user/info?username=2024123456"
```

**响应格式**:
```json
{
  "success": true,
  "data": {
    "name": "张三",
    "student_id": "2024123456",
    "major": "计算机科学与技术",
    "class": "计科2401班",
    "department": "计算机学院"
  }
}
```

**错误处理**:
- 401 未登录：用户未通过身份验证
- 500 服务器错误：爬取过程中发生异常

#### 实现流程

**更新** 现在使用统一的会话管理机制：

```mermaid
flowchart TD
Start([接收请求]) --> ValidateParams["验证username参数"]
ValidateParams --> CallSecurity["调用enforce_username_isolation(username)"]
CallSecurity --> ValidateSession["调用ensure_user_session(username)"]
ValidateSession --> CheckSession["检查会话有效性"]
CheckSession --> SessionExists{"会话存在?"}
SessionExists --> |否| Return401["返回401未登录"]
SessionExists --> |是| CreateScraper["创建JwxtScraper实例"]
CreateScraper --> GetInfo["调用get_personal_info()"]
GetInfo --> ParseHTML["解析个人信息HTML"]
ParseHTML --> ExtractData["提取姓名、学号等信息"]
ExtractData --> BuildResponse["构建响应数据"]
BuildResponse --> Success["返回成功响应"]
Return401 --> End([结束])
Success --> End
```

**新增** 调试增强功能：
- 详细的请求日志记录
- 会话状态监控
- 爬取结果分析
- 错误追踪和诊断

**章节来源**
- [backend/app/api/education.py:15-30](file://backend/app/api/education.py#L15-L30)
- [backend/app/services/education_sync.py:169-184](file://backend/app/services/education_sync.py#L169-L184)
- [backend/app/security.py:4-26](file://backend/app/security.py#L4-L26)

### 个人信息解析策略

**重大更新** 个人信息解析功能现在采用双重解析策略：

```mermaid
flowchart TD
Start([开始解析]) --> FindBlock1Text["查找 div.block1text 元素"]
FindBlock1Text --> Block1TextExists{"找到元素?"}
Block1TextExists --> |是| ParseBlock1Text["解析结构化元素"]
ParseBlock1Text --> ExtractNameStudent["提取姓名和学号"]
ExtractNameStudent --> Success["解析成功"]
Block1TextExists --> |否| FindTop1Div["查找 #Top1_divLoginName 元素"]
FindTop1Div --> Top1DivExists{"找到元素?"}
Top1DivExists --> |是| ParseTop1Div["解析降级元素"]
ParseTop1Div --> ExtractNameStudent2["提取姓名和学号"]
ExtractNameStudent2 --> Success
Top1DivExists --> |否| LogWarning["记录警告：未找到任何个人信息元素"]
LogWarning --> Success
Success --> End([结束])
```

**更新** 双重解析策略的具体实现：

1. **优先策略**：查找 `div.block1text` 元素
   - HTML结构：`<div class="block1text"> 姓名：张靖<br/> 学号：24251102121<br/></div>`
   - 优点：结构化程度高，解析准确度更高
   - 日志记录：`【个人信息】从 block1text 解析: name=张靖, student_id=24251102121`

2. **降级策略**：查找 `#Top1_divLoginName` 元素
   - HTML结构：`<div id="Top1_divLoginName">张靖(24251102121)</div>`
   - 优点：向后兼容，确保在旧系统中也能正常工作
   - 日志记录：`【个人信息】从 Top1_divLoginName 降级解析: name=张靖, student_id=24251102121`

3. **错误处理**：如果两种策略都失败，记录警告并返回空值
   - 日志记录：`【个人信息】未找到任何个人信息元素`

**新增** 结构化表格解析与正则提取的双重保障策略：

```mermaid
flowchart TD
Start([解析学籍卡片]) --> ExtractText["提取纯文本内容"]
ExtractText --> StructuredExtraction["结构化表格键值抽取"]
StructuredExtraction --> TableLoop["遍历所有表格"]
TableLoop --> RowLoop["遍历表格行"]
RowLoop --> CellLoop["遍历单元格"]
CellLoop --> KeyValue["提取键值对"]
KeyValue --> DetailMap["构建detail_map"]
DetailMap --> PickDetail["使用pick_detail函数匹配"]
PickDetail --> Major["提取专业信息"]
PickDetail --> Class["提取班级信息"]
PickDetail --> Department["提取院系信息"]
Major --> Fallback["表格未命中时使用正则提取"]
Class --> Fallback
Department --> Fallback
Fallback --> ExtractLabeledValue["使用extract_labeled_value函数"]
ExtractLabeledValue --> FinalResult["最终解析结果"]
FinalResult --> End([结束])
```

**新增** extract_labeled_value 函数实现：

```python
def extract_labeled_value(text: str, labels, next_labels):
    label_pattern = "|".join(re.escape(label) for label in labels)
    next_pattern = "|".join(re.escape(label) for label in next_labels)
    pattern = rf"(?:{label_pattern})[：:]\s*(.+?)(?=(?:{next_pattern})[：:]|$)"
    match = re.search(pattern, text, re.S)
    if match:
        return " ".join(match.group(1).split()).strip()
    return ""
```

**新增** 表格键值对提取机制：
- 优先按学籍卡片表格键值抽取，避免正则截断"计算机科学与技术"这类值
- 遍历所有表格，提取键值对并存储在 detail_map 中
- 使用 pick_detail 函数根据关键词匹配提取信息
- 表格解析失败时退回更稳定的标签提取

**图表来源**
- [backend/scraper.py:164-230](file://backend/scraper.py#L164-L230)

**章节来源**
- [backend/scraper.py:95-254](file://backend/scraper.py#L95-L254)

### 学籍卡片查询接口

#### 接口规范

**端点**: `GET /api/user/card`

**请求参数**:
- `username` (必需): 学号，用于识别用户会话

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/user/card?username=2024123456"
```

**响应格式**:
```json
{
  "success": true,
  "data": {
    "姓名": "张三",
    "性别": "男",
    "出生日期": "2005-01-01",
    "民族": "汉",
    "政治面貌": "共青团员",
    "身份证号": "440101200501011234",
    "学号": "2024123456",
    "入学日期": "2024-09-01",
    "学制": "4年",
    "培养层次": "本科",
    "所在学院": "计算机学院",
    "所在专业": "计算机科学与技术",
    "所在班级": "计科2401班",
    "学籍状态": "在读",
    "学籍注册日期": "2024-09-01"
  }
}
```

**错误处理**:
- 401 未登录：用户未通过身份验证
- 500 服务器错误：爬取过程中发生异常

#### 实现流程

**更新** 现在使用统一的会话管理机制：

```mermaid
sequenceDiagram
participant Client as "客户端"
participant API as "FastAPI接口"
participant Security as "安全检查"
participant SessionMgr as "会话管理器"
participant Scraper as "JwxtScraper"
participant EduSys as "教务系统"
Client->>API : GET /api/user/card?username=2024123456
API->>Security : enforce_username_isolation(username)
Security->>Security : 验证用户名隔离
Security-->>API : 验证通过
API->>SessionMgr : ensure_user_session(username)
SessionMgr->>SessionMgr : 验证用户会话
SessionMgr-->>API : 返回(session, server_url)
API->>Scraper : 创建JwxtScraper(session, server_url)
Scraper->>EduSys : GET /jsxsd/grxx/xsxx
EduSys-->>Scraper : 学籍卡片HTML
Scraper->>Scraper : 解析HTML表格
Scraper->>Scraper : 提取学籍信息字段
Scraper-->>API : 返回解析结果
API-->>Client : {success, data}
```

**新增** 调试增强功能：
- URL访问跟踪
- 响应特征监控
- 内容分析
- 编码检测
- 页面结构验证

**图表来源**
- [backend/app/api/education.py:32-46](file://backend/app/api/education.py#L32-L46)
- [backend/app/services/education_sync.py:169-184](file://backend/app/services/education_sync.py#L169-L184)
- [backend/scraper.py:256-289](file://backend/scraper.py#L256-L289)

**章节来源**
- [backend/app/api/education.py:32-46](file://backend/app/api/education.py#L32-L46)
- [backend/app/services/education_sync.py:169-184](file://backend/app/services/education_sync.py#L169-L184)
- [backend/scraper.py:256-289](file://backend/scraper.py#L256-L289)

### 登录认证机制

系统采用基于会话的认证机制：

```mermaid
flowchart TD
GetCaptcha["获取验证码"] --> SubmitLogin["提交登录请求"]
SubmitLogin --> ValidateCreds["验证用户名密码"]
ValidateCreds --> LoginSuccess{"登录成功?"}
LoginSuccess --> |是| SaveSession["保存会话到SESSIONS"]
LoginSuccess --> |否| ReturnError["返回错误信息"]
SaveSession --> ReturnSuccess["返回登录成功"]
ReturnError --> End([结束])
ReturnSuccess --> End
```

**新增** 增强的调试日志：
- 验证码获取过程跟踪
- 登录服务器选择记录
- 响应状态码监控
- 编码检测分析
- 错误信息提取

**图表来源**
- [backend/main.py:132-163](file://backend/main.py#L132-L163)
- [backend/test_login.py:19-74](file://backend/test_login.py#L19-L74)

**章节来源**
- [backend/main.py:132-163](file://backend/main.py#L132-L163)
- [backend/test_login.py:19-74](file://backend/test_login.py#L19-L74)

### 会话管理机制

**新增** 统一的会话管理机制确保所有API端点的一致性：

```mermaid
flowchart TD
EnsureUserSession["ensure_user_session(username)"] --> CheckUsername["检查username参数"]
CheckUsername --> ValidateSession["验证SESSIONS字典中的会话"]
ValidateSession --> SessionExists{"会话是否存在?"}
SessionExists --> |否| Raise401["抛出401未登录异常"]
SessionExists --> |是| ExtractData["提取session和server_url"]
ExtractData --> LogSession["记录会话信息"]
LogSession --> ReturnTuple["返回(session, server_url)"]
Raise401 --> End([结束])
ReturnTuple --> End
```

**新增** 调试增强功能：
- 会话状态监控
- 用户活动跟踪
- 服务器实例验证
- 性能指标记录

**图表来源**
- [backend/app/services/education_sync.py:169-184](file://backend/app/services/education_sync.py#L169-L184)

**章节来源**
- [backend/app/services/education_sync.py:169-184](file://backend/app/services/education_sync.py#L169-L184)

### 用户名隔离机制

**新增** 严格的用户名隔离机制确保会话安全性：

```mermaid
flowchart TD
EnforceUsernameIsolation["enforce_username_isolation(http_request, username)"] --> CheckAuthSession["检查auth_session_id"]
CheckAuthSession --> HasAuthSession{"存在auth_session_id?"}
HasAuthSession --> |是| GetAuthPayload["获取auth_session_payload"]
GetAuthPayload --> ValidateUsername{"用户名匹配?"}
ValidateUsername --> |否| Raise401["抛出401未登录异常"]
ValidateUsername --> |是| ReturnSuccess["返回"]
HasAuthSession --> |否| CheckCookie["检查session_username cookie"]
CheckCookie --> CookieMatch{"用户名匹配?"}
CookieMatch --> |否| Raise403["抛出403权限错误"]
CookieMatch --> |是| ReturnSuccess
Raise401 --> End([结束])
Raise403 --> End
ReturnSuccess --> End
```

**新增** 调试增强功能：
- 会话ID验证
- 用户名一致性检查
- 权限验证日志

**图表来源**
- [backend/app/security.py:4-26](file://backend/app/security.py#L4-L26)

**章节来源**
- [backend/app/security.py:4-26](file://backend/app/security.py#L4-L26)

## 依赖关系分析

### 外部依赖

系统的主要外部依赖包括：

```mermaid
graph TB
subgraph "Web框架"
FastAPI[FastAPI 0.115.6]
Uvicorn[Uvicorn 0.32.1]
end
subgraph "HTTP请求"
Requests[Requests 2.32.3]
Aiohttp[Aiohttp 3.11.11]
end
subgraph "HTML解析"
BeautifulSoup[BeautifulSoup4 4.12.3]
Lxml[Lxml 5.3.0]
end
subgraph "爬虫工具"
Pyppeteer[Pyppeteer 2.0.0]
Selenium[Selenium 4.27.1]
end
subgraph "缓存"
Redis[Redis 5.2.1]
end
subgraph "向量数据库"
Grpcio[Grpcio 1.66.2]
Milvus[Milvus 2.6.11]
end
FastAPI --> Requests
FastAPI --> BeautifulSoup
Requests --> Lxml
Selenium --> Pyppeteer
FastAPI --> Redis
FastAPI --> Milvus
```

**图表来源**
- [backend/requirements.txt:1-61](file://backend/requirements.txt#L1-L61)

**章节来源**
- [backend/requirements.txt:1-61](file://backend/requirements.txt#L1-L61)

### 内部模块依赖

```mermaid
graph LR
Main[main.py] --> Scraper[scraper.py]
Main --> EducationAPI[app/api/education.py]
Main --> Services[app/services/]
Main --> Security[app/security.py]
EducationAPI --> Scraper
EducationAPI --> Services
Services --> Scraper
Security --> EducationAPI
Scraper --> EduSys[教务系统]
```

**图表来源**
- [backend/main.py:1-170](file://backend/main.py#L1-170)
- [backend/scraper.py:1-1615](file://backend/scraper.py#L1-L1615)

**章节来源**
- [backend/main.py:1-170](file://backend/main.py#L1-L170)
- [backend/scraper.py:1-1615](file://backend/scraper.py#L1-L1615)

## 性能考虑

### 服务器选择策略

系统实现了智能的服务器选择机制，基于学号进行负载均衡：

```mermaid
flowchart TD
InputUsername["输入学号"] --> CheckDigit{"是否为数字?"}
CheckDigit --> |是| CalcIndex["index = int(username) % len(SERVERS)"]
CheckDigit --> |否| UseFirstServer["使用第一个服务器"]
CalcIndex --> SelectServer["选择对应服务器"]
UseFirstServer --> SelectServer
SelectServer --> ReturnServer["返回服务器地址"]
```

**图表来源**
- [backend/main.py:83-93](file://backend/main.py#L83-L93)

### 会话管理优化

**更新** 统一的会话管理机制提供了更好的性能和可靠性：

```mermaid
graph TB
subgraph "会话存储"
Memory[内存存储 - SESSIONS]
Redis[Redis缓存]
Mongo[MongoDB持久化]
end
subgraph "会话管理"
EnsureUserSession[ensure_user_session函数]
Cache[会话缓存]
Cleanup[会话清理]
end
subgraph "用户操作"
Login[用户登录]
Access[访问受保护资源]
Logout[用户登出]
end
Login --> StoreSession["存储会话"]
Access --> EnsureUserSession
EnsureUserSession --> Cache
EnsureUserSession --> Cleanup
Logout --> RemoveSession["移除会话"]
StoreSession --> Memory
Cache --> Memory
Cleanup --> Memory
RemoveSession --> Memory
```

**图表来源**
- [backend/app/services/education_sync.py:169-184](file://backend/app/services/education_sync.py#L169-L184)

### 爬取性能优化

1. **超时设置**: 所有HTTP请求设置10秒超时
2. **编码处理**: 统一使用UTF-8编码
3. **错误重试**: 对于临时性错误提供重试机制
4. **连接复用**: 使用requests.Session复用连接
5. **统一会话管理**: 通过 ensure_user_session() 函数确保会话一致性
6. **新增** **增强的调试日志**: 提供详细的性能监控和问题诊断信息
7. **新增** **结构化解析优化**: 使用表格键值对提取减少正则匹配开销

**章节来源**
- [backend/app/services/education_sync.py:169-184](file://backend/app/services/education_sync.py#L169-L184)
- [backend/scraper.py:1-1615](file://backend/scraper.py#L1-L1615)

## 故障排除指南

### 常见错误及解决方案

#### 1. 验证码相关问题

**问题**: 验证码获取失败
**原因**: 
- 教务系统服务器不可达
- 网络连接问题
- 服务器选择错误

**解决方案**:
- 检查网络连接
- 验证教务系统URL配置
- 确认服务器列表配置正确

#### 2. 登录失败

**问题**: 用户名、密码或验证码错误
**原因**:
- 凭据不正确
- 验证码过期
- 服务器选择错误

**解决方案**:
- 重新获取验证码
- 检查用户名密码
- 确认验证码输入正确

#### 3. 个人信息获取失败

**问题**: 401未登录错误
**原因**:
- 用户未登录
- 会话已过期
- 用户名不匹配
- **更新**：会话管理器无法找到对应的会话

**解决方案**:
- 先执行登录操作
- 检查会话有效期
- 确认用户名正确
- **更新**：检查 ensure_user_session() 函数的日志输出

#### 4. 学籍卡片解析错误

**问题**: 学籍信息解析失败
**原因**:
- 教务系统页面结构变化
- 网络请求失败
- HTML解析异常
- **更新**：会话管理失败导致的请求失败

**解决方案**:
- 检查页面结构变化
- 增加重试机制
- 更新解析规则
- **更新**：检查会话管理器的错误日志

#### 5. 会话管理问题

**新增** 由于引入了统一的会话管理机制，可能出现以下问题：

**问题**: ensure_user_session() 函数抛出401错误
**原因**:
- 用户未登录
- 会话数据损坏
- 服务器实例不一致

**解决方案**:
- 检查登录状态
- 清理会话数据
- 确认服务器实例配置

#### 6. 个人信息解析问题

**重大更新** 由于采用了双重解析策略，可能出现以下问题：

**问题**: 个人信息解析失败
**原因**:
- `div.block1text` 元素结构发生变化
- `#Top1_divLoginName` 元素不存在
- 教务系统页面结构变化
- 编码问题影响解析
- **新增**：extract_labeled_value 函数匹配失败
- **新增**：表格键值对提取机制失效

**解决方案**:
- 检查页面结构变化
- 增加更多日志记录
- 更新解析策略
- 检查编码处理
- **新增**：验证正则表达式模式
- **新增**：检查表格结构变化

#### 7. 用户名隔离问题

**新增** 由于引入了用户名隔离机制，可能出现以下问题：

**问题**: enforce_username_isolation() 函数抛出401或403错误
**原因**:
- 会话ID无效
- 用户名不匹配
- Cookie验证失败

**解决方案**:
- 检查会话状态
- 验证用户名一致性
- 清理浏览器Cookie

### 调试工具

系统提供了完整的测试脚本和增强的调试功能：

1. **test_scraper.py**: 爬虫功能测试
2. **test_login.py**: 登录功能测试
3. **新增** **详细日志记录**: 提供完整的请求跟踪和响应分析
4. **新增** **结构化调试信息**: 包括HTML内容预览、解析结果等

**新增** 调试增强功能：
- URL访问跟踪
- 响应特征监控
- 内容分析
- 编码检测
- 性能指标记录
- **新增** **个人信息解析调试**: 详细的解析过程日志

**章节来源**
- [backend/test_scraper.py:1-200](file://backend/test_scraper.py#L1-L200)
- [backend/test_login.py:1-152](file://backend/test_login.py#L1-L152)

## 结论

本项目提供了一个完整的个人信息查询API解决方案，具有以下特点：

### 优势
1. **功能完整**: 支持个人信息和学籍卡片查询
2. **架构清晰**: 前后端分离，职责明确
3. **扩展性强**: 易于添加新的查询功能
4. **错误处理**: 完善的异常处理和错误反馈
5. **统一会话管理**: 通过 ensure_user_session() 函数确保所有API端点的一致性
6. **提高可靠性**: 登录和爬取使用同一服务器实例
7. **新增** **增强的调试能力**: 详细的日志记录改善问题诊断能力
8. **新增** **安全隔离**: 严格的用户名隔离机制确保会话安全性
9. **新增** **双重解析策略**: 结构化表格解析与正则提取的双重保障

### 重大改进
**更新** 个人信息解析功能的重大改进：
- **双重解析策略**：优先使用结构化 `div.block1text` 元素，确保更高的解析准确性
- **向后兼容性**：保留 `#Top1_divLoginName` 元素的降级解析机制
- **错误处理**：完善的日志记录和错误追踪
- **性能提升**：结构化元素解析比降级方案更高效
- **新增** **extract_labeled_value函数**：提供精确的标签值提取能力
- **新增** **表格键值对提取机制**：避免正则截断长文本值的问题
- **新增** **pick_detail函数**：智能关键词匹配提取信息

### 改进建议
1. **认证安全**: 引入JWT令牌认证机制
2. **会话持久化**: 使用Redis替代内存存储
3. **限流控制**: 添加API访问频率限制
4. **缓存策略**: 实现数据缓存减少重复爬取
5. **监控告警**: 添加系统监控和错误告警
6. **会话管理优化**: 进一步优化 ensure_user_session() 函数的性能
7. **新增** **日志分析工具**: 建立专门的日志分析和监控系统
8. **新增** **解析规则维护**: 建立解析规则版本管理和回滚机制

### 使用场景
- 学生自助查询个人信息
- 辅导员批量查询学生信息
- 系统集成第三方应用
- 数据分析和报表生成

## 附录

### API使用示例

#### 获取验证码
```bash
curl -X GET "http://localhost:8000/api/captcha?username=2024123456"
```

#### 用户登录
```bash
curl -X POST "http://localhost:8000/api/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "2024123456",
    "password": "your_password",
    "code": "ABCD",
    "captcha_session_id": "captcha_123456789_0"
  }'
```

#### 获取个人信息
```bash
curl -X GET "http://localhost:8000/api/user/info?username=2024123456"
```

#### 获取学籍卡片
```bash
curl -X GET "http://localhost:8000/api/user/card?username=2024123456"
```

### 数据安全和隐私保护

1. **传输安全**: 建议在生产环境中使用HTTPS
2. **敏感信息**: 用户密码仅在本地验证，不存储明文
3. **会话管理**: 会话信息存储在服务器端，避免泄露
4. **日志记录**: 敏感信息不在日志中记录
5. **权限控制**: 受保护资源仅对已认证用户开放
6. **统一会话管理**: 通过 ensure_user_session() 函数确保数据完整性
7. **新增** **用户名隔离**: 严格的用户名隔离机制防止会话劫持
8. **新增** **日志安全**: 调试日志不包含敏感数据，仅记录必要的诊断信息

### 性能优化建议

1. **连接池**: 使用连接池复用HTTP连接
2. **异步处理**: 对于耗时操作使用异步处理
3. **缓存策略**: 实现多级缓存减少重复请求
4. **并发控制**: 限制同时发起的爬取请求数量
5. **监控指标**: 添加性能监控和指标收集
6. **会话管理优化**: 优化 ensure_user_session() 函数的性能
7. **服务器实例管理**: 确保所有API端点使用同一服务器实例
8. **新增** **日志性能优化**: 使用异步日志记录，避免阻塞请求处理
9. **新增** **解析性能优化**: 优化表格键值对提取算法

### 会话管理最佳实践

**新增** 使用 ensure_user_session() 函数的最佳实践：

1. **参数验证**: 确保username参数有效
2. **错误处理**: 正确处理401未登录错误
3. **日志记录**: 记录会话管理过程的关键信息
4. **性能监控**: 监控会话管理的响应时间和成功率
5. **一致性保证**: 确保所有API端点使用相同的会话管理逻辑
6. **新增** **调试日志**: 利用详细的日志记录进行问题诊断和性能分析
7. **新增** **用户名隔离**: 确保会话安全性和数据隔离

### 调试日志示例

**新增** 系统提供的调试日志示例：

```
INFO:     【个人信息调试】请求学籍卡片URL: http://172.19.13.60:80/jsxsd/grxx/xsxx?Ves632DSdyV=NEW_XSD_XJCJ
INFO:     【个人信息调试】学籍卡片响应状态: 200
INFO:     【个人信息调试】学籍卡片响应URL: http://172.19.13.60:80/jsxsd/grxx/xsxx?Ves632DSdyV=NEW_XSD_XJCJ
INFO:     【个人信息调试】学籍卡片HTML长度: 12345
INFO:     【个人信息调试】HTML已保存到 C:\Users\...\debug_personal_info.html
INFO:     【个人信息调试】HTML前500字符: <!DOCTYPE html><html>...
INFO:     【个人信息调试】专业匹配: 计算机科学与技术
INFO:     【个人信息调试】班级匹配: 计科2401班
INFO:     【个人信息调试】院系匹配: 计算机学院
INFO:     【个人信息】解析成功: {"name": "张三", "student_id": "2024123456", "major": "计算机科学与技术", "class": "计科2401班", "department": "计算机学院"}
```

这些日志提供了完整的请求跟踪、响应分析和内容监控，大大改善了问题诊断能力。

### 个人信息解析策略详解

**重大更新** 双重解析策略的技术细节：

1. **结构化解析（优先）**
   - 查找 `div.block1text` 元素
   - 解析结构化文本内容
   - 提取姓名和学号字段
   - 优点：解析准确度高，结构清晰

2. **降级解析（备用）**
   - 查找 `#Top1_divLoginName` 元素
   - 解析合并的文本格式
   - 提取姓名和学号字段
   - 优点：向后兼容性强

3. **结构化表格解析（增强）**
   - **新增** 遍历所有表格提取键值对
   - **新增** 使用 detail_map 存储解析结果
   - **新增** 使用 pick_detail 函数智能匹配
   - **新增** 避免正则截断长文本值的问题

4. **正则提取（降级）**
   - **新增** extract_labeled_value 函数实现精确匹配
   - **新增** 支持多种标签格式（中文冒号、英文冒号）
   - **新增** 使用正向预查避免截断
   - **新增** 处理空白字符和换行符

5. **错误恢复机制**
   - 两种策略都失败时记录警告
   - 返回空值并继续处理
   - 便于上层逻辑处理

**章节来源**
- [backend/scraper.py:95-254](file://backend/scraper.py#L95-L254)