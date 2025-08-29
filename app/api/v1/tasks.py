from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import Any, List, Optional, Dict
from datetime import datetime
import uuid
from pydantic import BaseModel, Field, validator

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError, AuthorizationError, ValidationError
from app.core.logging import logger
from app.core.config import settings
from app.models.user import User
from app.models.task import ScanTask, TaskStatus, TaskLog
from app.schemas.task import (
    CreateTaskSchema, TaskResponseSchema, TaskListResponseSchema,
    TaskConfigPresetSchema, PerformanceMetricsSchema
)
from app.tasks.scan_tasks import scan_domain_task
from app.websocket.handlers import task_monitor

router = APIRouter()


def safe_get_value(obj, attr, default=None):
    """安全获取SQLAlchemy对象属性值"""
    try:
        value = getattr(obj, attr, default)
        # 对于Column对象，直接返回其实际值
        return value
    except Exception:
        return default


def convert_task_to_response(task) -> Dict[str, Any]:
    """将ScanTask对象转换为响应格式"""
    return {
        "id": str(safe_get_value(task, 'id')),
        "target_domain": str(safe_get_value(task, 'target_domain')),
        "task_name": safe_get_value(task, 'task_name'),
        "description": safe_get_value(task, 'description'),
        "status": safe_get_value(task, 'status'),
        "progress": int(safe_get_value(task, 'progress', 0)),
        "config": safe_get_value(task, 'config') or {},
        "total_subdomains": int(safe_get_value(task, 'total_subdomains', 0)),
        "total_pages_crawled": int(safe_get_value(task, 'total_pages_crawled', 0)),
        "total_domain_records": int(safe_get_value(task, 'total_domain_records', 0)),
        "total_violations": int(safe_get_value(task, 'total_violations', 0)),
        "critical_violations": int(safe_get_value(task, 'critical_violations', 0)),
        "high_violations": int(safe_get_value(task, 'high_violations', 0)),
        "medium_violations": int(safe_get_value(task, 'medium_violations', 0)),
        "low_violations": int(safe_get_value(task, 'low_violations', 0)),
        "created_at": task.created_at.isoformat() if safe_get_value(task, 'created_at') else None,
        "started_at": task.started_at.isoformat() if safe_get_value(task, 'started_at') else None,
        "completed_at": task.completed_at.isoformat() if safe_get_value(task, 'completed_at') else None,
        "error_message": safe_get_value(task, 'error_message')
    }


