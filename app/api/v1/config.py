from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_admin_user
from app.core.exceptions import AuthorizationError, ValidationError, NotFoundError
from app.core.logging import logger
from app.schemas.auth import (
    AIConfigRequest, AIConfigResponse, AIConfigTestRequest, AIConfigTestResponse
)
from app.services.user_service import AIConfigService
from app.models.user import User

router = APIRouter()


@router.get("/ai", response_model=AIConfigResponse)
async def get_ai_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> AIConfigResponse:
    """获取用户AI配置"""
    try:
        ai_service = AIConfigService(db)
        config = await ai_service.get_user_ai_config(str(current_user.id))
        
        if not config:
            # 返回空配置而不是默认配置
            return AIConfigResponse(
                id="",
                user_id=str(current_user.id),
                openai_base_url="",
                ai_model_name="",
                max_tokens=0,
                temperature=0.0,
                request_timeout=0,
                retry_count=0,
                enable_streaming=False,
                has_valid_config=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        
        logger.info(f"获取AI配置: 用户 {current_user.username}")
        # 手动构建响应以确保字段映射正确
        return AIConfigResponse(
            id=str(config.id),
            user_id=str(config.user_id),
            openai_base_url=str(config.openai_base_url),
            openai_organization=str(config.openai_organization) if config.openai_organization is not None else None,  # type: ignore
            ai_model_name=str(config.model_name),  # 映射model_name到ai_model_name
            max_tokens=config.max_tokens_int,
            temperature=config.temperature_float,
            system_prompt=str(config.system_prompt) if config.system_prompt is not None else None,  # type: ignore
            custom_prompt_template=str(config.custom_prompt_template) if config.custom_prompt_template is not None else None,  # type: ignore
            request_timeout=config.request_timeout_int,
            retry_count=config.retry_count_int,
            enable_streaming=bool(config.enable_streaming),
            has_valid_config=config.has_valid_config,
            created_at=config.created_at,  # type: ignore
            updated_at=config.updated_at,  # type: ignore
            last_tested=config.last_tested  # type: ignore
        )
        
    except Exception as e:
        logger.error(f"获取AI配置异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取AI配置失败"
        )


@router.put("/ai", response_model=AIConfigResponse)
async def update_ai_config(
    config_data: AIConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> AIConfigResponse:
    """更新用户AI配置"""
    try:
        ai_service = AIConfigService(db)
        config = await ai_service.create_or_update_ai_config(str(current_user.id), config_data)
        
        logger.info(f"AI配置更新成功: 用户 {current_user.username}")
        # 手动构建响应以确保字段映射正确
        return AIConfigResponse(
            id=str(config.id),
            user_id=str(config.user_id),
            openai_base_url=str(config.openai_base_url),
            openai_organization=str(config.openai_organization) if config.openai_organization is not None else None,  # type: ignore
            ai_model_name=str(config.model_name),  # 映射model_name到ai_model_name
            max_tokens=config.max_tokens_int,
            temperature=config.temperature_float,
            system_prompt=str(config.system_prompt) if config.system_prompt is not None else None,  # type: ignore
            custom_prompt_template=str(config.custom_prompt_template) if config.custom_prompt_template is not None else None,  # type: ignore
            request_timeout=config.request_timeout_int,
            retry_count=config.retry_count_int,
            enable_streaming=bool(config.enable_streaming),
            has_valid_config=config.has_valid_config,
            created_at=config.created_at,  # type: ignore
            updated_at=config.updated_at,  # type: ignore
            last_tested=config.last_tested  # type: ignore
        )
        
    except ValidationError as e:
        logger.warning(f"AI配置更新失败: {e.detail}")
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail
        )
    except Exception as e:
        logger.error(f"AI配置更新异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI配置更新失败"
        )


@router.delete("/ai")
async def delete_ai_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """删除用户AI配置"""
    try:
        ai_service = AIConfigService(db)
        await ai_service.delete_ai_config(str(current_user.id))
        
        logger.info(f"AI配置删除成功: 用户 {current_user.username}")
        return {"message": "AI配置删除成功"}
        
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.detail
        )
    except Exception as e:
        logger.error(f"AI配置删除异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI配置删除失败"
        )


