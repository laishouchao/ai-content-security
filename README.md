# AI网站外链域名安全性合规检测系统

🚀 AI网站外链域名安全性合规检测系统

## 📋 项目简介

AI网站外链域名安全性合规检测系统是一个全面的域名合规扫描解决方案，能够：

- 🔍 **智能扫描**: 自动扫描指定域名下的所有页面、子域名和外链域名
- 🤖 **AI分析**: 利用OpenAI GPT-4 Vision对页面内容和截图进行智能分析
- 🏠 **子域名检测**: 对目标域名的子域名主页进行安全性评估
- 🌐 **外链分析**: 识别和分析网站引用的第三方域名安全风险
- ⚡ **实时监控**: WebSocket实时推送扫描进度和结果
- 📊 **可视化报告**: 提供详细的违规检测报告和统计数据
- 🔒 **安全管理**: 完整的用户认证和权限管理系统
- 🎛️ **灵活配置**: 支持自定义扫描参数和AI分析规则

## 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端 (Vue.js)  │    │  后端 (FastAPI) │    │  数据库 (PostgreSQL)│
│                 │    │                 │    │                 │
│ - 用户界面       │◄──►│ - REST API      │◄──►│ - 用户数据       │
│ - 实时通信       │    │ - WebSocket     │    │ - 任务记录       │
│ - 状态管理       │    │ - 任务调度      │    │ - 扫描结果       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │ 异步队列 (Celery)│    │  缓存 (Redis)   │
                    │                 │    │                 │
                    │ - 扫描任务       │◄──►│ - 会话缓存       │
                    │ - AI分析        │    │ - 任务状态       │
                    │ - 定时清理       │    │ - 实时数据       │
                    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   AI服务 (OpenAI)│
                    │                 │
                    │ - GPT-4 Vision  │
                    │ - 内容分析       │
                    │ - 风险评估       │
                    └─────────────────┘
```

## 🛠️ 技术栈

### 后端
- **FastAPI**: 高性能Web框架
- **SQLAlchemy**: ORM数据库操作
- **Alembic**: 数据库迁移工具
- **Celery**: 异步任务队列
- **Redis**: 缓存和消息代理
- **PostgreSQL**: 主数据库
- **Playwright**: 浏览器自动化
- **OpenAI API**: AI内容分析

### 前端
- **Vue.js 3**: 渐进式JavaScript框架
- **TypeScript**: 类型安全的JavaScript
- **Element Plus**: Vue组件库
- **Pinia**: 状态管理
- **Vue Router**: 路由管理
- **Vite**: 构建工具
- **Axios**: HTTP客户端

### 部署
- **Docker**: 容器化部署
- **Docker Compose**: 多容器编排
- **Nginx**: 反向代理和静态文件服务
- **Prometheus**: 监控指标收集
- **Grafana**: 监控仪表盘

## 🚀 快速开始

### 环境要求

- Docker >= 20.10
- Docker Compose >= 2.0
- Python >= 3.11 (本地开发)
- Node.js >= 18 (本地开发)

### 使用Docker部署（推荐）

1. **克隆项目**
```bash
git clone https://github.com/your-org/ai-content-security.git
cd ai-content-security
```

2. **配置环境变量**
```bash
# 复制环境配置文件
cp .env.example .env

# 编辑配置文件，填入必要的配置
nano .env
```

**重要配置项：**

```env
# 数据库配置（需要修改为实际值）
DATABASE_URL="postgresql+asyncpg://postgres:yourpassword@115.190.95.157:5432/mydb"
REDIS_URL="redis://:yourredispassword@115.190.95.157:6379/0"

# Celery配置
CELERY_BROKER_URL="redis://:yourredispassword@115.190.95.157:6379/0"
CELERY_RESULT_BACKEND="redis://:yourredispassword@115.190.95.157:6379/0"

# AI配置（用户可在系统中配置）
DEFAULT_AI_MODEL="gpt-4-vision-preview"

# 安全配置
SECRET_KEY="your-super-secret-key-change-this-in-production"
```

3. **启动服务**
```bash
# 给部署脚本执行权限
chmod +x deploy.sh

# 启动开发环境
./deploy.sh dev start

