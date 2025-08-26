from sqlalchemy import Column, String, DateTime, Boolean, Integer, Float, Text, JSON, ForeignKey
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from enum import Enum
from typing import Dict, Any, Optional

from app.core.database import Base


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class DomainType(str, Enum):
    """域名类型枚举"""
    CDN = "cdn"
    ANALYTICS = "analytics"
    ADVERTISING = "advertising"
    SOCIAL = "social"
    API = "api"
    PAYMENT = "payment"
    SECURITY = "security"
    UNKNOWN = "unknown"


class ViolationType(str, Enum):
    """违规类型枚举"""
    NSFW = "nsfw"
    VIOLENCE = "violence"
    GAMBLING = "gambling"
    FRAUD = "fraud"
    MALWARE = "malware"
    HATE_SPEECH = "hate_speech"
    COPYRIGHT = "copyright"
    OTHER = "other"


class ScanTask(Base):
    """扫描任务模型"""
    __tablename__ = "scan_tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # 任务基本信息
    target_domain = Column(String(255), nullable=False, index=True)
    task_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # 任务状态
    status = Column(String(20), default=TaskStatus.PENDING, nullable=False, index=True)
    progress = Column(Integer, default=0, nullable=False)  # 0-100
    
    # 配置信息
    config = Column(JSON, nullable=False)
    
    # 结果摘要（可选字段）
    results_summary = Column(JSON, nullable=True)
    
    # 统计信息
    total_subdomains = Column(Integer, default=0, nullable=False)
    total_pages_crawled = Column(Integer, default=0, nullable=False)
    total_third_party_domains = Column(Integer, default=0, nullable=False)
    total_violations = Column(Integer, default=0, nullable=False)
    
    # 风险统计
    critical_violations = Column(Integer, default=0, nullable=False)
    high_violations = Column(Integer, default=0, nullable=False)
    medium_violations = Column(Integer, default=0, nullable=False)
    low_violations = Column(Integer, default=0, nullable=False)
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 关联关系
    user = relationship("User", back_populates="scan_tasks")
    task_logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")
    subdomains = relationship("SubdomainRecord", back_populates="task", cascade="all, delete-orphan")
    third_party_domains = relationship("ThirdPartyDomain", back_populates="task", cascade="all, delete-orphan")
    violations = relationship("ViolationRecord", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ScanTask(id={self.id}, domain={self.target_domain}, status={self.status})>"
    
    @property
    def duration_seconds(self) -> Optional[int]:
        """获取任务执行时间（秒）"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
    
    @property
    def is_running(self) -> bool:
        """检查任务是否正在运行"""
        return self.status == TaskStatus.RUNNING
    
    @property
    def is_completed(self) -> bool:
        """检查任务是否已完成"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    @property
    def has_violations(self) -> bool:
        """检查是否有违规记录"""
        return self.total_violations > 0


class TaskLog(Base):
    """任务日志模型"""
    __tablename__ = "task_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("scan_tasks.id"), nullable=False, index=True)
    
    # 日志信息
    level = Column(String(20), nullable=False, index=True)
    module = Column(String(100), nullable=False, index=True)
    message = Column(Text, nullable=False)
    
    # 额外数据
    extra_data = Column(JSON, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # 关联关系
    task = relationship("ScanTask", back_populates="task_logs")
    
    def __repr__(self):
        return f"<TaskLog(id={self.id}, task_id={self.task_id}, level={self.level})>"


class SubdomainRecord(Base):
    """子域名记录模型"""
    __tablename__ = "subdomain_records"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("scan_tasks.id"), nullable=False, index=True)
    
    # 子域名信息
    subdomain = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    discovery_method = Column(String(50), nullable=False)
    
    # 状态信息
    is_accessible = Column(Boolean, default=False, nullable=False)
    response_code = Column(Integer, nullable=True)
    response_time = Column(Float, nullable=True)  # 响应时间（秒）
    
    # 技术信息
    server_header = Column(String(255), nullable=True)
    content_type = Column(String(100), nullable=True)
    page_title = Column(String(500), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 关联关系
    task = relationship("ScanTask", back_populates="subdomains")
    
    def __repr__(self):
        return f"<SubdomainRecord(id={self.id}, subdomain={self.subdomain})>"


class ThirdPartyDomain(Base):
    """第三方域名模型"""
    __tablename__ = "third_party_domains"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("scan_tasks.id"), nullable=False, index=True)
    
    # 域名信息
    domain = Column(String(255), nullable=False, index=True)
    found_on_url = Column(Text, nullable=False)
    domain_type = Column(String(50), default=DomainType.UNKNOWN, nullable=False)
    
    # 风险信息
    risk_level = Column(String(20), default=RiskLevel.LOW, nullable=False)
    
    # 内容信息
    page_title = Column(String(500), nullable=True)
    page_description = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True)  # 内容哈希用于去重
    
    # 文件路径
    screenshot_path = Column(String(500), nullable=True)
    html_content_path = Column(String(500), nullable=True)
    
    # 分析状态
    is_analyzed = Column(Boolean, default=False, nullable=False)
    analysis_error = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    analyzed_at = Column(DateTime, nullable=True)
    
    # 关联关系
    task = relationship("ScanTask", back_populates="third_party_domains")
    violations = relationship("ViolationRecord", back_populates="domain", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ThirdPartyDomain(id={self.id}, domain={self.domain}, type={self.domain_type})>"
    
    @property
    def has_violations(self) -> bool:
        """检查是否有违规记录"""
        return len(self.violations) > 0


class ViolationRecord(Base):
    """违规记录模型"""
    __tablename__ = "violation_records"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("scan_tasks.id"), nullable=False, index=True)
    domain_id = Column(String(36), ForeignKey("third_party_domains.id"), nullable=False)
    
    # 违规信息
    violation_type = Column(String(100), nullable=False, index=True)
    confidence_score = Column(Float, nullable=False)  # 0.0-1.0
    risk_level = Column(String(20), nullable=False, index=True)
    
    # 描述信息
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    content_snippet = Column(Text, nullable=True)
    
    # AI分析结果
    ai_analysis_result = Column(JSON, nullable=False)
    ai_model_used = Column(String(100), nullable=True)
    
    # 证据信息
    evidence = Column(JSON, nullable=True)  # 证据列表
    recommendations = Column(JSON, nullable=True)  # 建议列表
    
    # 时间戳
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 关联关系
    task = relationship("ScanTask", back_populates="violations")
    domain = relationship("ThirdPartyDomain", back_populates="violations")
    
    def __repr__(self):
        return f"<ViolationRecord(id={self.id}, type={self.violation_type}, risk={self.risk_level})>"
    
    @property
    def is_high_risk(self) -> bool:
        """检查是否为高风险违规"""
        return self.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    
    @property
    def confidence_percentage(self) -> int:
        """获取置信度百分比"""
        return int(self.confidence_score * 100)