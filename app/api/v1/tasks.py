from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import Any, List, Optional
from datetime import datetime
import uuid

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError, AuthorizationError, ValidationError
from app.core.logging import logger
from app.core.config import settings
from app.models.user import User
from app.models.task import ScanTask, TaskStatus, TaskLog
from app.tasks.scan_tasks import scan_domain_task
from app.websocket.handlers import task_monitor

router = APIRouter()


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
    task_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """创建扫描任务"""
    try:
        target_domain = task_data.get("target_domain")
        if not target_domain:
            raise ValidationError("缺少目标域名")
        
        config = task_data.get("config", {})
        
        # 创建任务记录
        task_id = str(uuid.uuid4())
        task = ScanTask(
            id=task_id,
            user_id=current_user.id,
            target_domain=target_domain,
            status=TaskStatus.PENDING,
            config=config,
            created_at=datetime.utcnow()
        )
        
        db.add(task)
        await db.commit()
        await db.refresh(task)
        
        # 发送任务创建通知
        await task_monitor.notify_task_created(task_id, str(current_user.id), target_domain)
        
        # 启动异步任务
        from celery_app import celery_app
        celery_app.send_task("scan_domain_task", args=[task_id, str(current_user.id), target_domain, config])
        
        logger.info(f"扫描任务已创建: {task_id} - {target_domain}")
        
        return {
            "success": True,
            "task_id": task_id,
            "target_domain": target_domain,
            "status": task.status,
            "message": "扫描任务已创建并开始执行"
        }
        
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
            task_data = {
                "id": task.id,
                "target_domain": task.target_domain,
                "task_name": task.task_name,
                "status": task.status,
                "progress": task.progress,
                "created_at": task.created_at.isoformat() if task.created_at is not None else None,
                "started_at": task.started_at.isoformat() if task.started_at is not None else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at is not None else None,
                "statistics": {
                    "total_subdomains": task.total_subdomains,
                    "total_pages_crawled": task.total_pages_crawled,
                    "total_third_party_domains": task.total_third_party_domains,
                    "total_violations": task.total_violations,
                    "critical_violations": task.critical_violations,
                    "high_violations": task.high_violations,
                    "medium_violations": task.medium_violations,
                    "low_violations": task.low_violations
                },
                "error_message": task.error_message
            }
            task_list.append(task_data)
        
        return {
            "success": True,
            "data": {
                "items": task_list,
                "total": total,
                "skip": skip,
                "limit": limit
            }
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
                    "total_third_party_domains": task.total_third_party_domains,
                    "total_violations": task.total_violations,
                    "critical_violations": task.critical_violations,
                    "high_violations": task.high_violations,
                    "medium_violations": task.medium_violations,
                    "low_violations": task.low_violations
                },
                "total_subdomains": task.total_subdomains,
                "total_pages_crawled": task.total_pages_crawled,
                "total_third_party_domains": task.total_third_party_domains,
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
            total_third_party_domains=0,
            total_violations=0,
            critical_violations=0,
            high_violations=0,
            medium_violations=0,
            low_violations=0
        )
        await db.execute(stmt)
        
        await db.commit()
        
        # 发送任务创建通知
        await task_monitor.notify_task_created(task_id, str(current_user.id), task.target_domain)
        
        # 启动异步任务
        from celery_app import celery_app
        celery_app.send_task("scan_domain_task", args=[task_id, str(current_user.id), task.target_domain, task.config])
        
        logger.info(f"扫描任务已重试: {task_id} - {task.target_domain}")
        
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
                    "total_third_party_domains": task.total_third_party_domains,
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
        from app.models.task import SubdomainRecord
        count_query = select(func.count(SubdomainRecord.id)).where(
            SubdomainRecord.task_id == task_id
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询子域名记录列表
        query = select(SubdomainRecord).where(
            SubdomainRecord.task_id == task_id
        ).order_by(SubdomainRecord.created_at.desc()).offset(skip).limit(limit)
        
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
async def get_task_third_party_domains(
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
        from app.models.task import ThirdPartyDomain
        conditions = [ThirdPartyDomain.task_id == task_id]
        if domain_type:
            conditions.append(ThirdPartyDomain.domain_type == domain_type)
        if risk_level:
            conditions.append(ThirdPartyDomain.risk_level == risk_level)
        
        count_query = select(func.count(ThirdPartyDomain.id)).where(
            and_(*conditions)
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询第三方域名记录列表，包含违规记录
        from sqlalchemy.orm import selectinload
        from app.models.task import ViolationRecord
        
        query = select(ThirdPartyDomain).options(
            selectinload(ThirdPartyDomain.violations)
        ).where(
            and_(*conditions)
        ).order_by(ThirdPartyDomain.created_at.desc()).offset(skip).limit(limit)
        
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