@router.get("/stats")
async def get_task_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取任务统计信息"""
    try:
        from app.services.statistics_service import get_statistics_service
        
        # 获取统计服务
        stats_service = await get_statistics_service(db)
        
        # 获取仪表板统计数据
        dashboard_stats = await stats_service.get_dashboard_stats(str(current_user.id))
        
        return {
            "success": True,
            "data": dashboard_stats
        }
        
    except Exception as e:
        logger.error(f"获取任务统计失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="获取任务统计失败"
        )


@router.post("")
async def create_scan_task(
    task_data: CreateTaskSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """创建扫描任务"""
    try:
        target_domain = task_data.target_domain
        config = task_data.config.dict()
        
        # 确保性能优化配置默认值
        performance_defaults = {
            'use_parallel_executor': True,
            'smart_prefilter_enabled': True,
            'dns_concurrency': 100,
            'ai_skip_threshold': 0.0,  # 不跳过任何AI分析
            'multi_viewport_capture': False
        }
        
        # 合并配置，优先使用用户提供的配置
        for key, default_value in performance_defaults.items():
            if key not in config:
                config[key] = default_value
        
        # 创建任务记录
        task_id = str(uuid.uuid4())
        task = ScanTask(
            id=task_id,
            user_id=current_user.id,
            target_domain=target_domain,
            task_name=task_data.task_name,
            description=task_data.description,
            status=TaskStatus.PENDING,
            config=config,
            created_at=datetime.utcnow()
        )
        
        # 使用Redis分布式锁确保任务创建的原子性
        from app.core.cache_manager import cache_manager
        from app.core.redis_lock import lock_manager
        
        # 初始化缓存管理器和锁管理器
        await cache_manager.initialize()
        await lock_manager.initialize()
        
        lock_key = f"task_creation_lock:{task_id}"
        
        try:
            # 获取分布式锁
            async with lock_manager.lock(lock_key, timeout=30, expire_time=60):
                # 添加任务到数据库
                db.add(task)
                await db.commit()
                await db.refresh(task)
                
                # 在Redis中设置任务创建标记，供Celery任务检查
                if cache_manager.redis_client:
                    task_creation_key = f"task_created:{task_id}"
                    await cache_manager.redis_client.setex(task_creation_key, 300, "created")  # 5分钟过期
                    logger.info(f"任务已创建并标记: {task_id} - {target_domain}")
                else:
                    logger.warning("缓存管理器未初始化，跳过Redis标记")
                
            # 发送任务创建通知
            await task_monitor.notify_task_created(task_id, str(current_user.id), target_domain)
            
            # 启动异步任务（使用延迟执行避免竞态条件）
            from celery_app import celery_app
            celery_app.send_task(
                "scan_domain_task", 
                args=[task_id, str(current_user.id), target_domain, config],
                countdown=2  # 延迟2秒执行，确保数据库事务完全提交
            )
            
            logger.info(f"扫描任务已创建: {task_id} - {target_domain}")
            
            # 构建响应
            task_response_data: Dict[str, Any] = convert_task_to_response(task)
            # 重写config字段为传入的config
            task_response_data["config"] = config
            task_response_data["progress"] = 0  # 初始状态进度为0
            
            response_data = TaskResponseSchema(**task_response_data)
            
            return {
                "success": True,
                "data": response_data,
                "message": "扫描任务已创建并开始执行"
            }
            
        except Exception as lock_error:
            await db.rollback()
            logger.error(f"获取任务创建锁失败: {lock_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="任务创建失败，请稍后重试"
            )
        finally:
            await cache_manager.close()
            await lock_manager.close()
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.detail
        )
    except Exception as e:
        logger.error(f"创建扫描任务失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="创建扫描任务失败"
        )


@router.get("")
async def get_scan_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取扫描任务列表"""
    try:
        # 构建查询条件
        conditions = [ScanTask.user_id == current_user.id]
        if status:
            conditions.append(ScanTask.status == status)
        
        # 查询总数
        count_query = select(func.count(ScanTask.id)).where(and_(*conditions))
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询任务列表
        query = select(ScanTask).where(
            and_(*conditions)
        ).order_by(ScanTask.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        # 转换为响应格式
        task_list = []
        for task in tasks:
            task_response_data: Dict[str, Any] = convert_task_to_response(task)
            task_response = TaskResponseSchema(**task_response_data)
            task_list.append(task_response)
        
        return {
            "success": True,
            "data": TaskListResponseSchema(
                total=total,
                items=task_list,
                skip=skip,
                limit=limit
            )
        }
        
    except Exception as e:
        logger.error(f"获取扫描任务列表失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="获取扫描任务列表失败"
        )


@router.get("/{task_id}")
async def get_scan_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取单个扫描任务详情"""
    try:
        # 查询任务
        query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        result = await db.execute(query)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 返回任务详情
        return {
            "success": True,
            "data": {
                "id": task.id,
                "target_domain": task.target_domain,
                "status": task.status,
                "progress": task.progress,
                "config": task.config,
                "created_at": task.created_at.isoformat() if task.created_at is not None else None,
                "started_at": task.started_at.isoformat() if task.started_at is not None else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at is not None else None,
                "statistics": {
                    "total_subdomains": task.total_subdomains,
                    "total_pages_crawled": task.total_pages_crawled,
                    "total_domain_records": task.total_domain_records,
                    "total_violations": task.total_violations,
                    "critical_violations": task.critical_violations,
                    "high_violations": task.high_violations,
                    "medium_violations": task.medium_violations,
                    "low_violations": task.low_violations
                },
                "total_subdomains": task.total_subdomains,
                "total_pages_crawled": task.total_pages_crawled,
                "total_domain_records": task.total_domain_records,
                "total_violations": task.total_violations,
                "critical_violations": task.critical_violations,
                "high_violations": task.high_violations,
                "medium_violations": task.medium_violations,
                "low_violations": task.low_violations,
                "error_message": task.error_message,
                "results_summary": task.results_summary
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取扫描任务详情失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="获取扫描任务详情失败"
        )


@router.get("/{task_id}/logs")
async def get_task_logs(
    task_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    level: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取任务日志"""
    try:
        # 验证任务存在且属于当前用户
        task_query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        task_result = await db.execute(task_query)
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 构建查询条件
        conditions = [TaskLog.task_id == task_id]
        if level:
            conditions.append(TaskLog.level == level.upper())
        
        # 查询总数
        count_query = select(func.count(TaskLog.id)).where(and_(*conditions))
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询日志列表
        query = select(TaskLog).where(
            and_(*conditions)
        ).order_by(TaskLog.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        # 转换为响应格式
        log_list = []
        for log in logs:
            log_data = {
                "id": log.id,
                "level": log.level,
                "module": log.module,
                "message": log.message,
                "extra_data": log.extra_data,
                "created_at": log.created_at.isoformat() if log.created_at is not None else None
            }
            log_list.append(log_data)
        
        return {
            "success": True,
            "data": {
                "items": log_list,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务日志失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="获取任务日志失败"
        )


@router.delete("/{task_id}")
async def delete_scan_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """删除扫描任务"""
    try:
        # 查询任务
        query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        result = await db.execute(query)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 检查任务是否可以删除（只能删除已完成、失败或取消的任务）
        if task.is_running:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法删除正在运行的任务，请先取消任务"
            )
        
        # 删除相关日志
        await db.execute(
            select(TaskLog).where(TaskLog.task_id == task_id)
        )
        
        # 删除任务
        await db.delete(task)
        await db.commit()
        
        logger.info(f"扫描任务已删除: {task_id}")
        
        return {
            "success": True,
            "message": "任务已成功删除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除扫描任务失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="删除扫描任务失败"
        )


@router.get("/config/presets")
async def get_config_presets(
    current_user: User = Depends(get_current_user)
) -> Any:
    """获取任务配置预设"""
    try:
        from app.schemas.task import TaskConfigSchema
        
        # 定义预设配置
        presets = [
            TaskConfigPresetSchema(
                name="快速扫描",
                description="适合日常安全检查的快速扫描配置，执行时间约5分钟",
                config=TaskConfigSchema(
                    subdomain_discovery_enabled=True,
                    link_crawling_enabled=True,
                    third_party_identification_enabled=True,
                    content_capture_enabled=True,
                    ai_analysis_enabled=True,
                    max_subdomains=200,
                    max_crawl_depth=2,
                    max_pages_per_domain=500,
                    request_delay=1000,
                    timeout=30,
                    use_parallel_executor=True,
                    smart_prefilter_enabled=True,
                    dns_concurrency=100,
                    ai_skip_threshold=0.0,  # 不跳过任何AI分析
                    max_crawl_iterations=3,
                    multi_viewport_capture=False,
                    enable_aggressive_caching=False,
                    certificate_discovery_enabled=True,
                    passive_dns_enabled=False,
                    max_concurrent_ai_calls=3,
                    batch_size=10,
                    screenshot_optimization=True
                )
            ),
            TaskConfigPresetSchema(
                name="标准扫描",
                description="平衡性能和准确性的标准扫描配置，执行时间约15分钟",
                config=TaskConfigSchema(
                    subdomain_discovery_enabled=True,
                    link_crawling_enabled=True,
                    third_party_identification_enabled=True,
                    content_capture_enabled=True,
                    ai_analysis_enabled=True,
                    max_subdomains=500,
                    max_crawl_depth=3,
                    max_pages_per_domain=1000,
                    request_delay=1000,
                    timeout=30,
                    use_parallel_executor=True,
                    smart_prefilter_enabled=True,
                    dns_concurrency=100,
                    ai_skip_threshold=0.0,  # 不跳过任何AI分析
                    max_crawl_iterations=5,
                    multi_viewport_capture=True,
                    enable_aggressive_caching=False,
                    certificate_discovery_enabled=True,
                    passive_dns_enabled=False,
                    max_concurrent_ai_calls=3,
                    batch_size=10,
                    screenshot_optimization=True
                )
            ),
            TaskConfigPresetSchema(
                name="深度扫描",
                description="全面扫描所有功能，适合安全审计，执行时间约30分钟",
                config=TaskConfigSchema(
                    subdomain_discovery_enabled=True,
                    link_crawling_enabled=True,
                    third_party_identification_enabled=True,
                    content_capture_enabled=True,
                    ai_analysis_enabled=True,
                    max_subdomains=1000,
                    max_crawl_depth=5,
                    max_pages_per_domain=5000,
                    request_delay=1000,
                    timeout=30,
                    use_parallel_executor=True,
                    smart_prefilter_enabled=True,
                    dns_concurrency=150,
                    ai_skip_threshold=0.0,  # 不跳过任何AI分析
                    max_crawl_iterations=8,
                    multi_viewport_capture=True,
                    enable_aggressive_caching=False,
                    certificate_discovery_enabled=True,
                    passive_dns_enabled=True,
                    max_concurrent_ai_calls=5,
                    batch_size=15,
                    screenshot_optimization=True
                )
            ),
            TaskConfigPresetSchema(
                name="成本优化",
                description="最大化节省AI调用成本的配置，适合大批量扫描",
                config=TaskConfigSchema(
                    subdomain_discovery_enabled=True,
                    link_crawling_enabled=True,
                    third_party_identification_enabled=True,
                    content_capture_enabled=True,
                    ai_analysis_enabled=True,
                    max_subdomains=300,
                    max_crawl_depth=2,
                    max_pages_per_domain=1000,
                    request_delay=1000,
                    timeout=30,
                    use_parallel_executor=True,
                    smart_prefilter_enabled=True,
                    dns_concurrency=100,
                    ai_skip_threshold=0.0,  # 用户要求全部进行扫描，不跳过AI分析
                    max_crawl_iterations=4,
                    multi_viewport_capture=False,
                    enable_aggressive_caching=True,
                    certificate_discovery_enabled=False,
                    passive_dns_enabled=False,
                    max_concurrent_ai_calls=2,
                    batch_size=20,
                    screenshot_optimization=False
                )
            )
        ]
        
        return {
            "success": True,
            "data": [preset.dict() for preset in presets]
        }
        
    except Exception as e:
        logger.error(f"获取配置预设失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取配置预设失败"
        )


@router.post("/{task_id}/performance-metrics")
async def get_task_performance_metrics(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取任务性能指标"""
    try:
        # 验证任务存在且属于当前用户
        query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        result = await db.execute(query)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 计算性能指标
        execution_time = 0
        started_at = safe_get_value(task, 'started_at')
        completed_at = safe_get_value(task, 'completed_at')
        if started_at and completed_at:
            execution_time = (completed_at - started_at).total_seconds()
        
        # 从任务配置和结果中提取性能数据
        config = safe_get_value(task, 'config') or {}
        results_summary = safe_get_value(task, 'results_summary') or {}
        ai_calls_made = results_summary.get('ai_calls_made', 0)
        ai_calls_skipped = results_summary.get('ai_calls_skipped', 0)
        
        # 估算成本节省（假设每次AI调用成本0.01美元）
        cost_saved = ai_calls_skipped * 0.01
        
        metrics = PerformanceMetricsSchema(
            execution_time=execution_time,
            subdomains_discovered=int(safe_get_value(task, 'total_subdomains', 0)),
            pages_crawled=int(safe_get_value(task, 'total_pages_crawled', 0)),
            ai_calls_made=ai_calls_made,
            ai_calls_skipped=ai_calls_skipped,
            cost_saved=cost_saved
        )
        
        return {
            "success": True,
            "data": {
                "metrics": metrics.dict(),
                "ai_skip_rate": f"{metrics.ai_skip_rate:.1f}%",
                "efficiency_score": f"{metrics.efficiency_score:.1f}",
                "performance_optimizations": {
                    "parallel_executor_enabled": config.get('use_parallel_executor', False),
                    "smart_prefilter_enabled": config.get('smart_prefilter_enabled', False),
                    "dns_concurrency": config.get('dns_concurrency', 50)
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务性能指标失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取任务性能指标失败"
        )


@router.post("/{task_id}/cancel")
async def cancel_scan_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """取消扫描任务"""
    try:
        # 查询任务
        query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        result = await db.execute(query)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 检查任务是否可以取消
        if task.is_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"任务状态为 {task.status}，无法取消"
            )
        
        # 更新任务状态
        from sqlalchemy import update
        stmt = update(ScanTask).where(ScanTask.id == task_id).values(
            status=TaskStatus.CANCELLED,
            completed_at=datetime.utcnow(),
            error_message="用户取消任务"
        )
        await db.execute(stmt)
        
        await db.commit()
        
        # 发送任务取消通知
        await task_monitor.notify_task_completed(
            task_id, 
            str(current_user.id), 
            TaskStatus.CANCELLED,
            {"message": "任务已被用户取消"}
        )
        
        # TODO: 取消Celery任务
        # 这里需要根据实际的Celery配置来取消任务
        
        logger.info(f"扫描任务已取消: {task_id}")
        
        return {
            "success": True,
            "message": "任务已成功取消"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消扫描任务失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="取消扫描任务失败"
        )


@router.post("/{task_id}/retry")
async def retry_scan_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """重试扫描任务"""
    try:
        # 查询任务
        query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        result = await db.execute(query)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 检查任务是否可以重试
        if task.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"任务状态为 {task.status}，无法重试"
            )
        
        # 重置任务状态和相关字段
        from sqlalchemy import update
        stmt = update(ScanTask).where(ScanTask.id == task_id).values(
            status=TaskStatus.PENDING,
            progress=0,
            started_at=None,
            completed_at=None,
            error_message=None,
            error_code=None,
            # 重置统计信息
            total_subdomains=0,
            total_pages_crawled=0,
            total_domain_records=0,
            total_violations=0,
            critical_violations=0,
            high_violations=0,
            medium_violations=0,
            low_violations=0
        )
        await db.execute(stmt)
        
        await db.commit()
        
        # 使用Redis分布式锁确保任务重启的原子性
        from app.core.cache_manager import cache_manager
        from app.core.redis_lock import lock_manager
        
        await cache_manager.initialize()
        await lock_manager.initialize()
        
        lock_key = f"task_retry_lock:{task_id}"
        
        try:
            async with lock_manager.lock(lock_key, timeout=30, expire_time=60):
                # 在Redis中设置任务创建标记
                if cache_manager.redis_client:
                    task_creation_key = f"task_created:{task_id}"
                    await cache_manager.redis_client.setex(task_creation_key, 300, "recreated")  # 5分钟过期
                
                # 发送任务创建通知
                await task_monitor.notify_task_created(task_id, str(current_user.id), str(task.target_domain))
                
                # 启动异步任务（使用延迟执行）
                from celery_app import celery_app
                celery_app.send_task(
                    "scan_domain_task", 
                    args=[task_id, str(current_user.id), task.target_domain, task.config],
                    countdown=2  # 延迟2秒执行
                )
                
                logger.info(f"扫描任务已重试: {task_id} - {task.target_domain}")
            
        finally:
            await cache_manager.close()
            await lock_manager.close()
        
        return {
            "success": True,
            "message": "任务已重新启动"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重试扫描任务失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="重试扫描任务失败"
        )


@router.get("/{task_id}/status")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取任务状态"""
    try:
        # 查询任务
        query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        result = await db.execute(query)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 返回任务状态信息
        return {
            "success": True,
            "data": {
                "task_id": task.id,
                "status": task.status,
                "progress": task.progress,
                "target_domain": task.target_domain,
                "created_at": task.created_at.isoformat() if task.created_at is not None else None,
                "started_at": task.started_at.isoformat() if task.started_at is not None else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at is not None else None,
                "statistics": {
                    "total_subdomains": task.total_subdomains,
                    "total_pages_crawled": task.total_pages_crawled,
                    "total_domain_records": task.total_domain_records,
                    "total_violations": task.total_violations,
                    "critical_violations": task.critical_violations,
                    "high_violations": task.high_violations,
                    "medium_violations": task.medium_violations,
                    "low_violations": task.low_violations
                },
                "error_message": task.error_message
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="获取任务状态失败"
        )


@router.get("/{task_id}/subdomains")
async def get_task_subdomains(
    task_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取任务的子域名记录"""
    try:
        # 验证任务存在且属于当前用户
        task_query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        task_result = await db.execute(task_query)
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 查询总数
        from app.models.domain import DomainRecord
        count_query = select(func.count(DomainRecord.id)).where(
            DomainRecord.task_id == task_id
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询子域名记录列表
        query = select(DomainRecord).where(
            DomainRecord.task_id == task_id
        ).order_by(DomainRecord.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        subdomains = result.scalars().all()
        
        # 转换为响应格式
        subdomain_list = []
        for subdomain in subdomains:
            subdomain_data = {
                "id": subdomain.id,
                "task_id": subdomain.task_id,
                "subdomain": subdomain.subdomain,
                "ip_address": subdomain.ip_address,
                "discovery_method": subdomain.discovery_method,
                "is_accessible": subdomain.is_accessible,
                "response_code": subdomain.response_code,
                "response_time": subdomain.response_time,
                "server_header": subdomain.server_header,
                "content_type": subdomain.content_type,
                "page_title": subdomain.page_title,
                "created_at": subdomain.created_at.isoformat() if subdomain.created_at is not None else None
            }
            subdomain_list.append(subdomain_data)
        
        return {
            "success": True,
            "data": {
                "items": subdomain_list,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取子域名记录失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="获取子域名记录失败"
        )


@router.get("/{task_id}/violations")
async def get_task_violations(
    task_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    risk_level: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取任务的违规记录"""
    try:
        # 验证任务存在且属于当前用户
        task_query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        task_result = await db.execute(task_query)
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 查询总数
        from app.models.task import ViolationRecord
        conditions = [ViolationRecord.task_id == task_id]
        if risk_level:
            conditions.append(ViolationRecord.risk_level == risk_level)
        
        count_query = select(func.count(ViolationRecord.id)).where(
            and_(*conditions)
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询违规记录列表
        query = select(ViolationRecord).where(
            and_(*conditions)
        ).order_by(ViolationRecord.detected_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        violations = result.scalars().all()
        
        # 转换为响应格式
        violation_list = []
        for violation in violations:
            violation_data = {
                "id": violation.id,
                "task_id": violation.task_id,
                "domain_id": violation.domain_id,
                "violation_type": violation.violation_type,
                "confidence_score": violation.confidence_score,
                "risk_level": violation.risk_level,
                "title": violation.title,
                "description": violation.description,
                "content_snippet": violation.content_snippet,
                "ai_analysis_result": violation.ai_analysis_result,
                "ai_model_used": violation.ai_model_used,
                "evidence": violation.evidence,
                "recommendations": violation.recommendations,
                "detected_at": violation.detected_at.isoformat() if violation.detected_at is not None else None
            }
            violation_list.append(violation_data)
        
        return {
            "success": True,
            "data": {
                "items": violation_list,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取违规记录失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="获取违规记录失败"
        )


@router.get("/{task_id}/domains")
async def get_task_domain_records(
    task_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    domain_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取任务的第三方域名记录"""
    try:
        # 验证任务存在且属于当前用户
        task_query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        task_result = await db.execute(task_query)
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 查询总数
        from app.models.domain import DomainRecord
        conditions = [DomainRecord.task_id == task_id]
        if domain_type:
            conditions.append(DomainRecord.domain_type == domain_type)
        if risk_level:
            conditions.append(DomainRecord.risk_level == risk_level)
        
        count_query = select(func.count(DomainRecord.id)).where(
            and_(*conditions)
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询第三方域名记录列表，包含违规记录
        from sqlalchemy.orm import selectinload
        from app.models.task import ViolationRecord
        
        query = select(DomainRecord).options(
            selectinload(DomainRecord.violations)
        ).where(
            and_(*conditions)
        ).order_by(DomainRecord.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        domains = result.scalars().all()
        
        # 转换为响应格式
        domain_list = []
        for domain in domains:
            domain_data = {
                "id": domain.id,
                "task_id": domain.task_id,
                "domain": domain.domain,
                "found_on_url": domain.found_on_url,
                "domain_type": domain.domain_type,
                "risk_level": domain.risk_level,
                "page_title": domain.page_title,
                "page_description": domain.page_description,
                "content_hash": domain.content_hash,
                "screenshot_path": domain.screenshot_path,
                "html_content_path": domain.html_content_path,
                "is_analyzed": domain.is_analyzed,
                "analysis_error": domain.analysis_error,
                "created_at": domain.created_at.isoformat() if domain.created_at is not None else None,
                "analyzed_at": domain.analyzed_at.isoformat() if domain.analyzed_at is not None else None,
                # 添加违规记录信息
                "violations": [
                    {
                        "id": violation.id,
                        "task_id": violation.task_id,
                        "domain_id": violation.domain_id,
                        "violation_type": violation.violation_type,
                        "confidence_score": violation.confidence_score,
                        "risk_level": violation.risk_level,
                        "title": violation.title,
                        "description": violation.description,
                        "content_snippet": violation.content_snippet,
                        "ai_analysis_result": violation.ai_analysis_result,
                        "ai_model_used": violation.ai_model_used,
                        "evidence": violation.evidence,
                        "recommendations": violation.recommendations,
                        "detected_at": violation.detected_at.isoformat() if violation.detected_at is not None else None
                    }
                    for violation in domain.violations
                ] if domain.violations else []
            }
            domain_list.append(domain_data)
        
        return {
            "success": True,
            "data": {
                "items": domain_list,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取第三方域名记录失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="获取第三方域名记录失败"
        )


# 新增：统一域名管理接口
@router.get("/{task_id}/scan-domains")
async def get_task_scan_domains(
    task_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    category_filter: Optional[str] = Query(None, alias="category"),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取任务的需要扫描的域名列表（目标域名和子域名）"""
    try:
        # 验证任务存在且属于当前用户
        task_query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        task_result = await db.execute(task_query)
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 导入新的域名模型
        from app.models.domain import DomainRecord, DomainCategory, DomainStatus
        
        # 构建查询条件 - 只查询目标相关域名
        conditions = [
            DomainRecord.task_id == task_id,
            or_(
                DomainRecord.category == DomainCategory.TARGET_MAIN,
                DomainRecord.category == DomainCategory.TARGET_SUBDOMAIN
            )
        ]
        
        # 应用过滤器
        if status_filter:
            conditions.append(DomainRecord.status == status_filter)
        if category_filter:
            conditions.append(DomainRecord.category == category_filter)
        if search:
            conditions.append(DomainRecord.domain.contains(search))
        
        # 查询总数
        count_query = select(func.count(DomainRecord.id)).where(and_(*conditions))
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询域名列表
        query = select(DomainRecord).where(
            and_(*conditions)
        ).order_by(DomainRecord.first_discovered_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        domains = result.scalars().all()
        
        # 转换为响应格式
        domain_list = []
        for domain in domains:
            domain_data = {
                "id": domain.id,
                "task_id": domain.task_id,
                "domain": domain.domain,
                "category": domain.category,
                "status": domain.status,
                "discovery_method": domain.discovery_method,
                "ip_address": domain.ip_address,
                "is_accessible": domain.is_accessible,
                "response_code": domain.response_code,
                "response_time": domain.response_time,
                "server_header": domain.server_header,
                "content_type": domain.content_type,
                "page_title": domain.page_title,
                "parent_domain": domain.parent_domain,
                "depth_level": domain.depth_level,
                "risk_level": domain.risk_level,
                "confidence_score": domain.confidence_score,
                "is_analyzed": domain.is_analyzed,
                "first_discovered_at": domain.first_discovered_at.isoformat() if safe_get_value(domain, 'first_discovered_at') else None,
                "last_updated_at": domain.last_updated_at.isoformat() if safe_get_value(domain, 'last_updated_at') else None,
                "tags": domain.tags or []
            }
            domain_list.append(domain_data)
        
        return {
            "success": True,
            "data": {
                "items": domain_list,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取扫描域名失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="获取扫描域名失败"
        )


@router.get("/{task_id}/all-domains")
async def get_task_all_domains(
    task_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category_filter: Optional[str] = Query(None, alias="category"),
    risk_level_filter: Optional[str] = Query(None, alias="risk_level"),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取任务检测到的所有域名列表"""
    try:
        # 验证任务存在且属于当前用户
        task_query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        task_result = await db.execute(task_query)
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 导入新的域名模型
        from app.models.domain import DomainRecord
        
        # 构建查询条件
        conditions = [DomainRecord.task_id == task_id]
        
        # 应用过滤器
        if category_filter:
            conditions.append(DomainRecord.category == category_filter)
        if risk_level_filter:
            conditions.append(DomainRecord.risk_level == risk_level_filter)
        if search:
            conditions.append(DomainRecord.domain.contains(search))
        
        # 查询总数
        count_query = select(func.count(DomainRecord.id)).where(and_(*conditions))
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询域名列表
        query = select(DomainRecord).where(
            and_(*conditions)
        ).order_by(DomainRecord.first_discovered_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        domains = result.scalars().all()
        
        # TODO: 查询违规记录关联
        
        # 转换为响应格式
        domain_list = []
        for domain in domains:
            domain_data = {
                "id": domain.id,
                "task_id": domain.task_id,
                "domain": domain.domain,
                "category": domain.category,
                "status": domain.status,
                "discovery_method": domain.discovery_method,
                "ip_address": domain.ip_address,
                "is_accessible": domain.is_accessible,
                "response_code": domain.response_code,
                "page_title": domain.page_title,
                "page_description": domain.page_description,
                "parent_domain": domain.parent_domain,
                "depth_level": domain.depth_level,
                "risk_level": domain.risk_level,
                "confidence_score": domain.confidence_score,
                "is_analyzed": domain.is_analyzed,
                "first_discovered_at": domain.first_discovered_at.isoformat() if safe_get_value(domain, 'first_discovered_at') else None,
                "last_updated_at": domain.last_updated_at.isoformat() if safe_get_value(domain, 'last_updated_at') else None,
                "has_violations": False,  # TODO: 从违规记录计算
                "is_target_related": domain.category in ['target_main', 'target_subdomain'],
                "is_third_party": domain.category == 'third_party',
                "tags": domain.tags or []
            }
            domain_list.append(domain_data)
        
        return {
            "success": True,
            "data": {
                "items": domain_list,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取所有域名失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="获取所有域名失败"
        )


@router.get("/{task_id}/domain-stats")
async def get_task_domain_stats(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """获取任务的域名统计信息"""
    try:
        # 验证任务存在且属于当前用户
        task_query = select(ScanTask).where(
            and_(
                ScanTask.id == task_id,
                ScanTask.user_id == current_user.id
            )
        )
        task_result = await db.execute(task_query)
        task = task_result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 导入新的域名模型
        from app.models.domain import DomainRecord, DomainCategory, DomainStatus, RiskLevel
        
        # 查询所有域名
        query = select(DomainRecord).where(DomainRecord.task_id == task_id)
        result = await db.execute(query)
        domains = result.scalars().all()
        
        # 计算统计信息
        total_domains = len(domains)
        target_domains = sum(1 for d in domains if safe_get_value(d, 'category') == DomainCategory.TARGET_MAIN)
        subdomain_count = sum(1 for d in domains if safe_get_value(d, 'category') == DomainCategory.TARGET_SUBDOMAIN)
        third_party_count = sum(1 for d in domains if safe_get_value(d, 'category') == DomainCategory.THIRD_PARTY)
        accessible_count = sum(1 for d in domains if safe_get_value(d, 'is_accessible', False))
        analyzed_count = sum(1 for d in domains if safe_get_value(d, 'is_analyzed', False))
        
        # TODO: 从违规记录计算违规域名数量
        violation_count = 0
        
        stats = {
            "total_domains": total_domains,
            "target_domains": target_domains,
            "subdomain_count": subdomain_count,
            "third_party_count": third_party_count,
            "accessible_count": accessible_count,
            "analyzed_count": analyzed_count,
            "violation_count": violation_count
        }
        
        return {
            "success": True,
            "data": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取域名统计失败: {e}")
        raise HTTPException(
            status_code=getattr(status, "HTTP_500_INTERNAL_SERVER_ERROR", 500),
            detail="获取域名统计失败"
        )











