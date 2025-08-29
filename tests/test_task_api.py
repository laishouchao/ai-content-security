import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from datetime import datetime

from app.main import app
from app.models.user import User
from app.models.task import ScanTask, TaskStatus, TaskLog
from app.core.database import get_db
from app.core.dependencies import get_current_user


class TestTaskAPI:
    """任务API测试"""
    
    @pytest.fixture
    def client(self):
        """测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = User(
            id=str(uuid.uuid4()),
            username="testuser",
            email="test@example.com",
            is_active=True,
            is_admin=False
        )
        return user
    
    @pytest.fixture
    def mock_task(self, mock_user):
        """模拟任务"""
        task = ScanTask(
            id=str(uuid.uuid4()),
            user_id=mock_user.id,
            target_domain="example.com",
            status=TaskStatus.PENDING,
            progress=0,
            config={"max_depth": 3},
            created_at=datetime.utcnow()
        )
        return task
    
    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return AsyncMock(spec=AsyncSession)
    
    def test_create_task_success(self, client, mock_user, mock_db):
        """测试创建任务成功"""
        # 模拟依赖注入
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        # 模拟数据库操作
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # 模拟Celery任务
        with patch('app.tasks.scan_tasks.scan_domain_task.delay') as mock_celery:
            with patch('app.websocket.handlers.task_monitor.notify_task_created') as mock_notify:
                response = client.post(
                    "/api/v1/tasks",
                    json={
                        "target_domain": "example.com",
                        "config": {"max_depth": 3}
                    }
                )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["target_domain"] == "example.com"
        assert "task_id" in data
        
        # 验证调用
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_celery.assert_called_once()
        mock_notify.assert_called_once()
        
        # 清理依赖覆盖
        app.dependency_overrides.clear()
    
    def test_create_task_missing_domain(self, client, mock_user, mock_db):
        """测试创建任务缺少域名"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        response = client.post(
            "/api/v1/tasks",
            json={"config": {"max_depth": 3}}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "缺少目标域名" in data["detail"]
        
        app.dependency_overrides.clear()
    
    def test_get_tasks_success(self, client, mock_user, mock_db, mock_task):
        """测试获取任务列表成功"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        # 模拟数据库查询结果
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        
        mock_tasks_result = MagicMock()
        mock_tasks_result.scalars.return_value.all.return_value = [mock_task]
        
        mock_db.execute.side_effect = [mock_count_result, mock_tasks_result]
        
        response = client.get("/api/v1/tasks")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 1
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["target_domain"] == "example.com"
        
        app.dependency_overrides.clear()
    
    def test_get_tasks_with_pagination(self, client, mock_user, mock_db):
        """测试带分页的任务列表"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        
        mock_tasks_result = MagicMock()
        mock_tasks_result.scalars.return_value.all.return_value = []
        
        mock_db.execute.side_effect = [mock_count_result, mock_tasks_result]
        
        response = client.get("/api/v1/tasks?skip=10&limit=5")
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["skip"] == 10
        assert data["data"]["limit"] == 5
        
        app.dependency_overrides.clear()
    
    def test_get_task_detail_success(self, client, mock_user, mock_db, mock_task):
        """测试获取任务详情成功"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_db.execute.return_value = mock_result
        
        response = client.get(f"/api/v1/tasks/{mock_task.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == mock_task.id
        assert data["data"]["target_domain"] == "example.com"
        
        app.dependency_overrides.clear()
    
    def test_get_task_detail_not_found(self, client, mock_user, mock_db):
        """测试获取不存在的任务详情"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        task_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/tasks/{task_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "任务不存在" in data["detail"]
        
        app.dependency_overrides.clear()
    
    def test_get_task_logs_success(self, client, mock_user, mock_db, mock_task):
        """测试获取任务日志成功"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        # 模拟任务存在
        mock_task_result = MagicMock()
        mock_task_result.scalar_one_or_none.return_value = mock_task
        
        # 模拟日志查询结果
        mock_log = TaskLog(
            id=str(uuid.uuid4()),
            task_id=mock_task.id,
            level="INFO",
            module="scanner",
            message="Test log message",
            created_at=datetime.utcnow()
        )
        
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        
        mock_logs_result = MagicMock()
        mock_logs_result.scalars.return_value.all.return_value = [mock_log]
        
        mock_db.execute.side_effect = [
            mock_task_result,  # 任务查询
            mock_count_result,  # 日志计数
            mock_logs_result   # 日志查询
        ]
        
        response = client.get(f"/api/v1/tasks/{mock_task.id}/logs")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 1
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["message"] == "Test log message"
        
        app.dependency_overrides.clear()
    
    def test_cancel_task_success(self, client, mock_user, mock_db, mock_task):
        """测试取消任务成功"""
        # 设置任务为运行状态
        mock_task.status = TaskStatus.RUNNING
        
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()
        
        with patch('app.websocket.handlers.task_monitor.notify_task_completed') as mock_notify:
            response = client.post(f"/api/v1/tasks/{mock_task.id}/cancel")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "取消" in data["message"]
        
        # 验证任务状态更新
        assert mock_task.status == TaskStatus.CANCELLED
        assert mock_task.completed_at is not None
        
        mock_db.commit.assert_called_once()
        mock_notify.assert_called_once()
        
        app.dependency_overrides.clear()
    
    def test_cancel_task_invalid_status(self, client, mock_user, mock_db, mock_task):
        """测试取消已完成的任务"""
        # 设置任务为已完成状态
        mock_task.status = TaskStatus.COMPLETED
        
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_db.execute.return_value = mock_result
        
        response = client.post(f"/api/v1/tasks/{mock_task.id}/cancel")
        
        assert response.status_code == 400
        data = response.json()
        assert "无法取消" in data["detail"]
        
        app.dependency_overrides.clear()
    
    def test_delete_task_success(self, client, mock_user, mock_db, mock_task):
        """测试删除任务成功"""
        # 设置任务为已完成状态
        mock_task.status = TaskStatus.COMPLETED
        
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_db.execute.return_value = mock_result
        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()
        
        response = client.delete(f"/api/v1/tasks/{mock_task.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "删除" in data["message"]
        
        mock_db.delete.assert_called_once_with(mock_task)
        mock_db.commit.assert_called_once()
        
        app.dependency_overrides.clear()
    
    def test_delete_running_task(self, client, mock_user, mock_db, mock_task):
        """测试删除正在运行的任务"""
        # 设置任务为运行状态
        mock_task.status = TaskStatus.RUNNING
        
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_db.execute.return_value = mock_result
        
        response = client.delete(f"/api/v1/tasks/{mock_task.id}")
        
        assert response.status_code == 400
        data = response.json()
        assert "无法删除正在运行的任务" in data["detail"]
        
        app.dependency_overrides.clear()
    
    def test_get_task_status(self, client, mock_user, mock_db, mock_task):
        """测试获取任务状态"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_db.execute.return_value = mock_result
        
        response = client.get(f"/api/v1/tasks/{mock_task.id}/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["task_id"] == mock_task.id
        assert data["data"]["status"] == mock_task.status
        assert data["data"]["target_domain"] == mock_task.target_domain
        
        app.dependency_overrides.clear()


class TestTaskAPIIntegration:
    """任务API集成测试"""
    
    @pytest.fixture
    def auth_headers(self):
        """认证头部"""
        # 这里应该是真实的JWT token
        return {"Authorization": "Bearer test_token"}
    
    def test_task_lifecycle(self, client, auth_headers):
        """测试任务生命周期"""
        # 注意：这个测试需要真实的数据库和认证系统
        # 在实际测试中，你需要设置测试数据库和测试用户
        
        # 1. 创建任务
        create_response = client.post(
            "/api/v1/tasks",
            json={
                "target_domain": "test.example.com",
                "config": {"max_depth": 2}
            },
            headers=auth_headers
        )
        
        # 这个测试需要真实的环境才能通过
        # assert create_response.status_code == 200
        
        # 2. 获取任务列表
        # list_response = client.get("/api/v1/tasks", headers=auth_headers)
        # assert list_response.status_code == 200
        
        # 3. 获取任务详情
        # if create_response.status_code == 200:
        #     task_id = create_response.json()["task_id"]
        #     detail_response = client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
        #     assert detail_response.status_code == 200
        
        pass  # 占位符，实际测试需要真实环境


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])