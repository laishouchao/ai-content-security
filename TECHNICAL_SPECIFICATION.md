# 域名合规扫描系统技术规范

## 系统功能规范

### 1. 域名扫描流程规范

#### 1.1 输入验证规范
```python
# 域名格式验证
DOMAIN_PATTERN = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'

# 输入限制
MAX_DOMAIN_LENGTH = 253
MIN_DOMAIN_LENGTH = 4
BLOCKED_DOMAINS = ['localhost', '127.0.0.1', '0.0.0.0']
```

#### 1.2 扫描配置参数
```yaml
scan_config:
  subdomain_discovery:
    max_subdomains: 1000          # 最大子域名数量
    timeout_seconds: 300          # 发现超时时间
    concurrent_requests: 10       # 并发请求数
    methods:
      - dns_query                 # DNS查询
      - certificate_transparency  # 证书透明日志
      - bruteforce               # 字典爆破
    
  link_crawling:
    max_depth: 3                  # 最大爬取深度
    max_pages_per_domain: 100     # 每个域名最大页面数
    timeout_per_page: 30          # 单页面超时时间
    respect_robots_txt: true      # 遵循robots.txt
    user_agent: "DomainScanner/1.0"
    
  content_capture:
    screenshot_enabled: true      # 启用截图
    screenshot_format: "png"      # 截图格式
    screenshot_quality: 90        # 截图质量
    viewport_width: 1920          # 视口宽度
    viewport_height: 1080         # 视口高度
    wait_for_load: 5              # 等待加载时间(秒)
    
  ai_analysis:
    confidence_threshold: 0.7     # 置信度阈值
    max_content_length: 10000     # 最大分析内容长度
    batch_size: 5                 # 批量分析大小
    retry_count: 3                # 重试次数
```

### 2. 数据模型规范

#### 2.1 用户和权限模型
```python
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Float, JSON, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # 关联
    scan_tasks = relationship("ScanTask", back_populates="user", cascade="all, delete-orphan")
    ai_config = relationship("UserAIConfig", back_populates="user", uselist=False)

class UserAIConfig(Base):
    __tablename__ = "user_ai_configs"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    openai_api_key = Column(Text, nullable=True)  # 加密存储
    openai_base_url = Column(String(255), default="https://api.openai.com/v1")
    model_name = Column(String(100), default="gpt-4-vision-preview")
    max_tokens = Column(Integer, default=1000)
    temperature = Column(Float, default=0.7)
    system_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    
    user = relationship("User", back_populates="ai_config")
```

#### 2.2 扫描任务模型
```python
class ScanTask(Base):
    __tablename__ = "scan_tasks"
    
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    target_domain = Column(String(255), nullable=False, index=True)
    status = Column(String(20), default=TaskStatus.PENDING, index=True)
    progress = Column(Integer, default=0)
    config = Column(JSON, nullable=False)
    
    # 统计信息
    total_subdomains = Column(Integer, default=0)
    total_pages_crawled = Column(Integer, default=0)
    total_third_party_domains = Column(Integer, default=0)
    total_violations = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 关联
    user = relationship("User", back_populates="scan_tasks")
    task_logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")
    subdomains = relationship("SubdomainRecord", back_populates="task", cascade="all, delete-orphan")
    third_party_domains = relationship("ThirdPartyDomain", back_populates="task", cascade="all, delete-orphan")
    violations = relationship("ViolationRecord", back_populates="task", cascade="all, delete-orphan")

class TaskLog(Base):
    __tablename__ = "task_logs"
    
    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("scan_tasks.id"), nullable=False, index=True)
    level = Column(String(20), nullable=False)  # DEBUG, INFO, WARNING, ERROR
    module = Column(String(100), nullable=False)  # subdomain_discovery, crawler, ai_analysis
    message = Column(Text, nullable=False)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    
    task = relationship("ScanTask", back_populates="task_logs")
```

#### 2.3 域名和违规记录模型
```python
class SubdomainRecord(Base):
    __tablename__ = "subdomain_records"
    
    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("scan_tasks.id"), nullable=False, index=True)
    subdomain = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    discovery_method = Column(String(50), nullable=False)
    is_accessible = Column(Boolean, default=False)
    response_code = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False)
    
    task = relationship("ScanTask", back_populates="subdomains")

class ThirdPartyDomain(Base):
    __tablename__ = "third_party_domains"
    
    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("scan_tasks.id"), nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    found_on_url = Column(Text, nullable=False)
    domain_type = Column(String(50), nullable=False)  # 'cdn', 'analytics', 'ads', 'social', 'api'
    risk_level = Column(String(20), default=RiskLevel.LOW)
    screenshot_path = Column(String(500), nullable=True)
    content_hash = Column(String(64), nullable=True)  # 内容哈希用于去重
    is_analyzed = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    
    task = relationship("ScanTask", back_populates="third_party_domains")
    violations = relationship("ViolationRecord", back_populates="domain")

class ViolationRecord(Base):
    __tablename__ = "violation_records"
    
    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("scan_tasks.id"), nullable=False, index=True)
    domain_id = Column(String(36), ForeignKey("third_party_domains.id"), nullable=False)
    violation_type = Column(String(100), nullable=False)
    confidence_score = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    content_snippet = Column(Text, nullable=True)
    ai_analysis_result = Column(JSON, nullable=False)
    risk_level = Column(String(20), nullable=False)
    detected_at = Column(DateTime, nullable=False)
    
    task = relationship("ScanTask", back_populates="violations")
    domain = relationship("ThirdPartyDomain", back_populates="violations")
```

