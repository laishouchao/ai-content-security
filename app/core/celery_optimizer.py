"""
Celery任务队列优化配置
提供高性能、高可靠性的异步任务处理能力
"""

import os
from celery import Celery
from celery.signals import worker_init, worker_shutdown, task_prerun, task_postrun, task_failure
from kombu import Queue, Exchange
import logging
from datetime import timedelta

from app.core.config import settings
from app.core.logging import logger
from app.core.redis_lock import lock_manager


# Celery应用配置
celery_app = Celery(
    "ai_content_security",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'app.tasks.scan_tasks',
        'app.tasks.ai_analysis_tasks', 
        'app.tasks.notification_tasks',
        'app.tasks.maintenance_tasks'
    ]
)


# 基础配置
celery_app.conf.update(
    # 时区设置
    timezone='UTC',
    enable_utc=True,
    
    # 任务结果配置
    result_expires=3600,  # 结果保存1小时
    result_persistent=True,
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
    },
    
    # 序列化配置
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # 任务路由配置
    task_routes={
        'app.tasks.scan_tasks.*': {'queue': 'scan_queue'},
        'app.tasks.ai_analysis_tasks.*': {'queue': 'ai_queue'},
        'app.tasks.notification_tasks.*': {'queue': 'notification_queue'},
        'app.tasks.maintenance_tasks.*': {'queue': 'maintenance_queue'},
    },
    
    # 队列配置
    task_default_queue='default',
    task_queues=(
        # 默认队列
        Queue('default', Exchange('default'), routing_key='default'),
        
        # 扫描任务队列（高优先级）
        Queue('scan_queue', Exchange('scan'), routing_key='scan',
              queue_arguments={'x-max-priority': 10}),
        
        # AI分析队列（中优先级）
        Queue('ai_queue', Exchange('ai'), routing_key='ai',
              queue_arguments={'x-max-priority': 5}),
        
        # 通知队列（低优先级，快速处理）
        Queue('notification_queue', Exchange('notification'), routing_key='notification',
              queue_arguments={'x-max-priority': 2}),
        
        # 维护任务队列（最低优先级）
        Queue('maintenance_queue', Exchange('maintenance'), routing_key='maintenance',
              queue_arguments={'x-max-priority': 1}),
    ),
)


# Worker优化配置
celery_app.conf.update(
    # 并发配置
    worker_concurrency=4,  # 并发worker数量
    worker_prefetch_multiplier=1,  # 每个worker预取任务数
    
    # 内存管理
    worker_max_tasks_per_child=1000,  # 每个子进程最大任务数，防止内存泄漏
    worker_max_memory_per_child=200000,  # 每个子进程最大内存（KB）
    
    # 任务时间限制
    task_soft_time_limit=300,  # 软时间限制（5分钟）
    task_time_limit=600,  # 硬时间限制（10分钟）
    
    # 任务重试配置
    task_acks_late=True,  # 任务完成后才确认
    worker_disable_rate_limits=False,
    
    # 心跳配置
    broker_heartbeat=30,
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
)


# 监控和日志配置
celery_app.conf.update(
    # 监控配置
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # 日志配置
    worker_hijack_root_logger=False,
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)


# 高级配置
celery_app.conf.update(
    # 任务压缩
    task_compression='gzip',
    result_compression='gzip',
    
    # 连接池配置
    broker_pool_limit=10,
    broker_transport_options={
        'priority_steps': list(range(10)),
        'sep': ':',
        'queue_order_strategy': 'priority',
    },
    
    # 错误处理
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
)


class TaskMetrics:
    """任务指标收集器"""
    
    def __init__(self):
        self.task_stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'active_tasks': 0,
            'task_durations': {},
            'error_counts': {}
        }
    
    def record_task_start(self, task_id: str, task_name: str):
        """记录任务开始"""
        self.task_stats['total_tasks'] += 1
        self.task_stats['active_tasks'] += 1
        logger.debug(f"任务开始: {task_name}({task_id})")
    
    def record_task_success(self, task_id: str, task_name: str, duration: float):
        """记录任务成功"""
        self.task_stats['completed_tasks'] += 1
        self.task_stats['active_tasks'] -= 1
        
        if task_name not in self.task_stats['task_durations']:
            self.task_stats['task_durations'][task_name] = []
        self.task_stats['task_durations'][task_name].append(duration)
        
        logger.info(f"任务完成: {task_name}({task_id}), 耗时: {duration:.2f}s")
    
    def record_task_failure(self, task_id: str, task_name: str, error: str):
        """记录任务失败"""
        self.task_stats['failed_tasks'] += 1
        self.task_stats['active_tasks'] -= 1
        
        if task_name not in self.task_stats['error_counts']:
            self.task_stats['error_counts'][task_name] = {}
        
        error_type = type(error).__name__ if hasattr(error, '__class__') else str(error)
        self.task_stats['error_counts'][task_name][error_type] = \
            self.task_stats['error_counts'][task_name].get(error_type, 0) + 1
        
        logger.error(f"任务失败: {task_name}({task_id}), 错误: {error}")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        # 计算平均执行时间
        avg_durations = {}
        for task_name, durations in self.task_stats['task_durations'].items():
            if durations:
                avg_durations[task_name] = sum(durations) / len(durations)
        
        return {
            **self.task_stats,
            'average_durations': avg_durations,
            'success_rate': (
                self.task_stats['completed_tasks'] / max(1, self.task_stats['total_tasks'])
            ) * 100
        }


