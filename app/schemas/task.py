from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskConfigSchema(BaseModel):
    """任务配置Schema"""
    
    # 基础配置
    subdomain_discovery_enabled: bool = Field(True, description="启用子域名发现")
    link_crawling_enabled: bool = Field(True, description="启用链接爬取")
    third_party_identification_enabled: bool = Field(True, description="启用第三方域名识别")
    content_capture_enabled: bool = Field(True, description="启用内容抓取")
    ai_analysis_enabled: bool = Field(True, description="启用AI分析")
    
    # 基础限制
    max_subdomains: int = Field(100, ge=1, le=1000, description="最大子域名数量")
    max_crawl_depth: int = Field(3, ge=1, le=10, description="最大爬取深度")
    max_pages_per_domain: int = Field(1000, ge=1, le=10000, description="每域名最大页面数")
    request_delay: int = Field(1000, ge=100, le=5000, description="请求间隔(毫秒)")
    timeout: int = Field(30, ge=5, le=300, description="超时时间(秒)")
    
    # 性能优化配置
    use_parallel_executor: Optional[bool] = Field(True, description="使用并行执行器")
    smart_prefilter_enabled: Optional[bool] = Field(True, description="启用智能AI预筛选")
    dns_concurrency: Optional[int] = Field(100, ge=10, le=200, description="DNS查询并发数")
    ai_skip_threshold: Optional[float] = Field(0.3, ge=0.1, le=0.8, description="AI跳过阈值")
    multi_viewport_capture: Optional[bool] = Field(False, description="多视角截图")
    enable_aggressive_caching: Optional[bool] = Field(False, description="激进缓存策略")
    
    # 高级配置
    certificate_discovery_enabled: Optional[bool] = Field(True, description="证书透明日志发现")
    passive_dns_enabled: Optional[bool] = Field(False, description="被动DNS查询")
    max_concurrent_ai_calls: Optional[int] = Field(3, ge=1, le=10, description="最大并发AI调用")
    batch_size: Optional[int] = Field(10, ge=1, le=50, description="批处理大小")
    screenshot_optimization: Optional[bool] = Field(True, description="截图优化")
    
    # 迭代配置
    max_crawl_iterations: Optional[int] = Field(5, ge=1, le=10, description="最大爬取迭代次数")
    
    @validator('ai_skip_threshold')
    def validate_ai_skip_threshold(cls, v):
        """验证AI跳过阈值"""
        if v is not None and not 0.1 <= v <= 0.8:
            raise ValueError('AI跳过阈值必须在0.1到0.8之间')
        return v
    
    @validator('dns_concurrency')
    def validate_dns_concurrency(cls, v):
        """验证DNS并发数"""
        if v is not None and not 10 <= v <= 200:
            raise ValueError('DNS并发数必须在10到200之间')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "subdomain_discovery_enabled": True,
                "link_crawling_enabled": True,
                "third_party_identification_enabled": True,
                "content_capture_enabled": True,
                "ai_analysis_enabled": True,
                "max_subdomains": 100,
                "max_crawl_depth": 3,
                "max_pages_per_domain": 1000,
                "request_delay": 1000,
                "timeout": 30,
                "use_parallel_executor": True,
                "smart_prefilter_enabled": True,
                "dns_concurrency": 100,
                "ai_skip_threshold": 0.3,
                "multi_viewport_capture": False,
                "enable_aggressive_caching": False
            }
        }


class CreateTaskSchema(BaseModel):
    """创建任务Schema"""
    target_domain: str = Field(..., min_length=1, max_length=255, description="目标域名")
    task_name: Optional[str] = Field(None, max_length=100, description="任务名称")
    description: Optional[str] = Field(None, max_length=500, description="任务描述")
    config: TaskConfigSchema = Field(..., description="任务配置")
    
    @validator('target_domain')
    def validate_domain(cls, v):
        """验证域名格式"""
        import re
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        if not re.match(domain_pattern, v):
            raise ValueError('无效的域名格式')
        return v.lower()
    
    class Config:
        schema_extra = {
            "example": {
                "target_domain": "example.com",
                "task_name": "示例域名安全扫描",
                "description": "对example.com进行全面的安全扫描",
                "config": {
                    "use_parallel_executor": True,
                    "smart_prefilter_enabled": True,
                    "dns_concurrency": 100
                }
            }
        }


class TaskResponseSchema(BaseModel):
    """任务响应Schema"""
    id: str
    target_domain: str
    task_name: Optional[str]
    description: Optional[str]
    status: TaskStatus
    progress: int = Field(0, ge=0, le=100)
    config: Dict[str, Any]
    
    # 统计信息
    total_subdomains: int = 0
    total_pages_crawled: int = 0
    total_third_party_domains: int = 0
    total_violations: int = 0
    critical_violations: int = 0
    high_violations: int = 0
    medium_violations: int = 0
    low_violations: int = 0
    
    # 时间戳
    created_at: Optional[str]
    started_at: Optional[str] 
    completed_at: Optional[str]
    
    error_message: Optional[str]
    
    class Config:
        from_attributes = True


class TaskListResponseSchema(BaseModel):
    """任务列表响应Schema"""
    total: int
    items: list[TaskResponseSchema]
    skip: int
    limit: int