### 3. API接口规范

#### 3.1 认证接口
```python
from pydantic import BaseModel, EmailStr
from typing import Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    
class RefreshTokenRequest(BaseModel):
    refresh_token: str
```

#### 3.2 任务管理接口
```python
class ScanTaskRequest(BaseModel):
    target_domain: str
    config: Optional[Dict[str, Any]] = None
    
class ScanTaskResponse(BaseModel):
    id: str
    target_domain: str
    status: str
    progress: int
    total_subdomains: int
    total_pages_crawled: int
    total_violations: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

class TaskLogResponse(BaseModel):
    id: str
    level: str
    module: str
    message: str
    created_at: datetime
    
class TaskDetailResponse(BaseModel):
    task: ScanTaskResponse
    logs: List[TaskLogResponse]
    subdomains: List[SubdomainResponse]
    third_party_domains: List[ThirdPartyDomainResponse]
    violations: List[ViolationResponse]
```

#### 3.3 配置管理接口
```python
class AIConfigRequest(BaseModel):
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    model_name: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None

class SystemConfigRequest(BaseModel):
    scan_limits: Optional[Dict[str, int]] = None
    ai_settings: Optional[Dict[str, Any]] = None
    security: Optional[Dict[str, Any]] = None
```

### 4. AI分析规范

#### 4.1 提示词模板
```python
DEFAULT_SYSTEM_PROMPT = """
你是一个专业的内容安全分析专家。请分析提供的网页内容和截图，识别是否存在以下违规情况：

1. 色情内容 (NSFW)
2. 暴力内容
3. 赌博相关
4. 诈骗信息
5. 恶意软件
6. 仇恨言论
7. 侵权内容
8. 其他违法违规内容

请按照以下JSON格式返回分析结果：

{
  "has_violation": boolean,
  "violation_types": ["类型1", "类型2"],
  "confidence_score": 0.0-1.0,
  "risk_level": "low|medium|high|critical",
  "description": "详细描述",
  "evidence": ["证据1", "证据2"],
  "recommendations": ["建议1", "建议2"]
}

分析要客观准确，避免误报。
"""

CONTENT_ANALYSIS_PROMPT_TEMPLATE = """
分析域名：{domain}
页面URL：{url}
页面标题：{title}

页面内容摘要：
{content_summary}

请结合提供的页面截图，分析该页面是否存在违规内容。
"""
```

#### 4.2 AI响应解析规范
```python
class AIAnalysisResult(BaseModel):
    has_violation: bool
    violation_types: List[str]
    confidence_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    description: str
    evidence: List[str] = []
    recommendations: List[str] = []
    
class AIAnalysisEngine:
    async def analyze_content(
        self, 
        domain: str, 
        url: str, 
        content: str, 
        screenshot_path: str,
        user_ai_config: UserAIConfig
    ) -> AIAnalysisResult:
        """分析页面内容和截图"""
        
        # 构建提示词
        prompt = self._build_prompt(domain, url, content)
        
        # 准备图像数据
        image_data = await self._encode_image(screenshot_path)
        
        # 调用AI API
        response = await self._call_ai_api(
            prompt, image_data, user_ai_config
        )
        
        # 解析结果
        return self._parse_response(response)
```

### 5. 安全规范

#### 5.1 认证安全
```python
# JWT配置
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 480  # 8小时
JWT_REFRESH_EXPIRE_DAYS = 7  # 7天

# 密码安全
MIN_PASSWORD_LENGTH = 8
PASSWORD_PATTERN = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'

# 会话安全
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30
SESSION_TIMEOUT_MINUTES = 480
```

#### 5.2 API安全
```python
# 速率限制
RATE_LIMITS = {
    "login": "5 per minute",
    "api": "100 per minute", 
    "ai_analysis": "10 per minute",
    "scan_task": "5 per hour"
}

# CORS配置
CORS_ORIGINS = [
    "http://localhost:5173",  # 开发环境
    "https://yourdomain.com"  # 生产环境
]

# 请求验证
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_FILE_TYPES = ["png", "jpg", "jpeg", "gif"]
```

