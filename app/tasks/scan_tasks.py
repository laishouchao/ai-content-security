import asyncio
from celery import Celery
from typing import Dict, Any
from datetime import datetime

from app.core.config import settings
from app.core.logging import TaskLogger
from app.core.database import AsyncSessionLocal
from app.models.task import ScanTask, TaskStatus, TaskLog, SubdomainRecord, ThirdPartyDomain, ViolationRecord
from app.engines.scan_executor import ScanTaskExecutor, ScanExecutionResult
from app.websocket.handlers import task_monitor
from celery_app import celery_app


@celery_app.task(bind=True, name="scan_domain_task")
def scan_domain_task(self, task_id: str, user_id: str, target_domain: str, config: Dict[str, Any]):
    """域名扫描后台任务"""
    
    # 在Celery任务中运行异步代码
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            _execute_scan_task(task_id, user_id, target_domain, config)
        )
        return result
    finally:
        loop.close()


async def _execute_scan_task(
    task_id: str, 
    user_id: str, 
    target_domain: str, 
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """执行扫描任务的异步函数"""
    
    logger = TaskLogger(task_id, user_id)
    logger.info(f"开始执行扫描任务: {target_domain}")
    
    async with AsyncSessionLocal() as db:
        try:
            # 更新任务状态为运行中
            await _update_task_status(db, task_id, TaskStatus.RUNNING, 0, "开始扫描")
            
            # 发送任务开始通知
            await task_monitor.notify_task_started(task_id, user_id)
            
            # 创建扫描执行器
            executor = ScanTaskExecutor(task_id, user_id)
            
            # 设置进度回调
            async def progress_callback(task_id: str, progress: int, message: str):
                await _update_task_status(db, task_id, TaskStatus.RUNNING, progress, message)
                await _log_task_event(db, task_id, "INFO", "progress", message)
                # 实时通知已在scan_executor中处理
            
            executor.set_progress_callback(progress_callback)
            
            # 执行扫描
            scan_result = await executor.execute_scan(target_domain, config)
            
            # 保存扫描结果到数据库
            await _save_scan_results(db, scan_result)
            
            # 更新最终状态
            if scan_result.status == "completed":
                await _update_task_status(db, task_id, TaskStatus.COMPLETED, 100, "扫描完成")
                await task_monitor.notify_task_completed(
                    task_id, user_id, TaskStatus.COMPLETED, scan_result.statistics
                )
                logger.info(f"扫描任务完成: {target_domain}")
            elif scan_result.status == "cancelled":
                await _update_task_status(db, task_id, TaskStatus.CANCELLED, scan_result.progress, "任务已取消")
                await task_monitor.notify_task_completed(
                    task_id, user_id, TaskStatus.CANCELLED
                )
                logger.info(f"扫描任务已取消: {target_domain}")
            else:
                await _update_task_status(db, task_id, TaskStatus.FAILED, scan_result.progress, "扫描失败")
                await task_monitor.notify_task_completed(
                    task_id, user_id, TaskStatus.FAILED, scan_result.statistics
                )
                logger.error(f"扫描任务失败: {target_domain}")
            
            return {
                'task_id': task_id,
                'status': scan_result.status,
                'statistics': scan_result.statistics,
                'errors': scan_result.errors,
                'warnings': scan_result.warnings
            }
            
        except Exception as e:
            logger.error(f"扫描任务执行异常: {e}")
            await _update_task_status(db, task_id, TaskStatus.FAILED, 0, f"执行异常: {str(e)}")
            await _log_task_event(db, task_id, "ERROR", "execution", f"任务执行异常: {str(e)}")
            
            # 发送错误通知
            await task_monitor.notify_task_error(task_id, user_id, str(e))
            
            return {
                'task_id': task_id,
                'status': 'failed',
                'error': str(e)
            }


async def _update_task_status(
    db, 
    task_id: str, 
    status: TaskStatus, 
    progress: int, 
    message: str = None
):
    """更新任务状态"""
    try:
        from sqlalchemy import select, update
        
        # 准备更新数据
        update_data = {
            'status': status,
            'progress': progress
        }
        
        # 根据状态设置时间戳
        if status == TaskStatus.RUNNING and progress == 0:
            update_data['started_at'] = datetime.utcnow()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            update_data['completed_at'] = datetime.utcnow()
        
        if message:
            update_data['error_message'] = message if status == TaskStatus.FAILED else None
        
        # 执行更新
        stmt = update(ScanTask).where(ScanTask.id == task_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        
    except Exception as e:
        print(f"更新任务状态失败: {e}")


async def _log_task_event(
    db,
    task_id: str,
    level: str,
    module: str,
    message: str,
    extra_data: Dict[str, Any] = None
):
    """记录任务事件"""
    try:
        task_log = TaskLog(
            task_id=task_id,
            level=level,
            module=module,
            message=message,
            extra_data=extra_data,
            created_at=datetime.utcnow()
        )
        
        db.add(task_log)
        await db.commit()
        
    except Exception as e:
        print(f"记录任务日志失败: {e}")


async def _save_scan_results(db, scan_result: ScanExecutionResult):
    """保存扫描结果到数据库"""
    try:
        # 保存子域名记录
        for subdomain in scan_result.subdomains:
            subdomain_record = SubdomainRecord(
                task_id=scan_result.task_id,
                subdomain=subdomain.subdomain,
                ip_address=subdomain.ip_address,
                discovery_method=subdomain.method,
                is_accessible=subdomain.is_accessible,
                response_code=subdomain.response_code,
                response_time=subdomain.response_time,
                server_header=subdomain.server_header,
                created_at=subdomain.discovered_at
            )
            db.add(subdomain_record)
        
        # 保存第三方域名记录（检查是否已存在）
        from sqlalchemy import select
        for third_party in scan_result.third_party_domains:
            # 检查是否已经存在
            existing_query = select(ThirdPartyDomain).where(
                ThirdPartyDomain.task_id == scan_result.task_id,
                ThirdPartyDomain.domain == third_party.domain
            )
            existing_result = await db.execute(existing_query)
            existing_domain = existing_result.scalar_one_or_none()
            
            if existing_domain:
                # 如果已存在，只更新截图路径和分析状态
                screenshot_path = None
                for content in scan_result.content_results:
                    if third_party.domain in content.url:
                        screenshot_path = content.screenshot_path
                        break
                
                if screenshot_path:
                    existing_domain.screenshot_path = screenshot_path  # type: ignore
                if hasattr(scan_result, 'violation_records'):
                    existing_domain.is_analyzed = True  # type: ignore
            else:
                # 如果不存在，新建记录
                # 查找对应的内容结果
                screenshot_path = None
                html_content_path = None
                
                for content in scan_result.content_results:
                    if third_party.domain in content.url:
                        screenshot_path = content.screenshot_path
                        # 可以保存HTML内容到文件
                        break
                
                third_party_record = ThirdPartyDomain(
                    task_id=scan_result.task_id,
                    domain=third_party.domain,
                    found_on_url=', '.join(third_party.found_on_urls[:3]),  # 限制长度
                    domain_type=third_party.domain_type,
                    risk_level=third_party.risk_level,
                    page_title=f"{third_party.domain} - {third_party.description}",
                    page_description=third_party.description,
                    screenshot_path=screenshot_path,
                    is_analyzed=True if hasattr(scan_result, 'violation_records') else False,  # 根据是否有AI分析结果设置
                    created_at=third_party.discovered_at
                )
                db.add(third_party_record)
        
        # 保存AI分析的违规记录
        if hasattr(scan_result, 'violation_records') and scan_result.violation_records:
            for violation in scan_result.violation_records:
                db.add(violation)
                
                # 发送违规检测通知
                try:
                    await task_monitor.notify_violation_detected(
                        scan_result.task_id,
                        {
                            "domain": violation.domain.domain if hasattr(violation, 'domain') else 'unknown',
                            "violation_type": violation.violation_type,
                            "risk_level": violation.risk_level,
                            "confidence_score": violation.confidence_score,
                            "description": violation.description
                        }
                    )
                except Exception as e:
                    print(f"发送违规检测通知失败: {e}")
        
        # 更新任务统计信息
        from sqlalchemy import update
        
        update_data = {
            'total_subdomains': scan_result.statistics['total_subdomains'],
            'total_pages_crawled': scan_result.statistics['total_pages_crawled'],
            'total_third_party_domains': scan_result.statistics['total_third_party_domains'],
            'total_violations': scan_result.statistics.get('total_violations', 0),  # 包含AI分析的违规数量
            'critical_violations': 0,
            'high_violations': 0,
            'medium_violations': 0,
            'low_violations': 0
        }
        
        # 计算不同风险等级的违规数量
        if hasattr(scan_result, 'violation_records') and scan_result.violation_records:
            for violation in scan_result.violation_records:
                if violation.risk_level == 'critical':
                    update_data['critical_violations'] += 1
                elif violation.risk_level == 'high':
                    update_data['high_violations'] += 1
                elif violation.risk_level == 'medium':
                    update_data['medium_violations'] += 1
                elif violation.risk_level == 'low':
                    update_data['low_violations'] += 1
        
        stmt = update(ScanTask).where(ScanTask.id == scan_result.task_id).values(**update_data)
        await db.execute(stmt)
        
        await db.commit()
        
    except Exception as e:
        await db.rollback()
        print(f"保存扫描结果失败: {e}")
        raise


# 其他任务函数

@celery_app.task(bind=True, name="cancel_scan_task")
def cancel_scan_task(self, task_id: str):
    """取消扫描任务"""
    # 这里可以实现任务取消逻辑
    # 需要与正在运行的扫描器通信
    pass


@celery_app.task(bind=True, name="cleanup_old_tasks")
def cleanup_old_tasks(self):
    """清理旧任务数据"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(_cleanup_old_tasks())
    finally:
        loop.close()


async def _cleanup_old_tasks():
    """清理旧任务的异步函数"""
    from sqlalchemy import select, delete
    from datetime import timedelta
    
    async with AsyncSessionLocal() as db:
        try:
            # 删除30天前的已完成任务
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            # 查找要清理的任务
            stmt = select(ScanTask).where(
                ScanTask.completed_at < cutoff_date,
                ScanTask.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED])
            )
            result = await db.execute(stmt)
            old_tasks = result.scalars().all()
            
            for task in old_tasks:
                # 删除相关的截图文件
                # TODO: 实现文件清理逻辑
                
                # 删除数据库记录（级联删除相关记录）
                await db.delete(task)
            
            await db.commit()
            print(f"清理了 {len(old_tasks)} 个旧任务")
            
        except Exception as e:
            await db.rollback()
            print(f"清理旧任务失败: {e}")


# 定期任务配置
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'cleanup-old-tasks': {
        'task': 'cleanup_old_tasks',
        'schedule': crontab(hour=2, minute=0),  # 每天凌晨2点执行
    },
}