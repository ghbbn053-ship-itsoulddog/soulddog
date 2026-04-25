# 第一个可用版本测试指南

> 目标：把当前平台收口成“第一次可用版本（MVP）”的端到端测试清单。  
> 范围：工作区、知识库、Skill/MCP/Composition、工作区内嵌 AI 面板、基础聊天回溯。  
> 当前阶段：测试前收口。

---

## 1. 本次测试测什么

这次不要追求“全功能”，只测最核心闭环。

### 1.1 通过标准

只要下面 8 项全部通过，就可以认为当前代码达到了第一个可用版本：

1. 登录后可以正常进入首页 / 工作区
2. 可以创建工作区并进入详情页
3. 可以把文本或文件写入知识库
4. 知识库管理台可以查看文档 / chunk / 删除文档
5. Skill 可以导入，MCP 可以导入
6. Composition 可以启停 Skill / MCP，并调整 MCP 顺序
7. 工作区内嵌 AI 面板可以发起带 `workspace_id` 的对话
8. 回答里的引用可以跳回工作区文档 / chunk

### 1.2 暂时不纳入阻塞项

这些先不作为 MVP 阻塞条件：

- 回答正文内部的深度证据化分层
- 拖拽式编排 UI
- 多步 Agent orchestration
- 知识库批量治理
- 完整模型自定义配置迁移到内嵌 AI 面板

---

## 2. Linux 部署 / 更新命令

以下命令假设项目目录为 `~/soulddog`。

### 2.1 拉代码

```bash
cd ~/soulddog
git pull origin main
```

### 2.2 什么时候必须重构

以下情况必须 `--build`：

- 改了 `backend/Dockerfile`
- 改了 `frontend/Dockerfile` 或 `frontend/Dockerfile.dev`
- 改了 `backend/requirements.txt`
- 改了 `frontend/package.json`
- 改了容器启动命令或 `docker-compose.yml`

以下情况通常**不需要**重构镜像，只需要重启容器：

- 只改了前后端源码
- 只改了页面、API、服务逻辑
- 只改了文档、样式、组件、路由

### 2.3 需要重构时的完整命令

```bash
cd ~/soulddog
git pull origin main
docker compose -f docker-compose.yml down
docker compose -f docker-compose.yml rm -f frontend backend
docker image prune -f
docker compose -f docker-compose.yml up -d --build frontend backend
docker compose -f docker-compose.yml logs -f frontend backend
```

### 2.4 不需要重构时的完整命令

```bash
cd ~/soulddog
git pull origin main
docker compose -f docker-compose.yml restart frontend backend
docker compose -f docker-compose.yml logs -f frontend backend
```

### 2.5 如果要顺手清理没用容器 / 网络 / 缓存

```bash
cd ~/soulddog
docker compose -f docker-compose.yml down --remove-orphans
docker container prune -f
docker image prune -f
docker network prune -f
docker compose -f docker-compose.yml up -d --build frontend backend
docker compose -f docker-compose.yml logs -f frontend backend
```

> 注意：`postgres / redis / milvus / minio / etcd` 这些数据服务不要乱 `-v` 删卷，除非你明确要清库。

---

## 3. 测试顺序

不要乱测，按顺序走，这样最容易定位问题。

### 3.1 登录与入口

验证：

- 打开 `/login`
- 能正常登录
- 登录后能进入首页
- `/workspace` 能打开
- `/knowledge` 能打开
- `/composition` 能打开

通过标准：

- 没有无限跳转
- 没有明显白屏
- 没有频繁自动刷新导致不可用

### 3.2 工作区

验证：

- 创建一个新工作区
- 进入 `/workspace/[id]`
- 左中右三栏正常显示
- 工作区状态 / 学习状态 / 建议区正常加载

通过标准：

- 工作区可创建
- 详情页不报错
- 页面无结构性错乱

### 3.3 知识库入库

验证：

- 手工录入一段文本
- 上传一个小型 `.md` / `.txt` / `.pdf` / `.docx` 文件
- 文档出现在工作区详情页
- 文档出现在 `/knowledge`

通过标准：

- 文档成功写入
- 状态可见
- chunk 能看到

### 3.4 知识库管理台

验证：

- `/knowledge` 里切换工作区
- 搜索文档
- 选中文档看 chunk
- 删除一份文档

通过标准：

- 页面能正常切换工作区
- 文档和 chunk 能正常展示
- 删除后列表刷新正常

### 3.5 Skill / MCP 导入

验证：

- Skill：
  - YAML 粘贴导入
  - 文件导入
  - GitHub URL 导入
- MCP：
  - JSON 文件导入
  - URL 导入
  - 重载工具

通过标准：

- 导入成功后列表可见
- Skill 能看到 `input_schema`
- MCP 能看到参数结构

### 3.6 拼积木（Composition）

验证：

- 启用一个 Skill
- 启用一个 MCP
- 调整 MCP 顺序
- 页面摘要显示变化

通过标准：

- 启停状态能保存
- 刷新页面后状态仍在
- 编排页摘要与工作区页摘要一致

### 3.7 工作区内嵌 AI 面板

验证：

- 在 `/workspace/[id]` 右栏直接发起对话
- 切换 `chat / agent`
- 切换 `openai_agents / langgraph`
- 开关 `show_thinking`
- 查看当前工作区会话列表

通过标准：

- 能发消息
- 会话只属于当前工作区
- 不会把别的工作区会话串进来

### 3.8 引用回跳

验证：

- 提一个能命中文档的问题
- 回答里出现引用片段
- 点击引用片段回跳到工作区文档 / chunk

通过标准：

- 能跳转
- 能定位到对应文档
- 如果带 chunk，能定位到对应片段

---

## 4. 发现问题时怎么记

建议每个问题按下面格式记录：

```text
[模块]
工作区内嵌 AI 面板

[步骤]
1. 进入 /workspace/3
2. 右栏发送“培养方案里数据库相关课程有哪些”
3. 返回结果后点击引用片段

[现象]
跳转到了 /workspace/3，但没有滚动到对应 chunk

[日志]
贴 frontend/backend 容器日志关键段落
```

---

## 5. 当前测试前建议

现在最适合做的是：

1. 先在 Linux 上拉最新代码并部署
2. 严格按本清单走一遍
3. 把失败项集中返回
4. 再做一轮“修问题收口”

不要现在继续扩功能，不然测试边界会不断漂移。