### 6. 性能规范

#### 6.1 数据库优化
```sql
-- 关键索引
CREATE INDEX idx_scan_tasks_user_id ON scan_tasks(user_id);
CREATE INDEX idx_scan_tasks_status ON scan_tasks(status);
CREATE INDEX idx_scan_tasks_created_at ON scan_tasks(created_at);
CREATE INDEX idx_task_logs_task_id ON task_logs(task_id);
CREATE INDEX idx_third_party_domains_domain ON third_party_domains(domain);
CREATE INDEX idx_violation_records_task_id ON violation_records(task_id);

-- 复合索引
CREATE INDEX idx_scan_tasks_user_status ON scan_tasks(user_id, status);
CREATE INDEX idx_logs_task_level ON task_logs(task_id, level);
```

#### 6.2 缓存策略
```python
# Redis缓存配置
CACHE_CONFIG = {
    "user_config": 3600,        # 用户配置缓存1小时
    "system_config": 7200,      # 系统配置缓存2小时
    "domain_info": 1800,        # 域名信息缓存30分钟
    "ai_results": 86400,        # AI分析结果缓存1天
}

# 任务队列配置
CELERY_CONFIG = {
    "broker_url": "redis://localhost:6379/0",
    "result_backend": "redis://localhost:6379/0",
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "worker_max_tasks_per_child": 1000,
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
}
```

### 7. 监控和日志规范

#### 7.1 日志格式
```python
import logging
import json
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
            "user_id": getattr(record, 'user_id', None),
            "task_id": getattr(record, 'task_id', None),
            "request_id": getattr(record, 'request_id', None),
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry, ensure_ascii=False)

# 日志配置
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "()": StructuredFormatter,
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "structured",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["file"],
    },
}
```

#### 7.2 监控指标
```python
# Prometheus指标定义
from prometheus_client import Counter, Histogram, Gauge

# 业务指标
SCAN_TASKS_TOTAL = Counter('scan_tasks_total', 'Total scan tasks', ['status', 'user_role'])
VIOLATION_DETECTIONS = Counter('violation_detections_total', 'Total violations detected', ['type', 'risk_level'])
AI_ANALYSIS_REQUESTS = Counter('ai_analysis_requests_total', 'Total AI analysis requests', ['model', 'status'])

# 性能指标
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration', ['method', 'endpoint'])
TASK_DURATION = Histogram('task_duration_seconds', 'Task execution duration', ['task_type'])
QUEUE_SIZE = Gauge('task_queue_size', 'Current task queue size')

# 系统指标
ACTIVE_USERS = Gauge('active_users_count', 'Number of active users')
DATABASE_CONNECTIONS = Gauge('database_connections_active', 'Active database connections')
MEMORY_USAGE = Gauge('memory_usage_bytes', 'Memory usage in bytes')
```

### 8. 报告格式规范

#### 8.1 JSON报告格式
```json
{
  "scan_report": {
    "metadata": {
      "task_id": "uuid",
      "target_domain": "example.com",
      "scan_started": "2024-01-01T00:00:00Z",
      "scan_completed": "2024-01-01T01:00:00Z",
      "scan_duration_seconds": 3600,
      "scanner_version": "1.0.0"
    },
    "summary": {
      "total_subdomains": 150,
      "total_pages_crawled": 500,
      "total_third_party_domains": 25,
      "total_violations": 3,
      "risk_distribution": {
        "critical": 1,
        "high": 1,
        "medium": 1,
        "low": 0
      }
    },
    "subdomains": [
      {
        "subdomain": "api.example.com",
        "ip_address": "192.168.1.1",
        "discovery_method": "dns_query",
        "is_accessible": true,
        "response_code": 200
      }
    ],
    "third_party_domains": [
      {
        "domain": "cdn.cloudflare.com",
        "domain_type": "cdn",
        "found_on_urls": ["https://example.com/page1"],
        "risk_level": "low",
        "is_analyzed": true,
        "violations": []
      }
    ],
    "violations": [
      {
        "domain": "suspicious-ads.com",
        "violation_type": "malicious_advertising",
        "risk_level": "high",
        "confidence_score": 0.95,
        "description": "检测到恶意广告内容",
        "evidence": ["包含欺诈性广告", "重定向到可疑网站"],
        "found_on_url": "https://example.com/page2",
        "screenshot_path": "/screenshots/task_uuid/suspicious-ads.com.png",
        "detected_at": "2024-01-01T00:30:00Z"
      }
    ]
  }
}
```

这个技术规范文档涵盖了系统的所有关键技术细节，包括数据模型、API接口、安全规范、性能要求等，为开发团队提供了详细的技术指导。