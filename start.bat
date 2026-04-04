@echo off
chcp 65001 > nul
title 教务系统 AI 助手

echo ========================================
echo    教务系统 AI 助手 - Windows 启动脚本
echo ========================================
echo.

REM 检查 Anaconda 环境
where conda >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [错误] 未找到 Anaconda！请先安装 Anaconda。
    pause
    exit /b 1
)

echo [1/4] 检查 Python 虚拟环境...
conda env list | findstr "edu-assistant" >nul
if %ERRORLEVEL% neq 0 (
    echo [警告] 虚拟环境 edu-assistant 不存在！
    echo 请先创建虚拟环境：
    echo   conda create -n edu-assistant python=3.10
    pause
    exit /b 1
)

echo [2/4] 启动后端服务...
start "后端服务 - FastAPI" cmd /k "title 后端服务 - FastAPI && conda activate edu-assistant && cd backend && python main.py"

echo [3/4] 等待后端服务启动...
timeout /t 5 /nobreak >nul

echo [4/4] 启动前端服务...
start "前端服务 - Next.js" cmd /k "title 前端服务 - Next.js && conda activate edu-assistant && npm run dev"

echo.
echo ========================================
echo           启动完成！
echo ========================================
echo   前端地址: http://localhost:5000
echo   后端地址: http://localhost:8000
echo   API 文档: http://localhost:8000/docs
echo ========================================
echo.
echo 提示：
echo   - 请确保已连接校园网或 VPN（访问教务系统）
echo   - 关闭服务: 直接关闭对应的终端窗口
echo.
pause
