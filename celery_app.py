import sys
import os
import time
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 设置环境变量确保子进程也能找到模块
os.environ['PYTHONPATH'] = str(project_root) + os.pathsep + os.environ.get('PYTHONPATH', '')

from celery import Celery
from app.core.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s: %(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def test_redis_connection():
    """启动时测试Redis连接"""
    try:
        import redis
        logger.info("测试Redis连接...")
        r = redis.from_url(settings.CELERY_BROKER_URL)
        result = r.ping()
        logger.info(f"Redis连接测试成功: {result}")
        return True
    except Exception as e:
        logger.error(f"Redis连接失败: {e}")
        return False

def cleanup_redis_data():
    """清理可能导致冲突的Redis数据"""
    try:
        import redis
        logger.info("清理Redis冲突数据...")
        r = redis.from_url(settings.CELERY_BROKER_URL)
        
        # 清理可能导致冲突的键
        patterns = [
            "_kombu.binding.*",
            "unacked*"
        ]
        
        for pattern in patterns:
            keys = r.keys(pattern)
            if keys:
                r.delete(*keys)
                logger.info(f"清理了 {len(keys)} 个 {pattern} 键")
        
        logger.info("Redis数据清理完成")
        return True
    except Exception as e:
        logger.error(f"Redis数据清理失败: {e}")
        return False

# 启动时执行连接检测和数据清理
if __name__ != "__main__":
    logger.info("初始化Celery应用...")
    if test_redis_connection():
        cleanup_redis_data()
    else:
        logger.warning("Redis连接失败，但继续启动Celery（可能在Docker环境中）")

# 创建Celery应用实例
celery_app = Celery("domain_scanner")

# 完全重写配置以修复连接问题
celery_app.conf.update(
    # 基础配置
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    
    # 序列化配置
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # 时区配置
    timezone='UTC',
    enable_utc=True,
    
    # ======= 关键修复配置 =======
    # 连接重试配置
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_heartbeat=30,
    
    # 修复 "not enough values to unpack" 错误的核心配置
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True,
        'sep': ':',
        # 完全移除可能导致问题的配置项
        # 'priority_steps': list(range(10)),  # 可能导致解包错误
        # 'queue_order_strategy': 'priority', # 可能导致解包错误
        # 'master_name': None,                # Redis Sentinel相关，移除
    },
    
    # 结果后端配置 - 简化以避免错误
    result_backend_transport_options={
        'visibility_timeout': 3600,
        # 移除所有可能导致问题的配置
    },
    
    # 工作进程配置
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    
    # 内存和任务限制
    worker_max_tasks_per_child=1000,
    worker_max_memory_per_child=200000,  # 200MB
    
    # 任务超时
    task_soft_time_limit=300,  # 5分钟
    task_time_limit=600,       # 10分钟
    
    # 结果配置
    result_expires=3600,  # 1小时
    result_persistent=True,
    
    # 任务重试
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # 错误处理
    task_reject_on_worker_lost=True,
    worker_disable_rate_limits=False,
    task_ignore_result=False,
    
    # 连接池
    broker_pool_limit=10,
    
    # 禁用一些可能导致问题的功能
    worker_send_task_events=False,
    task_send_sent_event=False,
    
    # 简化的任务路由
    task_routes={
        'app.tasks.scan_tasks.scan_domain_task': {'queue': 'celery'},
        'app.tasks.scan_tasks.cancel_scan_task': {'queue': 'celery'},
        'app.tasks.scan_tasks.cleanup_old_tasks': {'queue': 'celery'},
    },
    
    # Windows特定配置
    worker_pool='solo' if sys.platform == 'win32' else 'prefork',
)

# 自动发现任务
celery_app.autodiscover_tasks([
    "app.tasks.scan_tasks",
    "app.tasks.analysis_tasks", 
    "app.tasks.capture_tasks",
])

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("AI内容安全监控系统 - Celery Worker")
    logger.info("=" * 60)
    
    # 执行启动检查
    if not test_redis_connection():
        logger.error("Redis连接失败，无法启动Celery Worker")
        sys.exit(1)
    
    # 清理数据
    cleanup_redis_data()
    
    logger.info("启动Celery Worker...")
    celery_app.start()