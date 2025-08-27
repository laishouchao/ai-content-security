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
echo 1. 仅启动后端服务 (推荐先启动)
echo 2. 仅启动前端服务
echo 3. 同时启动前后端 (推荐)
echo 4. 启动稳定版Celery Worker (修复连接问题)
echo 5. 检查服务状态
echo 6. 退出
echo.

set /p choice=请选择 (1-6): 

if "%choice%"=="1" (
    echo 🚀 启动后端 FastAPI 服务...
    echo 💡 服务将在 http://localhost:8000 启动
    echo 💡 API文档: http://localhost:8000/docs
    echo 💡 按 Ctrl+C 停止服务
    echo.
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
) else if "%choice%"=="2" (
    echo 🚀 启动前端 Vite 开发服务器...
    echo 💡 请确保后端服务已启动在 http://localhost:8000
    echo 💡 前端将在 http://localhost:5173 启动
    echo.
    cd frontend
    npm run dev
) else if "%choice%"=="3" (
    echo 🚀 同时启动前后端服务...
    echo 💡 后端: http://localhost:8000
    echo 💡 前端: http://localhost:5173
    echo.
    
    REM 启动后端 (新窗口)
    echo 启动后端服务...
    start "后端服务 - FastAPI" cmd /k "python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
    
    REM 等待后端启动
    echo 等待后端服务启动...
    timeout /t 8 /nobreak >nul
    
    REM 检查后端是否启动成功
    curl -s http://localhost:8000/health >nul 2>&1
    if errorlevel 1 (
        echo ⚠️ 后端服务可能仍在启动中，继续启动前端...
    ) else (
        echo ✅ 后端服务启动成功
    )
    
    REM 启动前端
    echo 启动前端服务...
    cd frontend
    start "前端服务 - Vite" cmd /k "npm run dev"
    
    echo.
    echo ==========================================
    echo ✅ 服务启动完成！
    echo.
    echo 🌐 访问地址:
    echo   - 前端界面: http://localhost:5173
    echo   - 后端API: http://localhost:8000
    echo   - API文档: http://localhost:8000/docs
    echo.
    echo 💡 提示:
    echo   - 两个服务在独立窗口中运行
    echo   - 关闭对应窗口即可停止服务
    echo   - 如果前端出现代理错误，请等待后端完全启动
    echo ==========================================
    
) else if "%choice%"=="4" (
    echo 🚀 启动稳定版Celery Worker...
    echo 📝 该脚本包含完整的错误处理和自动恢复机制
    echo 📁 日志文件: celery_stable.log
    echo 📊 按 Ctrl+C 停止服务
    echo.
    python start_celery_stable.py
    
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