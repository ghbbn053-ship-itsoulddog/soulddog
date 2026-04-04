# 教务系统 AI 助手

一个基于 Next.js + FastAPI + LangChain 的教务系统智能助手，支持验证码登录、数据爬取、AI 问答等功能。

## 📋 项目功能

### ✅ 已完成
- [x] 前端登录页面（Next.js + Shadcn/UI）
- [x] 后端 API（FastAPI）
- [x] 验证码获取与展示
- [x] 教务系统登录
- [x] 服务器自动选择逻辑
- [x] 前后端 CORS 通信
- [x] Dashboard 页面

### 🚧 开发中
- [ ] 教务系统数据爬取
- [ ] 个人信息存储
- [ ] Milvus 向量数据库集成
- [ ] LangChain RAG 系统
- [ ] 阿里云千问 AI 集成
- [ ] Redis 缓存
- [ ] 按学号数据隔离

## 📦 项目结构

```
教务系统 AI 助手/
├── src/                      # 前端代码（Next.js）
│   ├── app/                  # 页面路由
│   │   ├── page.tsx          # 登录页面
│   │   └── dashboard/        # Dashboard 页面
│   ├── components/ui/        # Shadcn UI 组件
│   └── lib/                  # 工具函数
├── backend/                  # 后端代码（FastAPI）
│   ├── main.py               # 主程序
│   ├── requirements.txt      # Python 依赖
│   └── .env                  # 环境变量
├── public/                   # 静态资源
└── package.json              # 前端依赖
```

## 🚀 快速开始

### 前置要求

- Python 3.8+
- Node.js 18+
- pnpm（前端包管理器）

### 1. 下载项目

在 PyCharm 中操作：

1. 打开 PyCharm
2. `File → Open`
3. 选择项目文件夹
4. 点击 `OK`

### 2. 安装后端依赖

在项目根目录打开终端，运行：

```bash
cd backend
pip install -r requirements.txt
```

### 3. 配置环境变量

后端 `.env` 文件已预配置：

```env
JWXT_BASE_URL=http://jwxt.gdufe.edu.cn
DASHSCOPE_API_KEY=sk-6c8dc750b9744c9cb60ce0eb7fcfce0e
DASHSCOPE_MODEL=qwen-plus
REDIS_HOST=localhost
REDIS_PORT=6379
MILVUS_HOST=localhost
MILVUS_PORT=19530
BACKEND_PORT=8000
```

### 4. 启动后端服务

在 `backend` 目录下运行：

```bash
python main.py
```

后端服务将运行在 `http://localhost:8000`

### 5. 安装前端依赖

在项目根目录运行：

```bash
pnpm install
```

### 6. 启动前端服务

在项目根目录运行：

```bash
pnpm dev
```

前端服务将运行在 `http://localhost:5000`

## 📱 使用说明

### 登录系统

1. 打开浏览器访问 `http://localhost:5000`
2. 输入教务系统学号、密码
3. 输入验证码（自动刷新）
4. 点击登录按钮

### Dashboard

登录成功后，自动跳转到 Dashboard 页面，可以查看：
- AI 智能问答
- 个人信息
- 成绩查询
- 课程表
- 选课中心
- 系统设置

## 🔧 技术栈

### 前端
- **框架**: Next.js 16 (App Router)
- **语言**: TypeScript 5
- **UI 组件**: Shadcn/UI (Radix UI)
- **样式**: Tailwind CSS 4

### 后端
- **框架**: FastAPI
- **语言**: Python 3.8+
- **HTTP 客户端**: requests, aiohttp
- **HTML 解析**: BeautifulSoup4

### AI 与数据
- **向量数据库**: Milvus
- **缓存**: Redis
- **LLM**: 阿里云千问（qwen-plus）
- **框架**: LangChain

## 📝 API 接口

### 1. 获取验证码
```
GET /api/captcha
Response: {
  "success": true,
  "image": "data:image/jpeg;base64,...",
  "session_id": "..."
}
```

### 2. 登录
```
POST /api/login
Body: {
  "username": "学号",
  "password": "密码",
  "code": "验证码"
}
Response: {
  "success": true,
  "message": "登录成功",
  "username": "学号",
  "session_id": "..."
}
```

### 3. 健康检查
```
GET /api/health
Response: {
  "status": "ok"
}
```

## 🎯 下一步计划

1. 实现教务系统数据爬取（个人信息、成绩、课程）
2. 集成 Milvus 向量数据库
3. 实现 LangChain RAG 系统
4. 集成阿里云千问 AI
5. 添加 Redis 缓存
6. 实现按学号数据隔离
7. 完善前端 UI 和交互
8. 添加单元测试
9. 优化性能和安全性
10. 生产环境部署

## 🐛 常见问题

### 1. 验证码获取失败
- 检查后端服务是否启动
- 检查网络连接
- 检查教务系统 URL 是否正确

### 2. 登录失败
- 检查用户名和密码是否正确
- 检查验证码是否输入正确
- 检查服务器选择逻辑

### 3. 前端无法连接后端
- 检查 CORS 配置
- 检查后端服务端口（默认 8000）
- 检查前端 API 地址配置

## 📄 许可证

MIT License

## 👤 作者

教务系统 AI 助手开发团队

---

**Powered by AI Assistant** 🚀
