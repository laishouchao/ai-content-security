"""
性能数据收集Celery任务

定期执行的性能监控任务
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from celery import current_app as celery_app
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.performance import PerformanceLog, PerformanceAlert
from app.services.performance_service import PerformanceCollector

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='app.tasks.performance_tasks.collect_performance_metrics')
def collect_performance_metrics(self):
    """收集性能指标任务"""
    try:
        logger.info("开始收集性能指标...")
        
        # 创建异步事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 运行异步任务
            result = loop.run_until_complete(_collect_metrics_async())
            logger.info(f"性能指标收集完成: {result}")
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"性能指标收集失败: {e}")
        raise self.retry(countdown=60, max_retries=3)


async def _collect_metrics_async() -> Dict[str, Any]:
    """异步收集性能指标"""
    collector = PerformanceCollector()
    
    try:
        # 收集所有性能指标
        metrics = await collector.collect_all_metrics()
        
        if not metrics:
            logger.warning("未收集到性能指标数据")
            return {"status": "warning", "message": "未收集到数据"}
        
        # 保存性能日志
        await collector.save_performance_log(metrics)
        
        # 检查并创建告警
        await collector.check_and_create_alerts(metrics)
        
        # 返回收集到的关键指标
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "cpu_percent": metrics.get('cpu_percent'),
            "memory_percent": metrics.get('memory_percent'),
            "disk_percent": metrics.get('disk_percent'),
            "active_users": metrics.get('active_users'),
            "running_tasks": metrics.get('running_scan_tasks'),
        }
        
    except Exception as e:
        logger.error(f"异步收集性能指标失败: {e}")
        raise


@celery_app.task(bind=True, name='app.tasks.performance_tasks.cleanup_old_performance_logs')
def cleanup_old_performance_logs(self):
    """清理过期性能日志任务"""
    try:
        logger.info("开始清理过期性能日志...")
        
        # 创建异步事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 运行异步任务
            result = loop.run_until_complete(_cleanup_old_logs_async())
            logger.info(f"性能日志清理完成: {result}")
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"性能日志清理失败: {e}")
        raise self.retry(countdown=300, max_retries=2)


async def _cleanup_old_logs_async() -> Dict[str, Any]:
    """异步清理过期性能日志"""
    try:
        async with AsyncSessionLocal() as db:
            # 删除7天前的性能日志
            cutoff_time = datetime.utcnow() - timedelta(days=7)
            
            # 计算要删除的记录数
            count_query = select(func.count(PerformanceLog.id)).where(
                PerformanceLog.timestamp < cutoff_time
            )
            count_result = await db.execute(count_query)
            delete_count = count_result.scalar() or 0
            
            if delete_count > 0:
                # 删除过期记录
                from sqlalchemy import delete
                delete_stmt = delete(PerformanceLog).where(
                    PerformanceLog.timestamp < cutoff_time
                )
                await db.execute(delete_stmt)
                await db.commit()
                
                logger.info(f"清理了 {delete_count} 条过期性能日志")
            else:
                logger.info("没有需要清理的过期性能日志")
            
            return {
                "status": "success",
                "deleted_count": delete_count,
                "cutoff_time": cutoff_time.isoformat(),
            }
            
    except Exception as e:
        logger.error(f"异步清理性能日志失败: {e}")
        raise


@celery_app.task(bind=True, name='app.tasks.performance_tasks.check_and_resolve_alerts')
def check_and_resolve_alerts(self):
    """检查和解决告警任务"""
    try:
        logger.info("开始检查和解决性能告警...")
        
        # 创建异步事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 运行异步任务
            result = loop.run_until_complete(_check_and_resolve_alerts_async())
            logger.info(f"告警检查完成: {result}")
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"告警检查失败: {e}")
        raise self.retry(countdown=300, max_retries=2)


async def _check_and_resolve_alerts_async() -> Dict[str, Any]:
    """异步检查和解决告警"""
    try:
        async with AsyncSessionLocal() as db:
            # 获取活跃的告警
            active_alerts_query = select(PerformanceAlert).where(
                PerformanceAlert.is_active == 1
            )
            active_alerts_result = await db.execute(active_alerts_query)
            active_alerts = active_alerts_result.scalars().all()
            
            resolved_count = 0
            
            # 获取最新的性能数据
            latest_log_query = select(PerformanceLog).order_by(
                PerformanceLog.timestamp.desc()
            ).limit(1)
            latest_log_result = await db.execute(latest_log_query)
            latest_log = latest_log_result.scalar_one_or_none()
            
            if latest_log:
                # 检查每个告警是否应该解决
                for alert in active_alerts:
                    should_resolve = await _should_resolve_alert(alert, latest_log)
                    
                    if should_resolve:
                        alert.is_active = 0
                        alert.resolved_at = datetime.utcnow()
                        resolved_count += 1
                        logger.info(f"解决告警: {alert.alert_type} - {alert.title}")
                
                if resolved_count > 0:
                    await db.commit()
            
            # 清理超过24小时的已解决告警
            cleanup_time = datetime.utcnow() - timedelta(hours=24)
            from sqlalchemy import delete
            cleanup_stmt = delete(PerformanceAlert).where(
                and_(
                    PerformanceAlert.is_active == 0,
                    PerformanceAlert.resolved_at < cleanup_time
                )
            )
            cleanup_result = await db.execute(cleanup_stmt)
            cleaned_count = cleanup_result.rowcount
            
            if cleaned_count > 0:
                await db.commit()
                logger.info(f"清理了 {cleaned_count} 个过期的已解决告警")
            
            return {
                "status": "success",
                "active_alerts": len(active_alerts),
                "resolved_alerts": resolved_count,
                "cleaned_alerts": cleaned_count,
            }
            
    except Exception as e:
        logger.error(f"异步检查告警失败: {e}")
        raise


async def _should_resolve_alert(alert: PerformanceAlert, latest_log: PerformanceLog) -> bool:
    """判断告警是否应该解决"""
    try:
        # 根据告警类型检查当前值
        if alert.alert_type == 'cpu':
            current_value = latest_log.cpu_percent
            threshold = alert.threshold_value or 80.0
            # CPU使用率降到阈值以下才解决
            return current_value is not None and current_value < threshold - 5  # 5%的缓冲
            
        elif alert.alert_type == 'memory':
            current_value = latest_log.memory_percent
            threshold = alert.threshold_value or 85.0
            # 内存使用率降到阈值以下才解决
            return current_value is not None and current_value < threshold - 5
            
        elif alert.alert_type == 'disk':
            current_value = latest_log.disk_percent
            threshold = alert.threshold_value or 90.0
            # 磁盘使用率降到阈值以下才解决
            return current_value is not None and current_value < threshold - 2
            
        elif alert.alert_type == 'redis':
            # Redis连接恢复正常
            return latest_log.redis_connected == 1
            
        else:
            # 未知类型的告警，暂时不自动解决
            return False
            
    except Exception as e:
        logger.error(f"判断告警解决条件失败: {e}")
        return False


@celery_app.task(bind=True, name='app.tasks.performance_tasks.generate_performance_report')
def generate_performance_report(self, hours: int = 24):
    """生成性能报告任务"""
    try:
        logger.info(f"开始生成性能报告（过去{hours}小时）...")
        
        # 创建异步事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 运行异步任务
            result = loop.run_until_complete(_generate_report_async(hours))
            logger.info(f"性能报告生成完成: {result.get('summary', {})}")
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"性能报告生成失败: {e}")
        raise self.retry(countdown=300, max_retries=2)


async def _generate_report_async(hours: int) -> Dict[str, Any]:
    """异步生成性能报告"""
    try:
        async with AsyncSessionLocal() as db:
            # 获取指定时间范围内的性能数据
            since_time = datetime.utcnow() - timedelta(hours=hours)
            
            query = select(PerformanceLog).where(
                PerformanceLog.timestamp >= since_time
            ).order_by(PerformanceLog.timestamp)
            
            result = await db.execute(query)
            logs = result.scalars().all()
            
            if not logs:
                return {
                    "status": "warning",
                    "message": "指定时间范围内没有性能数据",
                    "hours": hours,
                }
            
            # 计算统计信息
            cpu_values = [log.cpu_percent for log in logs if log.cpu_percent is not None]
            memory_values = [log.memory_percent for log in logs if log.memory_percent is not None]
            disk_values = [log.disk_percent for log in logs if log.disk_percent is not None]
            
            summary = {
                "time_range": {
                    "start": since_time.isoformat(),
                    "end": datetime.utcnow().isoformat(),
                    "hours": hours,
                },
                "data_points": len(logs),
                "cpu_stats": {
                    "avg": sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                    "max": max(cpu_values) if cpu_values else 0,
                    "min": min(cpu_values) if cpu_values else 0,
                },
                "memory_stats": {
                    "avg": sum(memory_values) / len(memory_values) if memory_values else 0,
                    "max": max(memory_values) if memory_values else 0,
                    "min": min(memory_values) if memory_values else 0,
                },
                "disk_stats": {
                    "avg": sum(disk_values) / len(disk_values) if disk_values else 0,
                    "max": max(disk_values) if disk_values else 0,
                    "min": min(disk_values) if disk_values else 0,
                },
            }
            
            # 计算健康分数趋势
            health_scores = [log.health_score for log in logs]
            summary["health_score"] = {
                "avg": sum(health_scores) / len(health_scores),
                "max": max(health_scores),
                "min": min(health_scores),
                "latest": health_scores[-1] if health_scores else 0,
            }
            
            return {
                "status": "success",
                "summary": summary,
                "generated_at": datetime.utcnow().isoformat(),
            }
            
    except Exception as e:
        logger.error(f"异步生成性能报告失败: {e}")
        raise


# 手动触发任务的辅助函数
def trigger_performance_collection():
    """手动触发性能数据收集"""
    return collect_performance_metrics.delay()


def trigger_log_cleanup():
    """手动触发日志清理"""
    return cleanup_old_performance_logs.delay()


def trigger_alert_check():
    """手动触发告警检查"""
    return check_and_resolve_alerts.delay()


def trigger_report_generation(hours: int = 24):
    """手动触发报告生成"""
    return generate_performance_report.delay(hours)