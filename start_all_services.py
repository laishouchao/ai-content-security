#!/usr/bin/env python3
"""
AI内容安全监控系统 - 统一启动脚本
一键启动后端、前端和Celery服务
"""

import sys
import os
import time
import signal
import subprocess
import threading
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
    format='[%(asctime)s: %(levelname)s/%(name)s] %(message)s'
)
logger = logging.getLogger("ServiceManager")

class ServiceManager:
    """服务管理器 - 统一管理所有服务"""
    
    def __init__(self):
        self.processes = {}
        self.should_stop = False
        
    def signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"接收到信号 {signum}，正在停止所有服务...")
        self.should_stop = True
        self.stop_all_services()
    
    def test_prerequisites(self):
        """检查先决条件"""
        logger.info("检查系统先决条件...")
        
        # 检查Python
        python_version = sys.version_info
        if python_version < (3, 8):
            logger.error(f"Python版本过低: {python_version}, 需要 >= 3.8")
            return False
        logger.info(f"✅ Python版本: {python_version.major}.{python_version.minor}")
        
        # 检查Node.js
        try:
            result = subprocess.run(['node', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.info(f"✅ Node.js版本: {result.stdout.strip()}")
            else:
                logger.warning("⚠️ Node.js未找到，前端服务可能无法启动")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("⚠️ Node.js检查失败，前端服务可能无法启动")
        
        # 检查必要文件
        required_files = ['main.py', 'celery_app.py', 'frontend/package.json']
        for file_path in required_files:
            if not (project_root / file_path).exists():
                logger.error(f"❌ 缺少必要文件: {file_path}")
                return False
        
        logger.info("✅ 先决条件检查通过")
        return True
    
    def test_redis_connection(self):
        """测试Redis连接"""
        try:
            from app.core.config import settings
            import redis
            
            logger.info("测试Redis连接...")
            r = redis.from_url(settings.CELERY_BROKER_URL)
            result = r.ping()
            logger.info(f"✅ Redis连接正常: {result}")
            return True
        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            return False
    
    def start_backend(self):
        """启动后端服务"""
        try:
            logger.info("🚀 启动后端FastAPI服务...")
            
            cmd = [
                sys.executable, "-m", "uvicorn", 
                "main:app", 
                "--host", "0.0.0.0", 
                "--port", "8000", 
                "--reload"
            ]
            
            self.processes['backend'] = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=project_root
            )
            
            logger.info("✅ 后端服务启动中... (http://localhost:8000)")
            return True
            
        except Exception as e:
            logger.error(f"❌ 后端服务启动失败: {e}")
            return False
    
    def start_celery(self):
        """启动Celery Worker"""
        try:
            logger.info("🚀 启动Celery Worker...")
            
            # 等待后端启动
            time.sleep(3)
            
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
            
            self.processes['celery'] = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=project_root
            )
            
            logger.info("✅ Celery Worker启动中...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Celery Worker启动失败: {e}")
            return False
    
    def start_frontend(self):
        """启动前端服务"""
        try:
            logger.info("🚀 启动前端Vite服务...")
            
            # 等待后端完全启动
            time.sleep(5)
            
            # 检查npm是否可用
            try:
                subprocess.run(['npm', '--version'], 
                             check=True, capture_output=True, timeout=10)
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                logger.error("❌ npm未找到，请安装Node.js")
                return False
            
            frontend_dir = project_root / "frontend"
            if not frontend_dir.exists():
                logger.error("❌ 前端目录不存在")
                return False
            
            cmd = ["npm", "run", "dev"]
            
            self.processes['frontend'] = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=frontend_dir
            )
            
            logger.info("✅ 前端服务启动中... (http://localhost:5173)")
            return True
            
        except Exception as e:
            logger.error(f"❌ 前端服务启动失败: {e}")
            return False
    
    def monitor_services(self):
        """监控服务状态"""
        logger.info("📊 开始监控服务状态...")
        
        while not self.should_stop:
            time.sleep(10)  # 每10秒检查一次
            
            # 检查各个服务状态
            for service_name, process in list(self.processes.items()):
                if process.poll() is not None:
                    logger.error(f"❌ {service_name} 服务意外退出 (返回码: {process.returncode})")
                    # 可以在这里添加自动重启逻辑
    
    def stop_all_services(self):
        """停止所有服务"""
        logger.info("🛑 停止所有服务...")
        
        for service_name, process in self.processes.items():
            if process.poll() is None:  # 进程还在运行
                logger.info(f"停止 {service_name} 服务...")
                try:
                    process.terminate()
                    process.wait(timeout=10)
                    logger.info(f"✅ {service_name} 服务已停止")
                except subprocess.TimeoutExpired:
                    logger.warning(f"⚠️ 强制终止 {service_name} 服务...")
                    process.kill()
                    process.wait()
                except Exception as e:
                    logger.error(f"❌ 停止 {service_name} 服务时出错: {e}")
    
    def run(self):
        """运行服务管理器"""
        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("=" * 60)
        logger.info("🎯 AI内容安全监控系统 - 统一启动管理器")
        logger.info("=" * 60)
        
        try:
            # 检查先决条件
            if not self.test_prerequisites():
                logger.error("❌ 先决条件检查失败")
                return False
            
            # 检查Redis连接
            if not self.test_redis_connection():
                logger.error("❌ Redis连接失败，请检查Redis服务")
                return False
            
            # 按顺序启动服务
            services_to_start = [
                ("后端服务", self.start_backend),
                ("Celery Worker", self.start_celery),
                ("前端服务", self.start_frontend)
            ]
            
            for service_name, start_func in services_to_start:
                if not start_func():
                    logger.error(f"❌ {service_name} 启动失败")
                    self.stop_all_services()
                    return False
            
            # 等待所有服务完全启动
            logger.info("⏳ 等待所有服务完全启动...")
            time.sleep(8)
            
            # 显示启动完成信息
            logger.info("=" * 60)
            logger.info("🎉 所有服务启动完成！")
            logger.info("")
            logger.info("🌐 访问地址:")
            logger.info("   - 前端界面: http://localhost:5173")
            logger.info("   - 后端API: http://localhost:8000")
            logger.info("   - API文档: http://localhost:8000/docs")
            logger.info("")
            logger.info("💡 按 Ctrl+C 停止所有服务")
            logger.info("=" * 60)
            
            # 启动监控线程
            monitor_thread = threading.Thread(target=self.monitor_services)
            monitor_thread.daemon = True
            monitor_thread.start()
            
            # 保持运行状态
            while not self.should_stop:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("收到中断信号...")
            self.should_stop = True
        except Exception as e:
            logger.error(f"运行过程中出错: {e}")
            return False
        finally:
            self.stop_all_services()
            logger.info("🏁 所有服务已停止")
        
        return True

def main():
    """主函数"""
    manager = ServiceManager()
    success = manager.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()