@router.post("/ai/test", response_model=AIConfigTestResponse)
async def test_ai_config(
    test_data: AIConfigTestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> AIConfigTestResponse:
    """测试AI配置连接"""
    try:
        ai_service = AIConfigService(db)
        test_result = await ai_service.test_ai_config(
            str(current_user.id), 
            test_data.test_message or "Hello, this is a test message."
        )
        
        logger.info(f"AI配置测试: 用户 {current_user.username}, 结果: {test_result['is_successful']}")
        return AIConfigTestResponse(**test_result)
        
    except ValidationError as e:
        logger.warning(f"AI配置测试失败: {e.detail}")
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail
        )
    except Exception as e:
        logger.error(f"AI配置测试异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI配置测试失败"
        )


@router.get("/system")
async def get_system_config(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """获取系统配置（仅管理员）"""
    try:
        from app.core.config import settings
        
        # 返回系统配置（隐藏敏感信息）
        config = {
            "scan_limits": {
                "max_concurrent_tasks_per_user": settings.MAX_CONCURRENT_TASKS_PER_USER,
                "max_subdomains_per_task": settings.MAX_SUBDOMAINS_PER_TASK,
                "max_crawl_depth": settings.MAX_CRAWL_DEPTH,
                "task_timeout_hours": settings.TASK_TIMEOUT_HOURS
            },
            "ai_settings": {
                "default_model": settings.DEFAULT_AI_MODEL,
                "default_max_tokens": settings.DEFAULT_MAX_TOKENS,
                "default_temperature": settings.DEFAULT_TEMPERATURE,
                "request_timeout": settings.AI_REQUEST_TIMEOUT,
                "retry_count": settings.AI_RETRY_COUNT
            },
            "security": {
                "max_login_attempts": settings.MAX_LOGIN_ATTEMPTS,
                "lockout_duration_minutes": settings.LOCKOUT_DURATION_MINUTES,
                "rate_limit_per_minute": settings.RATE_LIMIT_PER_MINUTE,
                "access_token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES
            }
        }
        
        logger.info(f"管理员获取系统配置: {current_user.username}")
        return config
        
    except Exception as e:
        logger.error(f"获取系统配置异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取系统配置失败"
        )


@router.put("/system")
async def update_system_config(
    config_data: dict,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """更新系统配置（仅管理员）"""
    # TODO: 实现系统配置更新逻辑
    # 这里需要实现将配置保存到数据库的SystemConfig表中
    logger.info(f"管理员更新系统配置: {current_user.username}")
    return {"message": "系统配置更新成功"}


@router.get("/scan-defaults")
async def get_scan_defaults(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """获取扫描默认配置"""
    try:
        from app.core.config import settings
        
        defaults = {
            "max_subdomains": settings.MAX_SUBDOMAINS_PER_TASK,
            "max_crawl_depth": settings.MAX_CRAWL_DEPTH,
            "task_timeout_hours": settings.TASK_TIMEOUT_HOURS,
            "subdomain_discovery": {
                "enabled": True,
                "methods": ["dns_query", "certificate_transparency", "bruteforce"],
                "timeout_seconds": 300,
                "concurrent_requests": 10
            },
            "link_crawling": {
                "enabled": True,
                "max_pages_per_domain": 100,
                "timeout_per_page": 30,
                "respect_robots_txt": True
            },
            "content_capture": {
                "screenshot_enabled": True,
                "screenshot_format": "png",
                "viewport_width": settings.SCREENSHOT_VIEWPORT_WIDTH,
                "viewport_height": settings.SCREENSHOT_VIEWPORT_HEIGHT,
                "wait_for_load": 5
            },
            "ai_analysis": {
                "enabled": True,
                "confidence_threshold": 0.7,
                "max_content_length": 10000,
                "batch_size": 5
            }
        }
        
        logger.info(f"获取扫描默认配置: 用户 {current_user.username}")
        return defaults
        
    except Exception as e:
        logger.error(f"获取扫描默认配置异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取扫描配置失败"
        )


@router.put("/scan-defaults")
async def update_scan_defaults(
    config_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """更新扫描默认配置"""
    # TODO: 实现用户扫描配置保存逻辑
    # 可以保存在用户相关的配置表中
    logger.info(f"用户更新扫描配置: {current_user.username}")
    return {"message": "扫描配置更新成功"}