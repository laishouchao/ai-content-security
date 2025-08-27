"""
API集成测试
测试域名列表管理和性能监控API的集成功能
"""

import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import os
from unittest.mock import patch
import uuid

# 假设我们有一个测试配置
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost/test_ai_content_security")

from main import app
from app.core.database import get_db
from app.models.user import User
from app.models.domain_list import DomainList, DomainListEntry

# 测试数据库引擎
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def test_db():
    """测试数据库会话"""
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def test_client():
    """测试客户端"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def test_user(test_db):
    """测试用户"""
    user = User(
        id=str(uuid.uuid4()),
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        is_active=True
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def auth_headers(test_user):
    """认证头部"""
    # 这里应该生成一个有效的JWT token
    # 为了简化，我们使用模拟的token
    token = "test_jwt_token"
    return {"Authorization": f"Bearer {token}"}


class TestDomainListAPI:
    """域名列表API集成测试"""

    @pytest.mark.asyncio
    async def test_create_domain_list(self, test_client, auth_headers, test_user):
        """测试创建域名列表"""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            response = await test_client.post(
                "/api/v1/domain-lists",
                json={
                    "name": "测试白名单",
                    "list_type": "whitelist",
                    "description": "测试用白名单",
                    "scope": "user"
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["name"] == "测试白名单"
            assert data["data"]["list_type"] == "whitelist"

    @pytest.mark.asyncio
    async def test_get_domain_lists(self, test_client, auth_headers, test_user):
        """测试获取域名列表"""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            response = await test_client.get(
                "/api/v1/domain-lists",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            assert "items" in data["data"]
            assert "total" in data["data"]

    @pytest.mark.asyncio
    async def test_add_domain_entry(self, test_client, auth_headers, test_user, test_db):
        """测试添加域名条目"""
        # 先创建一个域名列表
        domain_list = DomainList(
            id=uuid.uuid4(),
            name="测试列表",
            list_type="whitelist",
            scope="user",
            user_id=test_user.id,
            created_by=test_user.id
        )
        test_db.add(domain_list)
        await test_db.commit()
        await test_db.refresh(domain_list)
        
        with patch('app.api.deps.get_current_user', return_value=test_user):
            response = await test_client.post(
                f"/api/v1/domain-lists/{domain_list.id}/entries",
                json={
                    "domain_pattern": "example.com",
                    "description": "测试域名",
                    "is_regex": False,
                    "confidence_score": 100
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["domain_pattern"] == "example.com"

    @pytest.mark.asyncio
    async def test_batch_add_domains(self, test_client, auth_headers, test_user, test_db):
        """测试批量添加域名"""
        # 先创建一个域名列表
        domain_list = DomainList(
            id=uuid.uuid4(),
            name="批量测试列表",
            list_type="whitelist",
            scope="user",
            user_id=test_user.id,
            created_by=test_user.id
        )
        test_db.add(domain_list)
        await test_db.commit()
        await test_db.refresh(domain_list)
        
        with patch('app.api.deps.get_current_user', return_value=test_user):
            response = await test_client.post(
                f"/api/v1/domain-lists/{domain_list.id}/batch-add",
                json={
                    "domain_patterns": ["test1.com", "test2.com", "test3.org"],
                    "is_regex": False,
                    "is_wildcard": False
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["added_count"] == 3
            assert data["data"]["duplicate_count"] == 0

    @pytest.mark.asyncio
    async def test_check_domains(self, test_client, auth_headers, test_user, test_db):
        """测试域名检查功能"""
        # 创建测试数据
        domain_list = DomainList(
            id=uuid.uuid4(),
            name="检查测试列表",
            list_type="whitelist",
            scope="user",
            user_id=test_user.id,
            created_by=test_user.id,
            is_active=True
        )
        test_db.add(domain_list)
        await test_db.flush()
        
        domain_entry = DomainListEntry(
            id=uuid.uuid4(),
            domain_list_id=domain_list.id,
            domain_pattern="allowed.com",
            is_regex=False,
            is_wildcard=False,
            is_active=True,
            created_by=test_user.id
        )
        test_db.add(domain_entry)
        await test_db.commit()
        
        with patch('app.api.deps.get_current_user', return_value=test_user):
            response = await test_client.post(
                "/api/v1/domain-lists/check",
                json={
                    "domains": ["allowed.com", "notallowed.com"]
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "allowed.com" in data["data"]
            assert "notallowed.com" in data["data"]
            assert data["data"]["allowed.com"]["is_allowed"] is True
            assert data["data"]["notallowed.com"]["is_allowed"] is None


class TestPerformanceAPI:
    """性能监控API集成测试"""

    @pytest.mark.asyncio
    async def test_get_performance_stats(self, test_client, auth_headers, test_user):
        """测试获取性能统计"""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            response = await test_client.get(
                "/api/v1/performance/stats",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            
            # 检查性能统计的基本结构
            perf_data = data["data"]
            assert "timestamp" in perf_data
            assert "memory_stats" in perf_data
            assert "database_stats" in perf_data
            assert "celery_stats" in perf_data
            assert "system_health" in perf_data

    @pytest.mark.asyncio
    async def test_get_memory_usage(self, test_client, auth_headers, test_user):
        """测试获取内存使用情况"""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            response = await test_client.get(
                "/api/v1/performance/memory",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            
            # 检查内存统计结构
            memory_data = data["data"]
            assert "memory_info" in memory_data
            assert "resource_stats" in memory_data

    @pytest.mark.asyncio
    async def test_optimize_system(self, test_client, auth_headers, test_user):
        """测试系统优化功能"""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            response = await test_client.post(
                "/api/v1/performance/optimize",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            
            # 检查优化结果结构
            optimize_data = data["data"]
            assert "timestamp" in optimize_data
            assert "actions_performed" in optimize_data
            assert isinstance(optimize_data["actions_performed"], list)

    @pytest.mark.asyncio
    async def test_health_check(self, test_client, auth_headers, test_user):
        """测试系统健康检查"""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            response = await test_client.get(
                "/api/v1/performance/health",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            
            # 检查健康检查结构
            health_data = data["data"]
            assert "status" in health_data
            assert "health_score" in health_data
            assert "timestamp" in health_data
            assert health_data["status"] in ["healthy", "warning", "critical"]
            assert 0 <= health_data["health_score"] <= 100

    @pytest.mark.asyncio
    async def test_clear_cache(self, test_client, auth_headers, test_user):
        """测试清理缓存功能"""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            response = await test_client.delete(
                "/api/v1/performance/cache",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            
            # 检查缓存清理结果
            cache_data = data["data"]
            assert "message" in cache_data
            assert "cleared_items" in cache_data

    @pytest.mark.asyncio
    async def test_get_system_alerts(self, test_client, auth_headers, test_user):
        """测试获取系统告警"""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            response = await test_client.get(
                "/api/v1/performance/alerts",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            
            # 检查告警结构
            alerts_data = data["data"]
            assert "alerts" in alerts_data
            assert "alert_count" in alerts_data
            assert "timestamp" in alerts_data
            assert isinstance(alerts_data["alerts"], list)


class TestIntegratedWorkflow:
    """集成工作流测试"""

    @pytest.mark.asyncio
    async def test_complete_domain_management_workflow(self, test_client, auth_headers, test_user):
        """测试完整的域名管理工作流"""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            # 1. 创建域名列表
            create_response = await test_client.post(
                "/api/v1/domain-lists",
                json={
                    "name": "工作流测试列表",
                    "list_type": "whitelist",
                    "description": "完整工作流测试",
                    "scope": "user"
                },
                headers=auth_headers
            )
            
            assert create_response.status_code == 200
            list_data = create_response.json()["data"]
            list_id = list_data["id"]
            
            # 2. 添加域名条目
            add_response = await test_client.post(
                f"/api/v1/domain-lists/{list_id}/entries",
                json={
                    "domain_pattern": "workflow.com",
                    "description": "工作流测试域名"
                },
                headers=auth_headers
            )
            
            assert add_response.status_code == 200
            
            # 3. 批量添加域名
            batch_response = await test_client.post(
                f"/api/v1/domain-lists/{list_id}/batch-add",
                json={
                    "domain_patterns": ["batch1.com", "batch2.com"]
                },
                headers=auth_headers
            )
            
            assert batch_response.status_code == 200
            
            # 4. 检查域名
            check_response = await test_client.post(
                "/api/v1/domain-lists/check",
                json={
                    "domains": ["workflow.com", "batch1.com", "unknown.com"]
                },
                headers=auth_headers
            )
            
            assert check_response.status_code == 200
            check_data = check_response.json()["data"]
            assert check_data["workflow.com"]["is_allowed"] is True
            assert check_data["batch1.com"]["is_allowed"] is True
            assert check_data["unknown.com"]["is_allowed"] is None
            
            # 5. 获取列表详情
            detail_response = await test_client.get(
                f"/api/v1/domain-lists/{list_id}",
                headers=auth_headers
            )
            
            assert detail_response.status_code == 200
            detail_data = detail_response.json()["data"]
            assert detail_data["domain_count"] >= 3  # 至少有3个域名


# 运行测试的配置
@pytest.mark.asyncio
class TestConfiguration:
    """测试配置和设置"""

    @pytest.fixture(autouse=True)
    async def setup_test_database(self):
        """设置测试数据库"""
        # 这里应该创建测试数据库表
        # 为了简化，我们假设表已经存在
        yield
        # 清理测试数据
        pass

    @pytest.fixture(autouse=True)
    async def mock_dependencies(self):
        """模拟依赖项"""
        # 模拟Redis连接
        with patch('app.core.redis_lock.lock_manager.redis_client'):
            # 模拟内存管理器
            with patch('app.core.memory_manager.memory_manager'):
                yield


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])