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
4. 外部 Agent 直接连接平台原生远程 MCP server
5. MCP server 在平台内按 token 绑定的用户身份执行真实工具

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

### 原生远程 MCP Transport

- `POST /mcp`
  - `streamable_http` 入口
- `GET /sse`
  - SSE 握手入口

两者都要求：

- `Authorization: Bearer soulddog_at_xxx`

## 3. 原生远程 MCP Server

平台现在同时提供：

- `streamable_http`: `http://<host>:8000/mcp`
- `sse`: `http://<host>:8000/sse`

认证方式统一为：

- `Authorization: Bearer <AgentToken>`

`Agent Token` 仍然由 Web 平台签发，登录入口仍然是教务系统 Web 登录。

## 4. 最小接入步骤

### Web 侧

1. 在 Web 端完成教务系统登录
2. 进入 MCP 页面
3. 在 `Agent Access` 区块创建一个 token
4. 确认 `education` 服务绑定状态为 `active`

### Claude Desktop / OpenClaw / mcporter 侧

1. 配置一个远程 MCP server URL
2. 选择 `streamable_http` 或 `sse`
3. 把 `Authorization: Bearer <AgentToken>` 作为请求头传入

## 5. 远程 streamable_http 示例

```json
{
  "mcpServers": {
    "soulddog-platform": {
      "transport": "streamable_http",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "Bearer soulddog_at_xxx"
      }
    }
  }
}
```

## 6. 远程 SSE 示例

```json
{
  "mcpServers": {
    "soulddog-platform": {
      "transport": "sse",
      "url": "http://127.0.0.1:8000/sse",
      "headers": {
        "Authorization": "Bearer soulddog_at_xxx"
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
- 平台直接提供原生远程 `streamable_http` / `sse` MCP 入口

还没做到：
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
