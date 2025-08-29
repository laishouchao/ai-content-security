"""
内存管理和资源清理机制
防止内存泄漏，自动清理过期资源，优化系统性能
"""

import gc
import psutil
import asyncio
import weakref
from typing import Dict, List, Any, Optional, Callable, Set
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import threading
import time
from dataclasses import dataclass
from enum import Enum

from app.core.logging import logger
from app.core.config import settings


class ResourceType(Enum):
    """资源类型"""
    MEMORY = "memory"
    FILE_HANDLE = "file_handle"
    DATABASE_CONNECTION = "database_connection"
    NETWORK_CONNECTION = "network_connection"
    CACHE_ENTRY = "cache_entry"
    TEMPORARY_FILE = "temporary_file"


@dataclass
class ResourceInfo:
    """资源信息"""
    resource_id: str
    resource_type: ResourceType
    created_at: datetime
    last_accessed: datetime
    size_bytes: int = 0
    metadata: Optional[Dict[str, Any]] = None
    cleanup_callback: Optional[Callable] = None


class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.memory_threshold = 80  # 内存使用率阈值（百分比）
        self.memory_history = []
        self.max_history_size = 100
        
    def get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息"""
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            # 系统内存信息
            system_memory = psutil.virtual_memory()
            
            info = {
                'process_memory': {
                    'rss': memory_info.rss,  # 物理内存
                    'vms': memory_info.vms,  # 虚拟内存
                    'percent': round(memory_percent, 1),
                    'rss_mb': round(memory_info.rss / 1024 / 1024, 1),
                    'vms_mb': round(memory_info.vms / 1024 / 1024, 1),
                },
                'system_memory': {
                    'total': system_memory.total,
                    'available': system_memory.available,
                    'percent': round(system_memory.percent, 1),
                    'used': system_memory.used,
                    'free': system_memory.free,
                    'total_gb': round(system_memory.total / 1024 / 1024 / 1024, 2),
                    'available_gb': round(system_memory.available / 1024 / 1024 / 1024, 2),
                    'used_gb': round(system_memory.used / 1024 / 1024 / 1024, 2),
                },
                'gc_stats': {
                    'collections': gc.get_stats(),
                    'garbage_count': len(gc.garbage),
                    'object_count': len(gc.get_objects()),
                }
            }
            
            # 添加到历史记录
            self.memory_history.append({
                'timestamp': datetime.utcnow(),
                'memory_percent': memory_percent,
                'rss_mb': memory_info.rss / 1024 / 1024
            })
            
            # 限制历史记录大小
            if len(self.memory_history) > self.max_history_size:
                self.memory_history.pop(0)
            
            return info
            
        except Exception as e:
            logger.error(f"获取内存信息失败: {e}")
            return {}
    
    def is_memory_pressure(self) -> bool:
        """检查是否存在内存压力"""
        try:
            memory_percent = self.process.memory_percent()
            return memory_percent > self.memory_threshold
        except Exception:
            return False
    
    def get_memory_trend(self) -> Dict[str, Any]:
        """获取内存使用趋势"""
        if len(self.memory_history) < 2:
            return {'trend': 'stable', 'change_rate': 0}
        
        recent = self.memory_history[-10:]  # 最近10个记录
        if len(recent) < 2:
            return {'trend': 'stable', 'change_rate': 0}
        
        start_memory = recent[0]['memory_percent']
        end_memory = recent[-1]['memory_percent']
        change_rate = (end_memory - start_memory) / start_memory * 100
        
        if change_rate > 5:
            trend = 'increasing'
        elif change_rate < -5:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'change_rate': change_rate,
            'start_memory': start_memory,
            'end_memory': end_memory
        }


class ResourceTracker:
    """资源跟踪器"""
    
    def __init__(self):
        self.resources: Dict[str, ResourceInfo] = {}
        self.resource_refs: Dict[str, Any] = {}  # 弱引用
        self.cleanup_callbacks: Dict[str, Callable] = {}
        self._lock = asyncio.Lock()
    
    async def register_resource(
        self,
        resource_id: str,
        resource_type: ResourceType,
        resource_obj: Any = None,
        size_bytes: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        cleanup_callback: Optional[Callable] = None
    ):
        """注册资源"""
        async with self._lock:
            resource_info = ResourceInfo(
                resource_id=resource_id,
                resource_type=resource_type,
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                size_bytes=size_bytes,
                metadata=metadata or {},
                cleanup_callback=cleanup_callback
            )
            
            self.resources[resource_id] = resource_info
            
            # 如果提供了资源对象，创建弱引用
            if resource_obj is not None:
                self.resource_refs[resource_id] = weakref.ref(
                    resource_obj, 
                    lambda ref: self._on_resource_deleted(resource_id)
                )
            
            logger.debug(f"注册资源: {resource_id} ({resource_type.value})")
    
    async def update_access_time(self, resource_id: str):
        """更新资源访问时间"""
        async with self._lock:
            if resource_id in self.resources:
                self.resources[resource_id].last_accessed = datetime.utcnow()
    
    async def unregister_resource(self, resource_id: str):
        """注销资源"""
        async with self._lock:
            if resource_id in self.resources:
                resource_info = self.resources[resource_id]
                
                # 执行清理回调
                if resource_info.cleanup_callback:
                    try:
                        if asyncio.iscoroutinefunction(resource_info.cleanup_callback):
                            await resource_info.cleanup_callback()
                        else:
                            resource_info.cleanup_callback()
                    except Exception as e:
                        logger.error(f"执行资源清理回调失败 {resource_id}: {e}")
                
                del self.resources[resource_id]
                
                if resource_id in self.resource_refs:
                    del self.resource_refs[resource_id]
                
                logger.debug(f"注销资源: {resource_id}")
    
    def _on_resource_deleted(self, resource_id: str):
        """资源被垃圾回收时的回调"""
        logger.debug(f"资源被GC回收: {resource_id}")
        # 异步清理
        asyncio.create_task(self.unregister_resource(resource_id))
    
    async def get_resource_stats(self) -> Dict[str, Any]:
        """获取资源统计信息"""
        async with self._lock:
            stats = {
                'total_resources': len(self.resources),
                'by_type': {},
                'total_size_bytes': 0,
                'oldest_resource': None,
                'newest_resource': None
            }
            
            if not self.resources:
                return stats
            
            # 按类型统计
            for resource_info in self.resources.values():
                resource_type = resource_info.resource_type.value
                if resource_type not in stats['by_type']:
                    stats['by_type'][resource_type] = {
                        'count': 0,
                        'total_size': 0
                    }
                
                stats['by_type'][resource_type]['count'] += 1
                stats['by_type'][resource_type]['total_size'] += resource_info.size_bytes
                stats['total_size_bytes'] += resource_info.size_bytes
            
            # 最老和最新资源
            sorted_resources = sorted(
                self.resources.values(),
                key=lambda x: x.created_at
            )
            
            stats['oldest_resource'] = {
                'id': sorted_resources[0].resource_id,
                'type': sorted_resources[0].resource_type.value,
                'age_seconds': (datetime.utcnow() - sorted_resources[0].created_at).total_seconds()
            }
            
            stats['newest_resource'] = {
                'id': sorted_resources[-1].resource_id,
                'type': sorted_resources[-1].resource_type.value,
                'age_seconds': (datetime.utcnow() - sorted_resources[-1].created_at).total_seconds()
            }
            
            return stats
    
    async def cleanup_expired_resources(self, max_age_seconds: int = 3600):
        """清理过期资源"""
        cutoff_time = datetime.utcnow() - timedelta(seconds=max_age_seconds)
        expired_resources = []
        
        async with self._lock:
            for resource_id, resource_info in self.resources.items():
                if resource_info.last_accessed < cutoff_time:
                    expired_resources.append(resource_id)
        
        # 清理过期资源
        for resource_id in expired_resources:
            await self.unregister_resource(resource_id)
        
        if expired_resources:
            logger.info(f"清理过期资源: {len(expired_resources)} 个")
        
        return len(expired_resources)


class MemoryManager:
    """内存管理器"""
    
    def __init__(self):
        self.monitor = MemoryMonitor()
        self.tracker = ResourceTracker()
        self.cleanup_interval = 300  # 5分钟
        self.gc_interval = 60  # 1分钟
        self._cleanup_task = None
        self._gc_task = None
        self._running = False
    
    async def start(self):
        """启动内存管理器"""
        if self._running:
            return
        
        self._running = True
        
        # 启动清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._gc_task = asyncio.create_task(self._gc_loop())
        
        logger.info("内存管理器已启动")
    
    async def stop(self):
        """停止内存管理器"""
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._gc_task:
            self._gc_task.cancel()
            try:
                await self._gc_task
            except asyncio.CancelledError:
                pass
        
        logger.info("内存管理器已停止")
    
    async def _cleanup_loop(self):
        """清理循环"""
        while self._running:
            try:
                await self.cleanup_resources()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"资源清理循环异常: {e}")
                await asyncio.sleep(10)
    
    async def _gc_loop(self):
        """垃圾回收循环"""
        while self._running:
            try:
                await self.force_garbage_collection()
                await asyncio.sleep(self.gc_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"垃圾回收循环异常: {e}")
                await asyncio.sleep(10)
    
    async def cleanup_resources(self):
        """清理资源"""
        try:
            # 检查内存压力
            if self.monitor.is_memory_pressure():
                logger.warning("检测到内存压力，开始强制清理资源")
                # 更激进的清理策略
                await self.tracker.cleanup_expired_resources(max_age_seconds=1800)  # 30分钟
            else:
                # 常规清理
                await self.tracker.cleanup_expired_resources(max_age_seconds=3600)  # 1小时
            
            # 获取内存信息
            memory_info = self.monitor.get_memory_info()
            if memory_info:
                memory_mb = memory_info['process_memory']['rss_mb']
                logger.debug(f"当前内存使用: {memory_mb:.2f} MB")
                
        except Exception as e:
            logger.error(f"资源清理失败: {e}")
    
    async def force_garbage_collection(self):
        """强制垃圾回收"""
        try:
            # 执行垃圾回收
            collected = gc.collect()
            
            if collected > 0:
                logger.debug(f"垃圾回收: 清理了 {collected} 个对象")
            
            # 检查内存趋势
            trend = self.monitor.get_memory_trend()
            if trend['trend'] == 'increasing' and trend['change_rate'] > 10:
                logger.warning(f"内存使用持续增长: {trend['change_rate']:.2f}%")
                
        except Exception as e:
            logger.error(f"垃圾回收失败: {e}")
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        try:
            memory_info = self.monitor.get_memory_info()
            resource_stats = await self.tracker.get_resource_stats()
            memory_trend = self.monitor.get_memory_trend()
            
            return {
                'memory_info': memory_info,
                'resource_stats': resource_stats,
                'memory_trend': memory_trend,
                'memory_pressure': self.monitor.is_memory_pressure(),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return {}
    
    @asynccontextmanager
    async def track_resource(
        self,
        resource_id: str,
        resource_type: ResourceType,
        resource_obj: Any = None,
        size_bytes: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        cleanup_callback: Optional[Callable] = None
    ):
        """资源跟踪上下文管理器"""
        await self.tracker.register_resource(
            resource_id=resource_id,
            resource_type=resource_type,
            resource_obj=resource_obj,
            size_bytes=size_bytes,
            metadata=metadata,
            cleanup_callback=cleanup_callback
        )
        
        try:
            yield
        finally:
            await self.tracker.unregister_resource(resource_id)


# 全局内存管理器实例
memory_manager = MemoryManager()


# 装饰器：自动跟踪函数资源使用
def track_memory(resource_type: ResourceType = ResourceType.MEMORY):
    """内存跟踪装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            resource_id = f"{func.__name__}_{id(func)}_{time.time()}"
            
            async with memory_manager.track_resource(
                resource_id=resource_id,
                resource_type=resource_type,
                metadata={'function': func.__name__, 'args_count': len(args)}
            ):
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# 工具函数
async def cleanup_large_objects():
    """清理大对象"""
    try:
        # 强制回收所有代
        for generation in range(3):
            collected = gc.collect(generation)
            if collected > 0:
                logger.debug(f"Generation {generation}: 回收 {collected} 个对象")
        
        # 清理循环引用
        gc.collect()
        
        logger.info("大对象清理完成")
        
    except Exception as e:
        logger.error(f"大对象清理失败: {e}")


async def get_memory_usage_by_type():
    """按类型获取内存使用情况"""
    try:
        import sys
        from collections import defaultdict
        
        type_counts = defaultdict(int)
        type_sizes = defaultdict(int)
        
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            type_counts[obj_type] += 1
            try:
                type_sizes[obj_type] += sys.getsizeof(obj)
            except (TypeError, AttributeError):
                pass
        
        # 按大小排序
        sorted_types = sorted(
            type_sizes.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]  # 前20个最大的类型
        
        return {
            'type_counts': dict(type_counts),
            'type_sizes': dict(type_sizes),
            'largest_types': sorted_types
        }
        
    except Exception as e:
        logger.error(f"获取内存使用统计失败: {e}")
        return {}