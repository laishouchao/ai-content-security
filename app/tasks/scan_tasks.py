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


async def _check_task_exists(task_id: str, max_retries: int = 5, retry_delay: float = 1.0) -> bool:
    """检查任务是否在数据库中存在，支持重试机制"""
    import asyncio
    
    for attempt in range(max_retries):
        try:
            # 首先检查Redis中的任务创建标记
            from app.core.cache_manager import cache_manager
            await cache_manager.initialize()
            
            redis_check = None
            if cache_manager.redis_client:
                task_creation_key = f"task_created:{task_id}"
                redis_check = await cache_manager.redis_client.get(task_creation_key)
            
            if redis_check:
                # Redis中有创建标记，再检查数据库
                from sqlalchemy import select
                async with AsyncSessionLocal() as db:
                    stmt = select(ScanTask.id).where(ScanTask.id == task_id)
                    result = await db.execute(stmt)
                    exists = result.scalar_one_or_none() is not None
                    
                    if exists:
                        print(f"任务 {task_id} 验证成功（第{attempt + 1}次尝试）")
                        await cache_manager.close()
                        return True
            else:
                # Redis中没有标记，直接检查数据库
                from sqlalchemy import select
                async with AsyncSessionLocal() as db:
                    stmt = select(ScanTask.id).where(ScanTask.id == task_id)
                    result = await db.execute(stmt)
                    exists = result.scalar_one_or_none() is not None
                    
                    if exists:
                        print(f"任务 {task_id} 在数据库中存在（第{attempt + 1}次尝试）")
                        await cache_manager.close()
                        return True
            
            await cache_manager.close()
            
            # 如果还有重试机会，等待一段时间后重试
            if attempt < max_retries - 1:
                print(f"任务 {task_id} 未找到，{retry_delay}秒后进行第{attempt + 2}次尝试...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 1.5  # 指数退避
        
        except Exception as e:
            print(f"检查任务 {task_id} 第{attempt + 1}次尝试失败: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 1.5
            continue
    
    print(f"任务 {task_id} 在 {max_retries} 次尝试后仍未找到")
    return False


@celery_app.task(bind=True, name="scan_domain_task")
def scan_domain_task(self, task_id: str, user_id: str, target_domain: str, config: Dict[str, Any]):
    """域名扫描后台任务"""
    print(f"开始执行扫描任务: {target_domain}")
    
    # 在Celery任务中运行异步代码
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 检查任务是否在数据库中存在
        task_exists = loop.run_until_complete(_check_task_exists(task_id))
        if not task_exists:
            error_msg = f"任务 {task_id} 在数据库中不存在，无法执行"
            print(f"错误: {error_msg}")
            
            # 尝试从Redis中清理这个任务的相关信息
            try:
                from app.core.cache_manager import cache_manager
                loop.run_until_complete(cache_manager.initialize())
                
                # 清理当前任务的Redis键
                if cache_manager.redis_client:
                    task_key = f"celery-task-meta-{task_id}"
                    deleted = loop.run_until_complete(cache_manager.redis_client.delete(task_key))
                    if deleted:
                        print(f"已清理孤立的任务键: {task_key}")
                    
                    loop.run_until_complete(cache_manager.close())
            except Exception as cleanup_error:
                print(f"清理孤立任务时出错: {cleanup_error}")
            
            # 抛出异常，让Celery知道任务失败
            raise Exception(error_msg)
        
        # 任务存在，执行扫描
        result = loop.run_until_complete(
            _execute_scan_task(task_id, user_id, target_domain, config)
        )
        return result
    except Exception as e:
        print(f"扫描任务失败: {e}")
        raise e
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
    message: str = None # type: ignore
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
    extra_data: Dict[str, Any] = None   # type: ignore
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
                
                # 只有在置信度足够高且有明确违规类型时才发送通知
                if (violation.confidence_score >= 0.6 and 
                    violation.violation_type and 
                    violation.violation_type != '未知违规'):
                    
                    try:
                        # 获取域名信息
                        from sqlalchemy import select
                        domain_query = select(ThirdPartyDomain).where(ThirdPartyDomain.id == violation.domain_id)
                        domain_result = await db.execute(domain_query)
                        domain_record = domain_result.scalar_one_or_none()
                        
                        domain_name = domain_record.domain if domain_record else 'unknown'
                        
                        await task_monitor.notify_violation_detected(
                            scan_result.task_id,
                            {
                                "domain": domain_name,
                                "violation_type": violation.violation_type,
                                "risk_level": violation.risk_level,
                                "confidence_score": violation.confidence_score,
                                "description": violation.description,
                                "title": violation.title,
                                "evidence": violation.evidence or [],
                                "recommendations": violation.recommendations or []
                            }
                        )
                        
                        print(f"已发送违规检测通知: {domain_name} - {violation.violation_type} (置信度: {violation.confidence_score*100:.1f}%)")
                        
                    except Exception as e:
                        print(f"发送违规检测通知失败: {e}")
                else:
                    print(f"违规检测置信度过低或类型不明，跳过通知: {violation.violation_type} (置信度: {violation.confidence_score*100:.1f}%)")
        
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
        'schedule': crontab(hour=2, minute=0),  # 每天凌晨2点执行   # type: ignore
    },
}