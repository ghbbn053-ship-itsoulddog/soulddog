# GitHub Autopilot（全自动拿来主义）

自动流程：
1. 读取项目需求文档（`PLATFORM_UPGRADE_GUIDE.md`、`.qoder/项目结构.txt`）
2. 自动提取主题（multi-agent / mcp / rag / workflow / evaluation / skill-plugin）
3. 搜索 GitHub 高星且近期活跃仓库
4. 自动评分排序（星数 + 更新时效 + 语言/许可证）
5. 自动克隆 Top N 到 `vendor/autopilot/`
6. 生成可融入路径建议报告

## 运行命令
```bash
python scripts/github_autopilot.py --per-topic 8 --clone-top 4 --integrate-top 8 --update-repo-list
```

仅生成报告，不克隆：
```bash
python scripts/github_autopilot.py --no-clone
```

## 产物
- `docs/github-intake/autopilot-report.md`
- `docs/github-intake/autopilot-report.json`
- `docs/github-intake/repos.txt`（可选自动更新）
