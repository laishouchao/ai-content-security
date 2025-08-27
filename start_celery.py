#!/usr/bin/env python3
"""
增强的 Celery Worker 启动脚本
包含错误处理、连接监控和自动重启功能
"""

import sys
import os
import time
import signal
import threading
from pathlib import Path
import logging
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os.environ['PYTHONPATH'] = str(project_root) + os.pathsep + os.environ.get('PYTHONPATH', '')

from celery_app import celery_app
from app.core.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s: %(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('celery_worker.log')
    ]
)
logger = logging.getLogger(__name__)

class CeleryManager:
    """Celery Worker 管理器"""
    
    def __init__(self):
        self.worker = None
        self.should_stop = False
        self.restart_count = 0
        self.max_restarts = 5
        
    def signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"接收到信号 {signum}，准备停止worker...")
        self.should_stop = True
        if self.worker:
            self.worker.terminate()
    
    def check_redis_connection(self):
        """检查Redis连接"""
        try:
            import redis
            
            # 解析Redis URL
            redis_url = settings.CELERY_BROKER_URL
            logger.info(f"检查Redis连接: {redis_url}")
            
            r = redis.from_url(redis_url)
            r.ping()
            logger.info("✅ Redis连接正常")
            return True
        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            return False
    
    def cleanup_orphaned_tasks(self):
        """清理孤立任务"""
        try:
            import redis
            
            logger.info("🧹 开始清理孤立任务...")
            r = redis.from_url(settings.CELERY_BROKER_URL)
            
            # 获取所有任务键
            task_keys = r.keys("celery-task-meta-*")
            logger.info(f"发现 {len(task_keys)} 个任务元数据")
            
            if task_keys:
                # 删除过期的任务元数据（超过1小时）
                current_time = time.time()
                cleaned_count = 0
                
                for key in task_keys:
                    try:
                        ttl = r.ttl(key)
                        if ttl == -1 or ttl > 3600:  # 没有TTL或TTL太长
                            r.expire(key, 3600)  # 设置1小时过期
                            cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"处理键 {key} 时出错: {e}")
                
                logger.info(f"✅ 清理完成，处理了 {cleaned_count} 个任务")
            else:
                logger.info("✅ 没有发现需要清理的任务")
                
        except Exception as e:
            logger.error(f"❌ 清理孤立任务失败: {e}")
    
    def start_worker(self):
        """启动Celery Worker"""
        try:
            logger.info("🚀 启动Celery Worker...")
            
            # 检查Redis连接
            if not self.check_redis_connection():
                logger.error("Redis连接失败，无法启动worker")
                return False
            
            # 清理孤立任务
            self.cleanup_orphaned_tasks()
            
            # 启动worker
            argv = [
                'worker',
                '--app=celery_app',
                '--loglevel=info',
                '--concurrency=4',
                '--pool=solo' if sys.platform == 'win32' else '--pool=prefork',
                '--time-limit=600',
                '--soft-time-limit=300',
                '--max-tasks-per-child=1000',
                '--max-memory-per-child=200000',
                '--without-gossip',
                '--without-mingle',
                '--without-heartbeat'
            ]
            
            # 启动worker
            self.worker = celery_app.Worker()
            self.worker.start(argv=argv)
            
        except KeyboardInterrupt:
            logger.info("收到中断信号，停止worker...")
            return False
        except Exception as e:
            logger.error(f"Worker启动失败: {e}")
            return False
        
        return True
    
    def monitor_worker(self):
        """监控Worker状态"""
        while not self.should_stop:
            try:
                # 检查Redis连接
                if not self.check_redis_connection():
                    logger.warning("Redis连接丢失，将在30秒后重试...")
                    time.sleep(30)
                    continue
                
                # 休眠60秒后再次检查
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"监控过程中出错: {e}")
                time.sleep(30)
    
    def run(self):
        """运行Celery Manager"""
        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("=" * 60)
        logger.info("🎯 AI内容安全监控系统 - Celery Worker Manager")
        logger.info(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"🖥️  平台: {sys.platform}")
        logger.info(f"🐍 Python版本: {sys.version}")
        logger.info("=" * 60)
        
        while not self.should_stop and self.restart_count < self.max_restarts:
            try:
                success = self.start_worker()
                
                if not success:
                    self.restart_count += 1
                    if self.restart_count < self.max_restarts:
                        wait_time = min(60 * self.restart_count, 300)  # 最多等待5分钟
                        logger.warning(f"Worker启动失败，{wait_time}秒后重试 (第{self.restart_count}次)")
                        time.sleep(wait_time)
                    else:
                        logger.error("达到最大重启次数，停止尝试")
                        break
                else:
                    # 重置重启计数
                    self.restart_count = 0
                    
            except Exception as e:
                logger.error(f"运行过程中出错: {e}")
                self.restart_count += 1
                if self.restart_count < self.max_restarts:
                    time.sleep(30)
                else:
                    break
        
        logger.info("Celery Worker Manager 已停止")

def main():
    """主函数"""
    try:
        manager = CeleryManager()
        manager.run()
    except Exception as e:
        logger.error(f"启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()