# 或启动生产环境
./deploy.sh production start
```

4. **访问系统**
- 前端界面: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs
- 监控面板: http://localhost:3001 (Grafana)

### 本地开发部署

#### 后端开发

1. **安装依赖**
```bash
cd ai-content-security
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **配置数据库**
```bash
# 启动PostgreSQL和Redis
docker-compose up -d postgres redis

# 运行数据库迁移
alembic upgrade head
```

3. **启动后端服务**

**Linux/macOS:**
```bash
# 启动API服务
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 启动Celery Worker（新终端）
celery -A celery_app worker --loglevel=info

# 启动Celery Beat（新终端）
celery -A celery_app beat --loglevel=info
```

**Windows PowerShell:**
```powershell
# 启动API服务
cd "e:\01_Github\ai-content-security"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 启动Celery Worker（新PowerShell窗口）
cd "e:\01_Github\ai-content-security"
celery -A celery_app worker --loglevel=info

# 启动Celery Beat（新PowerShell窗口）
cd "e:\01_Github\ai-content-security"
celery -A celery_app beat --loglevel=info
```

**注意：** 
- Windows版本已自动配置为使用`solo`池模式以避免进程spawn问题
- 如果遇到模块导入问题，确保在项目根目录下运行命令
- Celery Worker在Windows上使用单线程模式，适合开发和测试

#### 前端开发

1. **安装依赖**
```bash
cd frontend
npm install
```

2. **启动开发服务器**
```bash
npm run dev
```

3. **访问应用**
- 前端: http://localhost:5173
- 后端: http://localhost:8000

## 📖 使用指南

### 1. 用户注册和登录

1. 访问系统首页
2. 点击"注册"创建账户
3. 使用邮箱和密码登录系统

### 2. 创建扫描任务

1. 登录后进入"任务管理"页面
2. 点击"创建任务"
3. 填写目标域名和扫描配置
4. 提交任务开始扫描

### 3. 监控扫描进度

1. 在任务列表中查看任务状态
2. 点击任务可查看详细进度
3. 系统会实时推送扫描进度

### 4. 查看扫描结果

1. 扫描完成后查看任务详情
2. 下载扫描报告
3. 查看违规内容详细分析

### 5. 系统配置

管理员可以在"系统设置"中配置：

- **AI配置**: OpenAI API密钥和模型参数
- **扫描配置**: 扫描深度、延迟等参数
- **通知配置**: 邮件和Webhook通知设置
- **安全配置**: 密码策略、登录限制等

## 🧪 测试

### 运行API测试
```bash
# 启动系统后运行API测试
python tests/test_api.py
```

### 运行单元测试
```bash
# 安装测试依赖
pip install pytest pytest-asyncio

# 运行单元测试
pytest tests/test_task_api.py -v
```

### 运行性能测试
```bash
# 测试系统性能
python tests/test_performance.py
```

### 运行集成测试
```bash
# 完整的端到端测试
python tests/test_integration.py
```

## 📊 监控和日志

### 系统监控

