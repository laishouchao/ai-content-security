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
project_root = Path(__file__).parent.parent.parent
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
        node_found = False
        try:
            result = subprocess.run(['node', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.info(f"✅ Node.js版本: {result.stdout.strip()}")
                node_found = True
            else:
                logger.warning("⚠️ Node.js未找到，前端服务可能无法启动")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("⚠️ Node.js检查失败，前端服务可能无法启动")
        
        # 检查npm（如果Node.js存在的话）
        if node_found:
            npm_commands = ['npm']
            if sys.platform == 'win32':
                npm_commands = ['npm.cmd', 'npm']
            
            npm_found = False
            for npm_cmd in npm_commands:
                try:
                    result = subprocess.run([npm_cmd, '--version'], 
                                           capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        logger.info(f"✅ npm版本: {result.stdout.strip()}")
                        npm_found = True
                        break
                except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                    continue
            
            if not npm_found:
                logger.warning("⚠️ npm未找到，前端服务可能无法启动")
        
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
        redis = None
        try:
            from app.core.config import settings
            import redis
            
            logger.info("测试Redis连接...")
            
            # 检查CELERY_BROKER_URL是否配置
            broker_url = getattr(settings, 'CELERY_BROKER_URL', None)
            if not broker_url:
                logger.error("❌ CELERY_BROKER_URL未配置")
                return False
            
            logger.info(f"连接Redis: {broker_url}")
            
            # 创建Redis连接
            r = redis.from_url(broker_url)
            
            # 检查连接对象是否创建成功
            if r is None:
                logger.error("❌ Redis连接对象创建失败")
                return False
            
            # 测试连接
            result = r.ping()
            logger.info(f"✅ Redis连接正常: {result}")
            return True
            
        except ImportError as e:
            logger.error(f"❌ 导入模块失败: {e}")
            return False
        except Exception as e:
            # 对于Redis相关的具体异常，检查异常类型
            error_message = str(e)
            if 'ConnectionError' in str(type(e)) or '连接' in error_message:
                logger.error(f"❌ Redis连接错误: {e}")
            elif 'TimeoutError' in str(type(e)) or '超时' in error_message:
                logger.error(f"❌ Redis连接超时: {e}")
            elif 'AttributeError' in str(type(e)):
                logger.error(f"❌ 配置属性错误: {e}")
            else:
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
            
            # 不重定向输出，让后端服务直接输出到控制台
            # 这样可以避免输出缓冲区满导致的进程阻塞
            self.processes['backend'] = subprocess.Popen(
                cmd,
                cwd=project_root
            )
            
            logger.info("✅ 后端服务启动中... (http://localhost:8000)")
            
            # 等待一下让服务有时间启动
            time.sleep(2)
            
            # 检查进程是否还在运行
            if self.processes['backend'].poll() is not None:
                logger.error(f"❌ 后端服务启动后立即退出 (return code: {self.processes['backend'].returncode})")
                return False
                
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
            
            # 不重定向输出，让Celery直接输出到控制台
            self.processes['celery'] = subprocess.Popen(
                cmd,
                cwd=project_root
            )
            
            logger.info("✅ Celery Worker启动中...")
            
            # 检查进程是否还在运行
            time.sleep(1)
            if self.processes['celery'].poll() is not None:
                logger.error(f"❌ Celery Worker启动后立即退出 (return code: {self.processes['celery'].returncode})")
                return False
                
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
            
            # 检查npm是否可用（Windows平台需要特殊处理）
            npm_commands = ['npm']
            if sys.platform == 'win32':
                npm_commands = ['npm.cmd', 'npm']
            
            npm_found = False
            npm_version = None
            
            for npm_cmd in npm_commands:
                try:
                    result = subprocess.run([npm_cmd, '--version'], 
                                           check=True, capture_output=True, 
                                           text=True, timeout=10)
                    npm_version = result.stdout.strip()
                    npm_found = True
                    logger.info(f"✅ npm版本: {npm_version} (命令: {npm_cmd})")
                    break
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                    continue
            
            if not npm_found:
                logger.error("❌ npm未找到，请检查：")
                logger.error("   1. Node.js是否正确安装")
                logger.error("   2. npm是否在PATH环境变量中")
                logger.error("   3. 在命令行中运行 'npm --version' 测试")
                return False
            
            frontend_dir = project_root / "frontend"
            if not frontend_dir.exists():
                logger.error("❌ 前端目录不存在")
                return False
            
            # 使用找到的npm命令
            npm_cmd = npm_commands[0] if npm_found else 'npm'
            cmd = [npm_cmd, "run", "dev"]
            
            # 不重定向输出，让前端服务直接输出到控制台
            self.processes['frontend'] = subprocess.Popen(
                cmd,
                cwd=frontend_dir
            )
            
            logger.info("✅ 前端服务启动中... (http://localhost:5173)")
            
            # 检查进程是否还在运行
            time.sleep(2)
            if self.processes['frontend'].poll() is not None:
                logger.error(f"❌ 前端服务启动后立即退出 (return code: {self.processes['frontend'].returncode})")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ 前端服务启动失败: {e}")
            return False
        
    def check_service_health(self):
        """检查服务健康状态"""
        logger.info("📈 检查服务健康状态...")
            
        # 检查后端API健康状态
        try:
            import requests
            response = requests.get('http://localhost:8000/api/v1/health', timeout=5)
            if response.status_code == 200:
                logger.info("✅ 后端API服务健康")
                result = response.json()
                if result.get('status') == 'healthy':
                    logger.info("✅ 后端服务内部状态正常")
            else:
                logger.warning(f"⚠️ 后端API健康检查失败: {response.status_code}")
                return False
        except ImportError:
            logger.warning("⚠️ requests模块未安装，跳过API健康检查")
            return True  # 不因为缺少requests就失败
        except Exception as e:
            # 更通用的异常处理
            error_type = type(e).__name__
            if 'ConnectionError' in error_type or 'Timeout' in error_type:
                logger.error(f"❌ 后端API连接失败: {e}")
            else:
                logger.error(f"❌ 后端API健康检查遇到错误 ({error_type}): {e}")
            return False
            
        # 检查前端服务
        try:
            import requests
            response = requests.get('http://localhost:5173', timeout=5)
            if response.status_code == 200:
                logger.info("✅ 前端服务健康")
            else:
                logger.warning(f"⚠️ 前端服务健康检查失败: {response.status_code}")
        except ImportError:
            pass  # 前端检查不是必须的
        except Exception as e:
            error_type = type(e).__name__
            logger.warning(f"⚠️ 前端服务无法访问 ({error_type}): {e}")
                
        return True
        
    def check_process_output(self):
        """检查进程输出信息"""
        for service_name, process in self.processes.items():
            if process.poll() is not None:
                logger.error(f"❌ {service_name} 服务意外退出 (return code: {process.returncode})")
                    
                # 由于我们不再重定向输出，所以无法读取stdout/stderr
                # 但可以提供一些诊断信息
                logger.error(f"❌ {service_name} 服务异常终止，请检查上方的日志输出")
                    
                return False
        return True
    
    def diagnose_connection_issues(self):
        """诊断连接问题"""
        logger.info("🔍 进行连接问题诊断...")
        
        # 检查端口占用情况
        try:
            import socket
            
            # 检查8000端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 8000))
            sock.close()
            if result == 0:
                logger.info("✅ 端口8000可访问")
            else:
                logger.error(f"❌ 端口8000不可访问 (error code: {result})")
            
            # 检查5173端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 5173))
            sock.close()
            if result == 0:
                logger.info("✅ 端口5173可访问")
            else:
                logger.error(f"❌ 端口5173不可访问 (error code: {result})")
                
        except Exception as e:
            logger.error(f"❌ 端口检查失败: {e}")
        
        # 检查进程状态
        logger.info("🔍 检查进程状态:")
        for service_name, process in self.processes.items():
            if process.poll() is None:
                logger.info(f"✅ {service_name}: 运行中 (PID: {process.pid})")
            else:
                logger.error(f"❌ {service_name}: 已退出 (return code: {process.returncode})")
                
                # 尝试读取错误输出
                try:
                    if hasattr(process, 'stdout') and process.stdout:
                        output = process.stdout.read()
                        if output:
                            logger.error(f"{service_name} output: {output[-1000:]}")
                except Exception as e:
                    logger.warning(f"无法读取{service_name}输出: {e}")
    
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
            
            # 检查进程状态
            if not self.check_process_output():
                logger.error("❌ 服务启动失败")
                self.stop_all_services()
                return False
            
            # 检查服务健康状态
            if not self.check_service_health():
                logger.error("❌ 服务健康检查失败")
                self.diagnose_connection_issues()
                self.stop_all_services()
                return False
            
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