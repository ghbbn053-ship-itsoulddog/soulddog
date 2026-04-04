# 🔄 Git 同步到 PyCharm 指南

## 🌟 推荐方案：使用 Git 远程仓库

### 为什么选择 Git？
- ✅ 自动版本控制
- ✅ 多设备协同开发
- ✅ 历史回溯
- ✅ 团队协作

---

## 📋 步骤详解

### 第一步：创建远程仓库

#### 选项 A：使用 Gitee（国内推荐）
1. 访问 https://gitee.com
2. 登录/注册账号
3. 点击右上角 "+" → "新建仓库"
4. 填写仓库信息：
   - 仓库名称：`gdufe-ai-assistant`
   - 仓库介绍：`教务系统 AI 助手`
   - **是否公开**：选择 `公开`
   - **初始化仓库**：取消勾选所有选项
5. 点击 "创建"

#### 选项 B：使用 GitHub
1. 访问 https://github.com
2. 登录/注册账号
3. 点击右上角 "+" → "New repository"
4. 填写仓库信息：
   - Repository name：`gdufe-ai-assistant`
   - Description：`教务系统 AI 助手`
   - **Public/Private**：选择 `Public`
   - **不要** 勾选 "Add a README file"
5. 点击 "Create repository"

---

### 第二步：获取仓库地址

创建完成后，复制仓库地址：
- **Gitee**：`https://gitee.com/你的用户名/gdufe-ai-assistant.git`
- **GitHub**：`https://github.com/你的用户名/gdufe-ai-assistant.git`

---

### 第三步：在沙箱中配置远程仓库

将下面的命令中的 `<仓库地址>` 替换为你刚才复制的地址：

```bash
cd /workspace/projects
git remote add origin <仓库地址>
git branch -M main
git push -u origin main
```

**示例（Gitee）：**
```bash
git remote add origin https://gitee.com/zhangsan/gdufe-ai-assistant.git
git branch -M main
git push -u origin main
```

---

### 第四步：在 PyCharm 中克隆仓库

1. **打开 PyCharm**
2. 点击 **Get from VCS**
3. 在 URL 中输入你的仓库地址
4. 选择本地目录（例如：`D:\Projects\gdufe-ai-assistant`）
5. 点击 **Clone**

**完成！** 现在你的代码已经同步到本地了。

---

## 🔄 日常工作流程

### 在沙箱中修改后同步到本地

**沙箱端（修改代码）：**
```bash
cd /workspace/projects
git add .
git commit -m "描述你的修改"
git push
```

**本地 PyCharm 端（拉取最新代码）：**
1. 点击 PyCharm 右上角的 **Update** 图标（蓝色箭头）
2. 或使用快捷键：`Ctrl + T`

---

### 在本地修改后同步到沙箱

**本地 PyCharm 端（修改代码）：**
1. 修改代码
2. 右键项目 → **Git** → **Commit**
3. 填写提交信息 → **Commit and Push**

**沙箱端（拉取最新代码）：**
```bash
cd /workspace/projects
git pull
```

---

## ⚠️ 常见问题

### 问题 1：push 时提示身份验证失败

**解决方案：**
```bash
# 配置用户信息
git config --global user.name "你的用户名"
git config --global user.email "你的邮箱"

# Gitee：使用个人访问令牌
# 访问：https://gitee.com/profile/personal_access_tokens
# 生成令牌，复制后使用：
git push
# 用户名：输入 Gitee 用户名
# 密码：粘贴访问令牌

# GitHub：使用个人访问令牌
# 访问：https://github.com/settings/tokens
# 生成令牌，复制后使用：
git push
# 用户名：GitHub 用户名
# 密码：粘贴访问令牌
```

---

### 问题 2：push 时提示 "Updates were rejected"

**解决方案：**
```bash
# 强制推送（谨慎使用！）
git push -u origin main --force
```

**更好的方案（保留远程修改）：**
```bash
git pull --rebase
git push
```

---

## 📦 备选方案：SFTP 同步

如果你不想用 Git，也可以配置 PyCharm 的 SFTP 直接同步。

### 配置步骤：

1. **打开 PyCharm**
2. 点击 **File** → **Settings** → **Build, Execution, Deployment** → **Deployment**
3. 点击 **+** 添加服务器
4. 配置：
   - **Name**：`沙箱服务器`
   - **Type**：`SFTP`
5. **Connection** 标签：
   - **SFTP host**：你的沙箱 IP 地址
   - **Port**：22
   - **User name**：root
   - **Auth type**：Password
   - **Password**：你的沙箱密码
6. **Mappings** 标签：
   - **Local path**：项目本地路径
   - **Deployment path**：`/workspace/projects`
7. 点击 **OK**

### 同步文件：
- **上传到沙箱**：右键文件 → **Deployment** → **Upload to...**
- **从沙箱下载**：右键文件 → **Deployment** → **Download from...**

---

## 🎯 推荐工作流

```
┌─────────────┐    git push    ┌─────────────┐
│  本地 PyCharm  │ ──────────────> │  Git 远程仓库  │
└─────────────┘                └─────────────┘
       │                               │
       │ git pull                      │ git push
       ↓                               ↓
┌─────────────┐    git pull    ┌─────────────┐
│  云端沙箱    │ <────────────── │  Git 远程仓库  │
└─────────────┘                └─────────────┘
```

---

## 📞 需要帮助？

如果遇到问题，可以：
1. 查看官方文档：https://git-scm.com/doc
2. 搜索报错信息
3. 联系项目维护者

---

**现在就开始配置你的 Git 仓库吧！** 🚀
