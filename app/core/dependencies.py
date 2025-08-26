from fastapi import Depends, HTTPException, status, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import WebSocket, WebSocketException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import asyncio
from datetime import datetime, timedelta
from jose import JWTError

from app.core.database import get_db
from app.core.security import token_manager, rate_limiter
from app.core.exceptions import AuthenticationError, AuthorizationError, RateLimitError
from app.core.logging import logger
from app.models.user import User, UserRole
from app.models.system import LoginAttempt

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """获取当前用户"""
    if not credentials:
        raise AuthenticationError("缺少认证令牌")
    
    try:
        # 验证令牌
        payload = token_manager.verify_token(credentials.credentials, "access")
        user_id = payload.get("sub")
        
        if user_id is None:
            raise AuthenticationError("令牌中缺少用户信息")
        
        # 查询用户
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user is None:
            raise AuthenticationError("用户不存在")
        
        if not user.is_active:
            raise AuthenticationError("用户账户已被禁用")
        
        if user.is_locked:
            raise AuthenticationError("用户账户已被锁定")
        
        return user
        
    except Exception as e:
        logger.warning(f"认证失败: {str(e)}")
        raise AuthenticationError("认证失败")


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """获取当前用户（可选）"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except:
        return None


async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取管理员用户"""
    if not current_user.is_admin:
        raise AuthorizationError("需要管理员权限")
    
    return current_user


class PermissionChecker:
    """权限检查器"""
    
    def __init__(self, required_permissions: List[str]):
        self.required_permissions = required_permissions
    
    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        """检查用户权限"""
        # 管理员拥有所有权限
        if current_user.is_admin:
            return current_user
        
        # TODO: 实现详细的权限检查逻辑
        # 这里可以查询 UserPermission 表来检查具体权限
        
        # 暂时简化实现：普通用户只能访问基本功能
        basic_permissions = [
            "task:create", "task:read", "task:update", "task:delete",
            "config:ai_read", "config:ai_update",
            "report:read"
        ]
        
        for permission in self.required_permissions:
            if permission not in basic_permissions:
                raise AuthorizationError(f"缺少权限: {permission}")
        
        return current_user


def require_permissions(*permissions: str):
    """权限装饰器"""
    return PermissionChecker(list(permissions))


class RateLimitChecker:
    """速率限制检查器"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def __call__(self, request: Request) -> None:
        """检查速率限制"""
        # 获取客户端IP
        client_ip = request.client.host
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        
        # 检查速率限制
        if not rate_limiter.is_allowed(
            f"ip:{client_ip}", 
            self.max_requests, 
            self.window_seconds
        ):
            remaining = rate_limiter.get_remaining_attempts(
                f"ip:{client_ip}", 
                self.max_requests, 
                self.window_seconds
            )
            raise RateLimitError(f"请求过于频繁，请稍后重试。剩余次数: {remaining}")


def rate_limit(max_requests: int, window_seconds: int):
    """速率限制装饰器"""
    return RateLimitChecker(max_requests, window_seconds)


async def log_login_attempt(
    username: str,
    ip_address: str,
    user_agent: str,
    is_successful: bool,
    failure_reason: Optional[str] = None,
    user_id: Optional[str] = None,
    db: AsyncSession = None
):
    """记录登录尝试"""
    if db is None:
        return
    
    try:
        login_attempt = LoginAttempt(
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            is_successful=is_successful,
            failure_reason=failure_reason,
            attempted_at=datetime.utcnow()
        )
        
        db.add(login_attempt)
        await db.commit()
        
        logger.info(
            f"登录尝试记录: {username} from {ip_address}, 成功: {is_successful}",
            extra={
                "username": username,
                "ip_address": ip_address,
                "is_successful": is_successful,
                "failure_reason": failure_reason
            }
        )
        
    except Exception as e:
        logger.error(f"记录登录尝试失败: {e}")
        await db.rollback()


async def check_user_lockout(username: str, db: AsyncSession) -> bool:
    """检查用户是否被锁定"""
    from app.core.config import settings
    
    # 查询最近的失败登录尝试
    stmt = select(LoginAttempt).where(
        LoginAttempt.username == username,
        LoginAttempt.is_successful == False,
        LoginAttempt.attempted_at > datetime.utcnow() - timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
    ).order_by(LoginAttempt.attempted_at.desc()).limit(settings.MAX_LOGIN_ATTEMPTS)
    
    result = await db.execute(stmt)
    failed_attempts = result.scalars().all()
    
    if len(failed_attempts) >= settings.MAX_LOGIN_ATTEMPTS:
        return True
    
    return False


async def reset_login_attempts(username: str, db: AsyncSession):
    """重置登录尝试计数"""
    # 这里可以选择删除失败记录或标记为已重置
    # 为了保持审计日志，我们选择不删除记录
    pass


class DataOwnershipChecker:
    """数据所有权检查器"""
    
    def __init__(self, model_class, id_field: str = "id"):
        self.model_class = model_class
        self.id_field = id_field
    
    async def __call__(
        self,
        resource_id: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> bool:
        """检查用户是否拥有资源"""
        # 管理员可以访问所有资源
        if current_user.is_admin:
            return True
        
        # 查询资源
        stmt = select(self.model_class).where(
            getattr(self.model_class, self.id_field) == resource_id
        )
        result = await db.execute(stmt)
        resource = result.scalar_one_or_none()
        
        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="资源不存在"
            )
        
        # 检查所有权
        if hasattr(resource, 'user_id') and resource.user_id != current_user.id:
            raise AuthorizationError("无权访问此资源")
        
        return True


def require_ownership(model_class, id_field: str = "id"):
    """资源所有权检查装饰器"""
    return DataOwnershipChecker(model_class, id_field)


async def get_current_user_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None, alias="token")
) -> User:
    """获取当前WebSocket用户（用于WebSocket连接）"""
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
    
    try:
        # 验证Token
        payload = token_manager.verify_token(token)
        user_id: str = payload.get("sub")
        
        if user_id is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        
        # 查询用户
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            stmt = select(User).where(User.id == user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user is None or not user.is_active:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found or inactive")
                raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="User not found or inactive")
            
            return user
    
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
    except Exception as e:
        logger.error(f"WebSocket用户认证失败: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Authentication failed")
        raise WebSocketException(code=status.WS_1011_INTERNAL_ERROR, reason="Authentication failed")