# Agent MCP Integration

更新时间：2026-04-26

目标：
- 将平台内部教务能力作为外部 Agent 可调用能力输出
- 保持统一身份入口仍然是 Web 端教务系统登录
- 外部 Agent 不直接登录教务系统，只复用平台授权

## 1. 当前架构

当前不是让外部 Agent 直接持有教务账号，而是：

1. 用户先登录 Web 平台
2. Web 平台持有教务系统 session
3. 平台为该 Web 用户生成 `Agent Access Token`
4. 外部 Agent 使用本地 `stdio MCP bridge`
5. bridge 通过平台 API 调用真实工具

这意味着：
- 统一身份中心在 Web
- 教务授权也统一在 Web
- 外部 Agent 只是复用平台能力，不直接触达教务系统

## 2. 已有后端接口

### Agent Access

- `GET /api/agent-access/{username}`
  - 查看 token、服务绑定、登录策略
- `POST /api/agent-access/tokens`
  - 创建 Agent Token
- `DELETE /api/agent-access/tokens/{token_id}`
  - 撤销 Agent Token
- `GET /api/agent-access/{username}/bootstrap`
  - 导出外部 Agent 接入所需 bootstrap 配置

### MCP

- `GET /api/mcp/agent/catalog`
  - 读取当前 Agent Token 可见的工具目录
- `POST /api/mcp/tools/{tool_name}`
  - 实际工具调用入口
- `GET /api/mcp/tools/{tool_name}/schema`
  - 单个工具 schema

## 3. Agent Bridge

桥接脚本：

- [mcp_agent_bridge.py](C:\Users\ASUS\Desktop\智能体构建\project_20260404_235124\backend\mcp_agent_bridge.py)

作用：
- 自己作为一个本地 `stdio MCP server`
- 对外暴露工具列表和工具调用
- 内部把所有调用转发到平台 API

所需环境变量：

- `SOULDDOG_API_BASE`
- `SOULDDOG_AGENT_TOKEN`
- `SOULDDOG_MCP_SERVER_NAME` 可选
- `SOULDDOG_VERIFY_TLS` 可选

## 4. 最小接入步骤

### Web 侧

1. 在 Web 端完成教务系统登录
2. 进入 MCP 页面
3. 在 `Agent Access` 区块创建一个 token
4. 确认 `education` 服务绑定状态为 `active`

### Claude Desktop / OpenClaw 侧

1. 配置一个本地 stdio MCP server
2. 启动命令指向 `backend/mcp_agent_bridge.py`
3. 把平台 API 地址和 Agent Token 注入环境变量

## 5. Claude Desktop 示例

```json
{
  "mcpServers": {
    "soulddog-platform": {
      "command": "python",
      "args": ["backend/mcp_agent_bridge.py"],
      "env": {
        "SOULDDOG_API_BASE": "http://127.0.0.1:8000",
        "SOULDDOG_AGENT_TOKEN": "soulddog_at_xxx"
      }
    }
  }
}
```

## 6. OpenClaw Skill 示例

```json
{
  "name": "soulddog-platform",
  "description": "Bridge to Souldog platform MCP tools using Web-managed auth",
  "tools": [
    "query_grades",
    "query_schedule",
    "query_academic_progress",
    "query_training_plan",
    "query_exam_schedule",
    "query_personal_info",
    "query_weather"
  ],
  "mcpServers": {
    "soulddog-platform": {
      "transport": "stdio",
      "command": "python",
      "args": ["backend/mcp_agent_bridge.py"],
      "env": {
        "SOULDDOG_API_BASE": "http://127.0.0.1:8000",
        "SOULDDOG_AGENT_TOKEN": "soulddog_at_xxx"
      }
    }
  }
}
```

## 7. 当前边界

已经能做到：
- 外部 Agent 复用 Web 端教务授权
- 平台按 token scope 控制可见工具
- 教务绑定失效时后端主动拒绝调用

还没做到：
- 平台自身直接作为完整远程 MCP transport server 对外提供 `sse/streamable_http`
- 外部 Agent 的自动登录/自动换 token
- 多外部服务绑定统一编排

## 8. 为什么先这样做

这是当前最稳的落地方式：

- 对现有 Web 平台侵入最小
- 统一身份模型清晰
- 可以先让 OpenClaw / Claude Desktop 真接起来
- 不需要立刻在平台侧完整实现所有 MCP transport server 细节

## 9. 后续自然演进

下一阶段可以继续做：

1. 把 bridge 配置导出直接做成前端一键复制
2. 支持多个 token profile
3. 再把平台自身升级成正式远程 MCP server
