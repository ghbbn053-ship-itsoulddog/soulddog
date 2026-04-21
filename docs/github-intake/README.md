# GitHub Intake（拿来主义工作流）

用途：批量拉取开源仓库，自动生成可融入项目的评估报告。

## 1. 配置仓库列表
- 编辑 `docs/github-intake/repos.txt`
- 每行一个 `owner/repo`

## 2. 执行分析（含克隆）
```powershell
pwsh ./scripts/github-intake.ps1
```

## 3. 仅分析元信息（不克隆）
```powershell
pwsh ./scripts/github-intake.ps1 -Clone:$false
```

## 4. 输出结果
- `docs/github-intake/analysis.json`
- `docs/github-intake/analysis.md`
- 仓库目录：`vendor/<owner__repo>/`
