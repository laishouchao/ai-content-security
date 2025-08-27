"""
缓存管理API
提供缓存清理、状态查询和诊断功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.dependencies import get_current_user
from app.core.cache_manager import cache_manager
from app.core.logging import logger
from app.models.user import User

router = APIRouter()


@router.get("/status", summary="获取缓存状态")
async def get_cache_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取缓存系统状态信息
    
    返回:
    - Redis连接状态
    - Celery任务统计
    - 孤立任务统计
    - 数据库任务统计
    """
    try:
        # 确保缓存管理器已初始化
        if not cache_manager.initialized:
            await cache_manager.initialize()
        
        status = await cache_manager.get_cache_status()
        
        return {
            'success': True,
            'data': status,
            'message': '缓存状态获取成功'
        }
        
    except Exception as e:
        logger.error(f"获取缓存状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缓存状态失败: {str(e)}")


@router.get("/celery-tasks", summary="获取Celery任务信息")
async def get_celery_tasks(
    show_orphaned_only: bool = Query(False, description="只显示孤立任务"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取Redis中的Celery任务信息
    
    参数:
    - show_orphaned_only: 是否只显示孤立任务
    """
    try:
        if not cache_manager.initialized:
            await cache_manager.initialize()
        
        if show_orphaned_only:
            tasks = await cache_manager.get_orphaned_celery_tasks()
            message = f"获取到 {len(tasks)} 个孤立的Celery任务"
        else:
            tasks = await cache_manager.get_celery_tasks_from_redis()
            message = f"获取到 {len(tasks)} 个Celery任务"
        
        return {
            'success': True,
            'data': {
                'tasks': tasks,
                'count': len(tasks),
                'orphaned_only': show_orphaned_only
            },
            'message': message
        }
        
    except Exception as e:
        logger.error(f"获取Celery任务信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Celery任务信息失败: {str(e)}")


@router.post("/cleanup/orphaned-tasks", summary="清理孤立的Celery任务")
async def cleanup_orphaned_tasks(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    清理Redis中孤立的Celery任务
    
    孤立任务是指在Redis中存在但在数据库中不存在的任务
    """
    try:
        if not cache_manager.initialized:
            await cache_manager.initialize()
        
        # 获取孤立任务信息
        orphaned_tasks = await cache_manager.get_orphaned_celery_tasks()
        orphaned_count = len(orphaned_tasks)
        
        if orphaned_count == 0:
            return {
                'success': True,
                'data': {
                    'cleaned_count': 0,
                    'orphaned_tasks': []
                },
                'message': '没有发现孤立的Celery任务'
            }
        
        # 执行清理
        cleaned_count = await cache_manager.cleanup_orphaned_celery_tasks()
        
        logger.info(f"用户 {current_user.username} 清理了 {cleaned_count} 个孤立的Celery任务")
        
        return {
            'success': True,
            'data': {
                'cleaned_count': cleaned_count,
                'orphaned_tasks': orphaned_tasks
            },
            'message': f'成功清理 {cleaned_count} 个孤立的Celery任务'
        }
        
    except Exception as e:
        logger.error(f"清理孤立Celery任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理孤立Celery任务失败: {str(e)}")


@router.post("/cleanup/expired-results", summary="清理过期的任务结果")
async def cleanup_expired_results(
    max_age_hours: int = Query(24, ge=1, le=168, description="最大保留时间（小时）"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    清理过期的任务结果
    
    参数:
    - max_age_hours: 任务结果最大保留时间（小时），默认24小时
    """
    try:
        if not cache_manager.initialized:
            await cache_manager.initialize()
        
        cleaned_count = await cache_manager.cleanup_expired_task_results(max_age_hours)
        
        logger.info(f"用户 {current_user.username} 清理了 {cleaned_count} 个过期任务结果")
        
        return {
            'success': True,
            'data': {
                'cleaned_count': cleaned_count,
                'max_age_hours': max_age_hours
            },
            'message': f'成功清理 {cleaned_count} 个过期任务结果'
        }
        
    except Exception as e:
        logger.error(f"清理过期任务结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理过期任务结果失败: {str(e)}")


@router.post("/cleanup/database-orphans", summary="清理数据库孤立记录")
async def cleanup_database_orphans(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    清理数据库中的孤立记录
    
    清理与不存在的扫描任务相关的记录
    """
    try:
        cleanup_stats = await cache_manager.cleanup_database_orphaned_records()
        
        total_cleaned = sum(cleanup_stats.values())
        
        logger.info(f"用户 {current_user.username} 清理了 {total_cleaned} 条数据库孤立记录")
        
        return {
            'success': True,
            'data': {
                'cleanup_stats': cleanup_stats,
                'total_cleaned': total_cleaned
            },
            'message': f'成功清理 {total_cleaned} 条数据库孤立记录'
        }
        
    except Exception as e:
        logger.error(f"清理数据库孤立记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理数据库孤立记录失败: {str(e)}")


@router.post("/cleanup/celery-queues", summary="清空所有Celery队列")
async def purge_celery_queues(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    清空所有Celery队列
    
    警告：这将清除所有等待执行的任务！
    """
    try:
        if not cache_manager.initialized:
            await cache_manager.initialize()
        
        cleaned_count = await cache_manager.purge_all_celery_queues()
        
        logger.warning(f"用户 {current_user.username} 清空了所有Celery队列，删除 {cleaned_count} 个键")
        
        return {
            'success': True,
            'data': {
                'cleaned_count': cleaned_count
            },
            'message': f'成功清空Celery队列，删除 {cleaned_count} 个Redis键'
        }
        
    except Exception as e:
        logger.error(f"清空Celery队列失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空Celery队列失败: {str(e)}")


@router.post("/cleanup/full", summary="执行完整缓存清理")
async def perform_full_cleanup(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    执行完整的缓存和数据清理
    
    包括：
    - 清理孤立的Celery任务
    - 清理过期的任务结果
    - 清理数据库孤立记录
    - 清理过期锁
    """
    try:
        if not cache_manager.initialized:
            await cache_manager.initialize()
        
        cleanup_results = await cache_manager.perform_full_cleanup()
        
        logger.info(f"用户 {current_user.username} 执行了完整缓存清理")
        
        return {
            'success': True,
            'data': cleanup_results,
            'message': '完整缓存清理执行完成'
        }
        
    except Exception as e:
        logger.error(f"执行完整缓存清理失败: {e}")
        raise HTTPException(status_code=500, detail=f"执行完整缓存清理失败: {str(e)}")


@router.post("/initialize", summary="初始化缓存管理器")
async def initialize_cache_manager(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    手动初始化缓存管理器
    
    用于重新建立Redis连接
    """
    try:
        await cache_manager.initialize()
        
        status = await cache_manager.get_cache_status()
        
        logger.info(f"用户 {current_user.username} 初始化了缓存管理器")
        
        return {
            'success': True,
            'data': {
                'initialized': cache_manager.initialized,
                'redis_connected': status['redis_connected']
            },
            'message': '缓存管理器初始化成功'
        }
        
    except Exception as e:
        logger.error(f"初始化缓存管理器失败: {e}")
        raise HTTPException(status_code=500, detail=f"初始化缓存管理器失败: {str(e)}")


@router.get("/health", summary="缓存健康检查")
async def cache_health_check() -> Dict[str, Any]:
    """
    缓存系统健康检查
    
    不需要认证，用于系统监控
    """
    try:
        if not cache_manager.initialized:
            await cache_manager.initialize()
        
        redis_connected = await cache_manager.is_connected()
        
        health_status = "healthy" if redis_connected else "unhealthy"
        
        return {
            'success': True,
            'data': {
                'status': health_status,
                'redis_connected': redis_connected,
                'manager_initialized': cache_manager.initialized,
                'timestamp': datetime.utcnow().isoformat()
            },
            'message': f'缓存系统状态: {health_status}'
        }
        
    except Exception as e:
        logger.error(f"缓存健康检查失败: {e}")
        return {
            'success': False,
            'data': {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            },
            'message': '缓存健康检查失败'
        }