- **Prometheus**: 收集应用指标 (http://localhost:9090)
- **Grafana**: 可视化监控面板 (http://localhost:3001)
- **健康检查**: API健康状态检查 (http://localhost:8000/health)

### 日志管理

- **应用日志**: 存储在 `logs/` 目录
- **访问日志**: Nginx访问和错误日志
- **任务日志**: Celery任务执行日志

## 🔧 运维指南

### 常用运维命令

```bash
# 查看服务状态
./deploy.sh production status

# 查看服务日志
./deploy.sh production logs

# 更新服务
./deploy.sh production update

# 重启服务
./deploy.sh production restart

# 停止服务
./deploy.sh production stop

# 清理资源
./deploy.sh production cleanup
```

### 数据备份

```bash
# 备份数据库
docker-compose exec postgres pg_dump -U postgres ai_content_security > backup.sql

# 恢复数据库
docker-compose exec -T postgres psql -U postgres ai_content_security < backup.sql
```

### 性能优化

1. **数据库优化**
   - 定期清理过期数据
   - 优化查询索引
   - 监控数据库性能

2. **缓存优化**
   - 配置Redis内存限制
   - 设置合适的缓存过期时间
   - 监控缓存命中率

3. **应用优化**
   - 调整Celery worker数量
   - 优化AI API调用频率
   - 配置负载均衡

## 🔒 安全指南

### 生产环境安全

1. **更改默认密码**
   - 数据库密码
   - Redis密码
   - 管理员账户密码

2. **配置HTTPS**
   - 使用SSL/TLS证书
   - 配置Nginx HTTPS
   - 强制HTTPS重定向

3. **网络安全**
   - 配置防火墙规则
   - 限制数据库访问
   - 使用VPN或私有网络

4. **定期更新**
   - 更新Docker镜像
   - 更新系统依赖
   - 应用安全补丁

## 🐛 故障排除

### 常见问题

1. **服务启动失败**
   ```bash
   # 检查Docker服务状态
   docker-compose ps
   
   # 查看错误日志
   docker-compose logs [service-name]
   ```

2. **Pydantic警告信息**
   如果看到关于"model_"命名空间冲突的警告，这些已经被修复：
   - 字段名已从 `model_name` 更改为 `ai_model_name`
   - 字段名已从 `model_used` 更改为 `ai_model_used`

3. **数据库连接问题**
   ```bash
   # 检查数据库连接
   docker-compose exec postgres pg_isready
   
   # 检查Redis连接
   docker-compose exec redis redis-cli ping
   ```

4. **登录后又被重定向回登录页面**
   如果登录成功后立即被重定向回登录页面，并在控制台看到以下错误：
   ```
   认证失败: 令牌验证失败: Not enough segments
   ```
   
   这通常是由于本地存储中的认证令牌损坏导致的。请按以下步骤解决：
   
   a. **清理浏览器本地存储**：
      1. 打开浏览器开发者工具 (F12)
      2. 切换到 Console (控制台) 标签
      3. 运行以下命令：
         ```javascript
         localStorage.removeItem('access_token');
         localStorage.removeItem('refresh_token');
         console.log('已清理本地存储中的认证令牌');
         ```
      4. 刷新页面后重新登录
   
   b. **或者使用我们提供的脚本**：
      1. 在项目 frontend 目录下找到 `clear-storage.js` 文件
      2. 将其内容复制到浏览器控制台中运行
      3. 刷新页面后重新登录

5. **数据库连接失败**
   ```bash
   # 检查数据库状态
   docker-compose exec postgres pg_isready -U postgres
   
   # 重启数据库服务
   docker-compose restart postgres
   ```

6. **前端页面加载失败**
   ```bash
   # 检查Nginx配置
   docker-compose exec frontend nginx -t
   
   # 重新构建前端镜像
   docker-compose build frontend
   ```

7. **AI分析失败**
   - 检查OpenAI API密钥配置
   - 验证网络连接
   - 检查API配额和限制

### 日志文件位置

- 应用日志: `logs/app.log`
- 错误日志: `logs/error.log`
- 任务日志: `logs/celery.log`
- Nginx日志: `logs/nginx/`

## 📚 API文档

系统启动后可以访问以下API文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 主要API端点

- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/auth/register` - 用户注册
- `GET /api/v1/auth/me` - 获取当前用户信息
- `POST /api/v1/tasks` - 创建扫描任务
- `GET /api/v1/tasks` - 获取任务列表
- `GET /api/v1/tasks/{task_id}` - 获取任务详情
- `POST /api/v1/tasks/{task_id}/cancel` - 取消任务
- `GET /api/v1/config/*` - 系统配置接口

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 开发规范

- 遵循PEP 8代码风格
- 编写单元测试
- 更新API文档
- 添加必要的注释

## 📄 许可证

本项目基于 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 支持和反馈

- **问题报告**: [GitHub Issues](https://github.com/your-org/ai-content-security/issues)
- **功能请求**: [GitHub Discussions](https://github.com/your-org/ai-content-security/discussions)
- **邮件联系**: support@your-domain.com

## 🙏 致谢

感谢以下开源项目：

- [FastAPI](https://fastapi.tiangolo.com/)
- [Vue.js](https://vuejs.org/)
- [Element Plus](https://element-plus.org/)
- [Playwright](https://playwright.dev/)
- [OpenAI](https://openai.com/)

---

**AI内容安全监控系统** - 让网络环境更安全 🛡️