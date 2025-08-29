"""
数据库优化器单元测试
测试批量操作、查询优化、连接池管理等功能
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import Result
from datetime import datetime, timedelta
import uuid

from app.core.database_optimizer import DatabaseOptimizer, ConnectionPoolManager, QueryCache
from app.models.scan_task import ScanTask
from app.core.database import Base


class TestDatabaseOptimizer:
    """数据库优化器测试"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def optimizer(self, mock_db):
        """创建优化器实例"""
        return DatabaseOptimizer(mock_db)

    @pytest.fixture
    def sample_records(self):
        """样例记录数据"""
        return [
            {
                "id": str(uuid.uuid4()),
                "target_domain": "example.com",
                "status": "pending",
                "created_at": datetime.utcnow()
            },
            {
                "id": str(uuid.uuid4()),
                "target_domain": "test.com",
                "status": "pending",
                "created_at": datetime.utcnow()
            },
            {
                "id": str(uuid.uuid4()),
                "target_domain": "demo.org",
                "status": "pending",
                "created_at": datetime.utcnow()
            }
        ]

    @pytest.mark.asyncio
    async def test_batch_insert_success(self, optimizer, mock_db, sample_records):
        """测试批量插入成功"""
        # 模拟插入结果
        mock_result = MagicMock()
        mock_result.rowcount = len(sample_records)
        mock_db.execute.return_value = mock_result
        
        # 执行批量插入
        result = await optimizer.batch_insert(
            model=ScanTask,
            records=sample_records,
            batch_size=2
        )
        
        # 验证结果
        assert result == len(sample_records)
        
        # 验证数据库操作（应该分批执行）
        assert mock_db.execute.call_count >= 1
        assert mock_db.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_batch_insert_empty_records(self, optimizer, mock_db):
        """测试批量插入空记录"""
        result = await optimizer.batch_insert(
            model=ScanTask,
            records=[]
        )
        
        # 验证结果
        assert result == 0
        
        # 验证未调用数据库操作
        mock_db.execute.assert_not_called()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_insert_with_error(self, optimizer, mock_db, sample_records):
        """测试批量插入遇到错误"""
        # 模拟数据库错误
        mock_db.execute.side_effect = Exception("Database error")
        
        # 执行批量插入并验证异常
        with pytest.raises(Exception, match="Database error"):
            await optimizer.batch_insert(
                model=ScanTask,
                records=sample_records
            )
        
        # 验证回滚
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_update_success(self, optimizer, mock_db):
        """测试批量更新成功"""
        # 准备更新数据
        updates = [
            {"id": str(uuid.uuid4()), "status": "completed"},
            {"id": str(uuid.uuid4()), "status": "failed"},
        ]
        
        # 模拟更新结果
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        
        # 执行批量更新
        result = await optimizer.batch_update(
            model=ScanTask,
            updates=updates,
            key_field="id"
        )
        
        # 验证结果
        assert result == len(updates)
        
        # 验证数据库操作
        assert mock_db.execute.call_count == len(updates)
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_optimize_query_with_filters(self, optimizer, mock_db):
        """测试优化查询带过滤条件"""
        # 模拟查询结果
        mock_tasks = [MagicMock() for _ in range(3)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_tasks
        mock_db.execute.return_value = mock_result
        
        # 执行优化查询
        results = await optimizer.optimize_query(
            model=ScanTask,
            filters={"status": "completed"},
            relationships=["user"],
            order_by="created_at",
            limit=10,
            offset=0
        )
        
        # 验证结果
        assert len(results) == 3
        
        # 验证数据库查询被调用
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_with_filters(self, optimizer, mock_db):
        """测试带过滤条件的计数查询"""
        # 模拟计数结果
        mock_result = MagicMock()
        mock_result.scalar.return_value = 25
        mock_db.execute.return_value = mock_result
        
        # 执行计数查询
        count = await optimizer.count_with_filters(
            model=ScanTask,
            filters={"status": "pending"}
        )
        
        # 验证结果
        assert count == 25
        
        # 验证数据库查询被调用
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_raw_query(self, optimizer, mock_db):
        """测试执行原生SQL查询"""
        # 模拟查询结果
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("row1",), ("row2",)]
        mock_db.execute.return_value = mock_result
        
        # 执行原生查询
        results = await optimizer.execute_raw_query(
            query="SELECT * FROM scan_tasks WHERE status = :status",
            params={"status": "completed"}
        )
        
        # 验证结果
        assert len(results) == 2
        
        # 验证数据库查询被调用
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_records(self, optimizer, mock_db):
        """测试清理旧记录"""
        # 模拟删除结果
        mock_result = MagicMock()
        mock_result.rowcount = 10
        mock_db.execute.return_value = mock_result
        
        # 执行清理
        deleted_count = await optimizer.cleanup_old_records(
            model=ScanTask,
            date_field="created_at",
            days=30
        )
        
        # 验证结果
        assert deleted_count == 10
        
        # 验证数据库操作
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


