from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from app.models.user import UserRole


class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    full_name: Optional[str] = Field(None, max_length=255, description="真实姓名")
    bio: Optional[str] = Field(None, max_length=1000, description="个人简介")


class UserCreate(UserBase):
    """用户创建模型"""
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    
    @validator('password')
    def validate_password(cls, v):
        from app.core.security import security_validator
        result = security_validator.validate_password_strength(v)
        if not result["is_valid"]:
            raise ValueError(f"密码不符合要求: {', '.join(result['errors'])}")
        return v


class UserUpdate(BaseModel):
    """用户更新模型"""
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    full_name: Optional[str] = Field(None, max_length=255, description="真实姓名")
    bio: Optional[str] = Field(None, max_length=1000, description="个人简介")
    avatar_url: Optional[str] = Field(None, max_length=500, description="头像URL")


class UserChangePassword(BaseModel):
    """用户修改密码模型"""
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")
    
    @validator('new_password')
    def validate_password(cls, v):
        from app.core.security import security_validator
        result = security_validator.validate_password_strength(v)
        if not result["is_valid"]:
            raise ValueError(f"密码不符合要求: {', '.join(result['errors'])}")
        return v


class UserResponse(BaseModel):
    """用户响应模型"""
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")
    remember_me: bool = Field(False, description="记住我")


class LoginResponse(BaseModel):
    """登录响应模型"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field("bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")
    user: UserResponse = Field(..., description="用户信息")


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求模型"""
    refresh_token: str = Field(..., description="刷新令牌")


class TokenResponse(BaseModel):
    """令牌响应模型"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field("bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")


class PasswordResetRequest(BaseModel):
    """密码重置请求模型"""
    email: EmailStr = Field(..., description="邮箱地址")


class PasswordResetConfirm(BaseModel):
    """密码重置确认模型"""
    token: str = Field(..., description="重置令牌")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")
    
    @validator('new_password')
    def validate_password(cls, v):
        from app.core.security import security_validator
        result = security_validator.validate_password_strength(v)
        if not result["is_valid"]:
            raise ValueError(f"密码不符合要求: {', '.join(result['errors'])}")
        return v


class AIConfigRequest(BaseModel):
    """AI配置请求模型"""
    openai_api_key: Optional[str] = Field(None, description="OpenAI API密钥")
    openai_base_url: Optional[str] = Field("https://api.openai.com/v1", description="OpenAI API基础URL")
    openai_organization: Optional[str] = Field(None, description="OpenAI组织ID")
    ai_model_name: Optional[str] = Field("gpt-4-vision-preview", description="模型名称")
    max_tokens: Optional[int] = Field(4096, ge=1, le=32768, description="最大令牌数")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    system_prompt: Optional[str] = Field(None, max_length=2000, description="系统提示词")
    custom_prompt_template: Optional[str] = Field(None, max_length=5000, description="自定义提示词模板")
    request_timeout: Optional[int] = Field(120, ge=10, le=300, description="请求超时时间（秒）")
    retry_count: Optional[int] = Field(3, ge=1, le=10, description="重试次数")
    enable_streaming: Optional[bool] = Field(False, description="启用流式响应")


class AIConfigResponse(BaseModel):
    """AI配置响应模型"""
    id: str
    user_id: str
    openai_base_url: str
    openai_organization: Optional[str] = None
    ai_model_name: str
    max_tokens: int
    temperature: float
    system_prompt: Optional[str] = None
    custom_prompt_template: Optional[str] = None
    request_timeout: int
    retry_count: int
    enable_streaming: bool
    has_valid_config: bool
    created_at: datetime
    updated_at: datetime
    last_tested: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AIConfigTestRequest(BaseModel):
    """AI配置测试请求模型"""
    test_message: Optional[str] = Field("Hello, this is a test message.", description="测试消息")


class AIConfigTestResponse(BaseModel):
    """AI配置测试响应模型"""
    is_successful: bool = Field(..., description="是否成功")
    response_message: Optional[str] = Field(None, description="响应消息")
    error_message: Optional[str] = Field(None, description="错误消息")
    response_time: Optional[float] = Field(None, description="响应时间（秒）")
    ai_model_used: Optional[str] = Field(None, description="使用的模型")


class UserListRequest(BaseModel):
    """用户列表请求模型"""
    skip: int = Field(0, ge=0, description="跳过记录数")
    limit: int = Field(20, ge=1, le=100, description="限制记录数")
    role: Optional[str] = Field(None, description="角色过滤")
    is_active: Optional[bool] = Field(None, description="激活状态过滤")
    search: Optional[str] = Field(None, max_length=100, description="搜索关键词")


class UserListResponse(BaseModel):
    """用户列表响应模型"""
    total: int = Field(..., description="总记录数")
    items: List[UserResponse] = Field(..., description="用户列表")
    skip: int = Field(..., description="跳过记录数")
    limit: int = Field(..., description="限制记录数")


class UserAdminUpdate(BaseModel):
    """管理员用户更新模型"""
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    full_name: Optional[str] = Field(None, max_length=255, description="真实姓名")
    role: Optional[UserRole] = Field(None, description="用户角色")
    is_active: Optional[bool] = Field(None, description="激活状态")


class LoginAttemptResponse(BaseModel):
    """登录尝试响应模型"""
    id: str
    username: str
    ip_address: str
    is_successful: bool
    failure_reason: Optional[str] = None
    attempted_at: datetime
    
    class Config:
        from_attributes = True


class SecurityStatsResponse(BaseModel):
    """安全统计响应模型"""
    total_users: int = Field(..., description="总用户数")
    active_users: int = Field(..., description="活跃用户数")
    total_login_attempts: int = Field(..., description="总登录尝试数")
    successful_logins: int = Field(..., description="成功登录数")
    failed_logins: int = Field(..., description="失败登录数")
    locked_accounts: int = Field(..., description="锁定账户数")
    recent_login_attempts: List[LoginAttemptResponse] = Field(..., description="最近登录尝试")


class PasswordStrengthResponse(BaseModel):
    """密码强度响应模型"""
    is_valid: bool = Field(..., description="是否有效")
    score: int = Field(..., description="强度评分（0-100）")
    errors: List[str] = Field(..., description="错误列表")
    suggestions: List[str] = Field(..., description="建议列表")