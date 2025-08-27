# Celery Worker 错误修复指南

## 问题分析

根据日志分析，出现了两个主要错误：

### 1. Control Command Error
```
ValueError('not enough values to unpack (expected 3, got 1)')
```
**原因**: Redis 传输配置中的 `master_name` 设置导致解包错误

### 2. Unrecoverable Error  
```
AttributeError("'NoneType' object has no attribute '_callbacks'")
```
**原因**: Celery worker 连接对象变为 None，通常由网络中断或配置问题引起

## 解决方案

### 1. 立即修复步骤

#### 停止当前 Worker
```bash
# 找到 Celery 进程并停止
tasklist | findstr celery
taskkill /F /PID <进程ID>
```

#### 清理 Redis 缓存
```bash
# 运行 Redis 测试脚本
python test_redis.py
```

#### 使用新的启动脚本
```bash
# 使用增强的启动脚本
python start_celery.py
```

### 2. 配置修复

已经修复的配置项：

1. **移除 Redis Sentinel 配置**
   - 删除 `master_name` 设置
   - 修复传输选项配置

2. **增强连接重试**
   - `broker_connection_retry_on_startup = True`
   - `broker_connection_max_retries = 10`
   - `broker_heartbeat = 30`

3. **内存管理优化**
   - `worker_max_memory_per_child = 200000` (200MB)
   - `worker_max_tasks_per_child = 1000`

4. **任务超时调整**
   - `task_soft_time_limit = 300` (5分钟)
   - `task_time_limit = 600` (10分钟)

### 3. 监控和预防

#### 启用监控
```bash
# 使用监控启动脚本
python start_celery.py
```

#### 定期清理
```bash
# 每天运行清理脚本
python test_redis.py
```

#### 日志监控
监控以下日志文件：
- `celery_worker.log` - Worker 运行日志
- 系统日志中的 Redis 连接信息

### 4. 网络优化建议

由于使用远程 Redis 服务器 (`115.190.95.157:6379`)：

1. **检查网络稳定性**
   ```bash
   ping 115.190.95.157
   telnet 115.190.95.157 6379
   ```

2. **考虑本地 Redis**
   - 如果网络不稳定，建议使用本地 Redis
   - 或者使用 Redis 集群提高可用性

3. **连接池优化**
   - `broker_pool_limit = 10`
   - 连接复用减少网络开销

### 5. 验证修复

运行以下命令验证修复效果：

```bash
# 1. 测试 Redis 连接
python test_redis.py

# 2. 启动 Worker
python start_celery.py

# 3. 检查 Worker 状态
celery -A celery_app status

# 4. 监控日志
tail -f celery_worker.log
```

### 6. 应急预案

如果问题持续存在：

1. **切换到本地 Redis**
   ```bash
   # 启动本地 Redis
   docker run -d -p 6379:6379 redis:latest
   
   # 修改环境变量
   export CELERY_BROKER_URL="redis://localhost:6379/0"
   export CELERY_RESULT_BACKEND="redis://localhost:6379/0"
   ```

2. **使用不同的消息队列**
   - 考虑使用 RabbitMQ
   - 或者使用数据库作为 broker

3. **降级方案**
   - 临时禁用后台任务
   - 使用同步处理模式

## 预防措施

1. **定期监控**
   - 每小时检查 Worker 状态
   - 监控 Redis 内存使用

2. **自动重启**
   - 使用 systemd 或 supervisor 管理 Worker
   - 配置自动重启策略

3. **健康检查**
   - 添加 API 健康检查端点
   - 监控任务队列长度

4. **备份策略**
   - 定期备份 Redis 数据
   - 准备故障转移方案

## 联系信息

如果问题仍然存在，请提供：
1. 完整的错误日志
2. Redis 连接测试结果
3. 网络连接状态
4. 系统资源使用情况