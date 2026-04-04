# 🎓 教务系统 AI 助手 - Windows 版本

**完全兼容 Windows 系统！** ✅

---

## 📦 Windows 完整部署指南

### 📋 前置要求

- ✅ Windows 10/11
- ✅ Python 3.8+
- ✅ Node.js 18+
- ✅ Anaconda（推荐用于 Python 环境）
- ✅ Git（可选）

---

## 🚀 Step 1: 下载项目

### 方法 1: 下载压缩包（推荐）

1. **下载项目文件到本地**
2. **解压到任意目录**，例如：
   ```
   C:\Users\你的用户名\Desktop\edu-ai-assistant
   ```

### 方法 2: 使用 Git

```bash
git clone [你的 Git 仓库地址] edu-ai-assistant
cd edu-ai-assistant
```

---

## 🚀 Step 2: 创建 Python 虚拟环境

### 使用 Anaconda（推荐）

#### 2.1 打开 Anaconda Prompt

- 按 `Win` 键
- 搜索 `Anaconda Prompt`
- 打开它

#### 2.2 创建虚拟环境

```bash
conda create -n edu-assistant python=3.10
```

输入 `y` 确认

#### 2.3 激活虚拟环境

```bash
conda activate edu-assistant
```

**成功后，前面会显示 `(edu-assistant)`**

---

## 🚀 Step 3: 配置 Python 镜像源

```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 🚀 Step 4: 安装后端依赖

```bash
cd backend
pip install -r requirements.txt --timeout 100
```

**等待安装完成...**（3-5 分钟）

---

## 🚀 Step 5: 启动后端

```bash
cd backend
python main.py
```

**成功后，你会看到：**
```
INFO:     Started server process [xxxx]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**保持这个终端不要关闭！**

---

## 🚀 Step 6: 配置 Node.js 镜像源

### 方法 1: 配置 npm 镜像

```bash
npm config set registry https://registry.npmmirror.com
```

### 方法 2: 关闭代理（如果有）

```bash
npm config set proxy null
npm config set https-proxy null
npm config set strict-ssl false
```

---

## 🚀 Step 7: 安装前端依赖

**打开新的终端（或新的 Anaconda Prompt）**

```bash
# 激活虚拟环境
conda activate edu-assistant

# 进入项目根目录
cd C:\Users\你的用户名\Desktop\edu-ai-assistant

# 清除缓存
npm cache clean --force

# 安装依赖
npm install
```

**等待安装完成...**（3-10 分钟）

---

## 🚀 Step 8: 启动前端

```bash
npm run dev
```

**成功后，你会看到：**
```
Ready in 2.3s
○ Local:   http://localhost:5000
```

---

## ✅ 访问应用

### 在浏览器中打开

```
http://localhost:5000
```

**你应该看到：**
- ✅ 登录页面
- ✅ 验证码图片（如果 VPN 已连接）
- ✅ 用户名、密码、验证码输入框

---

## 🧪 测试后端

### 健康检查

在浏览器访问：

```
http://localhost:8000/api/health
```

**应该返回：**
```json
{
  "status": "ok"
}
```

### 测试验证码

在浏览器访问：

```
http://localhost:8000/api/captcha
```

**应该返回验证码图片数据！**

---

## 🎯 测试登录

1. **输入你的教务系统学号**
2. **输入密码**
3. **输入验证码**
4. **点击登录**

**如果连接教务系统，需要：**
- 🔗 连接学校校园网
- 🔗 或使用学校 VPN

---

## 📂 项目结构

```
edu-ai-assistant/
├── src/                    # 前端代码
│   ├── app/
│   │   ├── page.tsx        # 登录页面
│   │   └── dashboard/      # Dashboard 页面
│   └── components/ui/      # UI 组件
├── backend/                # 后端代码
│   ├── main.py             # FastAPI 主程序
│   ├── requirements.txt    # Python 依赖
│   └── .env                # 环境变量
├── package.json            # 前端依赖（已修改为 Windows 版本）
└── README-Windows.md       # 本文档
```

---

## 🔧 常见问题

### Q1: npm install 报错 ETIMEDOUT

**解决方法：**

```bash
# 1. 配置镜像
npm config set registry https://registry.npmmirror.com

# 2. 关闭代理
npm config set proxy null
npm config set https-proxy null

# 3. 清除缓存
npm cache clean --force

# 4. 重新安装
npm install
```

---

### Q2: 验证码无法显示

**原因：** 无法连接到教务系统

**解决方法：**
- 连接学校校园网
- 或使用学校 VPN
- 检查 VPN 是否正常工作

---

### Q3: 后端启动失败

**检查端口是否被占用：**

```bash
netstat -ano | findstr :8000
```

**如果被占用，修改端口：**

编辑 `backend/main.py`，最后一行改为：

```python
uvicorn.run(app, host="0.0.0.0", port=8001)
```

---

### Q4: Python 依赖安装失败

**使用镜像源安装：**

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 100
```

---

## 🚀 快速启动命令（Windows 版本）

### 一键启动脚本（.bat）

**创建 `start.bat`：**

```batch
@echo off
echo ========================================
echo 教务系统 AI 助手 - Windows 启动脚本
echo ========================================

echo.
echo [1/2] 启动后端服务...
start cmd /k "cd backend && conda activate edu-assistant && python main.py"

echo.
echo [2/2] 启动前端服务...
timeout /t 3
start cmd /k "conda activate edu-assistant && npm run dev"

echo.
echo ========================================
echo 启动完成！
echo 前端地址: http://localhost:5000
echo 后端地址: http://localhost:8000
echo ========================================
echo.
echo 按任意键关闭此窗口...
pause > nul
```

**使用方法：**
1. **双击 `start.bat`**
2. **自动打开两个终端（后端 + 前端）**
3. **浏览器访问 `http://localhost:5000`**

---

## 💡 开发技巧

### 查看日志

**后端日志：**
- 在后端终端直接查看

**前端日志：**
- 在前端终端直接查看

### 停止服务

**在后端/前端终端按 `Ctrl + C`**

### 重启服务

**直接再次运行启动命令**

---

## 📱 技术栈

### 前端
- **框架**: Next.js 16
- **语言**: TypeScript
- **UI**: Shadcn/UI + Tailwind CSS

### 后端
- **框架**: FastAPI
- **语言**: Python 3.10
- **爬虫**: Selenium + BeautifulSoup4

### AI 与数据
- **LLM**: 阿里云千问（qwen-plus）
- **向量数据库**: Milvus
- **缓存**: Redis
- **框架**: LangChain

---

## 🎯 下一步

1. ✅ 测试登录功能
2. ⏳ 实现数据爬取
3. ⏳ 集成 AI 问答
4. ⏳ 完善前端 UI

---

## 📄 版本说明

- **版本**: v1.0.0
- **平台**: Windows 10/11
- **Python**: 3.8+
- **Node.js**: 18+

---

## 👤 支持

如有问题，请检查：
1. Python 虚拟环境是否激活
2. 镜像源是否配置正确
3. VPN 是否连接（如需访问教务系统）

---

**🎉 开始使用教务系统 AI 助手吧！**
