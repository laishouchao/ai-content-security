from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanTaskCreateRequest(BaseModel):
    """创建扫描任务请求模型"""
    target_domain: str = Field(..., min_length=4, max_length=253, description="目标域名")
    task_name: Optional[str] = Field(None, max_length=255, description="任务名称")
    description: Optional[str] = Field(None, max_length=1000, description="任务描述")
    config: Optional[Dict[str, Any]] = Field(None, description="扫描配置")
    
    @validator('target_domain')
    def validate_domain(cls, v):
        import re
        # 基本域名格式验证
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        if not re.match(pattern, v):
            raise ValueError('无效的域名格式')
        return v.lower().strip()


class ScanTaskResponse(BaseModel):
    """扫描任务响应模型"""
    id: str
    user_id: str
    target_domain: str
    task_name: Optional[str] = None
    description: Optional[str] = None
    status: str
    progress: int
    total_subdomains: int = 0
    total_pages_crawled: int = 0
    total_third_party_domains: int = 0
    total_violations: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class TaskLogResponse(BaseModel):
    """任务日志响应模型"""
    id: str
    level: str
    module: str
    message: str
    created_at: datetime
    extra_data: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """任务列表响应模型"""
    total: int = Field(..., description="总记录数")
    items: List[ScanTaskResponse] = Field(..., description="任务列表")
    skip: int = Field(..., description="跳过记录数")
    limit: int = Field(..., description="限制记录数")


class TaskDetailResponse(BaseModel):
    """任务详情响应模型"""
    task: ScanTaskResponse
    logs: List[TaskLogResponse]
    subdomains: List[Dict[str, Any]] = []
    third_party_domains: List[Dict[str, Any]] = []
    violations: List[Dict[str, Any]] = []


class TaskStatsResponse(BaseModel):
    """任务统计响应模型"""
    task_id: str
    target_domain: str
    status: str
    progress: int
    total_subdomains: int
    total_pages_crawled: int
    total_third_party_domains: int
    total_violations: int
    execution_duration: int = Field(..., description="执行时长（秒）")