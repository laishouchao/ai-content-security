#!/usr/bin/env python3
"""
稳定版 Celery Worker 启动脚本
专门解决连接错误和配置冲突问题
"""

import sys
import os
import time
import signal
import subprocess
import psutil
from pathlib import Path
import logging

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os.environ['PYTHONPATH'] = str(project_root) + os.pathsep + os.environ.get('PYTHONPATH', '')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s: %(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('celery_stable.log')
    ]
)
logger = logging.getLogger(__name__)

class StableCeleryManager:
    """稳定版 Celery Manager"""
    
    def __init__(self):
        self.worker_process = None
        self.should_stop = False
        self.restart_count = 0
        self.max_restarts = 3
        
    def signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"接收到信号 {signum}，准备停止...")
        self.should_stop = True
        self.cleanup()
    
    def cleanup(self):
        """清理进程"""
        if self.worker_process:
            try:
                # 优雅关闭
                self.worker_process.terminate()
                self.worker_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # 强制关闭
                self.worker_process.kill()
                self.worker_process.wait()
            except:
                pass
    
    def check_port_usage(self):
        """检查端口使用情况"""
        try:
            # 检查是否有其他Celery进程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'celery' in proc.info['name'].lower():
                        logger.info(f"发现Celery进程: PID={proc.info['pid']} CMD={' '.join(proc.info['cmdline'][:3])}")
                except:
                    continue
        except:
            pass
    
    def test_redis_connection(self):
        """测试Redis连接"""
        try:
            from app.core.config import settings
            import redis
            
            logger.info("测试Redis连接...")
            r = redis.from_url(settings.CELERY_BROKER_URL)
            result = r.ping()
            logger.info(f"Redis连接测试: {result}")
            return True
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            return False
    
    def cleanup_old_celery_data(self):
        """清理旧的Celery数据"""
        try:
            from app.core.config import settings
            import redis
            
            logger.info("清理旧的Celery数据...")
            r = redis.from_url(settings.CELERY_BROKER_URL)
            
            # 删除可能导致冲突的键
            patterns = [
                "celery-task-meta-*",
                "_kombu.binding.*",
                "unacked*"
            ]
            
            for pattern in patterns:
                keys = r.keys(pattern)
                if keys:
                    r.delete(*keys)
                    logger.info(f"清理了 {len(keys)} 个 {pattern} 键")
            
            logger.info("清理完成")
            return True
            
        except Exception as e:
            logger.error(f"清理失败: {e}")
            return False
    
    def start_worker_process(self):
        """启动Worker进程"""
        try:
            logger.info("启动Celery Worker进程...")
            
            # 构建启动命令
            cmd = [
                sys.executable, "-m", "celery", 
                "-A", "celery_app", 
                "worker",
                "--loglevel=info",
                "--concurrency=4",
                f"--pool={'solo' if sys.platform == 'win32' else 'prefork'}",
                "--without-gossip",
                "--without-mingle", 
                "--without-heartbeat",
                "--time-limit=600",
                "--soft-time-limit=300",
                "--max-tasks-per-child=1000",
                "--max-memory-per-child=200000"
            ]
            
            logger.info(f"启动命令: {' '.join(cmd)}")
            
            # 启动进程
            self.worker_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # 监控输出
            return self.monitor_worker_output()
            
        except Exception as e:
            logger.error(f"启动Worker失败: {e}")
            return False
    
    def monitor_worker_output(self):
        """监控Worker输出"""
        logger.info("开始监控Worker输出...")
        
        error_count = 0
        success_indicators = [
            "ready.",
            "Connected to redis"
        ]
        
        error_indicators = [
            "not enough values to unpack",
            "NoneType' object has no attribute '_callbacks'",
            "CRITICAL",
            "Unrecoverable error"
        ]
        
        start_time = time.time()
        max_startup_time = 60  # 60秒启动超时
        
        try:
            while self.worker_process.poll() is None:
                if time.time() - start_time > max_startup_time:
                    logger.error("Worker启动超时")
                    return False
                
                # 读取输出行
                line = self.worker_process.stdout.readline()
                if line:
                    line = line.strip()
                    print(line)  # 显示输出
                    
                    # 检查成功指示器
                    for indicator in success_indicators:
                        if indicator in line:
                            logger.info(f"检测到成功指示器: {indicator}")
                            return True
                    
                    # 检查错误指示器
                    for indicator in error_indicators:
                        if indicator in line:
                            error_count += 1
                            logger.error(f"检测到错误: {line}")
                            
                            if error_count >= 3:
                                logger.error("错误过多，停止Worker")
                                return False
                
                time.sleep(0.1)
            
            # 进程已退出
            return_code = self.worker_process.poll()
            logger.error(f"Worker进程异常退出，返回码: {return_code}")
            return False
            
        except Exception as e:
            logger.error(f"监控过程异常: {e}")
            return False
    
    def run(self):
        """运行管理器"""
        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("AI内容安全监控系统 - 稳定版 Celery Manager")
        logger.info("=" * 60)
        
        try:
            while not self.should_stop and self.restart_count < self.max_restarts:
                logger.info(f"启动尝试 #{self.restart_count + 1}")
                
                # 检查端口使用
                self.check_port_usage()
                
                # 测试Redis连接
                if not self.test_redis_connection():
                    logger.error("Redis连接失败，30秒后重试...")
                    time.sleep(30)
                    self.restart_count += 1
                    continue
                
                # 清理旧数据
                self.cleanup_old_celery_data()
                
                # 启动Worker
                success = self.start_worker_process()
                
                if success:
                    logger.info("Worker启动成功，进入运行状态...")
                    
                    # 保持运行状态
                    try:
                        while not self.should_stop and self.worker_process.poll() is None:
                            time.sleep(5)
                            
                            # 定期检查Redis连接
                            if not self.test_redis_connection():
                                logger.warning("Redis连接丢失，重启Worker...")
                                self.cleanup()
                                break
                        
                        if not self.should_stop:
                            logger.warning("Worker进程意外退出")
                            self.restart_count += 1
                            
                    except KeyboardInterrupt:
                        logger.info("收到中断信号...")
                        self.should_stop = True
                        
                else:
                    logger.error("Worker启动失败")
                    self.restart_count += 1
                    
                    if self.restart_count < self.max_restarts:
                        wait_time = min(30 * self.restart_count, 120)
                        logger.info(f"{wait_time}秒后重试...")
                        time.sleep(wait_time)
                
                # 清理当前进程
                self.cleanup()
            
            if self.restart_count >= self.max_restarts:
                logger.error(f"达到最大重启次数 ({self.max_restarts})，停止尝试")
            
        finally:
            self.cleanup()
            logger.info("Celery Manager 已停止")

def main():
    """主函数"""
    try:
        manager = StableCeleryManager()
        manager.run()
    except Exception as e:
        logger.error(f"启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()