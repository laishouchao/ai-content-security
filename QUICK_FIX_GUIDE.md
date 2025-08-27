# 缓存清理快速解决方案

## 立即解决当前问题

### 方法1: 使用命令行工具（推荐）

```bash
# 进入项目目录
cd e:\01_Github\ai-content-security

# 运行清理工具
python cache_manager_cli.py cleanup-orphaned
```

### 方法2: 使用API接口

```bash
# 首先启动应用
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 然后调用清理接口（需要认证token）
curl -X POST "http://localhost:8000/api/v1/cache/cleanup/orphaned-tasks" \
     -H "Authorization: Bearer YOUR_TOKEN"
```

### 方法3: 手动清理Redis

如果上述方法不可用，可以手动清理Redis：

```bash
# 连接到Redis
redis-cli -h 115.190.95.157 -p 6379 -a yourredispassword

# 查看所有Celery任务键
KEYS celery-task-meta-*

# 删除特定的任务键（替换为实际的task_id）
DEL celery-task-meta-7ba9a117-90e7-459e-8285-be15047ab548

# 或者删除所有Celery任务键（谨慎使用）
EVAL "return redis.call('del', unpack(redis.call('keys', 'celery-task-meta-*')))" 0
```

## 预防措施

### 1. 启用Worker自动清理

确保Celery Worker启动时会自动清理孤立任务。代码已经添加到 `app/core/celery_optimizer.py` 中。

### 2. 定期执行清理

建议添加到crontab中定期执行：

```bash
# 每天凌晨2点执行完整清理
0 2 * * * cd /path/to/project && python cache_manager_cli.py full-cleanup >> /var/log/cache_cleanup.log 2>&1
```

### 3. 监控告警

可以通过健康检查API监控孤立任务数量：

```bash
# 检查缓存健康状态
curl "http://localhost:8000/api/v1/cache/health"
```

## 故障排查

### 问题1: Redis连接失败

```bash
# 检查Redis服务状态
redis-cli -h 115.190.95.157 -p 6379 -a yourredispassword ping

# 检查网络连接
telnet 115.190.95.157 6379
```

### 问题2: 权限不足

确保用户有管理员权限，或者使用具有足够权限的用户token。

### 问题3: 数据库连接失败

检查数据库连接配置和服务状态：

```bash
# 检查PostgreSQL连接
psql "postgresql://postgres:yourpassword@115.190.95.157:5432/mydb" -c "SELECT 1;"
```

## 验证解决方案

1. **重启Celery Worker**:
```bash
celery -A celery_app worker --loglevel=info
```

2. **观察日志输出**:
   - 应该看到 "Worker启动时清理了 X 个孤立的Celery任务"
   - 不应该再有外键约束错误

3. **创建新任务测试**:
   - 通过Web界面或API创建新的扫描任务
   - 确认任务能正常执行

## 文件清单

新增文件：
- `app/core/cache_manager.py` - 缓存管理器
- `app/api/v1/cache.py` - 缓存管理API
- `cache_manager_cli.py` - 命令行工具
- `CACHE_MANAGEMENT_SOLUTION.md` - 详细文档

修改文件：
- `main.py` - 添加缓存管理路由和生命周期
- `app/core/celery_optimizer.py` - 添加Worker启动清理
- `app/tasks/scan_tasks.py` - 添加任务存在检查

## 联系支持

如果问题仍然存在，请提供以下信息：
1. 错误日志
2. Redis和数据库连接状态
3. Celery Worker启动日志
4. 缓存状态报告（`python cache_manager_cli.py status`）