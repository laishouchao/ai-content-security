from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import asyncio

from app.models.user import User, UserAIConfig, UserRole
from app.models.system import LoginAttempt
from app.schemas.auth import (
    UserCreate, UserUpdate, UserChangePassword, UserAdminUpdate,
    AIConfigRequest, UserListRequest
)
from app.core.security import (
    password_manager, token_manager, data_encryption, security_validator
)
from app.core.exceptions import (
    ValidationError, ConflictError, NotFoundError, AuthenticationError
)
from app.core.config import settings
from app.core.logging import logger


class UserService:
    """用户服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_user(self, user_data: UserCreate) -> User:
        """创建用户"""
        # 验证用户名
        username_validation = security_validator.validate_username(user_data.username)
        if not username_validation["is_valid"]:
            raise ValidationError(f"用户名不符合要求: {', '.join(username_validation['errors'])}")
        
        # 检查用户名是否已存在
        stmt = select(User).where(User.username == user_data.username)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ConflictError("用户名已存在")
        
        # 检查邮箱是否已存在
        stmt = select(User).where(User.email == user_data.email)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ConflictError("邮箱已存在")
        
        # 创建用户
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=password_manager.hash_password(user_data.password),
            full_name=user_data.full_name,
            bio=user_data.bio,
            role=UserRole.ADMIN,
            is_active=True
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"用户创建成功: {user.username} ({user.id})")
        return user
    
    async def authenticate_user(
        self, 
        username: str, 
        password: str,
        ip_address: str = "unknown",
        user_agent: str = "unknown"
    ) -> Optional[User]:
        """验证用户"""
        from app.core.dependencies import check_user_lockout, log_login_attempt
        
        # 检查用户是否被锁定
        if await check_user_lockout(username, self.db):
            await log_login_attempt(
                username, ip_address, user_agent, False, "账户已锁定", None, self.db
            )
            raise AuthenticationError("账户已被锁定，请稍后重试")
        
        # 查找用户（支持用户名或邮箱登录）
        stmt = select(User).where(
            or_(User.username == username, User.email == username)
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            await log_login_attempt(
                username, ip_address, user_agent, False, "用户不存在", None, self.db
            )
            raise AuthenticationError("用户名或密码错误")
        
        if user.is_active is not True:
            await log_login_attempt(
                username, ip_address, user_agent, False, "账户已禁用", str(user.id), self.db
            )
            raise AuthenticationError("账户已被禁用")
        
        if user.is_locked is True:
            await log_login_attempt(
                username, ip_address, user_agent, False, "账户已锁定", str(user.id), self.db
            )
            raise AuthenticationError("账户已被锁定")
        
        # 验证密码
        if not password_manager.verify_password(password, user.password_hash):
            await log_login_attempt(
                username, ip_address, user_agent, False, "密码错误", str(user.id), self.db
            )
            raise AuthenticationError("用户名或密码错误")
        
        # 更新最后登录时间
        user.last_login = datetime.utcnow()
        await self.db.commit()
        
        await log_login_attempt(
            username, ip_address, user_agent, True, None, str(user.id), self.db
        )
        
        logger.info(f"用户登录成功: {user.username} from {ip_address}")
        return user
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def update_user(self, user_id: str, user_data: UserUpdate) -> User:
        """更新用户信息"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        
        # 检查邮箱是否已被其他用户使用
        if user_data.email and user_data.email != user.email:
            stmt = select(User).where(
                and_(User.email == user_data.email, User.id != user_id)
            )
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                raise ConflictError("邮箱已被其他用户使用")
        
        # 更新字段
        for field, value in user_data.dict(exclude_unset=True).items():
            setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"用户信息更新: {user.username} ({user.id})")
        return user
    
    async def change_password(self, user_id: str, password_data: UserChangePassword) -> bool:
        """修改密码"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        
        # 验证当前密码
        if not password_manager.verify_password(password_data.current_password, user.password_hash):
            raise AuthenticationError("当前密码错误")
        
        # 更新密码
        user.password_hash = password_manager.hash_password(password_data.new_password)
        user.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        logger.info(f"用户密码修改: {user.username} ({user.id})")
        return True
    
    async def admin_update_user(self, user_id: str, user_data: UserAdminUpdate) -> User:
        """管理员更新用户"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        
        # 检查邮箱是否已被其他用户使用
        if user_data.email and user_data.email != user.email:
            stmt = select(User).where(
                and_(User.email == user_data.email, User.id != user_id)
            )
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                raise ConflictError("邮箱已被其他用户使用")
        
        # 更新字段
        for field, value in user_data.dict(exclude_unset=True).items():
            setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"管理员更新用户: {user.username} ({user.id})")
        return user
    
    async def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        
        await self.db.delete(user)
        await self.db.commit()
        
        logger.info(f"用户已删除: {user.username} ({user.id})")
        return True
    
    async def get_users(self, request: UserListRequest) -> Dict[str, Any]:
        """获取用户列表"""
        # 构建查询条件
        conditions = []
        
        if request.role:
            conditions.append(User.role == request.role)
        
        if request.is_active is not None:
            conditions.append(User.is_active == request.is_active)
        
        if request.search:
            search_term = f"%{request.search}%"
            conditions.append(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term),
                    User.full_name.ilike(search_term)
                )
            )
        
        # 查询总数
        count_stmt = select(func.count(User.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar()
        
        # 查询用户列表
        stmt = select(User)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        stmt = stmt.order_by(User.created_at.desc()).offset(request.skip).limit(request.limit)
        
        result = await self.db.execute(stmt)
        users = result.scalars().all()
        
        return {
            "total": total,
            "items": users,
            "skip": request.skip,
            "limit": request.limit
        }


class AIConfigService:
    """AI配置服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_ai_config(self, user_id: str) -> Optional[UserAIConfig]:
        """获取用户AI配置"""
        stmt = select(UserAIConfig).where(UserAIConfig.user_id == user_id)
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()
        
        # 解密API密钥
        if config and config.openai_api_key:
            try:
                config.openai_api_key = data_encryption.decrypt_data(config.openai_api_key)
            except Exception as e:
                logger.warning(f"解密API密钥失败: {e}")
                config.openai_api_key = None
        
        return config
    
    async def create_or_update_ai_config(self, user_id: str, config_data: AIConfigRequest) -> UserAIConfig:
        """创建或更新AI配置"""
        # 查找现有配置
        stmt = select(UserAIConfig).where(UserAIConfig.user_id == user_id)
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()
        
        # 加密API密钥
        encrypted_api_key = None
        if config_data.openai_api_key:
            encrypted_api_key = data_encryption.encrypt_data(config_data.openai_api_key)
        
        if config:
            # 更新现有配置
            config_dict = config_data.dict(exclude_unset=True)
            for field, value in config_dict.items():
                if field == "openai_api_key":
                    if value:  # 只有在提供新密钥时才更新
                        setattr(config, field, encrypted_api_key)
                elif field == "ai_model_name":
                    # 映射ai_model_name到model_name
                    setattr(config, "model_name", value)
                elif field == "max_tokens":
                    # 将整数转换为字符串
                    setattr(config, field, str(value))
                elif field == "temperature":
                    # 将浮点数转换为字符串
                    setattr(config, field, str(value))
                elif field == "request_timeout":
                    # 将整数转换为字符串
                    setattr(config, field, str(value))
                elif field == "retry_count":
                    # 将整数转换为字符串
                    setattr(config, field, str(value))
                else:
                    setattr(config, field, value)
            
            config.updated_at = datetime.utcnow()
        else:
            # 创建新配置
            config_dict = config_data.dict(exclude={"openai_api_key", "ai_model_name"}, exclude_unset=True)
            # 手动映射ai_model_name字段
            if config_data.ai_model_name is not None:
                config_dict["model_name"] = config_data.ai_model_name
            
            # 将数值类型转换为字符串
            if "max_tokens" in config_dict:
                config_dict["max_tokens"] = str(config_dict["max_tokens"])
            if "temperature" in config_dict:
                config_dict["temperature"] = str(config_dict["temperature"])
            if "request_timeout" in config_dict:
                config_dict["request_timeout"] = str(config_dict["request_timeout"])
            if "retry_count" in config_dict:
                config_dict["retry_count"] = str(config_dict["retry_count"])
            
            # 确保所有数值字段都被转换为字符串
            # 这些字段在数据库中是字符串类型，但在请求模型中是数值类型
            numeric_fields = ["max_tokens", "temperature", "request_timeout", "retry_count"]
            for field in numeric_fields:
                if field in config_dict and not isinstance(config_dict[field], str):
                    config_dict[field] = str(config_dict[field])
            
            config = UserAIConfig(
                user_id=user_id,
                openai_api_key=encrypted_api_key,
                **config_dict
            )
            self.db.add(config)
        
        await self.db.commit()
        await self.db.refresh(config)
        
        logger.info(f"AI配置更新: 用户 {user_id}")
        return config
    
    async def delete_ai_config(self, user_id: str) -> bool:
        """删除AI配置"""
        stmt = select(UserAIConfig).where(UserAIConfig.user_id == user_id)
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()
        
        if not config:
            raise NotFoundError("AI配置不存在")
        
        await self.db.delete(config)
        await self.db.commit()
        
        logger.info(f"AI配置已删除: 用户 {user_id}")
        return True
    
    async def test_ai_config(self, user_id: str, test_message: str = "Hello") -> Dict[str, Any]:
        """测试AI配置"""
        config = await self.get_user_ai_config(user_id)
        if not config or not config.has_valid_config:
            raise ValidationError("AI配置不完整")
        
        try:
            # 使用AI分析引擎进行实际测试
            from app.engines.ai_analysis import AIAnalysisEngine
            
            # 临时任务ID用于测试
            test_task_id = f"test_{user_id}_{int(datetime.utcnow().timestamp())}"
            
            ai_engine = AIAnalysisEngine(test_task_id, config)
            test_result = await ai_engine.test_configuration()
            
            # 更新测试时间
            config.last_tested = datetime.utcnow()
            await self.db.commit()
            
            return {
                "is_successful": test_result["success"],
                "response_message": test_result["message"],
                "response_time": None,
                "ai_model_used": test_result["model"]  # 修复字段名，从"model"改为"ai_model_used"
            }
            
        except Exception as e:
            logger.error(f"AI配置测试失败: {e}")
            return {
                "is_successful": False,
                "error_message": str(e),
                "response_time": None,
                "ai_model_used": config.ai_model_name
            }


class AuthService:
    """认证服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)
    
    async def login(self, username: str, password: str, ip_address: str = "unknown", user_agent: str = "unknown") -> Dict[str, Any]:
        """用户登录"""
        user = await self.user_service.authenticate_user(username, password, ip_address, user_agent)
        
        # 生成令牌
        token_data = {"sub": user.id, "username": user.username, "role": user.role}
        access_token = token_manager.create_access_token(token_data)
        refresh_token = token_manager.create_refresh_token(token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user
        }
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """刷新访问令牌"""
        try:
            payload = token_manager.verify_token(refresh_token, "refresh")
            user_id = payload.get("sub")
            
            if not user_id:
                raise AuthenticationError("无效的刷新令牌")
            
            # 检查用户是否仍然有效
            user = await self.user_service.get_user_by_id(user_id)
            if not user or user.is_active is not True:
                raise AuthenticationError("用户账户无效")
            
            # 生成新的访问令牌
            token_data = {"sub": user.id, "username": user.username, "role": user.role}
            access_token = token_manager.create_access_token(token_data)
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
            
        except Exception as e:
            logger.warning(f"刷新令牌失败: {e}")
            raise AuthenticationError("刷新令牌失败")




















