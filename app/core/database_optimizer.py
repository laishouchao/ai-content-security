"""
数据库操作优化工具类
提供批量操作,查询优化,连接池管理等功能
"""

import asyncio
from typing import List, Dict, Any, Optional, Union, Type, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, text, func
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.dialects.postgresql import insert as pg_insert
from contextlib import asynccontextmanager
import logging
from datetime import datetime, timedelta

from app.core.database import AsyncSessionLocal, Base
from app.core.logging import logger

T = TypeVar('T', bound=Any)


class DatabaseOptimizer:
    """数据库操作优化器"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.batch_size = 1000
        self.max_connections = 10
    
    async def batch_insert(
        self, 
        model: Type[T], 
        records: List[Dict[str, Any]], 
        batch_size: Optional[int] = None,
        on_conflict_do_nothing: bool = False
    ) -> int:
        """
        批量插入记录
        
        Args:
            model: SQLAlchemy模型类
            records: 要插入的记录列表
            batch_size: 批次大小
            on_conflict_do_nothing: 冲突时是否忽略
        
        Returns:
            插入的记录数量
        """
        if not records:
            return 0
        
        batch_size = batch_size or self.batch_size
        total_inserted = 0
        
        try:
            # 分批插入
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                
                if on_conflict_do_nothing:
                    # PostgreSQL特有的UPSERT操作
                    stmt = pg_insert(model).values(batch)
                    stmt = stmt.on_conflict_do_nothing()
                    result = await self.db.execute(stmt)
                    total_inserted += result.rowcount
                else:
                    # 标准批量插入
                    stmt = insert(model).values(batch)
                    await self.db.execute(stmt)
                    total_inserted += len(batch)
                
                # 每批提交一次，避免长事务
                await self.db.commit()
                
                logger.debug(f"批量插入 {model.__name__}: {len(batch)} 条记录")
        
        except Exception as e:
            await self.db.rollback()
            logger.error(f"批量插入失败: {e}")
            raise e
        
        logger.info(f"批量插入完成: {model.__name__} 总计 {total_inserted} 条记录")
        return total_inserted
    
    async def batch_update(
        self, 
        model: Type[T], 
        updates: List[Dict[str, Any]], 
        key_field: str = 'id',
        batch_size: Optional[int] = None
    ) -> int:
        """
        批量更新记录
        
        Args:
            model: SQLAlchemy模型类
            updates: 更新数据列表，每个字典必须包含key_field
            key_field: 用于匹配的字段名
            batch_size: 批次大小
        
        Returns:
            更新的记录数量
        """
        if not updates:
            return 0
        
        batch_size = batch_size or self.batch_size
        total_updated = 0
        
        try:
            for i in range(0, len(updates), batch_size):
                batch = updates[i:i + batch_size]
                
                # 构建批量更新语句
                for record in batch:
                    key_value = record.pop(key_field)
                    stmt = update(model).where(
                        getattr(model, key_field) == key_value
                    ).values(**record)
                    result = await self.db.execute(stmt)
                    total_updated += result.rowcount
                
                await self.db.commit()
                logger.debug(f"批量更新 {model.__name__}: {len(batch)} 条记录")
        
        except Exception as e:
            await self.db.rollback()
            logger.error(f"批量更新失败: {e}")
            raise e
        
        logger.info(f"批量更新完成: {model.__name__} 总计 {total_updated} 条记录")
        return total_updated
    
    async def batch_upsert(
        self,
        model: Type[T],
        records: List[Dict[str, Any]],
        conflict_fields: List[str],
        update_fields: Optional[List[str]] = None,
        batch_size: Optional[int] = None
    ) -> int:
        """
        批量插入或更新（UPSERT）
        
        Args:
            model: SQLAlchemy模型类
            records: 记录列表
            conflict_fields: 冲突检测字段
            update_fields: 冲突时要更新的字段
            batch_size: 批次大小
        
        Returns:
            处理的记录数量
        """
        if not records:
            return 0
        
        batch_size = batch_size or self.batch_size
        total_processed = 0
        
        try:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                
                # PostgreSQL UPSERT
                stmt = pg_insert(model).values(batch)
                
                # 设置冲突处理
                if update_fields:
                    update_dict = {
                        field: stmt.excluded[field] 
                        for field in update_fields
                    }
                    stmt = stmt.on_conflict_do_update(
                        index_elements=conflict_fields,
                        set_=update_dict
                    )
                else:
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=conflict_fields
                    )
                
                result = await self.db.execute(stmt)
                total_processed += len(batch)
                
                await self.db.commit()
                logger.debug(f"批量UPSERT {model.__name__}: {len(batch)} 条记录")
        
        except Exception as e:
            await self.db.rollback()
            logger.error(f"批量UPSERT失败: {e}")
            raise e
        
        logger.info(f"批量UPSERT完成: {model.__name__} 总计 {total_processed} 条记录")
        return total_processed
    
    async def optimize_query(
        self,
        model: Type[T],
        filters: Optional[Dict[str, Any]] = None,
        relationships: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[T]:
        """
        优化查询，使用预加载和索引
        
        Args:
            model: SQLAlchemy模型类
            filters: 过滤条件
            relationships: 要预加载的关系
            order_by: 排序字段
            limit: 限制数量
            offset: 偏移量
        
        Returns:
            查询结果列表
        """
        try:
            # 构建基础查询
            query = select(model)
            
            # 添加关系预加载
            if relationships:
                for rel in relationships:
                    query = query.options(selectinload(getattr(model, rel)))
            
            # 添加过滤条件
            if filters:
                for field, value in filters.items():
                    if hasattr(model, field):
                        if isinstance(value, list):
                            query = query.where(getattr(model, field).in_(value))
                        else:
                            query = query.where(getattr(model, field) == value)
            
            # 添加排序
            if order_by:
                if order_by.startswith('-'):
                    field = order_by[1:]
                    query = query.order_by(getattr(model, field).desc())
                else:
                    query = query.order_by(getattr(model, order_by))
            
            # 添加分页
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
        
        except Exception as e:
            logger.error(f"优化查询失败: {e}")
            raise e
    
    async def count_with_filters(
        self,
        model: Type[T],
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        带过滤条件的计数查询
        
        Args:
            model: SQLAlchemy模型类
            filters: 过滤条件
        
        Returns:
            记录数量
        """
        try:
            query = select(func.count(model.id))
            
            if filters:
                for field, value in filters.items():
                    if hasattr(model, field):
                        if isinstance(value, list):
                            query = query.where(getattr(model, field).in_(value))
                        else:
                            query = query.where(getattr(model, field) == value)
            
            result = await self.db.execute(query)
            return result.scalar() or 0
        
        except Exception as e:
            logger.error(f"计数查询失败: {e}")
            raise e
    
    async def execute_raw_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        执行原生SQL查询
        
        Args:
            query: SQL查询语句
            params: 查询参数
        
        Returns:
            查询结果
        """
        try:
            if params:
                result = await self.db.execute(text(query), params)
            else:
                result = await self.db.execute(text(query))
            
            return result.fetchall()
        
        except Exception as e:
            logger.error(f"原生查询失败: {e}")
            raise e
    
    async def cleanup_old_records(
        self,
        model: Type[T],
        date_field: str = 'created_at',
        days: int = 30
    ) -> int:
        """
        清理旧记录
        
        Args:
            model: SQLAlchemy模型类
            date_field: 日期字段名
            days: 保留天数
        
        Returns:
            删除的记录数量
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            stmt = delete(model).where(
                getattr(model, date_field) < cutoff_date
            )
            
            result = await self.db.execute(stmt)
            await self.db.commit()
            
            deleted_count = result.rowcount
            logger.info(f"清理旧记录: {model.__name__} 删除 {deleted_count} 条记录")
            
            return deleted_count
        
        except Exception as e:
            await self.db.rollback()
            logger.error(f"清理旧记录失败: {e}")
            raise e


class ConnectionPoolManager:
    """数据库连接池管理器"""
    
    def __init__(self):
        self.active_connections = 0
        self.max_connections = 20
        self._semaphore = asyncio.Semaphore(self.max_connections)
    
    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接"""
        async with self._semaphore:
            self.active_connections += 1
            try:
                async with AsyncSessionLocal() as session:
                    yield session
            finally:
                self.active_connections -= 1
    
    async def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        return {
            'active_connections': self.active_connections,
            'max_connections': self.max_connections,
            'available_connections': self.max_connections - self.active_connections
        }


# 全局连接池管理器实例
pool_manager = ConnectionPoolManager()


class QueryCache:
    """查询缓存管理器"""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, datetime] = {}
        self.default_ttl = 300  # 5分钟
    
    def _generate_cache_key(self, query: str, params: Optional[Dict] = None) -> str:
        """生成缓存键"""
        import hashlib
        content = f"{query}:{params or {}}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, query: str, params: Optional[Dict] = None) -> Optional[Any]:
        """获取缓存结果"""
        key = self._generate_cache_key(query, params)
        
        if key in self._cache:
            # 检查TTL
            if datetime.utcnow() < self._cache_ttl[key]:
                return self._cache[key]
            else:
                # 过期删除
                del self._cache[key]
                del self._cache_ttl[key]
        
        return None
    
    def set(
        self, 
        query: str, 
        result: Any, 
        params: Optional[Dict] = None, 
        ttl: Optional[int] = None
    ):
        """设置缓存结果"""
        key = self._generate_cache_key(query, params)
        ttl = ttl or self.default_ttl
        
        self._cache[key] = result
        self._cache_ttl[key] = datetime.utcnow() + timedelta(seconds=ttl)
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_ttl.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_keys = len(self._cache)
        expired_keys = sum(
            1 for ttl in self._cache_ttl.values()
            if datetime.utcnow() >= ttl
        )
        
        return {
            'total_keys': total_keys,
            'active_keys': total_keys - expired_keys,
            'expired_keys': expired_keys
        }


# 全局查询缓存实例
query_cache = QueryCache()