class TestConnectionPoolManager:
    """连接池管理器测试"""

    @pytest.fixture
    def pool_manager(self):
        """创建连接池管理器实例"""
        return ConnectionPoolManager()

    @pytest.mark.asyncio
    async def test_get_connection(self, pool_manager):
        """测试获取连接"""
        # 由于使用了真实的async_session_maker，我们需要mock它
        with patch('app.core.database_optimizer.async_session_maker') as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_session_maker.return_value.__aexit__.return_value = None
            
            async with pool_manager.get_connection() as session:
                assert session == mock_session
                assert pool_manager.active_connections == 1
            
            # 连接应该被释放
            assert pool_manager.active_connections == 0

    @pytest.mark.asyncio
    async def test_get_pool_status(self, pool_manager):
        """测试获取连接池状态"""
        status = await pool_manager.get_pool_status()
        
        assert 'active_connections' in status
        assert 'max_connections' in status
        assert 'available_connections' in status
        assert status['active_connections'] == 0
        assert status['max_connections'] == 20
        assert status['available_connections'] == 20

    @pytest.mark.asyncio
    async def test_max_connections_limit(self, pool_manager):
        """测试最大连接数限制"""
        # 设置较小的最大连接数用于测试
        pool_manager.max_connections = 2
        pool_manager._semaphore = asyncio.Semaphore(2)
        
        with patch('app.core.database_optimizer.async_session_maker') as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_session_maker.return_value.__aexit__.return_value = None
            
            # 获取两个连接
            async with pool_manager.get_connection():
                assert pool_manager.active_connections == 1
                
                async with pool_manager.get_connection():
                    assert pool_manager.active_connections == 2
                    
                    # 第三个连接应该等待
                    # 这里我们只是验证连接数，不实际等待
                    status = await pool_manager.get_pool_status()
                    assert status['available_connections'] == 0


class TestQueryCache:
    """查询缓存测试"""

    @pytest.fixture
    def cache(self):
        """创建查询缓存实例"""
        return QueryCache()

    def test_cache_set_and_get(self, cache):
        """测试缓存设置和获取"""
        query = "SELECT * FROM users WHERE id = :id"
        params = {"id": "123"}
        result = {"user": "test"}
        
        # 设置缓存
        cache.set(query, result, params)
        
        # 获取缓存
        cached_result = cache.get(query, params)
        
        assert cached_result == result

    def test_cache_different_params(self, cache):
        """测试不同参数的缓存隔离"""
        query = "SELECT * FROM users WHERE id = :id"
        
        # 设置不同参数的缓存
        cache.set(query, {"user": "user1"}, {"id": "1"})
        cache.set(query, {"user": "user2"}, {"id": "2"})
        
        # 验证缓存隔离
        assert cache.get(query, {"id": "1"}) == {"user": "user1"}
        assert cache.get(query, {"id": "2"}) == {"user": "user2"}
        assert cache.get(query, {"id": "3"}) is None

    def test_cache_ttl_expiry(self, cache):
        """测试缓存TTL过期"""
        import time
        
        query = "SELECT * FROM users"
        result = {"users": []}
        
        # 设置短TTL的缓存
        cache.set(query, result, ttl=1)
        
        # 立即获取应该有缓存
        assert cache.get(query) == result
        
        # 等待过期后获取应该为None
        time.sleep(1.1)
        assert cache.get(query) is None

    def test_cache_clear(self, cache):
        """测试清空缓存"""
        # 设置一些缓存
        cache.set("query1", "result1")
        cache.set("query2", "result2")
        
        # 验证缓存存在
        assert cache.get("query1") == "result1"
        assert cache.get("query2") == "result2"
        
        # 清空缓存
        cache.clear()
        
        # 验证缓存被清空
        assert cache.get("query1") is None
        assert cache.get("query2") is None

    def test_cache_stats(self, cache):
        """测试缓存统计"""
        # 设置一些缓存
        cache.set("query1", "result1")
        cache.set("query2", "result2")
        
        stats = cache.get_cache_stats()
        
        assert stats['total_keys'] == 2
        assert stats['active_keys'] == 2
        assert stats['expired_keys'] == 0

    def test_generate_cache_key(self, cache):
        """测试缓存键生成"""
        query1 = "SELECT * FROM users"
        query2 = "SELECT * FROM users"
        params1 = {"id": "1"}
        params2 = {"id": "2"}
        
        # 相同查询和参数应该生成相同的键
        key1a = cache._generate_cache_key(query1, params1)
        key1b = cache._generate_cache_key(query1, params1)
        assert key1a == key1b
        
        # 不同参数应该生成不同的键
        key2 = cache._generate_cache_key(query1, params2)
        assert key1a != key2
        
        # 不同查询应该生成不同的键
        key3 = cache._generate_cache_key(query2, params1)
        assert key1a != key3


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])