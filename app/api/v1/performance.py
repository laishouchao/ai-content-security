"""
系统性能监控API
集成所有优化组件，提供统一的性能监控和管理接口
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio

from app.core.database import get_db
from app.core.redis_lock import lock_manager
from app.core.celery_optimizer import CeleryTaskManager, task_metrics
from app.core.memory_manager import memory_manager
from app.core.database_optimizer import DatabaseOptimizer, pool_manager, query_cache
from app.models.user import User
from app.core.dependencies import get_current_user
from app.core.logging import logger

router = APIRouter()


class SystemPerformanceService:
    """系统性能服务"""
    
    def __init__(self):
        self.db_optimizer = None
    
    async def initialize(self, db: AsyncSession):
        """初始化服务"""
        self.db_optimizer = DatabaseOptimizer(db)
    
    async def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取综合性能统计"""
        try:
            # 并发获取各组件统计信息
            tasks = [
                self._get_memory_stats(),
                self._get_database_stats(),
                self._get_celery_stats(),
                self._get_redis_stats(),
                self._get_system_health()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            stats = {
                'timestamp': datetime.utcnow().isoformat(),
                'memory_stats': results[0] if not isinstance(results[0], Exception) else {},
                'database_stats': results[1] if not isinstance(results[1], Exception) else {},
                'celery_stats': results[2] if not isinstance(results[2], Exception) else {},
                'redis_stats': results[3] if not isinstance(results[3], Exception) else {},
                'system_health': results[4] if not isinstance(results[4], Exception) else {}
            }
            
            # 计算整体健康分数
            stats['overall_health_score'] = self._calculate_health_score(stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"获取综合性能统计失败: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    async def _get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计"""
        return await memory_manager.get_system_stats()
    
    async def _get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计"""
        pool_status = await pool_manager.get_pool_status()
        cache_stats = query_cache.get_cache_stats()
        
        return {
            'connection_pool': pool_status,
            'query_cache': cache_stats
        }
    
    async def _get_celery_stats(self) -> Dict[str, Any]:
        """获取Celery统计"""
        queue_stats = await CeleryTaskManager.get_queue_stats()
        worker_stats = await CeleryTaskManager.get_worker_stats()
        
        return {
            'queues': queue_stats,
            'workers': worker_stats,
            'metrics': task_metrics.get_stats()
        }
    
    async def _get_redis_stats(self) -> Dict[str, Any]:
        """获取Redis统计"""
        try:
            if lock_manager.redis_client:
                info = await lock_manager.redis_client.info()
                return {
                    'connected': True,
                    'memory_usage': info.get('used_memory_human', 'N/A'),
                    'connected_clients': info.get('connected_clients', 0),
                    'operations_per_second': info.get('instantaneous_ops_per_sec', 0),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0)
                }
            else:
                return {'connected': False}
        except Exception as e:
            return {'connected': False, 'error': str(e)}
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """获取系统健康状态"""
        try:
            import psutil
            
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 磁盘使用率
            disk_usage = psutil.disk_usage('/')
            
            # 网络统计
            net_io = psutil.net_io_counters()
            
            return {
                'cpu_percent': round(cpu_percent, 1),
                'disk_usage': {
                    'total': disk_usage.total,
                    'used': disk_usage.used,
                    'free': disk_usage.free,
                    'percent': round((disk_usage.used / disk_usage.total) * 100, 1)
                },
                'network': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv
                }
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _calculate_health_score(self, stats: Dict[str, Any]) -> int:
        """计算系统健康分数（0-100）"""
        score = 100
        
        try:
            # 内存健康检查（权重：30%）
            memory_stats = stats.get('memory_stats', {})
            if memory_stats.get('memory_pressure', False):
                score -= 20
            
            memory_info = memory_stats.get('memory_info', {})
            if memory_info.get('process_memory', {}).get('percent', 0) > 80:
                score -= 10
            
            # 数据库健康检查（权重：25%）
            db_stats = stats.get('database_stats', {})
            pool_status = db_stats.get('connection_pool', {})
            if pool_status.get('available_connections', 0) < 2:
                score -= 15
            
            # Celery健康检查（权重：25%）
            celery_stats = stats.get('celery_stats', {})
            metrics = celery_stats.get('metrics', {})
            if metrics.get('failed_tasks', 0) > metrics.get('completed_tasks', 1) * 0.1:
                score -= 15
            
            # Redis健康检查（权重：10%）
            redis_stats = stats.get('redis_stats', {})
            if not redis_stats.get('connected', False):
                score -= 10
            
            # 系统健康检查（权重：10%）
            system_health = stats.get('system_health', {})
            if system_health.get('cpu_percent', 0) > 90:
                score -= 5
            
            disk_percent = system_health.get('disk_usage', {}).get('percent', 0)
            if disk_percent > 90:
                score -= 5
            
        except Exception as e:
            logger.error(f"计算健康分数失败: {e}")
            score = 50  # 默认分数
        
        return max(0, min(100, score))
    
    async def perform_optimization(self) -> Dict[str, Any]:
        """执行系统优化"""
        optimization_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'actions_performed': []
        }
        
        try:
            # 1. 内存优化
            await memory_manager.force_garbage_collection()
            optimization_results['actions_performed'].append('强制垃圾回收')
            
            # 2. 清理过期资源
            cleaned_resources = await memory_manager.tracker.cleanup_expired_resources()
            if cleaned_resources > 0:
                optimization_results['actions_performed'].append(f'清理过期资源: {cleaned_resources}个')
            
            # 3. 清理Redis过期锁
            cleaned_locks = await lock_manager.cleanup_expired_locks()
            if cleaned_locks > 0:
                optimization_results['actions_performed'].append(f'清理过期锁: {cleaned_locks}个')
            
            # 4. 清理查询缓存
            query_cache.clear()
            optimization_results['actions_performed'].append('清理查询缓存')
            
            optimization_results['success'] = True
            optimization_results['message'] = '系统优化完成'
            
        except Exception as e:
            optimization_results['success'] = False
            optimization_results['error'] = str(e)
            logger.error(f"系统优化失败: {e}")
        
        return optimization_results


# 全局服务实例
performance_service = SystemPerformanceService()


@router.get("/stats", summary="获取系统性能统计")
async def get_performance_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取系统性能统计信息"""
    try:
        await performance_service.initialize(db)
        stats = await performance_service.get_comprehensive_stats()
        return {
            'success': True,
            'data': stats
        }
    except Exception as e:
        logger.error(f"获取性能统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory", summary="获取内存使用情况")
async def get_memory_usage(
    current_user: User = Depends(get_current_user)
):
    """获取详细的内存使用情况"""
    try:
        stats = await memory_manager.get_system_stats()
        return {
            'success': True,
            'data': stats
        }
    except Exception as e:
        logger.error(f"获取内存统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database", summary="获取数据库性能信息")
async def get_database_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取数据库性能信息"""
    try:
        optimizer = DatabaseOptimizer(db)
        
        # 获取连接池状态
        pool_status = await pool_manager.get_pool_status()
        
        # 获取缓存统计
        cache_stats = query_cache.get_cache_stats()
        
        return {
            'success': True,
            'data': {
                'connection_pool': pool_status,
                'query_cache': cache_stats
            }
        }
    except Exception as e:
        logger.error(f"获取数据库性能信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/celery", summary="获取Celery任务队列信息")
async def get_celery_performance(
    current_user: User = Depends(get_current_user)
):
    """获取Celery任务队列性能信息"""
    try:
        queue_stats = await CeleryTaskManager.get_queue_stats()
        worker_stats = await CeleryTaskManager.get_worker_stats()
        
        return {
            'success': True,
            'data': {
                'queues': queue_stats,
                'workers': worker_stats,
                'metrics': task_metrics.get_stats()
            }
        }
    except Exception as e:
        logger.error(f"获取Celery性能信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize", summary="执行系统优化")
async def optimize_system(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """执行系统优化操作"""
    try:
        await performance_service.initialize(db)
        result = await performance_service.perform_optimization()
        
        return {
            'success': True,
            'data': result
        }
    except Exception as e:
        logger.error(f"系统优化失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache", summary="清理缓存")
async def clear_cache(
    cache_type: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """清理指定类型的缓存"""
    try:
        cleared_items = 0
        
        if cache_type == "query" or cache_type is None:
            query_cache.clear()
            cleared_items += 1
        
        if cache_type == "locks" or cache_type is None:
            cleared_locks = await lock_manager.cleanup_expired_locks()
            cleared_items += cleared_locks
        
        return {
            'success': True,
            'data': {
                'message': f'缓存清理完成，清理项目数: {cleared_items}',
                'cleared_items': cleared_items
            }
        }
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", summary="系统健康检查")
async def health_check(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """执行系统健康检查"""
    try:
        await performance_service.initialize(db)
        stats = await performance_service.get_comprehensive_stats()
        
        health_score = stats.get('overall_health_score', 0)
        
        # 健康状态判断
        if health_score >= 80:
            status = "healthy"
            level = "success"
        elif health_score >= 60:
            status = "warning"
            level = "warning"
        else:
            status = "critical"
            level = "error"
        
        return {
            'success': True,
            'data': {
                'status': status,
                'level': level,
                'health_score': health_score,
                'timestamp': datetime.utcnow().isoformat(),
                'details': stats
            }
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts", summary="获取系统告警")
async def get_system_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取系统告警信息"""
    try:
        await performance_service.initialize(db)
        stats = await performance_service.get_comprehensive_stats()
        
        alerts = []
        
        # 内存告警
        memory_stats = stats.get('memory_stats', {})
        if memory_stats.get('memory_pressure', False):
            alerts.append({
                'type': 'memory',
                'level': 'warning',
                'message': '内存使用率过高',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # 数据库连接告警
        db_stats = stats.get('database_stats', {})
        pool_status = db_stats.get('connection_pool', {})
        if pool_status.get('available_connections', 0) < 2:
            alerts.append({
                'type': 'database',
                'level': 'error',
                'message': '数据库连接池可用连接不足',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Celery任务失败率告警
        celery_stats = stats.get('celery_stats', {})
        metrics = celery_stats.get('metrics', {})
        success_rate = metrics.get('success_rate', 100)
        if success_rate < 90:
            alerts.append({
                'type': 'celery',
                'level': 'warning',
                'message': f'任务成功率过低: {success_rate:.1f}%',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Redis连接告警
        redis_stats = stats.get('redis_stats', {})
        if not redis_stats.get('connected', False):
            alerts.append({
                'type': 'redis',
                'level': 'error',
                'message': 'Redis连接异常',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return {
            'success': True,
            'data': {
                'alerts': alerts,
                'alert_count': len(alerts),
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"获取系统告警失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", summary="获取性能指标时间序列数据")
async def get_performance_metrics(
    range: str = "1h",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取性能指标的时间序列数据用于图表显示"""
    try:
        # 生成模拟的时间序列数据
        from datetime import datetime, timedelta
        import random
        
        # 根据时间范围确定时间间隔和数据点数量
        if range == "1h":
            interval_minutes = 5
            points = 12
        elif range == "6h":
            interval_minutes = 30
            points = 12
        elif range == "24h":
            interval_minutes = 120
            points = 12
        else:  # 7d
            interval_minutes = 6 * 60  # 6小时
            points = 28
        
        # 生成时间戳
        now = datetime.utcnow()
        timestamps = []
        cpu_data = []
        memory_data = []
        disk_data = []
        
        for i in range(points):
            time_point = now - timedelta(minutes=interval_minutes * (points - 1 - i))
            timestamps.append(time_point.strftime('%H:%M'))
            
            # 生成模拟数据（在实际生产中应该从数据库或监控系统获取）
            base_cpu = 25 + random.random() * 30  # 25-55%
            base_memory = 40 + random.random() * 35  # 40-75%
            base_disk = 60 + random.random() * 20   # 60-80%
            
            cpu_data.append(round(base_cpu, 1))
            memory_data.append(round(base_memory, 1))
            disk_data.append(round(base_disk, 1))
        
        return {
            'success': True,
            'data': {
                'timestamps': timestamps,
                'cpu': cpu_data,
                'memory': memory_data,
                'disk': disk_data,
                'range': range
            }
        }
    except Exception as e:
        logger.error(f"获取性能指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))