# 全局指标收集器
task_metrics = TaskMetrics()


# Celery信号处理器
@worker_init.connect
def worker_init_handler(sender=None, **kwargs):
    """Worker初始化处理器"""
    logger.info(f"Celery Worker启动: {sender}")
    
    # 初始化Redis锁管理器
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(lock_manager.initialize())
    
    # 初始化并清理缓存
    try:
        from app.core.cache_manager import cache_manager
        
        # 初始化缓存管理器
        loop.run_until_complete(cache_manager.initialize())
        
        # 清理孤立的Celery任务
        orphaned_count = loop.run_until_complete(cache_manager.cleanup_orphaned_celery_tasks())
        if orphaned_count > 0:
            logger.info(f"Worker启动时清理了 {orphaned_count} 个孤立的Celery任务")
        
        logger.info("Worker缓存清理完成")
        
    except Exception as e:
        logger.error(f"Worker启动时缓存清理失败: {e}")


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Worker关闭处理器"""
    logger.info(f"Celery Worker关闭: {sender}")
    
    # 关闭Redis锁管理器
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(lock_manager.close())


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """任务执行前处理器"""
    if task_id and task and hasattr(task, 'name'):
        task_metrics.record_task_start(task_id, task.name)


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                        retval=None, state=None, **kwds):
    """任务执行后处理器"""
    if state == 'SUCCESS' and task_id and task and hasattr(task, 'name'):
        # 计算执行时间
        import time
        duration = getattr(task, '_duration', 0)
        task_metrics.record_task_success(task_id, task.name, duration)


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """任务失败处理器"""
    if task_id and sender and hasattr(sender, 'name'):
        task_metrics.record_task_failure(task_id, sender.name, str(exception))


class CeleryTaskManager:
    """Celery任务管理器"""
    
    @staticmethod
    async def get_queue_stats() -> dict:
        """获取队列统计信息"""
        try:
            # 直接使用celery_app而不是current_app
            inspect = celery_app.control.inspect()
            
            # 获取队列长度
            queue_lengths = {}
            active_tasks = inspect.active()
            reserved_tasks = inspect.reserved()
            
            if active_tasks:
                for worker, tasks in active_tasks.items():
                    for task in tasks:
                        queue = task.get('delivery_info', {}).get('routing_key', 'unknown')
                        queue_lengths[queue] = queue_lengths.get(queue, 0) + 1
            
            return {
                'queue_lengths': queue_lengths,
                'active_tasks': active_tasks,
                'reserved_tasks': reserved_tasks,
                'task_metrics': task_metrics.get_stats()
            }
            
        except Exception as e:
            logger.error(f"获取队列统计失败: {e}")
            return {}
    
    @staticmethod
    async def purge_queue(queue_name: str) -> bool:
        """清空指定队列"""
        try:
            celery_app.control.purge()
            logger.info(f"清空队列: {queue_name}")
            return True
        except Exception as e:
            logger.error(f"清空队列失败 {queue_name}: {e}")
            return False
    
    @staticmethod
    async def revoke_task(task_id: str, terminate: bool = False) -> bool:
        """撤销任务"""
        try:
            celery_app.control.revoke(task_id, terminate=terminate)
            logger.info(f"撤销任务: {task_id}")
            return True
        except Exception as e:
            logger.error(f"撤销任务失败 {task_id}: {e}")
            return False
    
    @staticmethod
    async def get_worker_stats() -> dict:
        """获取Worker统计信息"""
        try:
            inspect = celery_app.control.inspect()
            return {
                'stats': inspect.stats(),
                'active': inspect.active(),
                'scheduled': inspect.scheduled(),
                'reserved': inspect.reserved(),
                'revoked': inspect.revoked(),
            }
        except Exception as e:
            logger.error(f"获取Worker统计失败: {e}")
            return {}


# 任务基类，提供通用功能
class BaseTask(celery_app.Task):
    """任务基类"""
    
    def on_success(self, retval, task_id, args, kwargs):
        """任务成功回调"""
        logger.info(f"任务成功: {self.name}({task_id})")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败回调"""
        logger.error(f"任务失败: {self.name}({task_id}), 异常: {exc}")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试回调"""
        logger.warning(f"任务重试: {self.name}({task_id}), 异常: {exc}")


# 设置默认任务基类
celery_app.Task = BaseTask


# 任务装饰器工厂
def create_task(**kwargs):
    """创建任务装饰器"""
    default_kwargs = {
        'bind': True,
        'autoretry_for': (Exception,),
        'retry_kwargs': {'max_retries': 3, 'countdown': 60},
        'retry_backoff': True,
        'retry_jitter': True,
    }
    default_kwargs.update(kwargs)
    
    return celery_app.task(**default_kwargs)


# 导出主要组件
__all__ = [
    'celery_app',
    'task_metrics', 
    'CeleryTaskManager',
    'BaseTask',
    'create_task'
]