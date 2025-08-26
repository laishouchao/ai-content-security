# 域名合规扫描系统开发实施计划

## 项目概述

本项目将开发一个基于 Vue.js + FastAPI 的域名合规扫描系统，实现自动化的第三方域名内容安全检测。

## 开发阶段规划

### 第一阶段：基础架构搭建 (1-2周)

#### 1.1 后端FastAPI项目初始化
**目标**: 搭建基础的FastAPI项目框架
**任务列表**:
- [ ] 创建FastAPI项目结构
- [ ] 配置项目依赖和虚拟环境
- [ ] 设置开发环境配置
- [ ] 集成SQLAlchemy ORM
- [ ] 配置Redis连接
- [ ] 设置Celery任务队列
- [ ] 创建基础API路由结构

**关键文件**:
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI应用入口
│   ├── config.py            # 配置管理
│   ├── database.py          # 数据库连接
│   ├── dependencies.py      # 依赖注入
│   └── core/
│       ├── __init__.py
│       ├── security.py      # 安全相关
│       ├── config.py        # 核心配置
│       └── celery.py        # Celery配置
├── requirements.txt
├── .env.example
└── alembic.ini
```

#### 1.2 数据库模型设计
**目标**: 设计完整的数据库模型和迁移系统
**任务列表**:
- [ ] 设计用户认证相关表
- [ ] 设计扫描任务相关表
- [ ] 设计AI配置和系统配置表
- [ ] 设计权限和角色表
- [ ] 创建数据库迁移脚本
- [ ] 设置数据库索引优化

**数据模型**:
```python
# models/user.py
class User(Base):
    id = Column(String, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# models/scan_task.py
class ScanTask(Base):
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    target_domain = Column(String(255), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    progress = Column(Integer, default=0)
    config = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### 1.3 用户认证和权限系统
**目标**: 实现完整的用户认证和权限控制
**任务列表**:
- [ ] 实现JWT Token认证
- [ ] 创建用户注册和登录API
- [ ] 实现基于角色的权限控制(RBAC)
- [ ] 设计用户数据隔离机制
- [ ] 创建权限装饰器和中间件
- [ ] 实现用户个人资料管理

**API接口**:
```python
# api/v1/auth.py
@router.post("/auth/login")
async def login(credentials: LoginRequest) -> LoginResponse

@router.post("/auth/register") 
async def register(user_data: RegisterRequest) -> UserResponse

@router.get("/auth/me")
async def get_current_user() -> UserResponse

@router.post("/auth/logout")
async def logout() -> dict
```

### 第二阶段：核心扫描引擎开发 (2-3周)

#### 2.1 子域名发现引擎
**目标**: 实现多种方法的子域名发现
**任务列表**:
- [ ] DNS查询方法实现
- [ ] 证书透明日志查询
- [ ] 子域名字典爆破
- [ ] 并发控制和去重逻辑
- [ ] 结果验证和筛选
- [ ] 性能优化和错误处理

```python
# engines/subdomain_discovery.py
class SubdomainDiscoveryEngine:
    async def discover_dns(self, domain: str) -> List[str]
    async def discover_certificate_transparency(self, domain: str) -> List[str]
    async def discover_bruteforce(self, domain: str) -> List[str]
    async def discover_all(self, domain: str) -> List[SubdomainResult]
```

#### 2.2 链接爬取引擎
**目标**: 实现智能的网页链接爬取
**任务列表**:
- [ ] 网页内容解析和链接提取
- [ ] 递归爬取深度控制
- [ ] robots.txt遵循机制
- [ ] 请求频率控制
- [ ] 异常页面处理
- [ ] 爬取结果去重和验证

```python
# engines/crawler.py
class LinkCrawlerEngine:
    async def crawl_page(self, url: str) -> PageResult
    async def extract_links(self, html: str, base_url: str) -> List[str]
    async def crawl_domain(self, domain: str, max_depth: int) -> CrawlResult
```

#### 2.3 第三方域名识别引擎
**目标**: 精确识别第三方域名和服务
**任务列表**:
- [ ] 静态资源域名识别
- [ ] API接口域名提取
- [ ] 社交媒体插件识别
- [ ] 广告和追踪域名检测
- [ ] CDN和云服务识别
- [ ] 域名分类和标记

```python
# engines/third_party_identifier.py
class ThirdPartyIdentifierEngine:
    async def identify_static_resources(self, html: str) -> List[ThirdPartyDomain]
    async def identify_api_endpoints(self, requests: List[Request]) -> List[ThirdPartyDomain]
    async def classify_domain_type(self, domain: str) -> DomainType
```

### 第三阶段：AI分析引擎集成 (1-2周)

#### 3.1 用户AI配置管理
**目标**: 实现用户自定义AI服务配置
**任务列表**:
- [ ] AI配置数据模型设计
- [ ] 用户AI配置API接口
- [ ] API密钥加密存储
- [ ] 配置验证和测试
- [ ] 默认配置和模板
- [ ] 多AI提供商支持框架

```python
# models/ai_config.py
class UserAIConfig(Base):
    user_id = Column(String, ForeignKey("users.id"))
    openai_api_key = Column(String(255))  # 加密存储
    openai_base_url = Column(String(255))
    model_name = Column(String(100))
    max_tokens = Column(Integer, default=1000)
    temperature = Column(Float, default=0.7)
```

#### 3.2 内容抓取引擎
**目标**: 实现页面内容和截图抓取
**任务列表**:
- [ ] Playwright浏览器自动化集成
- [ ] 页面截图服务
- [ ] HTML内容提取
- [ ] 动态内容等待和处理
- [ ] 文件存储和管理
- [ ] 异常处理和重试机制

```python
# engines/content_capture.py
class ContentCaptureEngine:
    async def capture_screenshot(self, url: str) -> str
    async def extract_content(self, url: str) -> ContentResult
    async def process_page(self, url: str) -> PageAnalysisData
```

#### 3.3 AI多模态分析引擎
**目标**: 实现基于AI的内容违规检测
**任务列表**:
- [ ] 多模态提示词设计
- [ ] AI API客户端封装
- [ ] 分析结果解析和验证
- [ ] 风险等级评估算法
- [ ] 违规类型分类系统
- [ ] 批量分析优化

```python
# engines/ai_analysis.py
class AIAnalysisEngine:
    async def analyze_content(self, content: str, image_path: str) -> AnalysisResult
    async def build_prompt(self, domain: str, content: str) -> str
    async def parse_ai_response(self, response: str) -> ViolationResult
```

### 第四阶段：任务监控和通信系统 (1周)

#### 4.1 任务监控系统
**目标**: 实现详细的任务状态跟踪
**任务列表**:
- [ ] 任务进度跟踪机制
- [ ] 详细日志记录系统
- [ ] 性能指标监控
- [ ] 错误处理和恢复
- [ ] 任务超时控制
- [ ] 资源使用监控

```python
# services/task_monitor.py
class TaskMonitorService:
    async def track_progress(self, task_id: str, progress: int)
    async def log_event(self, task_id: str, level: str, message: str)
    async def handle_error(self, task_id: str, error: Exception)
```

#### 4.2 WebSocket实时通信
**目标**: 实现任务状态的实时推送
**任务列表**:
- [ ] WebSocket连接管理
- [ ] 用户连接状态维护
- [ ] 实时消息推送
- [ ] 连接异常处理
- [ ] 消息队列集成
- [ ] 性能优化

```python
# websocket/manager.py
class WebSocketManager:
    async def connect(self, websocket: WebSocket, user_id: str)
    async def disconnect(self, websocket: WebSocket, user_id: str)
    async def broadcast_to_user(self, user_id: str, message: dict)
```

### 第五阶段：前端Vue.js开发 (2-3周)

#### 5.1 前端项目搭建
**目标**: 创建现代化的Vue.js前端项目
**任务列表**:
- [ ] Vue 3 + TypeScript项目初始化
- [ ] Element Plus UI框架集成
- [ ] Pinia状态管理配置
- [ ] Vue Router路由配置
- [ ] Axios HTTP客户端配置
- [ ] 开发环境和构建配置

**项目结构**:
```
frontend/
├── src/
│   ├── components/         # 通用组件
│   ├── views/             # 页面组件
│   ├── stores/            # Pinia状态管理
│   ├── api/               # API接口
│   ├── router/            # 路由配置
│   ├── utils/             # 工具函数
│   ├── types/             # TypeScript类型
│   └── assets/            # 静态资源
├── package.json
├── vite.config.ts
└── tsconfig.json
```

#### 5.2 核心页面组件开发
**目标**: 实现系统的主要功能页面
**任务列表**:
- [ ] 用户登录和注册页面
- [ ] 系统仪表板页面
- [ ] 扫描任务创建页面
- [ ] 任务列表和管理页面
- [ ] 任务详情和监控页面
- [ ] 报告查看和导出页面
- [ ] 用户设置和AI配置页面
- [ ] 系统配置管理页面(管理员)

**关键组件**:
```vue
<!-- views/ScanTask/CreateScan.vue -->
<template>
  <el-form :model="scanForm" :rules="rules">
    <el-form-item label="目标域名" prop="domain">
      <el-input v-model="scanForm.domain" placeholder="请输入要扫描的域名" />
    </el-form-item>
    <!-- 更多配置项 -->
  </el-form>
</template>

<!-- views/ScanTask/TaskDetail.vue -->
<template>
  <div class="task-detail">
    <task-progress :progress="task.progress" />
    <task-logs :logs="task.logs" />
    <task-results :results="task.results" />
  </div>
</template>
```

#### 5.3 状态管理和API集成
**目标**: 实现完整的前后端数据交互
**任务列表**:
- [ ] 用户认证状态管理
- [ ] 任务状态管理
- [ ] 系统配置状态管理
- [ ] API接口封装
- [ ] 错误处理机制
- [ ] 数据缓存策略

```typescript
// stores/auth.ts
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    token: localStorage.getItem('token'),
    isAuthenticated: false
  }),
  actions: {
    async login(credentials: LoginRequest) { ... },
    async logout() { ... },
    async refreshToken() { ... }
  }
})

// stores/scanTask.ts
export const useScanTaskStore = defineStore('scanTask', {
  state: () => ({
    tasks: [] as ScanTask[],
    currentTask: null as ScanTask | null,
    loading: false
  }),
  actions: {
    async createTask(taskData: CreateTaskRequest) { ... },
    async fetchTasks() { ... },
    async getTaskDetail(taskId: string) { ... }
  }
})
```

### 第六阶段：系统配置管理 (1周)

#### 6.1 系统配置界面
**目标**: 实现灵活的系统配置管理
**任务列表**:
- [ ] 扫描任务参数配置
- [ ] AI分析参数配置
- [ ] 安全和限制配置
- [ ] 系统监控配置
- [ ] 配置验证和保存
- [ ] 配置历史和回滚

**配置分类**:
```typescript
interface SystemConfig {
  scanLimits: {
    maxConcurrentTasks: number;
    maxSubdomains: number;
    maxCrawlDepth: number;
    taskTimeoutHours: number;
  };
  aiSettings: {
    defaultModel: string;
    maxTokens: number;
    temperature: number;
    timeoutSeconds: number;
  };
  security: {
    sessionTimeoutMinutes: number;
    maxLoginAttempts: number;
    rateLimitPerMinute: number;
  };
}
```

### 第七阶段：API接口完善和测试 (1周)

#### 7.1 API接口开发
**目标**: 完善所有业务API接口
**任务列表**:
- [ ] 用户管理API完善
- [ ] 任务管理API完善
- [ ] 配置管理API完善
- [ ] 报告相关API开发
- [ ] 统计分析API开发
- [ ] API文档生成

**完整API列表**:
```python
# 认证相关
POST /api/v1/auth/login
POST /api/v1/auth/register
POST /api/v1/auth/logout
GET  /api/v1/auth/me

# 任务管理
POST /api/v1/tasks
GET  /api/v1/tasks
GET  /api/v1/tasks/{id}
GET  /api/v1/tasks/{id}/logs
DELETE /api/v1/tasks/{id}

# 配置管理
GET  /api/v1/config/ai
PUT  /api/v1/config/ai
GET  /api/v1/config/system
PUT  /api/v1/config/system

# 报告相关
GET  /api/v1/reports/{task_id}
GET  /api/v1/reports/{task_id}/export
```

### 第八阶段：系统集成测试和部署 (1周)

#### 8.1 集成测试
**目标**: 确保系统各模块协同工作
**任务列表**:
- [ ] 端到端测试用例编写
- [ ] API接口测试
- [ ] 前端组件测试
- [ ] 性能测试
- [ ] 安全测试
- [ ] 用户体验测试

#### 8.2 部署配置
**目标**: 完成生产环境部署准备
**任务列表**:
- [ ] Docker容器化配置
- [ ] 数据库部署脚本
- [ ] 反向代理配置
- [ ] 环境变量配置
- [ ] 监控和日志配置
- [ ] 备份和恢复策略

## 开发资源和依赖

### 技术依赖
```json
{
  "后端依赖": {
    "fastapi": "^0.104.0",
    "sqlalchemy": "^2.0.0",
    "alembic": "^1.12.0",
    "celery": "^5.3.0",
    "redis": "^5.0.0",
    "playwright": "^1.40.0",
    "pyjwt": "^2.8.0",
    "bcrypt": "^4.0.0",
    "pydantic": "^2.0.0"
  },
  "前端依赖": {
    "vue": "^3.3.0",
    "typescript": "^5.0.0",
    "element-plus": "^2.4.0",
    "pinia": "^2.1.0",
    "vue-router": "^4.2.0",
    "axios": "^1.5.0",
    "vite": "^4.4.0"
  }
}
```

### 开发工具
- IDE: VS Code / PyCharm
- API测试: Postman / Insomnia
- 数据库工具: pgAdmin / DBeaver
- 版本控制: Git
- 容器化: Docker / Docker Compose

## 质量保证

### 代码规范
- 后端: PEP 8 + Black + isort
- 前端: ESLint + Prettier
- 类型检查: mypy + TypeScript strict mode

### 测试策略
- 单元测试覆盖率 > 80%
- 集成测试覆盖主要业务流程
- E2E测试覆盖核心用户场景

### 文档要求
- API文档自动生成
- 组件使用文档
- 部署运维文档
- 用户使用手册

## 项目里程碑

1. **Week 1-2**: 基础架构完成，用户认证系统可用
2. **Week 3-5**: 核心扫描引擎完成，基础功能可测试
3. **Week 6-7**: AI分析集成完成，端到端流程打通
4. **Week 8**: 任务监控和实时通信完成
5. **Week 9-11**: 前端界面完成，用户体验良好
6. **Week 12**: 系统配置和管理功能完成
7. **Week 13**: API完善，文档齐全
8. **Week 14**: 测试完成，生产环境部署就绪

## 风险评估和应对

### 技术风险
- AI API调用限制 → 实现请求池和重试机制
- 大规模域名扫描性能 → 分布式架构和缓存优化
- 浏览器自动化稳定性 → 异常处理和备用方案

### 业务风险
- 扫描目标的法律合规性 → 添加免责声明和使用条款
- 用户数据安全 → 加密存储和权限控制
- 系统资源消耗 → 资源限制和监控告警

### 应对策略
- 分阶段交付，持续集成
- 完善的测试覆盖
- 详细的监控和日志
- 定期的安全审计