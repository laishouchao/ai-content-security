from sqlalchemy import Column, String, DateTime, Boolean, Integer, Float, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from enum import Enum

from app.core.database import Base


class DomainCategory(str, Enum):
    """域名分类枚举"""
    TARGET_MAIN = "target_main"                    # 目标主域名
    TARGET_SUBDOMAIN = "target_subdomain"          # 目标子域名
    THIRD_PARTY = "third_party"                    # 第三方域名
    UNKNOWN = "unknown"                            # 未知类型


class DomainStatus(str, Enum):
    """域名状态枚举"""
    DISCOVERED = "discovered"                      # 已发现
    ACCESSIBLE = "accessible"                      # 可访问
    INACCESSIBLE = "inaccessible"                 # 不可访问
    ANALYZING = "analyzing"                        # 分析中
    ANALYZED = "analyzed"                          # 已分析
    ERROR = "error"                               # 错误


class DiscoveryMethod(str, Enum):
    """发现方法枚举"""
    SUBDOMAIN_ENUM = "subdomain_enum"              # 子域名枚举
    DNS_LOOKUP = "dns_lookup"                      # DNS查询
    CERTIFICATE = "certificate"                   # 证书透明度
    LINK_CRAWLING = "link_crawling"                # 链接爬取
    MANUAL = "manual"                             # 手动添加
    THIRD_PARTY_SCAN = "third_party_scan"         # 第三方扫描


class RiskLevel(str, Enum):
    """风险等级枚举"""
    CRITICAL = "critical"                          # 严重
    HIGH = "high"                                 # 高
    MEDIUM = "medium"                             # 中
    LOW = "low"                                   # 低
    SAFE = "safe"                                 # 安全


class DomainRecord(Base):
    """统一域名记录模型"""
    __tablename__ = "domain_records"
    
    # 基础信息
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("scan_tasks.id"), nullable=False, index=True)
    
    # 域名信息
    domain = Column(String(255), nullable=False, index=True)                   # 域名
    category = Column(String(50), default=DomainCategory.UNKNOWN, nullable=False, index=True)  # 域名分类
    status = Column(String(50), default=DomainStatus.DISCOVERED, nullable=False, index=True)   # 域名状态
    discovery_method = Column(String(50), nullable=False, index=True)          # 发现方法
    
    # 网络信息
    ip_address = Column(String(45), nullable=True)                            # IP地址 (IPv4/IPv6)
    is_accessible = Column(Boolean, default=False, nullable=False, index=True) # 是否可访问
    response_code = Column(Integer, nullable=True)                            # HTTP响应码
    response_time = Column(Float, nullable=True)                              # 响应时间（秒）
    
    # 技术信息
    server_header = Column(String(255), nullable=True)                        # 服务器头信息
    content_type = Column(String(100), nullable=True)                         # 内容类型
    page_title = Column(String(500), nullable=True)                           # 页面标题
    page_description = Column(Text, nullable=True)                            # 页面描述
    content_hash = Column(String(64), nullable=True)                          # 内容哈希（去重用）
    
    # 发现信息
    found_on_urls = Column(JSON, nullable=True)                               # 发现该域名的URL列表
    parent_domain = Column(String(255), nullable=True, index=True)            # 父域名
    depth_level = Column(Integer, default=0, nullable=False)                  # 发现深度级别
    
    # 风险评估
    risk_level = Column(String(20), default=RiskLevel.LOW, nullable=False, index=True)  # 风险等级
    confidence_score = Column(Float, default=0.0, nullable=False)             # 置信度分数 (0.0-1.0)
    
    # 文件路径
    screenshot_path = Column(String(500), nullable=True)                      # 截图路径
    html_content_path = Column(String(500), nullable=True)                    # HTML内容路径
    
    # 分析状态
    is_analyzed = Column(Boolean, default=False, nullable=False, index=True)  # 是否已分析
    analysis_error = Column(Text, nullable=True)                              # 分析错误信息
    ai_analysis_result = Column(JSON, nullable=True)                          # AI分析结果
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)      # 创建时间
    first_discovered_at = Column(DateTime, default=datetime.utcnow, nullable=False)         # 首次发现时间
    last_updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)             # 最后更新时间
    last_accessed_at = Column(DateTime, nullable=True)                                      # 最后访问时间
    analyzed_at = Column(DateTime, nullable=True)                                           # 分析时间
    
    # 扩展信息
    extra_data = Column(JSON, nullable=True)                                  # 扩展数据字段
    tags = Column(JSON, nullable=True)                                        # 标签列表
    
    # 关联关系
    task = relationship("ScanTask", back_populates="domains")
    violations = relationship("ViolationRecord", back_populates="domain_record", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<DomainRecord(id={self.id}, domain={self.domain}, category={self.category})>"
    
    @property
    def has_violations(self) -> bool:
        """检查是否有违规记录"""
        return len(self.violations) > 0
    
    @property
    def is_target_related(self) -> bool:
        """检查是否为目标域名相关"""
        return self.category in [DomainCategory.TARGET_MAIN, DomainCategory.TARGET_SUBDOMAIN]
    
    @property
    def is_third_party(self) -> bool:
        """检查是否为第三方域名"""
        return self.category == DomainCategory.THIRD_PARTY
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "domain": self.domain,
            "category": self.category,
            "status": self.status,
            "discovery_method": self.discovery_method,
            "ip_address": self.ip_address,
            "is_accessible": self.is_accessible,
            "response_code": self.response_code,
            "response_time": self.response_time,
            "server_header": self.server_header,
            "content_type": self.content_type,
            "page_title": self.page_title,
            "page_description": self.page_description,
            "content_hash": self.content_hash,
            "found_on_urls": self.found_on_urls,
            "parent_domain": self.parent_domain,
            "depth_level": self.depth_level,
            "risk_level": self.risk_level,
            "confidence_score": self.confidence_score,
            "screenshot_path": self.screenshot_path,
            "html_content_path": self.html_content_path,
            "is_analyzed": self.is_analyzed,
            "analysis_error": self.analysis_error,
            "ai_analysis_result": self.ai_analysis_result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "first_discovered_at": self.first_discovered_at.isoformat() if self.first_discovered_at else None,
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at is not None else None,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at is not None else None,
            "extra_data": self.extra_data,
            "tags": self.tags,
            "has_violations": self.has_violations,
            "is_target_related": self.is_target_related,
            "is_third_party": self.is_third_party
        }