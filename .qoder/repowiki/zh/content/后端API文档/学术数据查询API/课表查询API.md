# 课表查询API

<cite>
**本文档引用的文件**
- [backend/app/api/education.py](file://backend/app/api/education.py)
- [backend/main.py](file://backend/main.py)
- [backend/scraper.py](file://backend/scraper.py)
- [backend/education_options.py](file://backend/education_options.py)
- [backend/app/models/education_data.py](file://backend/app/models/education_data.py)
- [backend/test_scraper.py](file://backend/test_scraper.py)
</cite>

## 更新摘要
**变更内容**
- 修正了课表查询端点的URL构造逻辑，确保正确的课程数据获取
- 更新了课表查询接口的URL路径为 `/api/schedule`
- 完善了课表查询参数的详细说明和使用示例

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

本文档详细说明了教务系统中的课表查询接口，重点介绍 `/api/schedule` 接口的完整规范。该接口支持按学期和周次查询课表，提供了灵活的查询参数组合，能够满足不同场景下的课表查询需求。

**更新** 课表查询接口现已修复URL构造逻辑，确保正确的课程数据获取。接口路径为 `/api/schedule`，支持GET请求方式。

系统基于FastAPI框架构建，采用前后端分离架构，通过爬虫技术从教务系统中抓取课表数据，并提供RESTful API接口供前端应用调用。

## 项目结构

该项目采用模块化设计，主要包含以下核心模块：

```mermaid
graph TB
subgraph "后端服务"
API[API路由层<br/>/api/schedule]
Service[业务服务层<br/>EducationService]
Scraper[爬虫层<br/>JwxtScraper]
Model[数据模型层<br/>EducationData]
end
subgraph "外部系统"
JWXT[教务系统<br/>jwxt.gdufe.edu.cn]
Database[(数据库)]
end
subgraph "前端应用"
Frontend[前端界面]
end
Frontend --> API
API --> Service
Service --> Scraper
Scraper --> JWXT
Service --> Database
Model --> Database
```

**图表来源**
- [backend/main.py:455-488](file://backend/main.py#L455-L488)
- [backend/app/api/education.py:93-103](file://backend/app/api/education.py#L93-L103)

**章节来源**
- [backend/main.py:1-124](file://backend/main.py#L1-L124)
- [backend/app/api/education.py:1-13](file://backend/app/api/education.py#L1-L13)

## 核心组件

### API路由层

系统提供了两个主要的课表查询接口：

1. **FastAPI路由接口** (`/api/schedule`)
   - **更新** 修正了URL构造逻辑，确保正确的课程数据获取
   - 适用于需要用户认证的场景
   - 使用数据库会话管理
   - 支持异步操作

2. **传统API接口** (`/api/education/schedule`)
   - 适用于简单的课表查询
   - 使用会话管理
   - 支持学期和周次参数

### 爬虫服务层

`JwxtScraper` 类负责与教务系统的交互：

- **课表查询方法** (`get_schedule`)
- **学期参数映射** (`xnxq01id`)
- **周次参数映射** (`zc`)
- **HTML解析和数据提取**
- **更新** 修正了课表查询端点URL构造逻辑

### 数据模型层

教育数据模型支持课表数据的持久化存储：

- `EducationData` 主表，存储完整的教务数据
- `Course` 课程表，专门存储课表相关信息
- JSON字段支持灵活的数据结构

**章节来源**
- [backend/app/api/education.py:93-103](file://backend/app/api/education.py#L93-L103)
- [backend/scraper.py:348-516](file://backend/scraper.py#L348-L516)
- [backend/app/models/education_data.py:11-103](file://backend/app/models/education_data.py#L11-L103)

## 架构概览

```mermaid
sequenceDiagram
participant Client as 客户端
participant API as API网关
participant Service as 业务服务
participant Scraper as 爬虫服务
participant JWXT as 教务系统
Client->>API : GET /api/schedule?username=xxx&semester=2024-2025-2&week=5
API->>API : 验证用户会话
API->>Service : 调用课表查询服务
Service->>Scraper : get_schedule(semester, week)
Scraper->>JWXT : POST /jsxsd/xskb/xskb_list.do
Scraper->>Scraper : 解析HTML课表
Scraper-->>Service : 返回课程数据
Service-->>API : 格式化响应数据
API-->>Client : JSON响应
Note over Client,JWXT : 异步处理，支持并发请求
```

**图表来源**
- [backend/main.py:480-510](file://backend/main.py#L480-L510)
- [backend/scraper.py:348-372](file://backend/scraper.py#L348-L372)

## 详细组件分析

### 课表查询接口规范

#### 基础信息

| 属性 | 描述 |
|------|------|
| **接口地址** | `/api/schedule` |
| **HTTP方法** | GET |
| **认证要求** | 是（需要有效的用户会话） |
| **响应格式** | JSON |

#### 请求参数

| 参数名 | 类型 | 必填 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `username` | string | 是 | - | 用户标识符，用于会话验证 |
| `semester` | string | 否 | 空字符串 | 学期标识符，如 "2024-2025-2" |
| `week` | string | 否 | 空字符串 | 周次标识符，如 "1", "5" |

#### 学期参数规范

学期参数遵循特定的格式规范：

```mermaid
flowchart TD
Start([开始解析学期参数]) --> CheckEmpty{"学期参数为空?"}
CheckEmpty --> |是| UseCurrent["使用当前学期"]
CheckEmpty --> |否| ValidateFormat["验证格式"]
ValidateFormat --> FormatValid{"格式有效?"}
FormatValid --> |是| UseProvided["使用提供的学期"]
FormatValid --> |否| UseCurrent
UseCurrent --> ReturnSemester["返回学期标识"]
UseProvided --> ReturnSemester
ReturnSemester --> End([结束])
```

**图表来源**
- [backend/scraper.py:315-318](file://backend/scraper.py#L315-L318)

#### 周次参数规范

周次参数支持多种查询模式：

| 查询模式 | 示例 | 描述 |
|----------|------|------|
| 单周查询 | `week=5` | 查询第5周的课表 |
| 多周查询 | `week=1,3,5` | 查询第1、3、5周的课表 |
| 全部周次 | `week=` | 查询所有周次的课表 |
| 周次范围 | `week=1-16` | 查询第1到16周的课表 |

#### 响应数据结构

```mermaid
classDiagram
class ScheduleResponse {
+string 课程名称
+string 星期
+int 星期代码
+string 节次
+string 教师
+string 地点
+string 周次
+string 节次信息
}
class APIResponse {
+bool success
+ScheduleResponse[] data
+int count
+string semester
+string week
+string[] 未安排时间课程
}
APIResponse --> ScheduleResponse : 包含多个
```

**图表来源**
- [backend/scraper.py:474-484](file://backend/scraper.py#L474-L484)
- [backend/main.py:494-502](file://backend/main.py#L494-L502)

#### 实际使用示例

**示例1：查询特定学期课表**
```
GET /api/schedule?username=2024001&semester=2024-2025-2
```

**示例2：查询指定周次课表**
```
GET /api/schedule?username=2024001&week=5
```

**示例3：查询特定学期和周次的课表**
```
GET /api/schedule?username=2024001&semester=2024-2025-2&week=5
```

**示例4：查询所有周次课表**
```
GET /api/schedule?username=2024001&semester=2024-2025-2&week=
```

### 数据解析和处理

#### HTML解析流程

```mermaid
flowchart TD
LoadPage[加载课表页面] --> ParseHTML[解析HTML内容]
ParseHTML --> FindTable[查找课表表格]
FindTable --> CheckTable{"找到表格?"}
CheckTable --> |否| ReturnEmpty["返回空课表"]
CheckTable --> |是| ParseRows[解析行数据]
ParseRows --> ExtractPeriod[提取节次信息]
ExtractPeriod --> LoopDays[遍历星期列]
LoopDays --> ExtractCourse[提取课程信息]
ExtractCourse --> ParseCourseInfo[解析课程详细信息]
ParseCourseInfo --> AddToResult[添加到结果集]
AddToResult --> CheckRemarks[检查备注信息]
CheckRemarks --> ReturnResult[返回最终结果]
ReturnEmpty --> End([结束])
ReturnResult --> End
```

**图表来源**
- [backend/scraper.py:376-499](file://backend/scraper.py#L376-L499)

#### 课程信息字段详解

| 字段名 | 类型 | 描述 | 示例 |
|--------|------|------|------|
| `课程名称` | string | 课程的完整名称 | "数据结构" |
| `星期` | string | 星期的中文表示 | "周一" |
| `星期代码` | int | 星期的数字代码 | 1 |
| `节次` | string | 节次范围标识 | "1-2" |
| `教师` | string | 授课教师姓名 | "李教授" |
| `地点` | string | 上课教室信息 | "拓新楼(SS1)133" |
| `周次` | string | 上课周次范围 | "1-16" |
| `节次信息` | string | 节次详细信息 | "[01-02]节" |

### 未安排时间课程处理

系统能够识别并处理未安排时间的课程：

```mermaid
flowchart TD
Start([开始处理课表]) --> ParseTable[解析课表表格]
ParseTable --> FindRemarkRow[查找备注行]
FindRemarkRow --> CheckRemark{"找到备注信息?"}
CheckRemark --> |否| ProcessNormal[正常处理课表]
CheckRemark --> |是| ExtractCourses[提取未安排课程]
ExtractCourses --> ValidateFormat{"格式正确?"}
ValidateFormat --> |是| StoreCourses[存储课程列表]
ValidateFormat --> |否| ProcessNormal
StoreCourses --> ProcessNormal
ProcessNormal --> ReturnData[返回处理后的数据]
ReturnData --> End([结束])
```

**图表来源**
- [backend/scraper.py:486-499](file://backend/scraper.py#L486-L499)

## 依赖关系分析

### 组件依赖图

```mermaid
graph TB
subgraph "外部依赖"
Requests[requests库]
BeautifulSoup[beautifulsoup4]
FastAPI[fastapi]
SQLAlchemy[sqlalchemy]
end
subgraph "内部模块"
Main[main.py]
EducationAPI[education.py]
Scraper[scraper.py]
Options[education_options.py]
Models[education_data.py]
end
Main --> EducationAPI
Main --> Scraper
Main --> Options
EducationAPI --> Scraper
EducationAPI --> Models
Scraper --> Requests
Scraper --> BeautifulSoup
Models --> SQLAlchemy
```

**图表来源**
- [backend/main.py:15-25](file://backend/main.py#L15-L25)
- [backend/app/api/education.py:1-11](file://backend/app/api/education.py#L1-L11)

### 数据流分析

```mermaid
sequenceDiagram
participant Client as 客户端
participant Main as 主应用
participant API as API路由
participant Service as 业务服务
participant Scraper as 爬虫
participant Database as 数据库
Client->>Main : HTTP请求
Main->>API : 路由转发
API->>Service : 业务逻辑处理
Service->>Scraper : 数据抓取
Scraper->>Scraper : HTML解析
Scraper->>Database : 数据存储
Database-->>Scraper : 存储确认
Scraper-->>Service : 解析结果
Service-->>API : 格式化响应
API-->>Client : JSON响应
```

**图表来源**
- [backend/main.py:480-510](file://backend/main.py#L480-L510)
- [backend/app/api/education.py:93-103](file://backend/app/api/education.py#L93-L103)

**章节来源**
- [backend/main.py:480-510](file://backend/main.py#L480-L510)
- [backend/app/api/education.py:93-103](file://backend/app/api/education.py#L93-L103)
- [backend/scraper.py:348-516](file://backend/scraper.py#L348-L516)

## 性能考虑

### 查询优化策略

1. **缓存机制**
   - 会话数据缓存在内存中
   - 建议在生产环境中使用Redis等分布式缓存

2. **并发处理**
   - 支持异步操作
   - 使用连接池管理数据库连接

3. **网络优化**
   - 设置合理的超时时间
   - 实现重试机制

### 错误处理机制

系统实现了多层次的错误处理：

```mermaid
flowchart TD
Request[接收请求] --> ValidateParams[验证参数]
ValidateParams --> CheckSession{检查会话}
CheckSession --> |无效| Return401[返回401错误]
CheckSession --> |有效| CallService[调用服务]
CallService --> TryCatch{捕获异常}
TryCatch --> |异常| LogError[记录错误日志]
TryCatch --> |正常| FormatResponse[格式化响应]
LogError --> Return500[返回500错误]
FormatResponse --> Return200[返回200成功]
Return401 --> End([结束])
Return500 --> End
Return200 --> End
```

**图表来源**
- [backend/main.py:506-509](file://backend/main.py#L506-L509)

## 故障排除指南

### 常见问题及解决方案

| 问题类型 | 症状 | 可能原因 | 解决方案 |
|----------|------|----------|----------|
| 认证失败 | 401未授权 | 用户会话过期 | 重新登录获取新会话 |
| 参数错误 | 400参数错误 | 学期格式不正确 | 检查学期参数格式 |
| 网络超时 | 504网关超时 | 教务系统繁忙 | 增加超时时间或稍后重试 |
| 数据解析失败 | 500服务器错误 | HTML结构变化 | 更新解析规则 |

### 调试建议

1. **启用详细日志**
   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **检查网络连接**
   - 验证教务系统可达性
   - 检查防火墙设置

3. **验证参数格式**
   - 确保学期参数符合 "YYYY-YYYY-S" 格式
   - 确保周次参数为有效的数字或范围

**章节来源**
- [backend/main.py:506-509](file://backend/main.py#L506-L509)
- [backend/scraper.py:511-516](file://backend/scraper.py#L511-L516)

## 结论

课表查询API提供了灵活而强大的课表查询功能，支持按学期和周次的精确查询。系统采用模块化设计，具有良好的扩展性和维护性。

**更新** 课表查询接口现已修复URL构造逻辑，确保正确的课程数据获取。接口路径为 `/api/schedule`，支持GET请求方式，能够稳定地从教务系统中抓取课表数据。

### 主要特性

1. **灵活的查询参数**：支持学期、周次的独立和组合查询
2. **完整的数据结构**：包含课程的所有必要信息
3. **健壮的错误处理**：提供清晰的错误信息和恢复机制
4. **高性能设计**：支持并发处理和缓存机制
5. **稳定的URL构造**：修正了课表查询端点的URL构造逻辑

### 最佳实践

1. **参数验证**：始终验证输入参数的有效性
2. **错误处理**：实现完善的异常处理和日志记录
3. **性能优化**：合理使用缓存和连接池
4. **监控告警**：建立完善的监控和告警机制

该API为教务系统的课表查询提供了标准化的解决方案，能够满足各种复杂的查询需求。