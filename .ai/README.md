# .ai/ 目录 - AI 编程工具上下文

> **用途**: 为 Qoder、Codex、Cursor 等 AI 编程工具提供高效的上下文管理
> **策略**: Delta-Only（仅注入差异部分），节省 60-70% Token

---

## 📁 文件说明

| 文件 | 用途 | 更新权限 | Token |
|------|------|---------|-------|
| `FINGERPRINT.md` | 项目指纹（版本、状态） | 用户/AI | ~50 |
| `SYSTEM.md` | 系统约束（技术栈、规则） | 仅用户 | ~300 |
| `CURRENT-TASK.md` | 当前任务（进度、阻塞） | AI 可更新 | ~500 |
| `SESSION-LOG.md` | 会话日志（滚动覆盖） | AI 自动 | ~200 |
| `AI-CONTEXT.md` | 完整项目上下文 | 仅用户 | ~3000 |
| `CONTEXT-ENGINEERING-FOR-AI-TOOLS.md` | 上下文工程指南 | 仅用户 | 参考 |

---

## 🚀 快速使用

### 方法 1: 自动化脚本（推荐）

```powershell
# 生成优化后的提示词
.\scripts\ai-context.ps1 "你的问题"

# 示例
.\scripts\ai-context.ps1 "如何对接AI问答API"
```

脚本会：
1. ✅ 自动读取 `.ai/` 目录文件
2. ✅ 生成优化的提示词
3. ✅ 复制到剪贴板
4. ✅ 显示 Token 估算

### 方法 2: 手动复制

```
1. 读取 .ai/FINGERPRINT.md
2. 读取 .ai/SYSTEM.md
3. 读取 .ai/CURRENT-TASK.md
4. 组合后粘贴到 AI 工具
```

---

## 💡 使用场景

### 场景 1: 新会话启动

```powershell
.\scripts\ai-context.ps1 "继续AI问答前端开发"
```

**效果**:
- Token: ~1500（vs 传统 ~5000）
- 节省: 70%
- AI 立即理解项目状态

### 场景 2: 任务切换

```powershell
.\scripts\ai-context.ps1 "暂停AI问答，开始课表页面开发"
```

**AI 会**:
1. 保存当前任务进度
2. 更新 CURRENT-TASK.md
3. 开始新任务

### 场景 3: 跨平台交接

当从 Qoder 切换到 Codex 时：
1. 新 AI 读取 `.ai/CONTEXT-ENGINEERING-FOR-AI-TOOLS.md`
2. 运行 `.\scripts\ai-context.ps1 "了解项目"`
3. 立即可用，无需重新解释

---

## 📊 Token 优化效果

| 场景 | 传统方式 | 本框架 | 节省 |
|------|---------|--------|------|
| 新会话 | ~5000 tokens | ~1500 tokens | 70% |
| 继续任务 | ~4500 tokens | ~1200 tokens | 73% |
| 问题调试 | ~4000 tokens | ~1400 tokens | 65% |
| 跨平台交接 | ~5500 tokens | ~1600 tokens | 71% |

---

## 🔄 工作流

### 日常开发

```
1. 运行脚本生成提示词
   ↓
2. 粘贴到 AI 工具
   ↓
3. AI 理解上下文，开始工作
   ↓
4. 任务完成，AI 更新 CURRENT-TASK.md
   ↓
5. 更新 SESSION-LOG.md
   ↓
6. 更新 FINGERPRINT.md（如有重大变更）
```

### 任务完成检查清单

- [ ] 更新 `.ai/CURRENT-TASK.md` 进度
- [ ] 运行 `.\scripts\update-session.ps1 "完成的工作摘要"`
- [ ] 更新 `.ai/FINGERPRINT.md`（如有必要）
- [ ] Git 提交变更

---

## ⚠️ 注意事项

1. **SYSTEM.md**: 仅用户可修改，AI 不要自动更改
2. **FINGERPRINT.md**: 项目重大变更时更新
3. **SESSION-LOG.md**: 保留最近 5 次会话，定期清理
4. **跨平台**: 纯文档，任何 AI 工具都能读

---

## 📚 更多文档

- `docs/CONTEXT-ENGINEERING-STRATEGY.md` - 项目上线用的上下文策略
- `.ai/AI-CONTEXT.md` - 项目完整上下文说明
- `AGENTS.md` - 项目协作规范

---

**版本**: v1.0  
**创建日期**: 2026-04-13  
**维护者**: 项目开发团队