class PerformanceMetricsSchema(BaseModel):
    """性能指标Schema"""
    execution_time: float = Field(..., description="执行时间(秒)")
    subdomains_discovered: int = Field(..., description="发现的子域名数量")
    pages_crawled: int = Field(..., description="爬取的页面数量")
    ai_calls_made: int = Field(..., description="AI调用次数")
    ai_calls_skipped: int = Field(..., description="AI跳过次数")
    cost_saved: float = Field(..., description="节省的成本")
    
    @property
    def ai_skip_rate(self) -> float:
        """AI跳过率"""
        total = self.ai_calls_made + self.ai_calls_skipped
        return (self.ai_calls_skipped / total * 100) if total > 0 else 0
    
    @property 
    def efficiency_score(self) -> float:
        """效率评分"""
        # 基于执行时间、AI跳过率等计算效率评分
        time_score = max(0, 100 - self.execution_time * 2)  # 执行时间越短分数越高
        ai_efficiency = self.ai_skip_rate  # AI跳过率越高效率越高
        return (time_score + ai_efficiency) / 2


class TaskConfigPresetSchema(BaseModel):
    """任务配置预设Schema"""
    name: str = Field(..., description="预设名称")
    description: str = Field(..., description="预设描述")
    config: TaskConfigSchema = Field(..., description="配置内容")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "快速扫描",
                "description": "适合日常安全检查的快速扫描配置",
                "config": {
                    "use_parallel_executor": True,
                    "smart_prefilter_enabled": True,
                    "dns_concurrency": 50,
                    "ai_skip_threshold": 0.2,
                    "max_subdomains": 50,
                    "max_crawl_depth": 2
                }
            }
        }


# 预定义配置模板
TASK_CONFIG_PRESETS = {
    "quick": TaskConfigPresetSchema(
        name="快速扫描",
        description="适合日常安全检查，5分钟内完成",
        config=TaskConfigSchema(
            subdomain_discovery_enabled=True,
            link_crawling_enabled=True,
            third_party_identification_enabled=True,
            content_capture_enabled=True,
            ai_analysis_enabled=True,
            max_subdomains=50,
            max_crawl_depth=2,
            max_pages_per_domain=200,
            request_delay=1000,
            timeout=30,
            use_parallel_executor=True,
            smart_prefilter_enabled=True,
            dns_concurrency=50,
            ai_skip_threshold=0.2,
            multi_viewport_capture=False,
            enable_aggressive_caching=True,
            certificate_discovery_enabled=True,
            passive_dns_enabled=False,
            max_concurrent_ai_calls=3,
            batch_size=10,
            screenshot_optimization=True,
            max_crawl_iterations=5
        )
    ),
    
    "standard": TaskConfigPresetSchema(
        name="标准扫描", 
        description="平衡速度和准确性，15分钟内完成",
        config=TaskConfigSchema(
            subdomain_discovery_enabled=True,
            link_crawling_enabled=True,
            third_party_identification_enabled=True,
            content_capture_enabled=True,
            ai_analysis_enabled=True,
            max_subdomains=100,
            max_crawl_depth=3,
            max_pages_per_domain=1000,
            request_delay=1000,
            timeout=30,
            use_parallel_executor=True,
            smart_prefilter_enabled=True,
            dns_concurrency=100,
            ai_skip_threshold=0.3,
            multi_viewport_capture=False,
            enable_aggressive_caching=False,
            certificate_discovery_enabled=True,
            passive_dns_enabled=False,
            max_concurrent_ai_calls=3,
            batch_size=10,
            screenshot_optimization=True,
            max_crawl_iterations=5
        )
    ),
    
    "deep": TaskConfigPresetSchema(
        name="深度扫描",
        description="全面深度扫描，30分钟内完成",
        config=TaskConfigSchema(
            subdomain_discovery_enabled=True,
            link_crawling_enabled=True,
            third_party_identification_enabled=True,
            content_capture_enabled=True,
            ai_analysis_enabled=True,
            max_subdomains=500,
            max_crawl_depth=5,
            max_pages_per_domain=5000,
            request_delay=1000,
            timeout=30,
            use_parallel_executor=True,
            smart_prefilter_enabled=True,
            dns_concurrency=150,
            ai_skip_threshold=0.4,
            multi_viewport_capture=True,
            enable_aggressive_caching=False,
            certificate_discovery_enabled=True,
            passive_dns_enabled=False,
            max_concurrent_ai_calls=3,
            batch_size=10,
            screenshot_optimization=True,
            max_crawl_iterations=8
        )
    ),
    
    "cost_optimized": TaskConfigPresetSchema(
        name="成本优化",
        description="最大化成本节省，适合大批量扫描",
        config=TaskConfigSchema(
            subdomain_discovery_enabled=True,
            link_crawling_enabled=True,
            third_party_identification_enabled=True,
            content_capture_enabled=True,
            ai_analysis_enabled=True,
            max_subdomains=200,
            max_crawl_depth=3,
            max_pages_per_domain=1000,
            request_delay=1000,
            timeout=30,
            use_parallel_executor=True,
            smart_prefilter_enabled=True,
            dns_concurrency=100,
            ai_skip_threshold=0.1,  # 最激进的AI跳过
            multi_viewport_capture=False,
            enable_aggressive_caching=True,
            certificate_discovery_enabled=True,
            passive_dns_enabled=False,
            max_concurrent_ai_calls=2,  # 减少并发AI调用
            batch_size=20,  # 更大的批处理
            screenshot_optimization=True,
            max_crawl_iterations=5
        )
    )
}