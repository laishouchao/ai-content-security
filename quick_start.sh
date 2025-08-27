#!/bin/bash

# AI内容安全监控系统 - 快速启动脚本

echo "🎯 AI内容安全监控系统 - 快速启动"
echo "=================================="

# 检查是否在正确的目录
if [ ! -f "main.py" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "❌ 错误: 未找到Python环境"
    exit 1
fi

echo "📋 启动选项:"
echo "1. 仅启动后端服务 (推荐先启动)"
echo "2. 仅启动前端服务"
echo "3. 同时启动前后端 (实验性)"
echo "4. 检查服务状态"
echo "5. 退出"

read -p "请选择 (1-5): " choice

case $choice in
    1)
        echo "🚀 启动后端 FastAPI 服务..."
        echo "💡 服务将在 http://localhost:8000 启动"
        echo "💡 API文档: http://localhost:8000/docs"
        echo "💡 按 Ctrl+C 停止服务"
        echo ""
        python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
        ;;
    2)
        echo "🚀 启动前端 Vite 开发服务器..."
        echo "💡 请确保后端服务已启动在 http://localhost:8000"
        echo "💡 前端将在 http://localhost:5173 启动"
        echo ""
        cd frontend
        npm run dev
        ;;
    3)
        echo "🚀 同时启动前后端服务..."
        echo "💡 后端: http://localhost:8000"
        echo "💡 前端: http://localhost:5173"
        echo ""
        
        # 启动后端 (后台)
        echo "启动后端服务..."
        python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
        BACKEND_PID=$!
        
        # 等待后端启动
        echo "等待后端服务启动..."
        sleep 5
        
        # 检查后端是否启动成功
        if curl -s http://localhost:8000/health > /dev/null; then
            echo "✅ 后端服务启动成功"
        else
            echo "❌ 后端服务启动失败"
            kill $BACKEND_PID
            exit 1
        fi
        
        # 启动前端
        echo "启动前端服务..."
        cd frontend
        npm run dev
        
        # 清理后台进程
        trap "kill $BACKEND_PID" EXIT
        ;;
    4)
        echo "🔍 检查服务状态..."
        echo ""
        
        # 检查后端
        if curl -s http://localhost:8000/health > /dev/null; then
            echo "✅ 后端服务: 运行中 (http://localhost:8000)"
        else
            echo "❌ 后端服务: 未运行"
        fi
        
        # 检查前端 (简单检查端口)
        if lsof -i :5173 > /dev/null 2>&1; then
            echo "✅ 前端服务: 运行中 (http://localhost:5173)"
        else
            echo "❌ 前端服务: 未运行"
        fi
        
        echo ""
        echo "💡 如果服务未运行，请选择选项 1 或 2 启动"
        ;;
    5)
        echo "退出脚本"
        exit 0
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac