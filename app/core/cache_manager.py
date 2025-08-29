"""
缓存管理和清理模块
解决Redis缓存与数据库数据不一致的问题
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set

import redis.asyncio as aioredis
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.models.domain import DomainRecord
from app.models.task import ScanTask, TaskLog, ViolationRecord


class CacheManager:
    """缓存管理器 - 统一管理Redis缓存和清理操作"""
    
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.initialized = False
    
    async def initialize(self):
        """初始化Redis连接"""
        try:
            self.redis_client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # 测试连接
            await self.redis_client.ping()
            self.initialized = True
            logger.info("缓存管理器初始化成功")
            
        except Exception as e:
            logger.error(f"缓存管理器初始化失败: {e}")
            self.redis_client = None
            self.initialized = False
    
    async def close(self):
        """关闭Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            self.initialized = False
    
    async def is_connected(self) -> bool:
        """检查Redis连接状态"""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.ping()
            return True
        except Exception:
            return False
    
    async def get_celery_tasks_from_redis(self) -> List[Dict[str, Any]]:
        """从Redis中获取所有Celery任务信息"""
        if not await self.is_connected() or not self.redis_client:
            return []
        
        try:
            tasks = []
            
            # 获取所有Celery相关的键
            patterns = [
                "celery-task-meta-*",  # 任务结果
                "_kombu.binding.*",    # 队列绑定
                "unacked_mutex",       # 未确认任务互斥锁
                "*scan_domain_task*",  # 扫描任务
            ]
            
            for pattern in patterns:
                keys = await self.redis_client.keys(pattern)
                for key in keys:
                    try:
                        # 获取键的类型和值
                        key_type = await self.redis_client.type(key)
                        ttl = await self.redis_client.ttl(key)
                        
                        task_info = {
                            'key': key,
                            'type': key_type,
                            'ttl': ttl
                        }
                        
                        # 根据键类型获取值
                        if key_type == 'string':
                            value = await self.redis_client.get(key)
                            task_info['value'] = value
                            
                            # 尝试解析任务ID
                            if 'celery-task-meta-' in key:
                                task_id = key.replace('celery-task-meta-', '')
                                task_info['task_id'] = task_id
                                
                                # 尝试解析任务内容
                                try:
                                    task_data = json.loads(value) if value else {}
                                    task_info['task_data'] = task_data
                                except (json.JSONDecodeError, TypeError):
                                    pass
                        
                        tasks.append(task_info)
                        
                    except Exception as e:
                        logger.warning(f"获取键 {key} 信息失败: {e}")
                        continue
            
            logger.info(f"从Redis获取到 {len(tasks)} 个Celery相关键")
            return tasks
            
        except Exception as e:
            logger.error(f"从Redis获取Celery任务失败: {e}")
            return []
    
    async def get_orphaned_celery_tasks(self) -> List[Dict[str, Any]]:
        """获取孤立的Celery任务（Redis中存在但数据库中不存在的任务）"""
        celery_tasks = await self.get_celery_tasks_from_redis()
        orphaned_tasks = []
        
        if not celery_tasks:
            return orphaned_tasks
        
        # 提取所有任务ID
        task_ids = []
        for task in celery_tasks:
            if 'task_id' in task:
                task_ids.append(task['task_id'])
        
        if not task_ids:
            return orphaned_tasks
        
        # 检查数据库中是否存在这些任务
        try:
            async with AsyncSessionLocal() as db:
                stmt = select(ScanTask.id).where(ScanTask.id.in_(task_ids))
                result = await db.execute(stmt)
                existing_task_ids = {row[0] for row in result.fetchall()}
            
            # 找出孤立的任务
            for task in celery_tasks:
                task_id = task.get('task_id')
                if task_id and task_id not in existing_task_ids:
                    orphaned_tasks.append({
                        **task,
                        'status': 'orphaned',
                        'reason': f'任务ID {task_id} 在数据库中不存在'
                    })
            
            logger.info(f"发现 {len(orphaned_tasks)} 个孤立的Celery任务")
            return orphaned_tasks
            
        except Exception as e:
            logger.error(f"检查孤立任务失败: {e}")
            return []
    
    async def cleanup_orphaned_celery_tasks(self) -> int:
        """清理孤立的Celery任务"""
        if not await self.is_connected() or not self.redis_client:
            logger.warning("Redis未连接，无法清理孤立任务")
            return 0
        
        orphaned_tasks = await self.get_orphaned_celery_tasks()
        cleaned_count = 0
        
        for task in orphaned_tasks:
            try:
                key = task['key']
                await self.redis_client.delete(key)
                cleaned_count += 1
                logger.info(f"清理孤立任务键: {key}")
                
            except Exception as e:
                logger.error(f"清理孤立任务键 {task['key']} 失败: {e}")
                continue
        
        logger.info(f"清理孤立Celery任务完成，共清理 {cleaned_count} 个键")
        return cleaned_count
    
    async def purge_all_celery_queues(self) -> int:
        """清空所有Celery队列"""
        if not await self.is_connected() or not self.redis_client:
            logger.warning("Redis未连接，无法清空队列")
            return 0
        
        try:
            # 导入Celery应用
            from app.core.celery_optimizer import celery_app
            
            # 清空所有队列
            celery_app.control.purge()
            
            # 额外清理Redis中的Celery相关键
            patterns = [
                "celery-task-meta-*",
                "_kombu.binding.*",
                "unacked*",
                "*scan_domain_task*",
            ]
            
            total_deleted = 0
            for pattern in patterns:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    deleted = await self.redis_client.delete(*keys)
                    total_deleted += deleted
                    logger.info(f"删除模式 {pattern} 的 {deleted} 个键")
            
            logger.info(f"Celery队列清空完成，共删除 {total_deleted} 个Redis键")
            return total_deleted
            
        except Exception as e:
            logger.error(f"清空Celery队列失败: {e}")
            return 0
    
    async def cleanup_expired_task_results(self, max_age_hours: int = 24) -> int:
        """清理过期的任务结果"""
        if not await self.is_connected() or not self.redis_client:
            return 0
        
        try:
            pattern = "celery-task-meta-*"
            keys = await self.redis_client.keys(pattern)
            cleaned_count = 0
            
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            for key in keys:
                try:
                    # 获取任务结果
                    result_data = await self.redis_client.get(key)
                    if not result_data:
                        await self.redis_client.delete(key)
                        cleaned_count += 1
                        continue
                    
                    # 尝试解析任务结果
                    try:
                        task_result = json.loads(result_data)
                        # 检查任务时间戳（如果有的话）
                        if 'date_done' in task_result:
                            # 这里可以添加更复杂的时间检查逻辑
                            pass
                    except (json.JSONDecodeError, TypeError):
                        pass
                    
                    # 检查TTL
                    ttl = await self.redis_client.ttl(key)
                    if ttl == -1:  # 没有过期时间的键
                        await self.redis_client.expire(key, 3600)  # 设置1小时过期
                    elif ttl == -2:  # 键不存在
                        continue
                    
                except Exception as e:
                    logger.warning(f"处理任务结果键 {key} 失败: {e}")
                    continue
            
            logger.info(f"清理过期任务结果完成，处理 {cleaned_count} 个键")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理过期任务结果失败: {e}")
            return 0
    
    async def cleanup_database_orphaned_records(self) -> Dict[str, int]:
        """清理数据库中的孤立记录"""
        cleanup_stats = {
            'task_logs': 0,
            'domain_records': 0,
            'domain_records': 0,
            'violation_records': 0
        }
        
        try:
            async with AsyncSessionLocal() as db:
                # 获取所有有效的任务ID
                stmt = select(ScanTask.id)
                result = await db.execute(stmt)
                valid_task_ids = {row[0] for row in result.fetchall()}
                
                if not valid_task_ids:
                    logger.info("没有找到有效的扫描任务，跳过孤立记录清理")
                    return cleanup_stats
                
                # 清理孤立的任务日志
                stmt = select(TaskLog.id).where(~TaskLog.task_id.in_(valid_task_ids))
                result = await db.execute(stmt)
                orphaned_log_ids = [row[0] for row in result.fetchall()]
                
                if orphaned_log_ids:
                    stmt = delete(TaskLog).where(TaskLog.id.in_(orphaned_log_ids))
                    result = await db.execute(stmt)
                    cleanup_stats['task_logs'] = result.rowcount
                
                # 清理孤立的子域名记录
                stmt = select(DomainRecord.id).where(~DomainRecord.task_id.in_(valid_task_ids))
                result = await db.execute(stmt)
                orphaned_subdomain_ids = [row[0] for row in result.fetchall()]
                
                if orphaned_subdomain_ids:
                    stmt = delete(DomainRecord).where(DomainRecord.id.in_(orphaned_subdomain_ids))
                    result = await db.execute(stmt)
                    cleanup_stats['domain_records'] = result.rowcount
                
                # 清理孤立的第三方域名记录
                stmt = select(DomainRecord.id).where(~DomainRecord.task_id.in_(valid_task_ids))
                result = await db.execute(stmt)
                orphaned_domain_ids = [row[0] for row in result.fetchall()]
                
                if orphaned_domain_ids:
                    stmt = delete(DomainRecord).where(DomainRecord.id.in_(orphaned_domain_ids))
                    result = await db.execute(stmt)
                    cleanup_stats['domain_records'] = result.rowcount
                
                # 清理孤立的违规记录
                stmt = select(ViolationRecord.id).where(~ViolationRecord.task_id.in_(valid_task_ids))
                result = await db.execute(stmt)
                orphaned_violation_ids = [row[0] for row in result.fetchall()]
                
                if orphaned_violation_ids:
                    stmt = delete(ViolationRecord).where(ViolationRecord.id.in_(orphaned_violation_ids))
                    result = await db.execute(stmt)
                    cleanup_stats['violation_records'] = result.rowcount
                
                await db.commit()
                
                total_cleaned = sum(cleanup_stats.values())
                logger.info(f"数据库孤立记录清理完成，总计清理 {total_cleaned} 条记录")
                
        except Exception as e:
            logger.error(f"清理数据库孤立记录失败: {e}")
            # 确保所有统计值为0
            cleanup_stats = {k: 0 for k in cleanup_stats}
        
        return cleanup_stats
    
    async def perform_full_cleanup(self) -> Dict[str, Any]:
        """执行完整的缓存和数据清理"""
        cleanup_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'redis_connected': False,
            'celery_tasks_cleaned': 0,
            'task_results_cleaned': 0,
            'database_records_cleaned': {},
            'total_operations': 0,
            'errors': []
        }
        
        try:
            # 检查Redis连接
            cleanup_results['redis_connected'] = await self.is_connected()
            
            if cleanup_results['redis_connected']:
                # 1. 清理孤立的Celery任务
                try:
                    celery_cleaned = await self.cleanup_orphaned_celery_tasks()
                    cleanup_results['celery_tasks_cleaned'] = celery_cleaned
                    cleanup_results['total_operations'] += 1
                except Exception as e:
                    cleanup_results['errors'].append(f"清理Celery任务失败: {str(e)}")
                
                # 2. 清理过期的任务结果
                try:
                    results_cleaned = await self.cleanup_expired_task_results()
                    cleanup_results['task_results_cleaned'] = results_cleaned
                    cleanup_results['total_operations'] += 1
                except Exception as e:
                    cleanup_results['errors'].append(f"清理过期任务结果失败: {str(e)}")
            
            # 3. 清理数据库孤立记录
            try:
                db_cleanup = await self.cleanup_database_orphaned_records()
                cleanup_results['database_records_cleaned'] = db_cleanup
                cleanup_results['total_operations'] += 1
            except Exception as e:
                cleanup_results['errors'].append(f"清理数据库记录失败: {str(e)}")
            
            # 4. 清理Redis过期锁（如果锁管理器可用）
            try:
                from app.core.redis_lock import lock_manager
                if hasattr(lock_manager, 'redis_client') and lock_manager.redis_client:
                    locks_cleaned = await lock_manager.cleanup_expired_locks()
                    cleanup_results['locks_cleaned'] = locks_cleaned
                    cleanup_results['total_operations'] += 1
            except Exception as e:
                cleanup_results['errors'].append(f"清理Redis锁失败: {str(e)}")
            
            logger.info(f"完整缓存清理完成，执行了 {cleanup_results['total_operations']} 个操作")
            
        except Exception as e:
            cleanup_results['errors'].append(f"执行完整清理时出错: {str(e)}")
            logger.error(f"执行完整缓存清理失败: {e}")
        
        return cleanup_results
    
    async def get_cache_status(self) -> Dict[str, Any]:
        """获取缓存状态信息"""
        status = {
            'redis_connected': False,
            'redis_info': {},
            'celery_tasks_count': 0,
            'orphaned_tasks_count': 0,
            'database_tasks_count': 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            # Redis连接状态
            status['redis_connected'] = await self.is_connected()
            
            if status['redis_connected'] and self.redis_client:
                # Redis信息
                try:
                    info = await self.redis_client.info()
                    status['redis_info'] = {
                        'used_memory_human': info.get('used_memory_human', 'N/A'),
                        'connected_clients': info.get('connected_clients', 0),
                        'total_commands_processed': info.get('total_commands_processed', 0),
                        'keyspace_hits': info.get('keyspace_hits', 0),
                        'keyspace_misses': info.get('keyspace_misses', 0)
                    }
                except Exception as e:
                    logger.warning(f"获取Redis信息失败: {e}")
                
                # Celery任务数量
                try:
                    celery_tasks = await self.get_celery_tasks_from_redis()
                    status['celery_tasks_count'] = len(celery_tasks)
                    
                    orphaned_tasks = await self.get_orphaned_celery_tasks()
                    status['orphaned_tasks_count'] = len(orphaned_tasks)
                except Exception as e:
                    logger.warning(f"获取Celery任务信息失败: {e}")
            
            # 数据库任务数量
            try:
                async with AsyncSessionLocal() as db:
                    stmt = select(ScanTask.id)
                    result = await db.execute(stmt)
                    status['database_tasks_count'] = len(result.fetchall())
            except Exception as e:
                logger.warning(f"获取数据库任务数量失败: {e}")
            
        except Exception as e:
            logger.error(f"获取缓存状态失败: {e}")
        
        return status


# 全局缓存管理器实例
cache_manager = CacheManager()