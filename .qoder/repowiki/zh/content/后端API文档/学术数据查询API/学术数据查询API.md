# 学术数据查询API

<cite>
**本文档引用的文件**
- [main.py](file://backend/main.py)
- [scraper.py](file://backend/scraper.py)
- [education_options.py](file://backend/education_options.py)
- [education_data.py](file://backend/app/models/education_data.py)
- [user.py](file://backend/app/models/user.py)
- [data_processor.py](file://backend/app/services/data_processor.py)
- [test_scraper.py](file://backend/test_scraper.py)
- [test_login.py](file://backend/test_login.py)
- [test_academic_progress.py](file://backend/test_academic_progress.py)
- [education.py](file://backend/app/api/education.py)
- [tools.py](file://backend/app/mcp/tools.py)
</cite>

## 更新摘要
**所做更改**
- 学业进度查询接口得到显著增强，包括改进的表格解析逻辑、增强的数值提取能力、优化的学分统计机制
- 新增了智能的总学分提取算法，支持从标题和表格头部双重来源提取学分要求
- 改进了课程列表去重机制，支持基于课程代码和名称的复合去重
- 增强了合计行识别和已获学分统计功能
- 优化了HTML调试输出功能，提供详细的解析过程跟踪
- 新增了专门的学业进度解析测试工具

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构概览](#架构概览)
5. [详细组件分析](#详细组件分析)
6. [按学期分类的数据结构](#按学期分类的数据结构)
7. [AI上下文感知能力](#ai上下文感知能力)
8. [调试功能详解](#调试功能详解)
9. [依赖关系分析](#依赖关系分析)
10. [性能考虑](#性能考虑)
11. [故障排除指南](#故障排除指南)
12. [结论](#结论)

## 简介

本项目是一个基于FastAPI的学术数据查询系统，为广东财经大学的学生提供一站式教务数据查询服务。系统集成了多个核心功能模块，包括成绩查询、课表查询、培养方案查询、学业进度查询、考试安排查询等，为学生提供全面的学术数据服务。

该系统采用现代化的技术栈，包括Python 3.9+、FastAPI、SQLAlchemy、BeautifulSoup等，实现了高可靠性的数据爬取和处理功能。系统支持多种查询条件和筛选参数，提供灵活的数据查询能力，并具备良好的扩展性和维护性。

**更新** 本版本完成了学术数据组织系统的完全重构，实现了按学期分类的数据结构，显著提升了AI上下文感知能力和数据查询的精确性。特别地，学业进度查询接口得到了重大增强，包括改进的表格解析逻辑、增强的数值提取能力、优化的学分统计机制等。

## 项目结构

项目采用清晰的分层架构设计，主要分为以下几个层次：

```mermaid
graph TB
subgraph "前端层"
FE[前端应用]
end
subgraph "API层"
API[FastAPI应用]
ROUTER[路由处理器]
ENDPOINTS[端点实现]
end
subgraph "业务逻辑层"
SERVICE[业务服务]
SCRAPER[数据爬虫]
PROCESSOR[数据处理器]
end
subgraph "数据层"
MODEL[数据模型]
DB[(PostgreSQL)]
VECTOR[(Milvus)]
end
subgraph "外部系统"
JWXT[教务系统]
AUTH[认证系统]
end
subgraph "调试系统"
DEBUG[HTML调试输出]
LOG[日志系统]
TEST[测试工具]
end
FE --> API
API --> ROUTER
ROUTER --> ENDPOINTS
ENDPOINTS --> SERVICE
SERVICE --> SCRAPER
SERVICE --> PROCESSOR
PROCESSOR --> MODEL
MODEL --> DB
PROCESSOR --> VECTOR
SCRAPER --> JWXT
SERVICE --> AUTH
SCRAPER --> DEBUG
DEBUG --> LOG
DEBUG --> TEST
```

**图表来源**
- [main.py:1-1060](file://backend/main.py#L1-L1060)
- [scraper.py:1-1550](file://backend/scraper.py#L1-L1550)
- [data_processor.py:1-409](file://backend/app/services/data_processor.py#L1-L409)

**章节来源**
- [main.py:1-1060](file://backend/main.py#L1-L1060)
- [scraper.py:1-1550](file://backend/scraper.py#L1-L1550)
- [data_processor.py:1-409](file://backend/app/services/data_processor.py#L1-L409)

## 核心组件

### 主要技术栈

系统采用以下核心技术栈：

- **后端框架**: FastAPI 0.104.1+ - 提供高性能的异步API服务
- **数据库**: SQLAlchemy ORM - 提供对象关系映射和数据库操作
- **数据解析**: BeautifulSoup4 - 用于HTML页面解析和数据提取
- **HTTP客户端**: requests - 用于与教务系统交互
- **认证**: 自定义JWT认证系统
- **缓存**: 基于内存的会话存储（生产环境建议使用Redis）
- **向量化**: Milvus + 千问服务 - 支持RAG系统
- **调试**: HTML文件保存 + 详细日志记录

### 核心功能模块

系统提供以下核心功能模块：

1. **用户认证模块**: 处理用户登录、会话管理和权限控制
2. **数据爬取模块**: 从教务系统抓取各类学术数据，支持HTML调试输出
3. **数据处理模块**: 解析、转换和格式化爬取的数据，支持按学期分类
4. **API接口模块**: 提供RESTful API接口，包含调试功能
5. **数据存储模块**: 管理用户数据的持久化存储
6. **向量化模块**: 将数据转换为向量格式供RAG系统使用
7. **调试模块**: 提供HTML文件保存和详细日志记录功能

**更新** 核心爬虫功能经过重大重构，修复了URL构造逻辑，增强了编码处理能力，并新增了完整的向量化数据聚合接口和HTML调试输出功能。特别是学业进度查询接口，现在具备了更强大的表格解析和数值提取能力。

**章节来源**
- [main.py:1-1060](file://backend/main.py#L1-L1060)
- [scraper.py:1-1550](file://backend/scraper.py#L1-L1550)
- [data_processor.py:1-409](file://backend/app/services/data_processor.py#L1-L409)

## 架构概览

系统采用分层架构设计，确保各层职责清晰、耦合度低：

```mermaid
sequenceDiagram
participant Client as 客户端
participant API as API网关
participant Auth as 认证服务
participant Service as 业务服务
participant Scraper as 数据爬虫
participant Debug as 调试系统
participant Processor as 数据处理器
participant JWXT as 教务系统
Client->>API : HTTP请求
API->>Auth : 验证用户身份
Auth-->>API : 认证结果
API->>Service : 调用业务逻辑
Service->>Scraper : 执行数据爬取
Scraper->>Debug : 保存HTML调试文件
Scraper->>JWXT : 请求数据
JWXT-->>Scraper : 返回HTML数据
Scraper-->>Service : 解析后的数据
Service->>Processor : 处理数据
Processor-->>Service : 格式化数据
Service-->>API : 格式化响应
API-->>Client : 返回结果
```

**图表来源**
- [main.py:398-580](file://backend/main.py#L398-L580)
- [scraper.py:13-60](file://backend/scraper.py#L13-L60)
- [data_processor.py:13-96](file://backend/app/services/data_processor.py#L13-L96)

### 数据流架构

```mermaid
flowchart TD
Start([请求到达]) --> Validate[验证请求参数]
Validate --> CheckAuth{检查认证状态}
CheckAuth --> |未认证| AuthError[返回认证错误]
CheckAuth --> |已认证| CheckCache{检查缓存}
CheckCache --> |命中缓存| ReturnCache[返回缓存数据]
CheckCache --> |缓存未命中| FetchData[从教务系统抓取数据]
FetchData --> SaveHTML[保存HTML调试文件]
SaveHTML --> FixEncoding[修复编码问题]
FixEncoding --> ParseData[解析HTML数据]
ParseData --> TransformData[转换数据格式]
TransformData --> StoreData[存储到数据库]
StoreData --> Vectorize[向量化处理]
Vectorize --> ReturnData[返回响应数据]
ReturnCache --> End([结束])
ReturnData --> End
AuthError --> End
```

**图表来源**
- [main.py:398-580](file://backend/main.py#L398-L580)
- [scraper.py:23-56](file://backend/scraper.py#L23-L56)
- [data_processor.py:97-181](file://backend/app/services/data_processor.py#L97-L181)

## 详细组件分析

### 成绩查询接口

#### 接口定义

**GET `/api/grades`**
- **功能**: 获取学生成绩列表
- **认证**: 需要登录状态
- **参数**:
  - `username`: 学号（路径参数）
  - `kksj`: 开课时间（查询参数）
  - `kcxz`: 课程性质（查询参数）
  - `kcmc`: 课程名称（查询参数）
  - `fxkc`: 修读类别（查询参数，0=主修，1=辅修）
  - `xsfs`: 显示方式（查询参数，all=全部，max=最好）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": [
    {
      "序号": "1",
      "开课学期": "2024-2025-1",
      "课程编号": "CS101",
      "课程名称": "数据结构",
      "平时成绩": "80",
      "实验成绩": "85",
      "期末成绩": "88",
      "成绩": "85",
      "学分": "4.0",
      "总学时": "64",
      "考核方式": "考试",
      "课程属性": "必修",
      "课程性质": "专业必修",
      "通选课分类": "",
      "考试性质": "正常考试",
      "成绩标识": "",
      "备注": ""
    }
  ],
  "count": 10,
  "stats": {
    "total_credits_required": 120,
    "credits_exempted": 0,
    "credits_completed": 80,
    "credits_remaining": 40,
    "gpa_major": 3.2,
    "rank": "15/200",
    "gpa_minor": 0.0
  }
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/grades?username=2024110101&kcxz=01&fxkc=0&xsfs=all"
```

**更新** 成绩查询接口现在包含完整的统计信息，包括总学分要求、已完成学分、绩点等关键指标，并新增了HTML调试输出功能。

**章节来源**
- [main.py:629-666](file://backend/main.py#L629-L666)
- [scraper.py:243-385](file://backend/scraper.py#L243-L385)

### 课表查询接口

#### 接口定义

**GET `/api/schedule`**
- **功能**: 获取学期课表
- **认证**: 需要登录状态
- **参数**:
  - `username`: 学号（路径参数）
  - `semester`: 学期（查询参数，如"2024-2025-2"）
  - `week`: 周次（查询参数，如"1", "5"）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": [
    {
      "课程名称": "操作系统",
      "星期": "周一",
      "星期代码": 1,
      "节次": "1-2",
      "教师": "李汇熙副教授",
      "地点": "拓新楼(SS1)133",
      "周次": "1-16",
      "节次信息": "[01-02]节"
    }
  ],
  "count": 5,
  "semester": "2024-2025-2",
  "week": "",
  "未安排时间课程": ["高等数学"],
  "raw_html": "<!-- 原始HTML内容 -->"
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/schedule?username=2024110101&semester=2024-2025-2&week=1"
```

**更新** 课表查询接口现在包含原始HTML内容，便于调试和数据分析，并新增了HTML文件保存功能。

**章节来源**
- [main.py:683-713](file://backend/main.py#L683-L713)
- [scraper.py:473-714](file://backend/scraper.py#L473-L714)

### 培养方案查询接口

#### 接口定义

**GET `/api/training-plan/my`**
- **功能**: 获取我的培养方案
- **认证**: 需要登录状态
- **参数**:
  - `username`: 学号（路径参数）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": {
    "课程列表": [
      {
        "序号": "1",
        "学期": "3",
        "课程代码": "CS1001",
        "课程名称": "数据结构",
        "开课院系": "计算机学院",
        "学分": "4",
        "学时": "64",
        "考核方式": "考试",
        "性质": "必修",
        "是否适用": "是"
      }
    ],
    "count": 20
  }
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/training-plan/my?username=2024110101"
```

**更新** 培养方案查询接口现在使用更准确的表格解析逻辑，能够正确识别目标课程表格，并新增了HTML调试输出功能。

**章节来源**
- [main.py:715-739](file://backend/main.py#L715-L739)
- [scraper.py:803-829](file://backend/scraper.py#L803-L829)

### 学业进度查询接口

#### 接口定义

**GET `/api/academic-progress`**
- **功能**: 获取学业进度
- **认证**: 需要登录状态
- **参数**:
  - `username`: 学号（路径参数）
  - `study_type`: 修读类型（查询参数，0=主修，1=辅修）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": {
    "修读类型": "主修",
    "总学分要求": 120,
    "已获学分": 80,
    "还需学分": 40,
    "课程列表": [
      {
        "课程性质": "必修",
        "课程代码": "CS1001",
        "课程名称": "数据结构",
        "学分": "4",
        "建议修读学期": "3",
        "免听免修": "否",
        "模块应修学分": "",
        "已获学分": "4"
      }
    ],
    "count": 15
  }
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/academic-progress?username=2024110101&study_type=0"
```

**更新** 学业进度查询接口现在包含更详细的统计信息，包括修读类型和学分计算，并新增了HTML调试输出功能。该接口具备了以下增强功能：
- 智能的总学分提取：支持从标题和表格头部双重来源提取学分要求
- 增强的课程列表去重：基于课程代码和名称的复合去重机制
- 优化的合计行识别：准确识别并统计已获学分
- 完善的学分统计：自动计算还需学分
- 详细的HTML调试输出：提供完整的解析过程跟踪

**章节来源**
- [main.py:741-767](file://backend/main.py#L741-L767)
- [scraper.py:1051-1218](file://backend/scraper.py#L1051-L1218)
- [education.py:121-135](file://backend/app/api/education.py#L121-L135)

### 考试安排查询接口

#### 接口定义

**GET `/api/exam-schedule`**
- **功能**: 获取考试安排
- **认证**: 需要登录状态
- **参数**:
  - `username`: 学号（路径参数）
  - `semester`: 学期（查询参数，如"2024-2025-1"）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": [
    {
      "序号": "1",
      "课程名称": "数据结构",
      "考试时间": "2025-01-15 08:30-10:30",
      "考试地点": "教学楼A101",
      "座位号": "01",
      "考试方式": "期末考试",
      "考试性质": "正常考试",
      "状态": "已发布"
    }
  ],
  "count": 5,
  "semester": "2024-2025-1"
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/exam-schedule?username=2024110101&semester=2024-2025-1"
```

**更新** 考试安排查询接口现在包含更完整的考试信息，包括考试时间、地点、座位号等，并新增了HTML调试输出功能。

**章节来源**
- [main.py:769-796](file://backend/main.py#L769-L796)
- [scraper.py:1227-1282](file://backend/scraper.py#L1227-L1282)

### 教师查询接口

#### 接口定义

**GET `/api/teacher/search`**
- **功能**: 查询教师信息
- **认证**: 无需登录
- **参数**:
  - `name`: 教师姓名（查询参数，支持模糊查询）
  - `department`: 所属院系代码（查询参数）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": [
    {
      "序号": "1",
      "教职工号": "1001",
      "教师姓名": "李明",
      "所属院系": "计算机学院",
      "教师ID": "12345",
      "详情链接": "http://jwxt.gdufe.edu.cn/jsxsd/jsxx/jsxx_query_detail?jg0101id=12345"
    }
  ],
  "count": 3
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/teacher/search?name=李&department=11"
```

**更新** 教师查询接口现在包含教师ID和详情链接，便于进一步获取教师详细信息。

**章节来源**
- [main.py:798-825](file://backend/main.py#L798-L825)
- [scraper.py:1291-1376](file://backend/scraper.py#L1291-L1376)

### 课程查询接口

#### 接口定义

**GET `/api/course/search`**
- **功能**: 查询课程信息
- **认证**: 无需登录
- **参数**:
  - `course_name`: 课程名称（查询参数）
  - `course_code`: 课程代码（查询参数）
  - `department`: 开课院系（查询参数）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": [
    {
      "课程代码": "CS1001",
      "课程名称": "数据结构",
      "学分": "4",
      "总学时": "64",
      "课程性质": "必修",
      "开课院系": "计算机学院",
      "课程ID": "CS1001"
    }
  ],
  "count": 1
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/course/search?course_name=数据结构&department=11"
```

**更新** 课程查询接口现在包含课程ID，便于进一步获取课程详细信息。

**章节来源**
- [main.py:827-855](file://backend/main.py#L827-L855)
- [scraper.py:1378-1468](file://backend/scraper.py#L1378-L1468)

### 选课信息查询接口

#### 接口定义

**GET `/api/course-selection`**
- **功能**: 获取选课信息
- **认证**: 需要登录状态
- **参数**:
  - `username`: 学号（路径参数）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": {
    "当前选课轮次": [
      {
        "轮次名称": "2024-2025-1 第一轮",
        "开始时间": "2024-09-01 00:00:00",
        "结束时间": "2024-09-15 23:59:59",
        "状态": "进行中"
      }
    ],
    "可选课程": []
  }
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/course-selection?username=2024110101"
```

**更新** 选课信息查询接口提供了完整的选课轮次和可选课程信息。

**章节来源**
- [main.py:857-880](file://backend/main.py#L857-L880)
- [scraper.py:1470-1550](file://backend/scraper.py#L1470-L1550)

### 执行计划查询接口

#### 接口定义

**GET `/api/execution-plan`**
- **功能**: 获取执行计划
- **认证**: 需要登录状态
- **参数**:
  - `username`: 学号（路径参数）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": {
    "计划信息": {
      "培养方案版本": "2024级",
      "专业": "计算机科学与技术",
      "年级": "2024",
      "学制": "4年",
      "总学分": "120"
    },
    "课程列表": [
      {
        "学年学期": "2024-2025-1",
        "课程代码": "CS1001",
        "课程名称": "数据结构",
        "学分": "4",
        "课程性质": "必修",
        "考核方式": "考试",
        "是否选课": "是"
      }
    ],
    "count": 15
  }
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/execution-plan?username=2024110101"
```

**更新** 执行计划查询接口提供了完整的培养方案和已选课程信息。

**章节来源**
- [main.py:882-906](file://backend/main.py#L882-L906)
- [scraper.py:1551-1689](file://backend/scraper.py#L1551-L1689)

### 个人信息查询接口

#### 接口定义

**GET `/api/user/info`**
- **功能**: 获取用户个人信息
- **认证**: 需要登录状态
- **参数**:
  - `username`: 学号（路径参数）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": {
    "name": "张三",
    "student_id": "2024110101",
    "major": "计算机科学与技术",
    "class": "计科2401",
    "department": "计算机学院"
  }
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/user/info?username=2024110101"
```

**更新** 个人信息查询接口现在支持从多个HTML源提取准确信息。

**章节来源**
- [main.py:571-602](file://backend/main.py#L571-L602)
- [scraper.py:95-201](file://backend/scraper.py#L95-L201)

### 学籍卡片查询接口

#### 接口定义

**GET `/api/user/card`**
- **功能**: 获取学籍卡片详细信息
- **认证**: 需要登录状态
- **参数**:
  - `username`: 学号（路径参数）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": {
    "姓名": "张三",
    "学号": "2024110101",
    "性别": "男",
    "出生日期": "2005-09-01",
    "民族": "汉",
    "政治面貌": "共青团员",
    "身份证号": "44010120050901XXXX",
    "入学日期": "2024-09-01",
    "学制": "4年",
    "专业": "计算机科学与技术",
    "班级": "计科2401",
    "学籍状态": "在读"
  }
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/user/card?username=2024110101"
```

**更新** 学籍卡片查询接口提供了完整的个人信息。

**章节来源**
- [main.py:604-627](file://backend/main.py#L604-L627)
- [scraper.py:203-242](file://backend/scraper.py#L203-L242)

### 所有数据聚合接口

#### 接口定义

**GET `/api/all-data`**
- **功能**: 获取所有数据（用于向量化/RAG）
- **认证**: 需要登录状态
- **参数**:
  - `username`: 学号（路径参数）

#### 数据结构

**响应数据结构**:
```json
{
  "success": true,
  "data": {
    "个人信息": {
      "name": "张三",
      "student_id": "2024110101",
      "major": "计算机科学与技术",
      "class": "计科2401",
      "department": "计算机学院"
    },
    "成绩信息": {
      "按学期": {
        "2024-2025-1": [
          {
            "课程名称": "数据结构",
            "成绩": "85",
            "学分": "4.0",
            "开课学期": "2024-2025-1"
          }
        ]
      },
      "统计信息": {
        "total_credits_required": 120,
        "credits_completed": 80,
        "gpa_major": 3.2
      }
    },
    "课表信息": {
      "学期": "2024-2025-2",
      "课程列表": [...]
    },
    "培养方案": {...},
    "学业进度": {...},
    "考试安排": {
      "学期": "2024-2025-1",
      "考试列表": [...]
    },
    "教师信息": [...],
    "课程信息": [...]
  }
}
```

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/all-data?username=2024110101"
```

**更新** 新增的向量化数据聚合接口，为RAG系统提供完整数据支持，现已支持按学期分类的成绩、课表和考试安排数据。

**章节来源**
- [main.py:908-932](file://backend/main.py#L908-L932)
- [scraper.py:1470-1550](file://backend/scraper.py#L1470-L1550)

### 选项查询接口

#### 接口定义

**GET `/api/options/departments`**
- **功能**: 获取院系列表
- **认证**: 无需登录
- **参数**:
  - `keyword`: 搜索关键词（查询参数）
  - `include_admin`: 是否包含职能部门（查询参数）
  - `include_vocational`: 是否包含联合培养学院（查询参数）

**GET `/api/options/semesters`**
- **功能**: 获取学期列表
- **认证**: 无需登录
- **参数**:
  - `include_past`: 是否包含过去学期（查询参数）
  - `include_future`: 是否包含未来学期（查询参数）

**GET `/api/options/current-semester`**
- **功能**: 获取当前学期
- **认证**: 无需登录

**GET `/api/options/course`**
- **功能**: 获取课程相关选项
- **认证**: 无需登录

**GET `/api/options/schedule`**
- **功能**: 获取课表相关选项
- **认证**: 无需登录

**GET `/api/options/grade`**
- **功能**: 获取成绩查询相关选项
- **认证**: 无需登录

**GET `/api/options/all`**
- **功能**: 获取所有选项数据
- **认证**: 无需登录

**章节来源**
- [main.py:936-1018](file://backend/main.py#L936-L1018)
- [education_options.py:1-420](file://backend/education_options.py#L1-L420)

## 按学期分类的数据结构

### 成绩数据的学期分类

系统现在支持按学期对成绩数据进行分类存储，提供更精确的数据组织和查询能力：

```json
{
  "成绩信息": {
    "按学期": {
      "2024-2025-1": [
        {
          "课程名称": "数据结构",
          "开课学期": "2024-2025-1",
          "成绩": "85",
          "学分": "4.0",
          "课程性质": "必修"
        },
        {
          "课程名称": "算法设计",
          "开课学期": "2024-2025-1",
          "成绩": "88",
          "学分": "3.5",
          "课程性质": "必修"
        }
      ],
      "2024-2025-2": [
        {
          "课程名称": "操作系统",
          "开课学期": "2024-2025-2",
          "成绩": "82",
          "学分": "4.0",
          "课程性质": "专业必修"
        }
      ]
    },
    "统计信息": {
      "total_credits_required": 120,
      "credits_completed": 80,
      "gpa_major": 3.2,
      "course_count": 15
    }
  }
}
```

### 课表数据的学期分类

课表数据现在包含学期信息，便于按学期查询和展示：

```json
{
  "课表信息": {
    "学期": "2024-2025-2",
    "课程列表": [
      {
        "课程名称": "操作系统",
        "学期": "2024-2025-2",
        "星期": "周一",
        "节次": "1-2",
        "教师": "李教授",
        "地点": "教学楼A101",
        "周次": "1-16",
        "节次信息": "[01-02]节"
      }
    ]
  }
}
```

### 考试安排的学期分类

考试安排数据同样支持按学期分类：

```json
{
  "考试安排": {
    "学期": "2024-2025-1",
    "考试列表": [
      {
        "课程名称": "数据结构",
        "考试时间": "2025-01-15 08:30-10:30",
        "考试地点": "教学楼A101",
        "座位号": "01",
        "考试方式": "期末考试"
      }
    ]
  }
}
```

**更新** 学术数据组织系统完全重构，实现了按学期分类的数据结构，显著提升了数据查询的精确性和AI上下文感知能力。

## AI上下文感知能力

### 数据分块策略

系统现在采用更精细的数据分块策略，为AI系统提供更好的上下文感知能力：

```mermaid
flowchart TD
A[原始数据] --> B[个人信息分块]
B --> C[每门课程1个分块]
C --> D[每天课表1个分块]
D --> E[按学期分组的培养方案]
E --> F[学业进度综合分块]
F --> G[每门考试1个分块]
G --> H[最终向量集合]
```

**图表来源**
- [data_processor.py:182-404](file://backend/app/services/data_processor.py#L182-L404)

### 元数据标注

每个数据分块都包含丰富的元数据信息，用于AI系统理解和检索：

- **类型标识**: personal_info, grade, schedule, training_plan, academic_progress, exam
- **课程信息**: course, semester, day
- **来源标识**: 指明数据来自哪个接口或页面
- **文本内容**: 结构化的学习数据描述

### 向量化优化

系统现在支持批量向量化处理，提高了RAG系统的响应速度：

- **批量处理**: 每批10个数据块，避免超时
- **占位向量**: 对无法生成向量的数据使用占位向量
- **过滤机制**: 自动过滤无效数据块

**更新** AI上下文感知能力得到显著提升，数据分块策略更加精细化，元数据标注更加丰富，为RAG系统提供了更好的支持。

## 调试功能详解

### HTML调试输出功能

系统为所有核心API接口新增了HTML调试输出功能，提供详细的日志记录和问题诊断能力：

#### 调试文件保存

每个接口在处理数据时都会将原始HTML内容保存到临时文件中：

- **成绩查询**: `/tmp/debug_grades.html`
- **课表查询**: `/tmp/debug_schedule.html`  
- **培养方案**: `/tmp/debug_training_plan.html`
- **个人信息**: `/tmp/debug_personal_info.html`
- **学业进度**: `/tmp/debug_academic_progress.html`

#### 日志记录增强

所有爬虫操作都增加了详细的日志记录：

```python
logger.info(f"【学业进度调试】请求URL: {url}")
logger.info(f"【学业进度调试】响应状态: {response.status_code}")
logger.info(f"【学业进度调试】响应URL: {response.url}")
logger.info(f"【学业进度调试】HTML长度: {len(html_text)}")
logger.info(f"【学业进度调试】找到 {len(all_tables)} 个表格")
logger.info(f"【学业进度调试】提取总学分要求: {progress_data['总学分要求']}")
logger.info(f"【学业进度调试】表格{table_idx}合计已获学分: {table_earned}")
```

#### 调试功能特性

1. **实时HTML保存**: 每次请求都会保存原始HTML到文件系统
2. **详细日志跟踪**: 包含URL、状态码、响应时间等关键信息
3. **表格解析调试**: 显示找到的表格数量和解析过程
4. **编码问题诊断**: 提供编码检测和解码过程的日志
5. **错误快速定位**: 通过日志快速定位数据解析问题
6. **智能学分提取**: 跟踪总学分从标题和表格头部的提取过程

#### 调试文件内容

保存的HTML文件包含完整的原始页面内容，便于：

- **页面结构分析**: 查看真实的HTML结构和CSS类名
- **数据提取验证**: 验证表格选择器和解析逻辑
- **编码问题排查**: 检查页面编码和特殊字符处理
- **性能优化**: 分析页面加载时间和数据量
- **解析过程跟踪**: 查看详细的学分提取和课程解析过程

#### 专门的学业进度解析测试

系统新增了专门的学业进度解析测试工具，用于验证复杂的表格解析逻辑：

- **测试HTML文件**: `.qoder/教务系统源代码/学业进度查询.txt`
- **智能表格识别**: 自动识别包含特定表头的表格
- **学分提取验证**: 测试从标题和表格头部提取学分的能力
- **合计行识别**: 验证合计行的识别和已获学分统计
- **课程去重测试**: 验证基于课程代码和名称的去重逻辑

**章节来源**
- [scraper.py:1051-1218](file://backend/scraper.py#L1051-L1218)
- [test_academic_progress.py:1-109](file://backend/test_academic_progress.py#L1-L109)

## 依赖关系分析

### 组件依赖图

```mermaid
graph TB
subgraph "核心模块"
MAIN[main.py]
SCRAPER[scraper.py]
DATA_PROCESSOR[data_processor.py]
EDUCATION_API[education.py]
MCP_TOOLS[tools.py]
end
subgraph "数据模型"
USER_MODEL[user.py]
EDUCATION_MODEL[education_data.py]
end
subgraph "配置工具"
OPTIONS[education_options.py]
end
subgraph "测试模块"
TEST_SCRAPER[test_scraper.py]
TEST_LOGIN[test_login.py]
TEST_ACADEMIC_PROGRESS[test_academic_progress.py]
end
subgraph "调试模块"
DEBUG[HTML调试输出]
LOG[日志系统]
end
MAIN --> SCRAPER
MAIN --> DATA_PROCESSOR
EDUCATION_API --> SCRAPER
MCP_TOOLS --> SCRAPER
DATA_PROCESSOR --> USER_MODEL
DATA_PROCESSOR --> EDUCATION_MODEL
SCRAPER --> OPTIONS
SCRAPER --> DEBUG
DEBUG --> LOG
TEST_SCRAPER --> SCRAPER
TEST_LOGIN --> MAIN
TEST_ACADEMIC_PROGRESS --> SCRAPER
```

**图表来源**
- [main.py:1-1060](file://backend/main.py#L1-L1060)
- [scraper.py:1-1550](file://backend/scraper.py#L1-L1550)
- [data_processor.py:1-409](file://backend/app/services/data_processor.py#L1-L409)

### 外部依赖

系统对外部依赖主要包括：

1. **教务系统**: 通过HTTP请求与广东财经大学教务系统交互
2. **数据库**: 支持MySQL、PostgreSQL等关系型数据库
3. **向量数据库**: Milvus支持RAG系统
4. **认证服务**: JWT令牌认证系统
5. **网络服务**: 需要稳定的网络连接访问教务系统
6. **文件系统**: 用于保存HTML调试文件

**更新** 核心爬虫功能重构后，URL构造逻辑更加健壮，编码处理能力显著提升，向量化接口为RAG系统提供完整支持，调试功能增强了系统的可维护性。特别是学业进度查询接口，新增了专门的解析测试工具。

**章节来源**
- [main.py:50-81](file://backend/main.py#L50-L81)
- [scraper.py:16-21](file://backend/scraper.py#L16-L21)

## 性能考虑

### 编码处理优化

系统采用了智能的编码处理策略：

1. **UTF-8优先**: 首先尝试UTF-8编码解码
2. **GBK回退**: UTF-8解码失败时使用GBK/GB18030
3. **中文检测**: 通过正则表达式检测中文字符确保正确解码
4. **动态调整**: 根据响应内容自动选择最适合的编码方式

### 缓存策略

系统采用多层次缓存策略以提高性能：

1. **会话缓存**: 使用内存字典存储用户会话信息
2. **数据缓存**: 可选的Redis缓存用于存储频繁查询的数据
3. **静态资源缓存**: 图片和静态文件的浏览器缓存
4. **向量缓存**: Milvus中的向量数据缓存

### 性能优化建议

1. **并发处理**: 使用异步编程模式处理多个并发请求
2. **数据库优化**: 合理设置数据库连接池大小
3. **网络优化**: 实现超时控制和重试机制
4. **数据压缩**: 对大响应数据进行压缩传输
5. **向量化优化**: 批量处理向量数据，避免超时
6. **调试文件清理**: 定期清理临时HTML调试文件
7. **表格解析优化**: 缓存已识别的表格结构，避免重复解析

### 监控指标

建议监控以下关键指标：
- API响应时间
- 数据爬取成功率
- 数据库连接池使用率
- 内存使用情况
- 错误率统计
- 向量数据库性能
- 调试文件存储空间
- 学业进度解析准确率

**更新** 编码处理优化显著提升了数据解析的准确性，向量化接口为RAG系统提供了高效的查询能力，调试功能为系统维护提供了强大支持。新增的学业进度解析测试工具进一步提升了系统的可靠性。

## 故障排除指南

### 常见问题及解决方案

#### 登录失败

**问题症状**: 用户无法登录教务系统
**可能原因**:
1. 网络连接问题
2. 验证码过期
3. 用户名或密码错误
4. 教务系统维护
5. **URL构造错误**（已修复）

**解决步骤**:
1. 检查网络连接状态
2. 重新获取验证码
3. 验证用户名密码格式
4. 稍后重试或联系管理员
5. **确认URL构造正确，避免重复jsxsd前缀**

#### 数据获取失败

**问题症状**: 查询接口返回空数据或错误
**可能原因**:
1. 教务系统页面结构变化
2. 网络超时
3. 服务器负载过高
4. **编码处理失败**（已优化）
5. **URL路径错误**（已修复）
6. **HTML调试文件缺失**
7. **学业进度表格解析失败**（已增强）

**解决步骤**:
1. 检查教务系统页面结构
2. 增加超时时间
3. 实现重试机制
4. 降级处理策略
5. **验证编码处理逻辑**
6. **验证URL拼接逻辑，确保正确路径**
7. **检查调试文件是否正确保存**
8. **使用学业进度解析测试工具验证表格识别**

#### 性能问题

**问题症状**: API响应缓慢
**可能原因**:
1. 数据库查询效率低
2. 网络延迟
3. 并发请求过多
4. **重复URL请求**（已优化）
5. **调试文件过多占用磁盘空间**
6. **表格解析性能问题**（已优化）

**解决步骤**:
1. 优化数据库查询语句
2. 实施缓存策略
3. 负载均衡
4. 异步处理
5. **减少无效的URL重定向**
6. **定期清理调试文件**
7. **优化表格解析算法**

#### 编码问题

**问题症状**: 中文字符显示乱码
**可能原因**:
1. 页面编码不一致
2. 字符串解码错误
3. 编码检测失败

**解决步骤**:
1. 检查页面实际编码
2. 实现多编码尝试解码
3. 使用正则表达式检测中文字符
4. 回退到兼容编码方案

#### 调试问题

**问题症状**: HTML调试文件无法保存或访问
**可能原因**:
1. 文件权限不足
2. 磁盘空间不足
3. 路径不存在
4. 调试功能被禁用
5. **学业进度解析失败**（已增强）

**解决步骤**:
1. 检查/tmp目录权限
2. 清理磁盘空间
3. 确认路径存在
4. 启用调试功能
5. **检查日志输出**
6. **使用专门的解析测试工具**

#### 学业进度解析问题

**问题症状**: 学业进度数据不准确或缺失
**可能原因**:
1. 表格结构变化
2. 学分提取算法失效
3. 课程去重逻辑错误
4. 合计行识别失败
5. **HTML结构复杂**（已增强）

**解决步骤**:
1. 检查HTML结构变化
2. 更新学分提取算法
3. 验证去重逻辑
4. 检查合计行识别
5. **使用解析测试工具验证**
6. **查看详细的调试日志**

**更新** 编码处理逻辑经过优化，现在能够智能检测和处理UTF-8和GBK混合编码场景。URL构造逻辑修复解决了重复前缀导致的额外请求和重定向问题。调试功能提供了完整的HTML文件保存和详细日志记录能力。新增的学业进度解析测试工具大大提升了系统的可维护性。

**章节来源**
- [main.py:187-328](file://backend/main.py#L187-L328)
- [scraper.py:23-56](file://backend/scraper.py#L23-L56)

### 调试工具

系统提供了完善的调试工具：

1. **登录测试脚本**: `test_login.py` - 测试登录功能
2. **爬虫测试脚本**: `test_scraper.py` - 测试爬虫功能
3. **学业进度解析测试**: `test_academic_progress.py` - 专门测试学业进度解析
4. **日志系统**: 完整的日志记录和错误追踪
5. **健康检查**: `/api/health` - 系统健康状态检查
6. **向量化测试**: 完整的数据聚合和向量化流程测试
7. **HTML调试文件**: 自动保存的原始页面内容
8. **编码检测**: 智能编码处理和错误诊断
9. **学业进度解析测试工具**: 专门验证复杂的表格解析逻辑

**更新** 调试工具现在可以正确测试重构后的URL构造逻辑和编码处理能力。新增了向量化数据聚合接口的测试功能。调试功能提供了完整的HTML文件保存和详细日志记录能力。新增的学业进度解析测试工具专门验证复杂的表格解析和学分提取逻辑。

**章节来源**
- [test_login.py:1-152](file://backend/test_login.py#L1-L152)
- [test_scraper.py:1-280](file://backend/test_scraper.py#L1-L280)
- [test_academic_progress.py:1-109](file://backend/test_academic_progress.py#L1-L109)

## 结论

本学术数据查询API系统为广东财经大学学生提供了全面、便捷的学术数据查询服务。系统具有以下特点：

1. **功能完整**: 覆盖了学生成绩、课表、培养方案、学业进度、考试安排等核心功能
2. **接口规范**: 采用RESTful API设计，参数清晰，响应标准化
3. **性能优良**: 通过缓存、异步处理等技术手段保证系统性能
4. **易于扩展**: 模块化设计便于功能扩展和维护
5. **安全可靠**: 完善的认证机制和错误处理
6. **智能化**: 新增向量化接口支持RAG系统
7. **可调试性强**: 完善的HTML调试输出和日志记录功能
8. **按学期分类**: 支持按学期分类的成绩、课表和考试安排数据
9. **AI上下文感知**: 提供更精确的数据分块和元数据标注

**更新亮点**:
- **URL构造修复**: 成功消除了重复的'/jsxsd/'前缀问题
- **编码处理优化**: 智能处理UTF-8和GBK混合编码场景
- **个人信息增强**: 支持从多个HTML源提取准确信息
- **向量化支持**: 完整的数据聚合接口支持RAG系统
- **稳定性提升**: 统一了所有接口的URL拼接逻辑
- **兼容性改善**: 确保与不同服务器配置的兼容性
- **调试能力增强**: 提供了详细的日志输出和错误诊断
- **HTML调试输出**: 新增完整的HTML文件保存和分析功能
- **按学期分类**: 实现了按学期分类的数据组织结构
- **AI上下文感知**: 提升了数据分块和元数据标注的精确性
- **学业进度增强**: 学业进度查询接口得到重大增强，包括改进的表格解析逻辑、增强的数值提取能力、优化的学分统计机制等

**学业进度查询接口的重大改进**:
- **智能总学分提取**: 支持从标题和表格头部双重来源提取学分要求
- **增强的表格解析**: 更准确地识别课程表格和表头
- **优化的课程去重**: 基于课程代码和名称的复合去重机制
- **完善的合计行识别**: 准确识别并统计已获学分
- **详细的HTML调试**: 提供完整的解析过程跟踪和问题诊断
- **专门的解析测试**: 新增的测试工具验证复杂的表格解析逻辑

系统在实际部署中建议：
- 生产环境使用Redis作为缓存存储
- 配置适当的超时和重试机制
- 实施监控和告警系统
- 定期更新爬虫逻辑以适应教务系统变化
- 建立数据备份和恢复机制
- 部署Milvus向量数据库支持RAG功能
- 定期清理调试文件，避免磁盘空间不足
- 监控调试文件的存储和访问权限
- 利用按学期分类的数据结构优化查询性能
- 使用专门的解析测试工具验证学业进度解析准确性
- 建立完善的日志记录和错误追踪机制

通过持续的优化和维护，该系统能够为用户提供稳定、高效、可靠的学术数据查询服务，为教育智能化发展提供坚实的技术支撑。新增的调试功能和专门的解析测试工具大大提升了系统的可维护性和问题诊断能力，为后续的功能扩展和优化提供了强有力的支持。按学期分类的数据结构和AI上下文感知能力的提升，为RAG系统的应用奠定了坚实的基础。学业进度查询接口的增强功能显著提升了整体学术数据查询的准确性和稳定性，为学生提供了更优质的学术数据服务体验。