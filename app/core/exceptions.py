from typing import Any, Dict, Optional


class CustomException(Exception):
    """自定义异常基类"""
    
    def __init__(
        self,
        status_code: int,
        error_code: str,
        detail: str,
        headers: Optional[Dict[str, Any]] = None
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail
        self.headers = headers or {}


class AuthenticationError(CustomException):
    """认证错误"""
    
    def __init__(self, detail: str = "认证失败"):
        super().__init__(
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            detail=detail
        )


class AuthorizationError(CustomException):
    """授权错误"""
    
    def __init__(self, detail: str = "权限不足"):
        super().__init__(
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
            detail=detail
        )


class ValidationError(CustomException):
    """验证错误"""
    
    def __init__(self, detail: str = "数据验证失败"):
        super().__init__(
            status_code=422,
            error_code="VALIDATION_ERROR",
            detail=detail
        )


class NotFoundError(CustomException):
    """资源未找到错误"""
    
    def __init__(self, detail: str = "资源未找到"):
        super().__init__(
            status_code=404,
            error_code="NOT_FOUND_ERROR",
            detail=detail
        )


class ConflictError(CustomException):
    """冲突错误"""
    
    def __init__(self, detail: str = "资源冲突"):
        super().__init__(
            status_code=409,
            error_code="CONFLICT_ERROR",
            detail=detail
        )


class RateLimitError(CustomException):
    """频率限制错误"""
    
    def __init__(self, detail: str = "请求频率过高"):
        super().__init__(
            status_code=429,
            error_code="RATE_LIMIT_ERROR",
            detail=detail
        )


class InternalServerError(CustomException):
    """内部服务器错误"""
    
    def __init__(self, detail: str = "内部服务器错误"):
        super().__init__(
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
            detail=detail
        )


class TaskError(CustomException):
    """任务执行错误"""
    
    def __init__(self, detail: str = "任务执行失败"):
        super().__init__(
            status_code=500,
            error_code="TASK_ERROR",
            detail=detail
        )


class AIServiceError(CustomException):
    """AI服务错误"""
    
    def __init__(self, detail: str = "AI服务调用失败"):
        super().__init__(
            status_code=503,
            error_code="AI_SERVICE_ERROR",
            detail=detail
        )


class DomainValidationError(ValidationError):
    """域名验证错误"""
    
    def __init__(self, detail: str = "无效的域名格式"):
        super().__init__(detail=detail)


class ConfigurationError(CustomException):
    """配置错误"""
    
    def __init__(self, detail: str = "配置错误"):
        super().__init__(
            status_code=500,
            error_code="CONFIGURATION_ERROR",
            detail=detail
        )