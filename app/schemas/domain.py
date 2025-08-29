from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DomainCategoryEnum(str, Enum):
    """域名分类枚举"""
    TARGET_MAIN = "target_main"
    TARGET_SUBDOMAIN = "target_subdomain"
    THIRD_PARTY = "third_party"
    UNKNOWN = "unknown"


class DomainStatusEnum(str, Enum):
    """域名状态枚举"""
    DISCOVERED = "discovered"
    ACCESSIBLE = "accessible"
    INACCESSIBLE = "inaccessible"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    ERROR = "error"


class DiscoveryMethodEnum(str, Enum):
    """发现方法枚举"""
    SUBDOMAIN_ENUM = "subdomain_enum"
    DNS_LOOKUP = "dns_lookup"
    CERTIFICATE = "certificate"
    LINK_CRAWLING = "link_crawling"
    MANUAL = "manual"
    THIRD_PARTY_SCAN = "third_party_scan"


class RiskLevelEnum(str, Enum):
    """风险等级枚举"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SAFE = "safe"


class DomainRecordCreateSchema(BaseModel):
    """创建域名记录Schema"""
    domain: str = Field(..., description="域名", max_length=255)
    category: DomainCategoryEnum = Field(DomainCategoryEnum.UNKNOWN, description="域名分类")
    discovery_method: DiscoveryMethodEnum = Field(..., description="发现方法")
    found_on_urls: Optional[List[str]] = Field(None, description="发现该域名的URL列表")
    parent_domain: Optional[str] = Field(None, description="父域名", max_length=255)
    depth_level: int = Field(0, ge=0, le=10, description="发现深度级别")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="扩展数据")
    
    @validator('domain')
    def validate_domain(cls, v):
        """验证域名格式"""
        if not v or len(v.strip()) == 0:
            raise ValueError('域名不能为空')
        # 简单的域名格式检查
        if not ('.' in v and len(v) <= 255):
            raise ValueError('域名格式不正确')
        return v.lower().strip()


class DomainRecordUpdateSchema(BaseModel):
    """更新域名记录Schema"""
    category: Optional[DomainCategoryEnum] = Field(None, description="域名分类")
    status: Optional[DomainStatusEnum] = Field(None, description="域名状态")
    ip_address: Optional[str] = Field(None, description="IP地址", max_length=45)
    is_accessible: Optional[bool] = Field(None, description="是否可访问")
    response_code: Optional[int] = Field(None, description="HTTP响应码", ge=100, le=599)
    response_time: Optional[float] = Field(None, description="响应时间（秒）", ge=0)
    server_header: Optional[str] = Field(None, description="服务器头信息", max_length=255)
    content_type: Optional[str] = Field(None, description="内容类型", max_length=100)
    page_title: Optional[str] = Field(None, description="页面标题", max_length=500)
    page_description: Optional[str] = Field(None, description="页面描述")
    content_hash: Optional[str] = Field(None, description="内容哈希", max_length=64)
    risk_level: Optional[RiskLevelEnum] = Field(None, description="风险等级")
    confidence_score: Optional[float] = Field(None, description="置信度分数", ge=0.0, le=1.0)
    screenshot_path: Optional[str] = Field(None, description="截图路径", max_length=500)
    html_content_path: Optional[str] = Field(None, description="HTML内容路径", max_length=500)
    is_analyzed: Optional[bool] = Field(None, description="是否已分析")
    analysis_error: Optional[str] = Field(None, description="分析错误信息")
    ai_analysis_result: Optional[Dict[str, Any]] = Field(None, description="AI分析结果")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="扩展数据")


class DomainRecordResponseSchema(BaseModel):
    """域名记录响应Schema"""
    id: str = Field(..., description="域名记录ID")
    task_id: str = Field(..., description="任务ID")
    domain: str = Field(..., description="域名")
    category: str = Field(..., description="域名分类")
    status: str = Field(..., description="域名状态")
    discovery_method: str = Field(..., description="发现方法")
    ip_address: Optional[str] = Field(None, description="IP地址")
    is_accessible: bool = Field(..., description="是否可访问")
    response_code: Optional[int] = Field(None, description="HTTP响应码")
    response_time: Optional[float] = Field(None, description="响应时间（秒）")
    server_header: Optional[str] = Field(None, description="服务器头信息")
    content_type: Optional[str] = Field(None, description="内容类型")
    page_title: Optional[str] = Field(None, description="页面标题")
    page_description: Optional[str] = Field(None, description="页面描述")
    content_hash: Optional[str] = Field(None, description="内容哈希")
    found_on_urls: Optional[List[str]] = Field(None, description="发现该域名的URL列表")
    parent_domain: Optional[str] = Field(None, description="父域名")
    depth_level: int = Field(..., description="发现深度级别")
    risk_level: str = Field(..., description="风险等级")
    confidence_score: float = Field(..., description="置信度分数")
    screenshot_path: Optional[str] = Field(None, description="截图路径")
    html_content_path: Optional[str] = Field(None, description="HTML内容路径")
    is_analyzed: bool = Field(..., description="是否已分析")
    analysis_error: Optional[str] = Field(None, description="分析错误信息")
    ai_analysis_result: Optional[Dict[str, Any]] = Field(None, description="AI分析结果")
    created_at: str = Field(..., description="创建时间")
    first_discovered_at: str = Field(..., description="首次发现时间")
    last_updated_at: str = Field(..., description="最后更新时间")
    last_accessed_at: Optional[str] = Field(None, description="最后访问时间")
    analyzed_at: Optional[str] = Field(None, description="分析时间")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="扩展数据")
    has_violations: bool = Field(..., description="是否有违规记录")
    is_target_related: bool = Field(..., description="是否为目标域名相关")
    is_third_party: bool = Field(..., description="是否为第三方域名")


class DomainListResponseSchema(BaseModel):
    """域名列表响应Schema"""
    items: List[DomainRecordResponseSchema] = Field(..., description="域名记录列表")
    total: int = Field(..., description="总数量")
    skip: int = Field(..., description="跳过数量")
    limit: int = Field(..., description="限制数量")


class DomainStatsSchema(BaseModel):
    """域名统计Schema"""
    total_domains: int = Field(..., description="域名总数")
    target_domains: int = Field(..., description="目标域名数量")
    subdomain_count: int = Field(..., description="子域名数量")
    third_party_count: int = Field(..., description="第三方域名数量")
    accessible_count: int = Field(..., description="可访问域名数量")
    analyzed_count: int = Field(..., description="已分析域名数量")
    violation_count: int = Field(..., description="有违规的域名数量")
    category_distribution: Dict[str, int] = Field(..., description="分类分布")
    status_distribution: Dict[str, int] = Field(..., description="状态分布")
    risk_distribution: Dict[str, int] = Field(..., description="风险分布")
    discovery_method_distribution: Dict[str, int] = Field(..., description="发现方法分布")


class DomainFilterSchema(BaseModel):
    """域名过滤Schema"""
    category: Optional[DomainCategoryEnum] = Field(None, description="域名分类筛选")
    status: Optional[DomainStatusEnum] = Field(None, description="域名状态筛选")
    risk_level: Optional[RiskLevelEnum] = Field(None, description="风险等级筛选")
    discovery_method: Optional[DiscoveryMethodEnum] = Field(None, description="发现方法筛选")
    is_accessible: Optional[bool] = Field(None, description="是否可访问筛选")
    is_analyzed: Optional[bool] = Field(None, description="是否已分析筛选")
    has_violations: Optional[bool] = Field(None, description="是否有违规筛选")
    domain_search: Optional[str] = Field(None, description="域名搜索关键词")
    parent_domain: Optional[str] = Field(None, description="父域名筛选")
    tags: Optional[List[str]] = Field(None, description="标签筛选")


class TaskDomainSummarySchema(BaseModel):
    """任务域名汇总Schema"""
    task_id: str = Field(..., description="任务ID")
    target_domain: str = Field(..., description="目标域名")
    
    # 需要扫描的域名
    scan_domains: List[DomainRecordResponseSchema] = Field(..., description="需要扫描的域名列表")
    
    # 检测到的所有域名
    all_domains: List[DomainRecordResponseSchema] = Field(..., description="检测到的所有域名列表")
    
    # 统计信息
    stats: DomainStatsSchema = Field(..., description="域名统计信息")
    
    # 更新时间
    last_updated: str = Field(..., description="最后更新时间")