# 学业进度查询API

<cite>
**本文档引用的文件**
- [backend/main.py](file://backend/main.py)
- [backend/scraper.py](file://backend/scraper.py)
- [backend/education_options.py](file://backend/education_options.py)
- [backend/app/models/education_data.py](file://backend/app/models/education_data.py)
- [backend/app/api/education.py](file://backend/app/api/education.py)
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

本API提供教务系统的学业进度查询功能，能够查询学生的主修和辅修学业完成情况。该系统基于爬虫技术从教务系统中抓取实时数据，为学生提供准确的学业进度统计信息。

## 项目结构

该项目采用前后端分离架构，主要包含以下核心模块：

```mermaid
graph TB
subgraph "后端服务"
API[FastAPI 应用]
Scraper[爬虫模块]
Models[数据模型]
Services[业务服务]
end
subgraph "前端应用"
Dashboard[仪表板]
Grades[成绩查询]
Profile[个人资料]
end
subgraph "外部系统"
JWXT[教务系统]
Database[(数据库)]
end
API --> Scraper
API --> Models
Scraper --> JWXT
API --> Database
Dashboard --> API
Grades --> API
Profile --> API
```

**图表来源**
- [backend/main.py:1-120](file://backend/main.py#L1-L120)
- [backend/scraper.py:13-21](file://backend/scraper.py#L13-L21)

**章节来源**
- [backend/main.py:1-853](file://backend/main.py#L1-L853)

## 核心组件

### API路由定义

系统提供了完整的教育相关API接口，其中学业进度查询是核心功能之一：

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/academic-progress` | GET | 获取学业进度查询 |
| `/api/grades` | GET | 获取成绩列表 |
| `/api/schedule` | GET | 获取课表信息 |
| `/api/training-plan/my` | GET | 获取培养方案 |

### 数据模型

系统使用SQLAlchemy ORM定义了完整的数据模型结构：

```mermaid
classDiagram
class EducationData {
+int id
+int user_id
+dict personal_info
+list grades
+dict grade_stats
+list schedule
+dict training_plan
+dict academic_progress
+list exam_schedule
+dict execution_plan
+dict course_selection
+datetime last_updated
}
class User {
+int id
+string username
+string student_id
+string education_password
+EducationData education_data
}
class Grade {
+int id
+int user_id
+string semester
+string course_code
+string course_name
+string course_nature
+float credit
+string usual_score
+string exam_score
+string final_score
+float gpa
+string is_passed
+datetime created_at
+datetime updated_at
}
EducationData --> User : "属于"
Grade --> User : "属于"
```

**图表来源**
- [backend/app/models/education_data.py:11-47](file://backend/app/models/education_data.py#L11-L47)
- [backend/app/models/education_data.py:50-76](file://backend/app/models/education_data.py#L50-L76)

**章节来源**
- [backend/app/models/education_data.py:1-103](file://backend/app/models/education_data.py#L1-L103)

## 架构概览

系统采用分层架构设计，实现了清晰的关注点分离：

```mermaid
sequenceDiagram
participant Client as "客户端"
participant API as "FastAPI接口"
participant Scraper as "爬虫模块"
participant JWXT as "教务系统"
participant DB as "数据库"
Client->>API : GET /api/academic-progress?username=&study_type=
API->>API : 验证用户登录状态
API->>Scraper : 创建JwxtScraper实例
Scraper->>JWXT : 发送HTTP请求
JWXT-->>Scraper : 返回HTML页面
Scraper->>Scraper : 解析HTML数据
Scraper-->>API : 返回进度数据
API->>API : 格式化响应数据
API-->>Client : JSON响应
Note over Client,DB : 数据同时存储到数据库
```

**图表来源**
- [backend/main.py:519-547](file://backend/main.py#L519-L547)
- [backend/scraper.py:686-783](file://backend/scraper.py#L686-L783)

## 详细组件分析

### 学业进度查询接口

#### 接口定义

`/api/academic-progress` 接口提供完整的学业进度查询功能：

**请求参数**
- `username` (必需): 用户名
- `study_type` (可选): 修读类型，默认值为"0"

**修读类型参数说明**

| 参数值 | 说明 | 用途 |
|--------|------|------|
| "0" | 主修课程 | 查询主修专业的学业进度 |
| "1" | 辅修课程 | 查询辅修专业的学业进度 |

#### 数据结构

接口返回的标准响应格式：

```mermaid
flowchart TD
Start([请求开始]) --> Validate["验证参数"]
Validate --> CheckLogin{"用户已登录?"}
CheckLogin --> |否| Error["返回401错误"]
CheckLogin --> |是| CreateScraper["创建爬虫实例"]
CreateScraper --> CallAPI["调用get_academic_progress"]
CallAPI --> ParseData["解析HTML数据"]
ParseData --> ExtractProgress["提取进度信息"]
ExtractProgress --> Calculate["计算统计指标"]
Calculate --> FormatResponse["格式化响应"]
FormatResponse --> Success["返回成功响应"]
Error --> End([结束])
Success --> End
```

**图表来源**
- [backend/scraper.py:686-783](file://backend/scraper.py#L686-L783)

#### 统计指标计算

系统自动计算以下关键统计指标：

| 指标名称 | 计算公式 | 说明 |
|----------|----------|------|
| 总学分要求 | 从页面标题解析 | 培养方案规定的总学分要求 |
| 已获学分 | 累加各课程已获学分 | 实际已获得的学分总数 |
| 还需学分 | 总学分要求 - 已获学分 | 完成培养方案还需修读的学分 |
| 完成比例 | 已获学分 ÷ 总学分要求 × 100% | 学业完成百分比 |

#### 返回数据格式

标准响应结构：
```json
{
  "success": true,
  "data": {
    "修读类型": "主修",
    "总学分要求": 170,
    "已获学分": 120,
    "还需学分": 50,
    "课程列表": [
      {
        "课程性质": "必修",
        "课程代码": "CS101",
        "课程名称": "数据结构",
        "学分": "4.0",
        "建议修读学期": "3",
        "免听免修": "否",
        "已获学分": "4.0"
      }
    ]
  },
  "count": 25
}
```

**章节来源**
- [backend/main.py:519-547](file://backend/main.py#L519-L547)
- [backend/scraper.py:686-783](file://backend/scraper.py#L686-L783)

### 修读类型详解

#### 主修课程 (study_type = "0")

主修课程查询用于跟踪学生主修专业的学习进度。系统会：
- 获取主修专业的培养方案
- 统计已完成的课程学分
- 计算距离毕业还需要的学分
- 提供详细的课程完成情况

#### 辅修课程 (study_type = "1")

辅修课程查询用于跟踪学生辅修专业的学习进度。系统会：
- 获取辅修专业的培养方案
- 统计辅修课程的完成情况
- 计算辅修专业的学分完成度
- 提供辅修专业的学习建议

### 培养方案对比分析

系统支持将实际学习进度与培养方案进行对比分析：

```mermaid
graph LR
subgraph "培养方案"
Plan1[必修课程]
Plan2[选修课程]
Plan3[实践环节]
end
subgraph "实际进度"
Actual1[已完成必修]
Actual2[已完成选修]
Actual3[已完成实践]
end
subgraph "对比分析"
Diff1[必修缺口]
Diff2[选修缺口]
Diff3[实践缺口]
end
Plan1 --> Diff1
Plan2 --> Diff2
Plan3 --> Diff3
Actual1 --> Diff1
Actual2 --> Diff2
Actual3 --> Diff3
```

**图表来源**
- [backend/scraper.py:686-783](file://backend/scraper.py#L686-L783)

## 依赖关系分析

### 外部依赖

系统依赖以下外部组件：

```mermaid
graph TB
subgraph "核心依赖"
FastAPI[FastAPI Web框架]
Requests[Requests HTTP库]
BeautifulSoup[BeautifulSoup HTML解析]
SQLAlchemy[SQLAlchemy ORM]
end
subgraph "数据库"
PostgreSQL[PostgreSQL数据库]
Redis[Redis缓存]
end
subgraph "前端"
NextJS[Next.js框架]
TailwindCSS[TailwindCSS样式]
end
FastAPI --> Requests
FastAPI --> SQLAlchemy
FastAPI --> PostgreSQL
FastAPI --> Redis
NextJS --> FastAPI
TailwindCSS --> NextJS
```

**图表来源**
- [backend/main.py:1-50](file://backend/main.py#L1-L50)

### 内部模块依赖

```mermaid
graph TD
Main[main.py] --> Scraper[scraper.py]
Main --> EducationOptions[education_options.py]
Main --> EducationAPI[app/api/education.py]
Scraper --> Models[app/models/education_data.py]
EducationAPI --> Models
EducationAPI --> Services[app/services/]
```

**图表来源**
- [backend/main.py:1-853](file://backend/main.py#L1-L853)

**章节来源**
- [backend/education_options.py:1-420](file://backend/education_options.py#L1-L420)

## 性能考虑

### 数据更新策略

系统采用以下策略确保数据的时效性和准确性：

1. **实时爬取**: 每次查询时直接从教务系统抓取最新数据
2. **缓存机制**: 使用Redis缓存常用查询结果，减少重复请求
3. **增量更新**: 仅更新发生变化的数据，避免全量重新抓取

### 性能优化措施

- **并发处理**: 支持多用户并发查询
- **连接池**: 使用HTTP连接池复用TCP连接
- **异步处理**: 采用异步编程模式提高响应速度
- **数据压缩**: 对传输的数据进行压缩以减少带宽占用

## 故障排除指南

### 常见问题及解决方案

| 问题类型 | 症状 | 可能原因 | 解决方案 |
|----------|------|----------|----------|
| 登录失败 | 返回"未登录，请先登录" | 用户未登录或会话过期 | 检查用户认证状态，重新登录 |
| 数据为空 | 返回空的课程列表 | 教务系统数据异常 | 稍后重试或联系管理员 |
| 服务器超时 | 请求超时错误 | 教务系统繁忙或网络问题 | 检查网络连接，稍后重试 |
| 参数错误 | 返回400错误 | 缺少必需参数或参数格式错误 | 检查请求参数格式 |

### 错误处理机制

系统实现了完善的错误处理机制：

```mermaid
flowchart TD
Request[接收请求] --> ValidateParams["验证参数"]
ValidateParams --> ParamsValid{"参数有效?"}
ParamsValid --> |否| Return400["返回400错误"]
ParamsValid --> |是| CheckAuth["检查认证状态"]
CheckAuth --> AuthValid{"认证有效?"}
AuthValid --> |否| Return401["返回401错误"]
AuthValid --> |是| ProcessRequest["处理请求"]
ProcessRequest --> Success{"处理成功?"}
Success --> |否| Return500["返回500错误"]
Success --> |是| Return200["返回200成功"]
Return400 --> End([结束])
Return401 --> End
Return500 --> End
Return200 --> End
```

**图表来源**
- [backend/main.py:519-547](file://backend/main.py#L519-L547)

**章节来源**
- [backend/main.py:519-547](file://backend/main.py#L519-L547)

## 结论

本API为教务系统提供了完整的学业进度查询功能，具有以下特点：

1. **准确性**: 直接从教务系统抓取实时数据，确保信息的准确性
2. **完整性**: 支持主修和辅修两种修读类型的进度查询
3. **易用性**: 提供简洁的API接口和标准化的数据格式
4. **扩展性**: 模块化设计便于功能扩展和维护

通过该API，学生可以实时了解自己的学业进度，合理规划学习安排，提高学习效率。系统还支持与培养方案的对比分析，帮助学生更好地理解学习目标和要求。