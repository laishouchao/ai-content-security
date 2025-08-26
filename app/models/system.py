from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from enum import Enum

from app.core.database import Base


class ConfigType(str, Enum):
    """配置类型枚举"""
    SYSTEM = "system"
    SCAN = "scan"
    AI = "ai"
    SECURITY = "security"
    MONITORING = "monitoring"


class PermissionType(str, Enum):
    """权限类型枚举"""
    USER_MANAGE = "user_manage"
    SYSTEM_CONFIG = "system_config"
    TASK_MANAGE = "task_manage"
    REPORT_VIEW = "report_view"
    AI_CONFIG = "ai_config"


class SystemConfig(Base):
    """系统配置模型"""
    __tablename__ = "system_configs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 配置信息
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_type = Column(String(50), nullable=False, index=True)
    config_value = Column(JSON, nullable=False)
    
    # 元数据
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_sensitive = Column(Boolean, default=False, nullable=False)  # 是否敏感信息
    is_editable = Column(Boolean, default=True, nullable=False)   # 是否可编辑
    
    # 验证规则
    validation_schema = Column(JSON, nullable=True)  # JSON Schema用于验证
    default_value = Column(JSON, nullable=True)
    
    # 变更记录
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<SystemConfig(key={self.config_key}, type={self.config_type})>"
    
    @property
    def is_default(self) -> bool:
        """检查是否为默认值"""
        # 显式转换为布尔值以避免类型错误
        result = self.config_value == self.default_value
        return bool(result) if not isinstance(result, bool) else result


class UserPermission(Base):
    """用户权限模型"""
    __tablename__ = "user_permissions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # 权限信息
    permission_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String(36), nullable=True)  # 可选的资源ID
    is_granted = Column(Boolean, default=True, nullable=False)
    
    # 权限范围
    scope = Column(JSON, nullable=True)  # 权限的具体范围定义
    conditions = Column(JSON, nullable=True)  # 权限的条件限制
    
    # 授权信息
    granted_by = Column(String(36), nullable=True)
    granted_reason = Column(Text, nullable=True)
    
    # 时间戳
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # 权限过期时间
    
    # 关联关系
    user = relationship("User")
    
    def __repr__(self):
        return f"<UserPermission(user_id={self.user_id}, permission={self.permission_type})>"
    
    @property
    def is_expired(self) -> bool:
        """检查权限是否已过期"""
        if self.expires_at is None:
            return False
        result = datetime.utcnow() > self.expires_at
        return bool(result) if not isinstance(result, bool) else result
    
    @property
    def is_active(self) -> bool:
        """检查权限是否有效"""
        granted = bool(self.is_granted) if not isinstance(self.is_granted, bool) else self.is_granted
        expired = bool(self.is_expired) if not isinstance(self.is_expired, bool) else self.is_expired
        return granted and not expired


class LoginAttempt(Base):
    """登录尝试记录模型"""
    __tablename__ = "login_attempts"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)  # 可为空，支持记录不存在用户的尝试
    
    # 登录信息
    username = Column(String(100), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False, index=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    
    # 结果信息
    is_successful = Column(Boolean, nullable=False, index=True)
    failure_reason = Column(String(100), nullable=True)  # 失败原因
    
    # 安全信息
    is_suspicious = Column(Boolean, default=False, nullable=False)  # 是否可疑
    geo_location = Column(JSON, nullable=True)  # 地理位置信息
    
    # 时间戳
    attempted_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # 关联关系
    user = relationship("User", back_populates="login_attempts")
    
    def __repr__(self):
        return f"<LoginAttempt(username={self.username}, ip={self.ip_address}, success={self.is_successful})>"


class AuditLog(Base):
    """审计日志模型"""
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)  # 可为空，支持系统操作
    
    # 操作信息
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String(36), nullable=True)
    
    # 详细信息
    description = Column(Text, nullable=False)
    old_values = Column(JSON, nullable=True)  # 变更前的值
    new_values = Column(JSON, nullable=True)  # 变更后的值
    
    # 请求信息
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(36), nullable=True)
    
    # 结果信息
    is_successful = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<AuditLog(action={self.action}, resource={self.resource_type}, success={self.is_successful})>"


class APIUsageLog(Base):
    """API使用日志模型"""
    __tablename__ = "api_usage_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    
    # 请求信息
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    request_size = Column(Integer, nullable=True)
    response_size = Column(Integer, nullable=True)
    
    # 响应信息
    status_code = Column(Integer, nullable=False, index=True)
    response_time = Column(Integer, nullable=False)  # 毫秒
    
    # 客户端信息
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    
    # 标识信息
    request_id = Column(String(36), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<APIUsageLog(endpoint={self.endpoint}, status={self.status_code}, response_time={self.response_time})>"