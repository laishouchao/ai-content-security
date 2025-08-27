@echo off
chcp 65001 >nul 2>&1
title AI内容安全监控系统 - 快速启动

echo 🎯 AI内容安全监控系统 - 快速启动
echo ==================================

REM 检查是否在正确的目录
if not exist "main.py" (
    echo ❌ 错误: 请在项目根目录运行此脚本
    pause
    exit /b 1
)

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到Python环境
    pause
    exit /b 1
)

echo.
echo 📋 启动选项:
echo 1. 统一启动所有服务 (推荐) - 后端+前端+Celery
echo 2. 仅启动后端服务
echo 3. 仅启动前端服务
echo 4. 仅启动Celery Worker
echo 5. 检查服务状态
echo 6. 退出
echo.

set /p choice=请选择 (1-6): 

if "%choice%"=="1" (
    echo 🚀 统一启动所有服务...
    echo 💡 将按顺序启动: 后端 → Celery → 前端
    echo 💡 访问地址: http://localhost:5173 (前端) http://localhost:8000 (后端)
    echo 💡 按 Ctrl+C 停止所有服务
    echo.
    python start_all_services.py
) else if "%choice%"=="2" (
    echo 🚀 启动后端 FastAPI 服务...
    echo 💡 服务将在 http://localhost:8000 启动
    echo 💡 API文档: http://localhost:8000/docs
    echo 💡 按 Ctrl+C 停止服务
    echo.
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
) else if "%choice%"=="3" (
    echo 🚀 启动前端 Vite 开发服务器...
    echo 💡 请确保后端服务已启动在 http://localhost:8000
    echo 💡 前端将在 http://localhost:5173 启动
    echo.
    cd frontend
    npm run dev
) else if "%choice%"=="4" (
    echo 🚀 启动Celery Worker...
    echo 💡 使用优化配置，自动连接检测和数据清理
    echo 💡 按 Ctrl+C 停止服务
    echo.
    celery -A celery_app worker --loglevel=info
) else if "%choice%"=="5" (
    echo 🔍 检查服务状态...
    echo.
    
    REM 检查后端
    curl -s http://localhost:8000/health >nul 2>&1
    if errorlevel 1 (
        echo ❌ 后端服务: 未运行
    ) else (
        echo ✅ 后端服务: 运行中 (http://localhost:8000)
    )
    
    REM 检查前端端口 (简单检查)
    netstat -an | find ":5173" >nul 2>&1
    if errorlevel 1 (
        echo ❌ 前端服务: 未运行
    ) else (
        echo ✅ 前端服务: 运行中 (http://localhost:5173)
    )
    
    REM 检查Celery Worker
    tasklist | findstr python >nul 2>&1
    if errorlevel 1 (
        echo ❌ Celery Worker: 未运行
    ) else (
        echo ✅ Celery Worker: 可能运行中 (请检查python进程)
    )
    
    echo.
    echo 💡 如果服务未运行，请选择相应选项启动
    pause
    
) else if "%choice%"=="6" (
    echo 退出脚本
    exit /b 0
) else (
    echo ❌ 无效选择
    pause
    exit /b 1
)