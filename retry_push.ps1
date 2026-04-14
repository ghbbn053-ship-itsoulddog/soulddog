# Git持续推送直到成功脚本
$retryCount = 0
$success = $false

Write-Host "🚀 开始持续推送，直到成功..." -ForegroundColor Cyan
Write-Host "按 Ctrl+C 可随时中断" -ForegroundColor Yellow

while (-not $success) {
    $retryCount++
    Write-Host "`n[$retryCount] 尝试推送..." -ForegroundColor Yellow
    
    $output = git push origin main 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ 推送成功！总共尝试 $retryCount 次" -ForegroundColor Green
        $success = $true
    } else {
        # 提取错误信息
        $errorMsg = $output | Select-Object -Last 1
        Write-Host "❌ 失败: $errorMsg" -ForegroundColor Red
        
        # 指数退避：2, 4, 8, 16, 30, 30, 30... 秒
        if ($retryCount -le 4) {
            $waitTime = [Math]::Pow(2, $retryCount)
        } else {
            $waitTime = 30
        }
        
        Write-Host "⏳ 等待 ${waitTime}秒后重试..." -ForegroundColor Cyan
        Start-Sleep -Seconds $waitTime
    }
}

Write-Host "`n🎉 任务完成！代码已成功推送到远程仓库" -ForegroundColor Green
