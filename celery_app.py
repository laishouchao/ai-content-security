import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 设置环境变量确保子进程也能找到模块
os.environ['PYTHONPATH'] = str(project_root) + os.pathsep + os.environ.get('PYTHONPATH', '')

from celery import Celery
from app.core.config import settings, CeleryConfig

# 创建Celery应用实例
celery_app = Celery("domain_scanner")

# 应用配置
celery_app.config_from_object(CeleryConfig)

# 自动发现任务
celery_app.autodiscover_tasks([
    "app.tasks.scan_tasks",
    "app.tasks.analysis_tasks", 
    "app.tasks.capture_tasks",
])

# 任务路由配置
celery_app.conf.task_routes = {
    'app.tasks.scan_tasks.*': {'queue': 'scan'},
    'app.tasks.analysis_tasks.*': {'queue': 'analysis'},
    'app.tasks.capture_tasks.*': {'queue': 'capture'},
}

# Windows特定配置
if sys.platform == 'win32':
    # 在Windows上使用solo池避免spawn问题
    celery_app.conf.worker_pool = 'solo'
    # 或者设置为threads池
    # celery_app.conf.worker_pool = 'threads'

if __name__ == "__main__":
    celery_app.start()