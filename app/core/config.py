from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """应用配置"""
    
    # 基础配置
    PROJECT_NAME: str = "Domain Compliance Scanner"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # 数据库配置
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/domain_scanner"
    DATABASE_ECHO: bool = False
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8小时
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7天
    
    # CORS配置
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080"
    ]
    
    # 文件存储配置
    STORAGE_PATH: str = "./storage"
    SCREENSHOT_PATH: str = "./storage/screenshots"
    LOGS_PATH: str = "./storage/logs"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # 扫描配置
    MAX_CONCURRENT_TASKS_PER_USER: int = 5
    MAX_SUBDOMAINS_PER_TASK: int = 1000
    MAX_CRAWL_DEPTH: int = 5
    TASK_TIMEOUT_HOURS: int = 24
    
    # AI配置
    DEFAULT_AI_MODEL: str = "gpt-4-vision-preview"
    DEFAULT_MAX_TOKENS: int = 1000
    DEFAULT_TEMPERATURE: float = 0.7
    AI_REQUEST_TIMEOUT: int = 120
    AI_RETRY_COUNT: int = 3
    
    # 安全配置
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Celery配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # 浏览器配置
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT: int = 30000
    SCREENSHOT_VIEWPORT_WIDTH: int = 1920
    SCREENSHOT_VIEWPORT_HEIGHT: int = 1080
    
    # 监控配置
    ENABLE_METRICS: bool = True
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 创建必要的目录
        Path(self.STORAGE_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.SCREENSHOT_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.LOGS_PATH).mkdir(parents=True, exist_ok=True)


# 创建全局配置实例
settings = Settings()


class CeleryConfig:
    """Celery配置类"""
    
    broker_url = settings.CELERY_BROKER_URL
    result_backend = settings.CELERY_RESULT_BACKEND
    
    # 任务序列化
    task_serializer = "json"
    accept_content = ["json"]
    result_serializer = "json"
    
    # 时区设置
    timezone = "UTC"
    enable_utc = True
    
    # 任务路由
    task_routes = {
        "app.tasks.scan_domain": {"queue": "scan"},
        "app.tasks.analyze_content": {"queue": "analysis"},
        "app.tasks.capture_screenshot": {"queue": "capture"},
    }
    
    # 工作进程配置
    worker_max_tasks_per_child = 1000
    worker_prefetch_multiplier = 1
    task_acks_late = True
    
    # 任务超时
    task_soft_time_limit = 3600  # 1小时软限制
    task_time_limit = 7200      # 2小时硬限制
    
    # 结果过期时间
    result_expires = 3600  # 1小时
    
    # 任务重试
    task_default_retry_delay = 60
    task_max_retries = 3