# 会话日志更新脚本
# 用途: 追加会话摘要到 SESSION-LOG.md
# 使用: .\scripts\update-session.ps1 "完成的工作摘要"

param(
    [Parameter(Mandatory=$true)]
    [string]$Summary
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

# 检查文件
$sessionLog = Join-Path $PSScriptRoot "..\.ai\SESSION-LOG.md"

if (-not (Test-Path $sessionLog)) {
    Write-ColorOutput Red "❌ 错误: 未找到 .ai/SESSION-LOG.md"
    exit 1
}

# 获取当前日期和会话编号
$date = Get-Date -Format "yyyy-MM-dd"
$content = Get-Content $sessionLog -Raw
$sessionCount = ([regex]::Matches($content, "## Session")).Count + 1
$sessionNum = "$date #$sessionCount"

# 生成新条目
$entry = @"

---

## Session $sessionNum

$Summary
"@

# 追加到文件
Add-Content $sessionLog $entry

Write-ColorOutput Green "✅ 会话日志已更新"
Write-Output "📝 会话编号: $sessionNum"
Write-Output "📄 文件: .ai/SESSION-LOG.md`n"

# 检查是否需要清理（保留最近5次会话）
$content = Get-Content $sessionLog -Raw
$sessions = [regex]::Matches($content, "## Session")
if ($sessions.Count -gt 5) {
    Write-ColorOutput Yellow "⚠️  会话数超过5次，建议清理旧会话"
    Write-Output "手动编辑 .ai/SESSION-LOG.md 删除最早的会话`n"
}
