from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from enum import Enum

from app.core.database import Base


class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    USER = "user"


class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # 个人信息
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # 安全相关
    failed_login_attempts = Column(String(10), default="0", nullable=False)
    locked_until = Column(DateTime, nullable=True)
    
    # 关联关系
    scan_tasks = relationship("ScanTask", back_populates="user", cascade="all, delete-orphan")
    ai_config = relationship("UserAIConfig", back_populates="user", uselist=False, cascade="all, delete-orphan")
    login_attempts = relationship("LoginAttempt", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"
    
    @property
    def is_admin(self) -> bool:
        """检查是否为管理员"""
        return self.role == UserRole.ADMIN
    
    @property
    def is_locked(self) -> bool:
        """检查账户是否被锁定"""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until


class UserAIConfig(Base):
    """用户AI配置模型"""
    __tablename__ = "user_ai_configs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    
    # OpenAI配置
    openai_api_key = Column(Text, nullable=True)  # 加密存储
    openai_base_url = Column(String(255), default="https://api.openai.com/v1", nullable=False)
    openai_organization = Column(String(255), nullable=True)
    
    # 模型配置
    model_name = Column(String(100), default="gpt-4-vision-preview", nullable=False)
    max_tokens = Column(String(10), default="1000", nullable=False)
    temperature = Column(String(10), default="0.7", nullable=False)
    
    # 提示词配置
    system_prompt = Column(Text, nullable=True)
    custom_prompt_template = Column(Text, nullable=True)
    
    # 高级配置
    request_timeout = Column(String(10), default="120", nullable=False)  # 秒
    retry_count = Column(String(10), default="3", nullable=False)
    enable_streaming = Column(Boolean, default=False, nullable=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_tested = Column(DateTime, nullable=True)
    
    # 关联关系
    user = relationship("User", back_populates="ai_config")
    
    def __repr__(self):
        return f"<UserAIConfig(id={self.id}, user_id={self.user_id}, model={self.model_name})>"
    
    @property
    def ai_model_name(self) -> str:
        """获取AI模型名称（映射到model_name字段以避免Pydantic命名冲突）"""
        return self.model_name
    
    @ai_model_name.setter
    def ai_model_name(self, value: str):
        """设置AI模型名称"""
        self.model_name = value
    
    @property
    def has_valid_config(self) -> bool:
        """检查是否有有效的AI配置"""
        return bool(self.openai_api_key and self.model_name)
    
    @property
    def max_tokens_int(self) -> int:
        """获取最大令牌数的整数值"""
        try:
            return int(self.max_tokens)
        except (ValueError, TypeError):
            return 1000
    
    @property
    def temperature_float(self) -> float:
        """获取温度的浮点值"""
        try:
            return float(self.temperature)
        except (ValueError, TypeError):
            return 0.7
    
    @property
    def request_timeout_int(self) -> int:
        """获取请求超时的整数值"""
        try:
            return int(self.request_timeout)
        except (ValueError, TypeError):
            return 120
    
    @property
    def retry_count_int(self) -> int:
        """获取重试次数的整数值"""
        try:
            return int(self.retry_count)
        except (ValueError, TypeError):
            return 3