from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.core.database import get_db
from app.core.dependencies import get_current_user, rate_limit
from app.core.exceptions import AuthenticationError, ValidationError, ConflictError
from app.core.logging import logger
from app.core.security import security_validator
from app.schemas.auth import (
    LoginRequest, LoginResponse, UserCreate, UserResponse,
    RefreshTokenRequest, TokenResponse, UserUpdate, UserChangePassword,
    PasswordStrengthResponse
)
from app.services.user_service import AuthService, UserService
from app.models.user import User

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit(5, 300))  # 5次/5分钟
) -> UserResponse:
    """用户注册"""
    try:
        user_service = UserService(db)
        user = await user_service.create_user(user_data)
        
        logger.info(f"用户注册成功: {user.username}")
        return UserResponse.from_orm(user)
        
    except (ValidationError, ConflictError) as e:
        logger.warning(f"用户注册失败: {e.detail}")
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail
        )
    except Exception as e:
        logger.error(f"用户注册异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit(10, 300))  # 10次/5分钟
) -> LoginResponse:
    """用户登录"""
    try:
        # 获取客户端信息
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        if "x-forwarded-for" in request.headers:
            ip_address = request.headers["x-forwarded-for"].split(",")[0].strip()
        
        auth_service = AuthService(db)
        login_result = await auth_service.login(
            login_data.username,
            login_data.password,
            ip_address,
            user_agent
        )
        
        logger.info(f"用户登录成功: {login_data.username} from {ip_address}")
        return LoginResponse(
            access_token=login_result["access_token"],
            refresh_token=login_result["refresh_token"],
            token_type=login_result["token_type"],
            expires_in=login_result["expires_in"],
            user=UserResponse.from_orm(login_result["user"])
        )
        
    except AuthenticationError as e:
        logger.warning(f"用户登录失败: {e.detail} - {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.detail,
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"用户登录异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """刷新访问令牌"""
    try:
        auth_service = AuthService(db)
        token_result = await auth_service.refresh_access_token(refresh_data.refresh_token)
        
        logger.info("访问令牌刷新成功")
        return TokenResponse(**token_result)
        
    except AuthenticationError as e:
        logger.warning(f"令牌刷新失败: {e.detail}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.detail,
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"令牌刷新异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="令牌刷新失败"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """获取当前用户信息"""
    return UserResponse.from_orm(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """更新当前用户信息"""
    try:
        user_service = UserService(db)
        updated_user = await user_service.update_user(str(current_user.id), user_data)
        
        logger.info(f"用户信息更新成功: {current_user.username}")
        return UserResponse.from_orm(updated_user)
        
    except (ValidationError, ConflictError) as e:
        logger.warning(f"用户信息更新失败: {e.detail}")
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail
        )
    except Exception as e:
        logger.error(f"用户信息更新异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新失败，请稍后重试"
        )


@router.post("/change-password")
async def change_password(
    password_data: UserChangePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """修改密码"""
    try:
        user_service = UserService(db)
        await user_service.change_password(str(current_user.id), password_data)
        
        logger.info(f"用户密码修改成功: {current_user.username}")
        return {"message": "密码修改成功"}
        
    except AuthenticationError as e:
        logger.warning(f"密码修改失败: {e.detail} - {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.detail
        )
    except Exception as e:
        logger.error(f"密码修改异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码修改失败，请稍后重试"
        )


@router.post("/logout")
async def logout() -> dict:
    """用户登出"""
    # JWT是无状态的，客户端删除token即可
    # 如果需要黑名单功能，可以在这里实现
    logger.info("用户登出")
    return {"message": "登出成功"}


@router.post("/check-password-strength", response_model=PasswordStrengthResponse)
async def check_password_strength(
    password: str
) -> PasswordStrengthResponse:
    """检查密码强度"""
    result = security_validator.validate_password_strength(password)
    return PasswordStrengthResponse(**result)


@router.get("/validate-username/{username}")
async def validate_username(
    username: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """验证用户名可用性"""
    try:
        # 验证用户名格式
        validation_result = security_validator.validate_username(username)
        if not validation_result["is_valid"]:
            return {
                "is_available": False,
                "reason": "格式不符合要求",
                "errors": validation_result["errors"]
            }
        
        # 检查用户名是否已存在
        user_service = UserService(db)
        existing_user = await user_service.get_user_by_username(username)
        
        if existing_user:
            return {
                "is_available": False,
                "reason": "用户名已存在"
            }
        
        return {
            "is_available": True,
            "reason": "用户名可用"
        }
        
    except Exception as e:
        logger.error(f"验证用户名异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="验证失败"
        )


@router.get("/validate-email/{email}")
async def validate_email(
    email: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """验证邮箱可用性"""
    try:
        # 验证邮箱格式
        if not security_validator.validate_email(email):
            return {
                "is_available": False,
                "reason": "邮箱格式不正确"
            }
        
        # 检查邮箱是否已存在
        user_service = UserService(db)
        existing_user = await user_service.get_user_by_email(email)
        
        if existing_user:
            return {
                "is_available": False,
                "reason": "邮箱已被使用"
            }
        
        return {
            "is_available": True,
            "reason": "邮箱可用"
        }
        
    except Exception as e:
        logger.error(f"验证邮箱异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="验证失败"
        )