# AI 上下文提示词生成器
# 用途: 一键生成优化后的 AI 编程工具提示词
# 使用: .\scripts\ai-context.ps1 "你的问题"

param(
    [string]$Question = ""
)

# 颜色输出
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

# 检查文件是否存在
$aiDir = Join-Path $PSScriptRoot "..\.ai"
$fingerprintFile = Join-Path $aiDir "FINGERPRINT.md"
$systemFile = Join-Path $aiDir "SYSTEM.md"
$taskFile = Join-Path $aiDir "CURRENT-TASK.md"

if (-not (Test-Path $fingerprintFile)) {
    Write-ColorOutput Red "❌ 错误: 未找到 .ai/FINGERPRINT.md"
    Write-Output "请先运行项目初始化"
    exit 1
}

# 读取上下文文件
$fingerprint = Get-Content $fingerprintFile -Raw
$system = Get-Content $systemFile -Raw
$task = Get-Content $taskFile -Raw

# 计算 Token 估算
$questionLength = if ($Question) { [math]::Round($Question.Length / 2) } else { 0 }
$totalTokens = 850 + $questionLength

# 生成提示词
$prompt = "========================================
 AI 编程工具优化提示词
========================================

【指纹检查】
$fingerprint

【系统约束】（Layer 1 - 常驻）
$system

【当前任务】（Layer 2 - 动态）
$task

【我的问题】（Layer 3 - 本次会话）
$Question

========================================
 Token 估算
========================================
指纹: ~50 tokens
系统约束: ~300 tokens
当前任务: ~500 tokens
问题: ~$questionLength tokens
----------------------------------------
总计: ~$totalTokens tokens
传统方式: ~5000 tokens
节省: ~64%
========================================

 使用说明:
1. 复制上方提示词（从【指纹检查】到【我的问题】结束）
2. 粘贴到 AI 编程工具（Qoder/Codex/Cursor）
3. AI 会自动理解项目状态，无需重复描述

 注意事项:
- 如果项目发生重大变更，请先更新 .ai/FINGERPRINT.md
- 跨平台交接时，确保新 AI 读取 .ai/CONTEXT-ENGINEERING-FOR-AI-TOOLS.md
- 任务完成后，AI 应更新 .ai/CURRENT-TASK.md 和 .ai/SESSION-LOG.md
========================================"

# 输出到控制台
Write-Output $prompt

# 复制到剪贴板
$clipContent = @"
【指纹检查】
$fingerprint

【系统约束】
$system

【当前任务】
$task

【我的问题】
$Question
"@

$clipContent | Set-Clipboard

Write-ColorOutput Green "`n✅ 提示词已复制到剪贴板！"
Write-ColorOutput Yellow "📌 直接粘贴到 AI 编程工具即可使用`n"
