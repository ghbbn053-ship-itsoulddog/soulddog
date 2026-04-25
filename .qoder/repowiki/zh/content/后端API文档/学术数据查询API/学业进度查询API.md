# 学业进度查询API

<cite>
**本文档引用的文件**
- [backend/main.py](file://backend/main.py)
- [backend/scraper.py](file://backend/scraper.py)
- [backend/education_options.py](file://backend/education_options.py)
- [backend/app/models/education_data.py](file://backend/app/models/education_data.py)
- [backend/app/api/education.py](file://backend/app/api/education.py)
- [backend/test_academic_progress.py](file://backend/test_academic_progress.py)
- [crawled_html/08_学业进度查询.html](file://crawled_html/08_学业进度查询.html)
- [deep_crawl/depth_1/1__jsxsd_pyfa_xyjdcx.html](file://deep_crawl/depth_1/1__jsxsd_pyfa_xyjdcx.html)
</cite>

## 更新摘要
**变更内容**
- 新增_extract_first_number辅助方法，专门用于从文本中提取数字
- 改进_expand_table_rows方法，增强rowspan/colspan处理能力
- 增强重复检测机制，使用set避免重复课程数据
- 优化课程数据提取逻辑，支持"课程类别/课程模块"两种变体
- 改进多表格处理能力，能够处理多个进度表格并合并数据
- 增强错误处理和调试能力，提供详细的日志信息

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

本API提供教务系统的学业进度查询功能，能够查询学生的主修和辅修学业完成情况。该系统基于爬虫技术从教务系统中抓取实时数据，为学生提供准确的学业进度统计信息。最新的版本采用了先进的表头驱动解析方法，显著提高了数据解析的准确性和稳定性，并新增了多种辅助方法来增强数据处理能力。

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
        "已获学分": "4.0",
        "模块应修学分": "8.0"
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

### 表头驱动的表格解析算法

**更新** 系统采用了全新的表头驱动解析方法，显著提高了表格识别的准确性：

#### 表格识别逻辑

```mermaid
flowchart TD
Start([开始解析]) --> FindTables["查找所有表格"]
FindTables --> CheckHeaders["检查表头字段"]
CheckHeaders --> MatchExpected{"匹配预期表头?"}
MatchExpected --> |是| FoundTable["找到目标表格"]
MatchExpected --> |否| NextTable["检查下一个表格"]
NextTable --> CheckHeaders
FoundTable --> ExtractHeader["提取表头信息"]
ExtractHeader --> ParseRows["逐行解析数据"]
ParseRows --> ExtractCredits["提取学分信息"]
ExtractCredits --> CalculateStats["计算统计指标"]
CalculateStats --> FormatResult["格式化输出"]
FormatResult --> End([完成])
```

#### 预期表头组合

系统使用以下预期表头组合来识别目标表格：
- "课程性质"
- "课程代码" 
- "课程名称"
- "学分"
- "已获学分"

#### 动态列映射机制

当检测到标准表头时，系统会：
1. 自动识别表头位置和顺序
2. 建立动态列映射关系
3. 处理不同布局表格的列偏移
4. 提取合计行中的已获学分信息

**章节来源**
- [backend/scraper.py:1037-1136](file://backend/scraper.py#L1037-L1136)

### 增强的辅助方法

**更新** 系统新增了多个辅助方法来提升数据处理能力：

#### 数字提取辅助方法

```mermaid
flowchart TD
Start([开始提取]) --> NormalizeText["规范化文本"]
NormalizeText --> SearchNumber["搜索数字模式"]
SearchNumber --> NumberFound{"找到数字?"}
NumberFound --> |是| ConvertFloat["转换为浮点数"]
NumberFound --> |否| ReturnNone["返回None"]
ConvertFloat --> Success["返回数字"]
ReturnNone --> End([结束])
Success --> End
```

#### 表格展开辅助方法

```mermaid
flowchart TD
Start([开始展开]) --> InitVars["初始化变量"]
InitVars --> IterateRows["遍历表格行"]
IterateRows --> CheckCells["检查单元格"]
CheckCells --> HandleRowspan["处理rowspan"]
HandleRowspan --> HandleColspan["处理colspan"]
HandleColspan --> AppendValues["追加展开值"]
AppendValues --> NextCell["下一个单元格"]
NextCell --> CheckCells
CheckCells --> IterateRows
IterateRows --> Done["返回展开后的表格"]
Done --> End([结束])
```

**章节来源**
- [backend/scraper.py:105-117](file://backend/scraper.py#L105-L117)
- [backend/scraper.py:55-103](file://backend/scraper.py#L55-L103)

### 模块应修学分字段支持

**更新** 系统新增了对模块应修学分字段的支持，提供更详细的课程模块学分信息：

#### 字段提取机制

```mermaid
flowchart TD
Start([开始解析]) --> FindModuleHeader["查找模块应修学分表头"]
FindModuleHeader --> CheckHeader{"存在模块应修学分?"}
CheckHeader --> |是| ExtractModuleCredits["提取模块应修学分"]
CheckHeader --> |否| UseAlternative["使用替代学分字段"]
ExtractModuleCredits --> MapToCourse["映射到课程数据"]
UseAlternative --> MapToCourse
MapToCourse --> Complete["完成字段映射"]
Complete --> End([结束])
```

#### 字段映射规则

系统支持以下字段映射：
- 直接匹配"模块应修学分"表头
- 回退到"模块学分"或其他相关字段
- 默认为空字符串以保持数据完整性

**章节来源**
- [backend/scraper.py:1157](file://backend/scraper.py#L1157)

### 学分统计的标题提取机制

**更新** 系统采用了双重学分提取策略：

#### 标题提取流程

```mermaid
flowchart TD
Start([开始提取]) --> GetPageText["获取页面文本"]
GetPageText --> SearchPattern["搜索学分模式"]
SearchPattern --> PatternFound{"找到学分信息?"}
PatternFound --> |是| ExtractCredits["提取总学分要求"]
PatternFound --> |否| DefaultZero["使用默认值0"]
ExtractCredits --> ContinueParsing["继续解析表格"]
DefaultZero --> ContinueParsing
ContinueParsing --> End([完成])
```

#### 学分提取模式

系统使用正则表达式模式来提取总学分要求：
- `需修读总学分[:：]\s*(\d+(?:\.\d+)?)`
- 支持中文冒号"："和英文冒号":"
- 支持可选的小数点格式

**章节来源**
- [backend/scraper.py:1052-1056](file://backend/scraper.py#L1052-L1056)

### 增强的错误处理机制

**更新** 系统实现了多层次的错误处理和调试机制：

#### 错误处理流程

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
Success --> |否| LogError["记录错误日志"]
LogError --> Return500["返回500错误"]
Success --> |是| Return200["返回200成功"]
Return400 --> End([结束])
Return401 --> End
Return500 --> End
Return200 --> End
```

#### 调试信息记录

系统在关键节点记录详细的调试信息：
- HTML响应内容（前500字符）
- 表格识别过程
- 数据解析状态
- 错误发生位置

**章节来源**
- [backend/scraper.py:1017-1025](file://backend/scraper.py#L1017-L1025)

### 重复检测机制

**更新** 系统实现了增强的重复检测机制，确保数据的唯一性：

#### 重复检测流程

```mermaid
flowchart TD
Start([开始解析]) --> CheckCourse["检查课程信息"]
CheckCourse --> HasInfo{"有课程信息?"}
HasInfo --> |否| Skip["跳过此行"]
HasInfo --> |是| CreateKey["创建去重键"]
CreateKey --> CheckDuplicate{"已在集合中?"}
CheckDuplicate --> |是| Skip
CheckDuplicate --> |否| AddToSet["添加到集合"]
AddToSet --> ProcessCourse["处理课程数据"]
Skip --> NextRow["下一行"]
ProcessCourse --> NextRow
NextRow --> Start
```

#### 去重策略

系统使用课程代码和课程名称的组合作为去重键：
- `(course_code, course_name)`
- 避免重复课程的多次添加
- 提高数据处理效率

**章节来源**
- [backend/scraper.py:1181-1184](file://backend/scraper.py#L1181-L1184)

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
5. **稳定性**: 采用表头驱动解析方法，显著提高了数据解析的准确性

通过该API，学生可以实时了解自己的学业进度，合理规划学习安排，提高学习效率。系统还支持与培养方案的对比分析，帮助学生更好地理解学习目标和要求。

**最新改进**：
- 采用表头驱动的表格识别算法，提高了对不同布局表格的适应性
- 新增了基于预期表头组合的表格定位逻辑
- 改进了学分统计的标题提取机制，增强了数据解析的可靠性
- 增强了错误处理和调试能力，提升了系统的稳定性
- 新增模块应修学分字段支持，提供更详细的课程模块学分信息
- 优化课程数据提取的动态列映射机制，支持"课程类别/课程模块"两种变体
- 新增_extract_first_number辅助方法，专门用于数字提取
- 改进_expand_table_rows方法，增强rowspan/colspan处理能力
- 增强重复检测机制，使用set避免重复课程数据
- 优化多表格处理能力，能够处理多个进度表格并合并数据

这些改进使得学业进度查询功能更加健壮和准确，能够更好地服务于广大学生群体。