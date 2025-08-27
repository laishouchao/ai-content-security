"""
域名白名单/黑名单数据模型
"""

from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from enum import Enum

from app.core.database import Base


class DomainListType(str, Enum):
    """域名列表类型"""
    WHITELIST = "whitelist"  # 白名单
    BLACKLIST = "blacklist"  # 黑名单


class DomainListScope(str, Enum):
    """域名列表作用域"""
    GLOBAL = "global"  # 全局
    USER = "user"      # 用户级别
    TASK = "task"      # 任务级别


class DomainList(Base):
    """域名列表（白名单/黑名单）"""
    __tablename__ = "domain_lists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 基本信息
    name = Column(String(100), nullable=False, comment="列表名称")
    description = Column(Text, comment="列表描述")
    list_type = Column(String(20), nullable=False, comment="列表类型：whitelist/blacklist")
    scope = Column(String(20), nullable=False, default="user", comment="作用域：global/user/task")
    
    # 关联信息
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, comment="用户ID（用户级别列表）")
    task_id = Column(String(36), ForeignKey("scan_tasks.id"), nullable=True, comment="任务ID（任务级别列表）")
    
    # 配置信息
    is_active = Column(Boolean, default=True, comment="是否启用")
    is_regex_enabled = Column(Boolean, default=False, comment="是否启用正则表达式匹配")
    priority = Column(Integer, default=0, comment="优先级（数字越大优先级越高）")
    
    # 统计信息
    domain_count = Column(Integer, default=0, comment="域名数量")
    match_count = Column(Integer, default=0, comment="匹配次数")
    last_matched_at = Column(DateTime, comment="最后匹配时间")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    created_by = Column(String(36), ForeignKey("users.id"), comment="创建者")
    
    # 关联关系
    domains = relationship("DomainListEntry", back_populates="domain_list", cascade="all, delete-orphan")
    user = relationship("User", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])
    
    # 索引
    __table_args__ = (
        Index('idx_domain_lists_user_type', 'user_id', 'list_type'),
        Index('idx_domain_lists_scope_active', 'scope', 'is_active'),
        Index('idx_domain_lists_priority', 'priority'),
    )


class DomainListEntry(Base):
    """域名列表条目"""
    __tablename__ = "domain_list_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联信息
    domain_list_id = Column(UUID(as_uuid=True), ForeignKey("domain_lists.id"), nullable=False, comment="所属列表ID")
    
    # 域名信息
    domain_pattern = Column(String(255), nullable=False, comment="域名模式")
    is_regex = Column(Boolean, default=False, comment="是否为正则表达式")
    is_wildcard = Column(Boolean, default=False, comment="是否为通配符模式")
    
    # 附加信息
    description = Column(Text, comment="条目描述")
    tags = Column(JSONB, comment="标签列表")
    confidence_score = Column(Integer, default=100, comment="置信度（0-100）")
    
    # 统计信息
    match_count = Column(Integer, default=0, comment="匹配次数")
    last_matched_at = Column(DateTime, comment="最后匹配时间")
    last_matched_domain = Column(String(255), comment="最后匹配的具体域名")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否启用")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    created_by = Column(String(36), ForeignKey("users.id"), comment="创建者")
    
    # 关联关系
    domain_list = relationship("DomainList", back_populates="domains")
    creator = relationship("User")
    
    # 索引
    __table_args__ = (
        Index('idx_domain_entries_list_active', 'domain_list_id', 'is_active'),
        Index('idx_domain_entries_pattern', 'domain_pattern'),
        Index('idx_domain_entries_regex', 'is_regex'),
    )


class DomainMatchLog(Base):
    """域名匹配日志"""
    __tablename__ = "domain_match_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 匹配信息
    domain = Column(String(255), nullable=False, comment="被匹配的域名")
    matched_pattern = Column(String(255), nullable=False, comment="匹配的模式")
    list_type = Column(String(20), nullable=False, comment="列表类型")
    match_type = Column(String(20), nullable=False, comment="匹配类型：exact/regex/wildcard")
    
    # 关联信息
    domain_list_id = Column(UUID(as_uuid=True), ForeignKey("domain_lists.id"), comment="匹配的列表ID")
    domain_entry_id = Column(UUID(as_uuid=True), ForeignKey("domain_list_entries.id"), comment="匹配的条目ID")
    task_id = Column(String(36), ForeignKey("scan_tasks.id"), comment="所属任务ID")
    user_id = Column(String(36), ForeignKey("users.id"), comment="用户ID")
    
    # 匹配结果
    action_taken = Column(String(50), comment="采取的行动")
    confidence_score = Column(Integer, comment="匹配置信度")
    
    # 时间戳
    matched_at = Column(DateTime, default=func.now(), comment="匹配时间")
    
    # 关联关系
    domain_list = relationship("DomainList")
    domain_entry = relationship("DomainListEntry")
    
    # 索引
    __table_args__ = (
        Index('idx_match_logs_domain', 'domain'),
        Index('idx_match_logs_task', 'task_id'),
        Index('idx_match_logs_time', 'matched_at'),
        Index('idx_match_logs_user', 'user_id'),
    )