@echo off
chcp 65001 >nul 2>&1
echo ==========================================
echo AI内容安全检测系统 - 服务启动脚本
echo ==========================================
echo.

echo 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python环境，请确保Python已安装并添加到PATH
    pause
    exit /b 1
)

echo 检查依赖包...
pip show uvicorn >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到必要依赖，请运行 'pip install -r requirements.txt'
    pause
    exit /b 1
)

echo.
echo 选择启动模式:
echo 1. 启动FastAPI服务 (端口8000)
echo 2. 启动Celery Worker (异步任务处理)
echo 3. 启动Celery Beat (定时任务调度)
echo 4. 启动所有服务 (推荐)
echo 5. 退出
echo.

set /p choice=请输入选择 (1-5): 

if "%choice%"=="1" (
    echo 启动FastAPI服务...
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
) else if "%choice%"=="2" (
    echo 启动Celery Worker...
    celery -A celery_app worker --loglevel=info
) else if "%choice%"=="3" (
    echo 启动Celery Beat...
    celery -A celery_app beat --loglevel=info
) else if "%choice%"=="4" (
    echo 启动所有服务...
    echo.
    echo 将在新窗口中启动各个服务...
    
    REM 启动FastAPI服务
    start "FastAPI服务" cmd /k "python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
    
    REM 等待2秒让FastAPI启动
    timeout /t 2 /nobreak >nul
    
    REM 启动Celery Worker
    start "Celery Worker" cmd /k "celery -A celery_app worker --loglevel=info"
    
    REM 启动Celery Beat
    start "Celery Beat" cmd /k "celery -A celery_app beat --loglevel=info"
    
    echo.
    echo ==========================================
    echo 所有服务已启动！
    echo.
    echo 服务访问地址:
    echo - FastAPI服务: http://localhost:8000
    echo - API文档: http://localhost:8000/docs
    echo - 前端界面: 请在frontend目录运行 'npm run dev'
    echo.
    echo 各服务在独立窗口中运行，关闭窗口即可停止对应服务
    echo ==========================================
    pause
) else if "%choice%"=="5" (
    echo 退出脚本
) else (
    echo 无效选择
    pause
)