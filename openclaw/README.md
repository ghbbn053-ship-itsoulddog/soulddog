# 教务系统助手 - OpenClaw Skill

一个强大的教务系统查询工具，集成到OpenClaw中，让你通过自然语言查询成绩、课表、学业进度等教务数据。

## ✨ 功能特性

- 📊 **成绩查询** - 按学期查询成绩，支持统计分析
- 📅 **课表查询** - 查看学期课表，按星期展示
- 🎓 **学业进度** - 实时跟踪学分完成情况
- 📚 **培养方案** - 查看专业培养要求和课程规划
- 📝 **考试安排** - 查询考试时间、地点
- 👤 **个人信息** - 查看学籍基本信息

## 🚀 快速开始

### 前置要求

1. **Python 3.8+** - 运行MCP Server
2. **OpenClaw** - 已安装并配置完成
3. **教务系统账号** - 有效的学号和密码

### 安装步骤

#### 1. 克隆项目

```bash
git clone https://github.com/ghbbn053-ship-itsoulddog/soulddog.git
cd soulddog
```

#### 2. 安装Python依赖

```bash
cd backend
pip install -r requirements.txt
```

#### 3. 在Web端登录教务系统

首先需要启动Web应用并登录教务系统，这样MCP Server才能访问你的Session：

```bash
# 项目根目录
docker compose up -d
```

访问 `http://localhost:5000` 并登录教务系统。

#### 4. 配置OpenClaw

在OpenClaw的配置文件（通常是 `~/.openclaw/config.json` 或 OpenClaw设置界面）中添加MCP Server：

**方式1: 使用skill.json（推荐）**

```bash
# 复制skill.json到OpenClaw技能目录
cp openclaw/skill.json ~/.openclaw/skills/education-system/
```

**方式2: 手动配置**

在OpenClaw配置文件中添加：

```json
{
  "mcpServers": {
    "education-system": {
      "command": "python",
      "args": ["/path/to/soulddog/backend/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/path/to/soulddog/backend"
      }
    }
  }
}
```

#### 5. 重启OpenClaw

```bash
openclaw restart
```

## 💬 使用示例

### 成绩查询

```
你: 查询我的成绩
AI: 共查询到 45 条成绩记录

1. 高等数学
   成绩: 92 | 学分: 5
   学期: 2024-2025-1 | 性质: 必修

2. 大学英语
   成绩: 88 | 学分: 3
   学期: 2024-2025-1 | 性质: 必修
...
```

### 课表查询

```
你: 今天有什么课？
AI: 【星期三】
  1-2节 - 数据结构
    教师: 张教授 | 地点: 教学楼A301
    周次: 1-16周

  3-4节 - 操作系统
    教师: 李教授 | 地点: 教学楼B205
    周次: 1-16周
```

### 学业进度

```
你: 我还差多少学分毕业？
AI: 学业进度概览

总学分要求: 160
已修学分: 120
未修学分: 40

各模块进度:
  通识教育: 已修 40/50 学分
  专业基础: 已修 35/40 学分
  专业核心: 已修 30/40 学分
  实践教学: 已修 15/30 学分
```

### 考试安排

```
你: 什么时候期末考试？
AI: 2024-2025-1 学期考试安排
共 8 门考试

📅 2025-01-10 09:00-11:00
   课程: 高等数学
   地点: 教学楼C101
   方式: 闭卷

📅 2025-01-12 14:00-16:00
   课程: 大学英语
   地点: 教学楼A205
   方式: 闭卷
```

## 🔧 高级配置

### 环境变量

可以在MCP Server配置中设置环境变量：

```json
{
  "mcpServers": {
    "education-system": {
      "command": "python",
      "args": ["mcp_server.py"],
      "env": {
        "LOG_LEVEL": "INFO",
        "DATABASE_URL": "postgresql://user:pass@localhost/db"
      }
    }
  }
}
```

### 自定义学期格式

学期格式为：`YYYY-YYYY-X`
- `YYYY-YYYY`: 学年，如 `2024-2025`
- `X`: 学期编号，`1`为上学期，`2`为下学期

示例：`2024-2025-1` 表示2024-2025学年上学期

## ⚠️ 注意事项

1. **首次使用需要先登录** - MCP Server依赖Web端的Session，使用前请确保已在Web端登录教务系统
2. **Session有效期** - 教务系统Session可能过期，如果查询失败，请在Web端重新登录
3. **多用户支持** - 支持多用户查询，但每次需要指定学号
4. **数据同步** - 数据来自教务系统实时查询，确保信息最新

## 🐛 故障排除

### 问题1: "用户未登录"

**原因**: Web端未登录或Session已过期

**解决**: 
1. 访问 `http://localhost:5000`
2. 使用学号密码登录教务系统
3. 重新在OpenClaw中查询

### 问题2: MCP Server启动失败

**原因**: Python依赖未安装或路径错误

**解决**:
```bash
cd backend
pip install -r requirements.txt
python mcp_server.py  # 测试是否能正常启动
```

### 问题3: 查询结果为空

**原因**: 教务系统中无数据或学期参数错误

**解决**:
1. 确认学期格式正确（如 `2024-2025-1`）
2. 不传学期参数查询所有数据
3. 在Web端验证数据是否存在

## 📖 API文档

所有可用的MCP工具：

| 工具名 | 描述 | 参数 |
|--------|------|------|
| `query_grades` | 查询成绩 | username (必填), semester (可选) |
| `query_schedule` | 查询课表 | username (必填), semester (可选) |
| `query_academic_progress` | 查询学业进度 | username (必填) |
| `query_training_plan` | 查询培养方案 | username (必填) |
| `query_exam_schedule` | 查询考试安排 | username (必填), semester (可选) |
| `query_personal_info` | 查询个人信息 | username (必填) |

## 🤝 贡献

欢迎提交Issue和Pull Request！

项目地址: https://github.com/ghbbn053-ship-itsoulddog/soulddog

## 📄 许可证

MIT License

---

**Powered by Campus AI Assistant** 🎓
