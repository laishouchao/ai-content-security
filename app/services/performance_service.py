"""
性能数据收集服务

定期收集系统性能指标并存储到数据库
"""

import asyncio
import psutil
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.performance import PerformanceLog, PerformanceAlert
from app.models.task import ScanTask
from app.models.user import User
from app.core.prometheus import (
    ACTIVE_USERS, CONCURRENT_TASKS, DATABASE_CONNECTIONS, 
    REDIS_CONNECTIONS, ERROR_COUNT
)

logger = logging.getLogger(__name__)


class PerformanceCollector:
    """性能数据收集器"""
    
    def __init__(self):
        self.logger = logger
        self.last_network_stats = None
        self.request_counts = []
        self.response_times = []
        
    async def collect_system_metrics(self) -> Dict[str, Any]:
        """收集系统性能指标"""
        try:
            # CPU指标
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存指标
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_mb = memory.available / 1024 / 1024
            memory_total_mb = memory.total / 1024 / 1024
            
            # 磁盘指标
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_free_gb = disk.free / 1024 / 1024 / 1024
            disk_total_gb = disk.total / 1024 / 1024 / 1024
            
            # 网络指标
            net_io = psutil.net_io_counters()
            network_bytes_sent = net_io.bytes_sent
            network_bytes_recv = net_io.bytes_recv
            network_packets_sent = net_io.packets_sent
            network_packets_recv = net_io.packets_recv
            
            # 进程指标
            process_count = len(psutil.pids())
            current_process = psutil.Process()
            thread_count = current_process.num_threads()
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'memory_available_mb': memory_available_mb,
                'memory_total_mb': memory_total_mb,
                'disk_percent': disk_percent,
                'disk_free_gb': disk_free_gb,
                'disk_total_gb': disk_total_gb,
                'network_bytes_sent': network_bytes_sent,
                'network_bytes_recv': network_bytes_recv,
                'network_packets_sent': network_packets_sent,
                'network_packets_recv': network_packets_recv,
                'process_count': process_count,
                'thread_count': thread_count,
            }
            
        except Exception as e:
            self.logger.error(f"收集系统指标失败: {e}")
            return {}
    
    async def collect_database_metrics(self, db: AsyncSession) -> Dict[str, Any]:
        """收集数据库性能指标"""
        try:
            # 获取数据库连接池信息
            engine = db.bind
            pool = engine.pool
            
            db_active_connections = pool.checkedout()
            db_total_connections = pool.size()
            
            # 简单的查询计数统计（实际项目中可以更复杂）
            start_time = time.time()
            await db.execute(select(func.count()).select_from(ScanTask))
            query_time = (time.time() - start_time) * 1000  # 转换为毫秒
            
            return {
                'db_active_connections': db_active_connections,
                'db_total_connections': db_total_connections,
                'db_avg_query_time': query_time,
            }
            
        except Exception as e:
            self.logger.error(f"收集数据库指标失败: {e}")
            return {}
    
    async def collect_redis_metrics(self) -> Dict[str, Any]:
        """收集Redis性能指标"""
        try:
            from app.core.database import redis_client
            
            if redis_client:
                # 检查连接状态
                redis_connected = 1 if await redis_client.ping() else 0
                
                # 获取Redis信息
                info = await redis_client.info('memory')
                redis_memory_usage_mb = info.get('used_memory', 0) / 1024 / 1024
                
                # 获取键数量
                redis_keys_count = await redis_client.dbsize()
                
                return {
                    'redis_connected': redis_connected,
                    'redis_memory_usage_mb': redis_memory_usage_mb,
                    'redis_keys_count': redis_keys_count,
                }
            else:
                return {
                    'redis_connected': 0,
                    'redis_memory_usage_mb': 0,
                    'redis_keys_count': 0,
                }
                
        except Exception as e:
            self.logger.error(f"收集Redis指标失败: {e}")
            return {
                'redis_connected': 0,
                'redis_memory_usage_mb': 0,
                'redis_keys_count': 0,
            }
    
    async def collect_celery_metrics(self) -> Dict[str, Any]:
        """收集Celery性能指标"""
        try:
            from celery import current_app as celery_app
            
            # 获取任务状态统计
            inspect = celery_app.control.inspect()
            
            # 活跃任务
            active_tasks = inspect.active()
            celery_active_tasks = sum(len(tasks) for tasks in (active_tasks or {}).values())
            
            # 等待任务（需要额外配置）
            # 这里简化处理，实际项目中可以从Redis或数据库获取
            celery_pending_tasks = 0
            celery_failed_tasks = 0
            celery_completed_tasks = 0
            
            return {
                'celery_active_tasks': celery_active_tasks,
                'celery_pending_tasks': celery_pending_tasks,
                'celery_failed_tasks': celery_failed_tasks,
                'celery_completed_tasks': celery_completed_tasks,
            }
            
        except Exception as e:
            self.logger.error(f"收集Celery指标失败: {e}")
            return {}
    
    async def collect_application_metrics(self, db: AsyncSession) -> Dict[str, Any]:
        """收集应用层性能指标"""
        try:
            # 活跃用户数（简化：过去5分钟内有活动的用户）
            five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
            active_users_query = select(func.count(User.id)).where(
                User.last_login > five_minutes_ago
            )
            active_users_result = await db.execute(active_users_query)
            active_users = active_users_result.scalar() or 0
            
            # 运行中的扫描任务数
            running_tasks_query = select(func.count(ScanTask.id)).where(
                ScanTask.status == 'running'
            )
            running_tasks_result = await db.execute(running_tasks_query)
            running_scan_tasks = running_tasks_result.scalar() or 0
            
            # 总违规数（今天）
            today = datetime.utcnow().date()
            from app.models.task import ViolationRecord
            violations_query = select(func.count(ViolationRecord.id)).where(
                func.date(ViolationRecord.created_at) == today
            )
            violations_result = await db.execute(violations_query)
            total_violations = violations_result.scalar() or 0
            
            return {
                'active_users': active_users,
                'running_scan_tasks': running_scan_tasks,
                'total_violations': total_violations,
            }
            
        except Exception as e:
            self.logger.error(f"收集应用指标失败: {e}")
            return {}
    
    async def collect_performance_metrics(self) -> Dict[str, Any]:
        """收集性能相关指标"""
        try:
            # 计算平均响应时间
            avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
            
            # 计算错误率（简化处理）
            error_rate = 0.0  # 实际项目中可以从日志或监控系统获取
            
            # 请求数
            request_count = sum(self.request_counts) if self.request_counts else 0
            
            # 清理历史数据（保持最近的100个点）
            if len(self.response_times) > 100:
                self.response_times = self.response_times[-50:]
            if len(self.request_counts) > 100:
                self.request_counts = self.request_counts[-50:]
            
            return {
                'avg_response_time': avg_response_time,
                'error_rate': error_rate,
                'request_count': request_count,
            }
            
        except Exception as e:
            self.logger.error(f"收集性能指标失败: {e}")
            return {}
    
    async def collect_all_metrics(self) -> Dict[str, Any]:
        """收集所有性能指标"""
        metrics = {}
        
        # 系统指标
        system_metrics = await self.collect_system_metrics()
        metrics.update(system_metrics)
        
        # 数据库相关指标
        async with AsyncSessionLocal() as db:
            try:
                db_metrics = await self.collect_database_metrics(db)
                metrics.update(db_metrics)
                
                app_metrics = await self.collect_application_metrics(db)
                metrics.update(app_metrics)
                
            except Exception as e:
                self.logger.error(f"数据库操作失败: {e}")
        
        # Redis指标
        redis_metrics = await self.collect_redis_metrics()
        metrics.update(redis_metrics)
        
        # Celery指标
        celery_metrics = await self.collect_celery_metrics()
        metrics.update(celery_metrics)
        
        # 性能指标
        perf_metrics = await self.collect_performance_metrics()
        metrics.update(perf_metrics)
        
        return metrics
    
    async def save_performance_log(self, metrics: Dict[str, Any]) -> None:
        """保存性能日志到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                performance_log = PerformanceLog(**metrics)
                db.add(performance_log)
                await db.commit()
                
                self.logger.debug(f"性能日志已保存: CPU={metrics.get('cpu_percent', 0):.1f}%, "
                                f"Memory={metrics.get('memory_percent', 0):.1f}%")
                
        except Exception as e:
            self.logger.error(f"保存性能日志失败: {e}")
    
    async def check_and_create_alerts(self, metrics: Dict[str, Any]) -> None:
        """检查指标并创建告警"""
        try:
            async with AsyncSessionLocal() as db:
                alerts = []
                
                # CPU告警
                cpu_percent = metrics.get('cpu_percent')
                if cpu_percent and cpu_percent > 80:
                    alerts.append(PerformanceAlert(
                        alert_type='cpu',
                        severity='warning' if cpu_percent < 90 else 'critical',
                        title='CPU使用率过高',
                        message=f'当前CPU使用率: {cpu_percent:.1f}%',
                        current_value=cpu_percent,
                        threshold_value=80.0,
                    ))
                
                # 内存告警
                memory_percent = metrics.get('memory_percent')
                if memory_percent and memory_percent > 85:
                    alerts.append(PerformanceAlert(
                        alert_type='memory',
                        severity='warning' if memory_percent < 95 else 'critical',
                        title='内存使用率过高',
                        message=f'当前内存使用率: {memory_percent:.1f}%',
                        current_value=memory_percent,
                        threshold_value=85.0,
                    ))
                
                # 磁盘告警
                disk_percent = metrics.get('disk_percent')
                if disk_percent and disk_percent > 90:
                    alerts.append(PerformanceAlert(
                        alert_type='disk',
                        severity='warning' if disk_percent < 95 else 'critical',
                        title='磁盘空间不足',
                        message=f'当前磁盘使用率: {disk_percent:.1f}%',
                        current_value=disk_percent,
                        threshold_value=90.0,
                    ))
                
                # Redis连接告警
                redis_connected = metrics.get('redis_connected', 0)
                if redis_connected == 0:
                    alerts.append(PerformanceAlert(
                        alert_type='redis',
                        severity='critical',
                        title='Redis连接异常',
                        message='Redis服务无法连接',
                        current_value=0,
                        threshold_value=1,
                    ))
                
                # 保存告警
                for alert in alerts:
                    db.add(alert)
                
                if alerts:
                    await db.commit()
                    self.logger.warning(f"创建了 {len(alerts)} 个性能告警")
                
        except Exception as e:
            self.logger.error(f"创建性能告警失败: {e}")
    
    def add_response_time(self, response_time_ms: float) -> None:
        """添加响应时间数据点"""
        self.response_times.append(response_time_ms)
    
    def add_request_count(self, count: int = 1) -> None:
        """添加请求计数"""
        self.request_counts.append(count)


class PerformanceMonitor:
    """性能监控服务"""
    
    def __init__(self, collection_interval: int = 60):
        self.collector = PerformanceCollector()
        self.collection_interval = collection_interval  # 收集间隔（秒）
        self.is_running = False
        self.task = None
        self.logger = logger
        
    async def start(self) -> None:
        """启动性能监控"""
        if self.is_running:
            self.logger.warning("性能监控已在运行中")
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._monitoring_loop())
        self.logger.info(f"性能监控已启动，收集间隔: {self.collection_interval}秒")
    
    async def stop(self) -> None:
        """停止性能监控"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("性能监控已停止")
    
    async def _monitoring_loop(self) -> None:
        """监控循环"""
        while self.is_running:
            try:
                # 收集性能指标
                metrics = await self.collector.collect_all_metrics()
                
                if metrics:
                    # 保存到数据库
                    await self.collector.save_performance_log(metrics)
                    
                    # 检查告警
                    await self.collector.check_and_create_alerts(metrics)
                
                # 等待下次收集
                await asyncio.sleep(self.collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"性能监控循环出错: {e}")
                await asyncio.sleep(5)  # 出错后短暂等待
    
    async def get_recent_metrics(self, hours: int = 1) -> List[Dict[str, Any]]:
        """获取最近的性能指标"""
        try:
            async with AsyncSessionLocal() as db:
                since_time = datetime.utcnow() - timedelta(hours=hours)
                
                query = select(PerformanceLog).where(
                    PerformanceLog.timestamp >= since_time
                ).order_by(desc(PerformanceLog.timestamp)).limit(1000)
                
                result = await db.execute(query)
                logs = result.scalars().all()
                
                return [log.to_dict() for log in logs]
                
        except Exception as e:
            self.logger.error(f"获取性能指标失败: {e}")
            return []
    
    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """获取活跃的告警"""
        try:
            async with AsyncSessionLocal() as db:
                query = select(PerformanceAlert).where(
                    PerformanceAlert.is_active == 1
                ).order_by(desc(PerformanceAlert.triggered_at))
                
                result = await db.execute(query)
                alerts = result.scalars().all()
                
                return [alert.to_dict() for alert in alerts]
                
        except Exception as e:
            self.logger.error(f"获取活跃告警失败: {e}")
            return []


# 全局性能监控实例
performance_monitor = PerformanceMonitor(collection_interval=60)  # 每分钟收集一次