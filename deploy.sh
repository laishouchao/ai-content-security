#!/bin/bash

# AI内容安全监控系统部署脚本
# 使用方法: ./deploy.sh [环境] [操作]
# 环境: dev, staging, production
# 操作: start, stop, restart, update, logs, status

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
PROJECT_NAME="ai-content-security"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

# 函数：打印带颜色的消息
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}[$(date +'%Y-%m-%d %H:%M:%S')] ${message}${NC}"
}

print_info() {
    print_message $BLUE "$1"
}

print_success() {
    print_message $GREEN "$1"
}

print_warning() {
    print_message $YELLOW "$1"
}

print_error() {
    print_message $RED "$1"
}

# 函数：检查环境
check_environment() {
    print_info "检查部署环境..."
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker未安装，请先安装Docker"
        exit 1
    fi
    
    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose未安装，请先安装Docker Compose"
        exit 1
    fi
    
    # 检查必要文件
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_error "找不到 $COMPOSE_FILE 文件"
        exit 1
    fi
    
    print_success "环境检查通过"
}

# 函数：创建环境文件
create_env_file() {
    local env=$1
    
    print_info "创建环境配置文件..."
    
    if [ ! -f "$ENV_FILE" ]; then
        cat > $ENV_FILE << EOF
# 环境配置
ENVIRONMENT=${env}

# 数据库配置
POSTGRES_DB=ai_content_security
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# Redis配置
REDIS_PASSWORD=redis123

# JWT配置
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_EXPIRATION=3600

# API配置
API_V1_STR=/api/v1
PROJECT_NAME="AI Content Security"

# 日志配置
LOG_LEVEL=INFO

# OpenAI配置（需要手动填入）
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_API_BASE=https://api.openai.com/v1

# 邮件配置（可选）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-email-password

# 域名配置（生产环境）
DOMAIN=your-domain.com
EMAIL=admin@your-domain.com
EOF
        print_warning "已创建 $ENV_FILE 文件，请根据实际情况修改配置"
    else
        print_info "环境文件已存在，跳过创建"
    fi
}

# 函数：构建镜像
build_images() {
    print_info "构建Docker镜像..."
    
    # 构建后端镜像
    docker build -t ${PROJECT_NAME}-backend .
    
    # 构建前端镜像
    docker build -t ${PROJECT_NAME}-frontend ./frontend
    
    print_success "镜像构建完成"
}

# 函数：启动服务
start_services() {
    local env=$1
    
    print_info "启动 $env 环境服务..."
    
    # 设置环境变量
    export ENVIRONMENT=$env
    
    # 启动核心服务
    docker-compose up -d postgres redis
    
    # 等待数据库启动
    print_info "等待数据库启动..."
    sleep 10
    
    # 运行数据库迁移
    print_info "运行数据库迁移..."
    docker-compose run --rm backend alembic upgrade head
    
    # 启动所有服务
    docker-compose up -d
    
    print_success "$env 环境服务启动完成"
}

# 函数：停止服务
stop_services() {
    print_info "停止服务..."
    docker-compose down
    print_success "服务已停止"
}

# 函数：重启服务
restart_services() {
    local env=$1
    print_info "重启服务..."
    stop_services
    sleep 5
    start_services $env
}

# 函数：更新服务
update_services() {
    local env=$1
    
    print_info "更新 $env 环境服务..."
    
    # 拉取最新代码（如果是从Git部署）
    if [ -d ".git" ]; then
        print_info "拉取最新代码..."
        git pull origin main
    fi
    
    # 重新构建镜像
    build_images
    
    # 重启服务
    restart_services $env
    
    print_success "服务更新完成"
}

# 函数：查看日志
view_logs() {
    local service=$1
    
    if [ -z "$service" ]; then
        print_info "查看所有服务日志..."
        docker-compose logs -f
    else
        print_info "查看 $service 服务日志..."
        docker-compose logs -f $service
    fi
}

# 函数：查看状态
check_status() {
    print_info "检查服务状态..."
    
    echo ""
    print_info "=== Docker Compose 服务状态 ==="
    docker-compose ps
    
    echo ""
    print_info "=== 系统健康检查 ==="
    
    # 检查后端API
    if curl -f http://localhost:8000/health &> /dev/null; then
        print_success "✓ 后端API服务正常"
    else
        print_error "✗ 后端API服务异常"
    fi
    
    # 检查前端服务
    if curl -f http://localhost:3000 &> /dev/null; then
        print_success "✓ 前端服务正常"
    else
        print_error "✗ 前端服务异常"
    fi
    
    # 检查数据库连接
    if docker-compose exec postgres pg_isready -U postgres &> /dev/null; then
        print_success "✓ 数据库连接正常"
    else
        print_error "✗ 数据库连接异常"
    fi
    
    # 检查Redis连接
    if docker-compose exec redis redis-cli ping &> /dev/null; then
        print_success "✓ Redis连接正常"
    else
        print_error "✗ Redis连接异常"
    fi
}

# 函数：清理资源
cleanup() {
    print_warning "清理Docker资源..."
    
    read -p "确定要清理所有相关Docker资源吗? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 停止并删除容器
        docker-compose down -v --remove-orphans
        
        # 删除相关镜像
        docker images | grep $PROJECT_NAME | awk '{print $3}' | xargs -r docker rmi
        
        # 清理未使用的资源
        docker system prune -f
        
        print_success "清理完成"
    else
        print_info "取消清理"
    fi
}

# 函数：安装依赖
install_dependencies() {
    print_info "安装系统依赖..."
    
    # 更新包管理器
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y curl wget git openssl
    elif command -v yum &> /dev/null; then
        sudo yum update -y
        sudo yum install -y curl wget git openssl
    elif command -v brew &> /dev/null; then
        brew update
        brew install curl wget git openssl
    fi
    
    print_success "依赖安装完成"
}

# 函数：显示帮助信息
show_help() {
    echo "AI内容安全监控系统部署脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 [环境] [操作] [参数]"
    echo ""
    echo "环境:"
    echo "  dev         开发环境"
    echo "  staging     测试环境" 
    echo "  production  生产环境"
    echo ""
    echo "操作:"
    echo "  start       启动服务"
    echo "  stop        停止服务"
    echo "  restart     重启服务"
    echo "  update      更新服务"
    echo "  logs        查看日志 [服务名]"
    echo "  status      查看状态"
    echo "  build       构建镜像"
    echo "  cleanup     清理资源"
    echo "  install     安装依赖"
    echo "  help        显示帮助"
    echo ""
    echo "示例:"
    echo "  $0 dev start              # 启动开发环境"
    echo "  $0 production update      # 更新生产环境"
    echo "  $0 staging logs backend   # 查看测试环境后端日志"
    echo "  $0 production status      # 查看生产环境状态"
}

# 主函数
main() {
    local env=${1:-dev}
    local action=${2:-help}
    local param=${3:-}
    
    # 检查参数
    if [ "$action" = "help" ] || [ -z "$env" ]; then
        show_help
        exit 0
    fi
    
    # 检查环境
    check_environment
    
    # 创建环境文件
    create_env_file $env
    
    # 执行操作
    case $action in
        "start")
            start_services $env
            check_status
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            restart_services $env
            ;;
        "update")
            update_services $env
            ;;
        "logs")
            view_logs $param
            ;;
        "status")
            check_status
            ;;
        "build")
            build_images
            ;;
        "cleanup")
            cleanup
            ;;
        "install")
            install_dependencies
            ;;
        *)
            print_error "未知操作: $action"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"