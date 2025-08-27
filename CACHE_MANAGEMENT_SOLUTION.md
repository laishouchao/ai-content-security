# Celery Worker 缓存清理解决方案

## 问题分析

在Celery Worker启动时出现的外键约束错误，根本原因是：

1. **数据不一致问题**: Redis中存在旧的Celery任务信息，但数据库中对应的 `scan_tasks` 记录已被删除
2. **任务执行失败**: 当Celery Worker尝试执行这些"孤立"任务时，会尝试向数据库插入子表记录，但外键约束失败
3. **缓存清理缺失**: 系统缺乏有效的缓存清理机制来处理这种数据不一致

## 解决方案

### 1. 缓存管理器 (`app/core/cache_manager.py`)

**功能特性:**
- 自动检测Redis中的孤立Celery任务
- 清理过期的任务结果
- 处理数据库孤立记录
- 提供完整的缓存清理流程

**核心方法:**
```python
# 检测孤立任务
async def get_orphaned_celery_tasks() -> List[Dict[str, Any]]

# 清理孤立任务
async def cleanup_orphaned_celery_tasks() -> int

# 完整清理
async def perform_full_cleanup() -> Dict[str, Any]
```

### 2. 缓存管理API (`app/api/v1/cache.py`)

**接口端点:**
- `GET /api/v1/cache/status` - 获取缓存状态
- `GET /api/v1/cache/celery-tasks` - 查看Celery任务信息
- `POST /api/v1/cache/cleanup/orphaned-tasks` - 清理孤立任务
- `POST /api/v1/cache/cleanup/full` - 执行完整清理

### 3. 命令行工具 (`cache_manager_cli.py`)

**使用方法:**
```bash
# 查看状态
python cache_manager_cli.py status

# 查看孤立任务
python cache_manager_cli.py tasks --orphaned

# 清理孤立任务
python cache_manager_cli.py cleanup-orphaned

# 完整清理
python cache_manager_cli.py full-cleanup
```

### 4. Worker自动清理

在Celery Worker启动时自动执行缓存清理：

```python
@worker_init.connect
def worker_init_handler(sender=None, **kwargs):
    # 初始化缓存管理器并清理孤立任务
    loop.run_until_complete(cache_manager.cleanup_orphaned_celery_tasks())
```

### 5. 任务执行前检查

在扫描任务执行前检查数据库一致性：

```python
@celery_app.task(bind=True, name="scan_domain_task")
def scan_domain_task(self, task_id: str, user_id: str, target_domain: str, config: Dict[str, Any]):
    # 检查任务是否在数据库中存在
    task_exists = loop.run_until_complete(_check_task_exists(task_id))
    if not task_exists:
        # 清理Redis中的孤立任务信息
        # 抛出异常终止任务执行
```

## 使用指南

### 立即解决当前问题

1. **手动清理孤立任务**:
```bash
python cache_manager_cli.py cleanup-orphaned
```

2. **或通过API清理**:
```bash
curl -X POST "http://localhost:8000/api/v1/cache/cleanup/orphaned-tasks" \
     -H "Authorization: Bearer YOUR_TOKEN"
```

### 预防措施

1. **定期清理**: 建议每天执行一次完整清理
2. **监控告警**: 通过API监控孤立任务数量
3. **Worker重启**: 重启Celery Worker时会自动清理

### 监控和诊断

**查看缓存状态:**
```bash
python cache_manager_cli.py status
```

**输出示例:**
```
📊 缓存状态报告 (2025-08-27T10:56:40.000Z)
==================================================
Redis连接: ✅ 已连接
  - 内存使用: 2.5MB
  - 客户端连接: 3

📋 任务统计:
  - Redis中的Celery任务: 5
  - 孤立任务: 2
  - 数据库中的任务: 10

⚠️  发现 2 个孤立任务，建议清理
```

## 技术实现

### 孤立任务检测逻辑

1. 从Redis获取所有 `celery-task-meta-*` 键
2. 提取任务ID列表
3. 查询数据库中对应的 `scan_tasks` 记录
4. 识别Redis中存在但数据库中不存在的任务

### 清理策略

1. **安全清理**: 只清理确认孤立的任务
2. **日志记录**: 详细记录清理过程
3. **错误处理**: 清理失败不影响系统运行
4. **批量操作**: 支持批量清理提高效率

### 数据库事务

所有数据库操作都在事务中执行，确保数据一致性：

```python
async with AsyncSessionLocal() as db:
    try:
        # 执行清理操作
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e
```

## 配置选项

### 环境变量

- `REDIS_URL`: Redis连接URL
- `DATABASE_URL`: 数据库连接URL

### 清理参数

- `max_age_hours`: 任务结果最大保留时间（默认24小时）
- `cleanup_on_startup`: Worker启动时是否自动清理（默认True）

## 性能考虑

1. **异步操作**: 所有清理操作都是异步的，不阻塞主线程
2. **批量处理**: 支持批量删除Redis键
3. **连接复用**: Redis连接池复用，减少连接开销
4. **内存优化**: 分批处理大量数据，避免内存溢出

## 安全性

1. **权限控制**: API接口需要用户认证
2. **操作确认**: 危险操作（如清空队列）需要确认
3. **日志审计**: 所有清理操作都有详细日志
4. **错误恢复**: 清理失败不会破坏现有数据

## 故障排除

### 常见问题

1. **Redis连接失败**:
   - 检查Redis服务状态
   - 验证连接URL和密码

2. **权限不足**:
   - 确认用户有管理员权限
   - 检查API认证token

3. **清理失败**:
   - 查看日志了解具体错误
   - 检查数据库连接状态

### 日志位置

- 应用日志: `logs/app.log`
- Celery日志: Worker控制台输出
- 清理日志: 包含在应用日志中

## 版本兼容性

- Python 3.8+
- FastAPI 0.68+
- Celery 5.3+
- Redis 5.0+
- PostgreSQL 12+

## 更新记录

- **v1.0.0**: 初始版本，基础缓存清理功能
- **v1.1.0**: 添加命令行工具和API接口
- **v1.2.0**: 添加Worker自动清理和任务检查