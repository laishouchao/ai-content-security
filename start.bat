@echo off
chcp 65001 >nul 2>&1
title AI内容安全监控系统 - 一键启动

echo 🎯 AI内容安全监控系统 - 一键启动所有服务
echo ==================================================

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

echo 🚀 正在启动所有服务...
echo 📋 启动顺序: 后端服务 → Celery Worker → 前端服务
echo 💡 完成后访问: http://localhost:5173
echo 💡 按 Ctrl+C 停止所有服务
echo.

python start_all_services.py

echo.
echo 👋 所有服务已停止
pause