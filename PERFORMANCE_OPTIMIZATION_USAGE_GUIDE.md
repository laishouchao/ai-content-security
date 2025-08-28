# 性能极限优化 - 完整使用指南

## 🚀 快速开始

### 1. 前端创建任务

在前端界面中，您现在可以通过以下方式使用性能优化：

**方式一：使用配置预设**
```typescript
// 选择预设配置
const presets = await taskAPI.getConfigPresets()
const quickScanPreset = presets.data.find(p => p.name === '快速扫描')

// 创建任务
const taskData = {
  target_domain: 'example.com',
  task_name: '示例快速扫描',
  config: quickScanPreset.config
}

const response = await taskAPI.createTask(taskData)
```

**方式二：手动配置**
```typescript
const taskData = {
  target_domain: 'example.com',
  task_name: '自定义高性能扫描',
  config: {
    use_parallel_executor: true,     // 启用并行执行器
    smart_prefilter_enabled: true,   // 启用智能预筛选
    dns_concurrency: 100,            // DNS并发数
    ai_skip_threshold: 0.3,          // AI跳过阈值
    multi_viewport_capture: true,    // 多视角截图
    enable_aggressive_caching: false // 激进缓存
  }
}
```

### 2. 后端 API 调用

**创建任务 API**
```bash
curl -X POST "http://localhost:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "target_domain": "example.com",
    "task_name": "高性能扫描测试",
    "config": {
      "use_parallel_executor": true,
      "smart_prefilter_enabled": true,
      "dns_concurrency": 100,
      "ai_skip_threshold": 0.3
    }
  }'
```

**获取配置预设**
```bash
curl -X GET "http://localhost:8000/api/v1/tasks/config/presets" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**获取性能指标**
```bash
curl -X POST "http://localhost:8000/api/v1/tasks/{task_id}/performance-metrics" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 📊 性能配置参数

### 子域名发现优化

```python
subdomain_config = {
    'dns_concurrency': 100,           # DNS查询并发数 (默认: 50)
    'dns_timeout': 2,                 # DNS超时时间 (默认: 5秒)
    'certificate_discovery_enabled': True,  # 证书透明日志
    'passive_dns_enabled': True,     # 被动DNS查询
    'max_subdomains': 1000           # 最大子域名数量
}
```

### AI分析优化

```python
ai_config = {
    'smart_prefilter_enabled': True,  # 启用智能预筛选
    'prefilter_threshold': 0.3,       # 预筛选阈值
    'batch_size': 10,                 # 批处理大小
    'max_concurrent_ai_calls': 3,     # 最大并发AI调用
    'enable_caching': True            # 启用结果缓存
}
```

### 爬取引擎优化

```python
crawl_config = {
    'max_crawl_iterations': 5,        # 爬取迭代次数
    'crawl_delay': 0.5,              # 爬取延迟(秒)
    'max_concurrent_requests': 10,    # 最大并发请求
    'screenshot_optimization': True   # 截图优化
}
```

## 🔧 实际使用场景

### 场景1: 快速扫描 (< 5分钟)
适用于：日常安全检查、CI/CD集成

```python
quick_config = {
    'use_parallel_executor': True,
    'dns_concurrency': 100,
    'max_crawl_iterations': 3,
    'max_subdomains': 200,
    'smart_prefilter_enabled': True,
    'ai_skip_threshold': 0.2  # 更激进的AI跳过
}
```

### 场景2: 深度扫描 (10-30分钟)
适用于：全面安全审计、合规检查

```python
deep_config = {
    'use_parallel_executor': True,
    'dns_concurrency': 150,
    'max_crawl_iterations': 8,
    'max_subdomains': 1000,
    'smart_prefilter_enabled': True,
    'ai_skip_threshold': 0.4,  # 保守的AI跳过
    'multi_viewport_capture': True
}
```

### 场景3: 成本敏感扫描
适用于：大批量扫描、预算有限

```python
cost_optimized_config = {
    'use_parallel_executor': True,
    'smart_prefilter_enabled': True,
    'ai_skip_threshold': 0.1,  # 最激进的AI跳过
    'enable_aggressive_caching': True,
    'ai_sample_rate': 0.2,     # 只有20%的内容进行AI分析
    'screenshot_quality': 'low'
}
```

## 📈 性能监控

### 1. 实时事件监听

```python
async def event_handler(event):
    if event.event_type == 'ai_analysis_skipped':
        print(f"AI分析跳过: {event.data.get('reason')}")
    elif event.event_type == 'stage_completed':
        print(f"阶段完成: {event.stage.value}")

executor.event_store.subscribe(event_handler)
```

### 2. 性能统计获取

```python
# 获取执行状态
status = executor.get_current_status()
print(f"队列状态: {status['queue_status']}")

# 获取AI预筛选统计
if hasattr(executor, 'prefilter'):
    stats = executor.prefilter.get_efficiency_stats()
    print(f"AI跳过率: {stats['ai_skip_rate']}")
    print(f"成本节省: {stats['cost_reduction']}")
```

### 3. WebSocket事件流

前端可以实时接收详细的执行事件：

```javascript
// 订阅任务事件
websocket.on('task_event', (event) => {
    if (event.event_type === 'subdomains_discovered') {
        console.log(`发现子域名: ${event.data.count}个`);
    } else if (event.event_type === 'ai_analysis_skipped') {
        console.log(`AI分析跳过: ${event.data.reason}`);
    }
});
```

## 🧪 性能测试

### 运行基准测试

```bash
# 运行性能对比测试
python test_performance_optimization.py

# 查看测试报告
cat performance_test_*.json
```

### 自定义测试

```python
from test_performance_optimization import PerformanceTester

tester = PerformanceTester()

# 添加自定义域名
TEST_DOMAINS.extend(['your-domain.com'])

# 修改测试配置
TEST_CONFIGS['custom'] = {
    'use_parallel_executor': True,
    'dns_concurrency': 200,  # 更高并发
    'smart_prefilter_enabled': True
}

await tester.run_performance_tests()
```

## 💡 最佳实践

### 1. 并发优化
- 根据服务器性能调整DNS并发数
- 监控CPU和内存使用情况
- 避免过度并发导致的资源竞争

### 2. 成本控制
- 启用智能预筛选减少AI调用
- 使用缓存避免重复分析
- 根据风险等级调整分析深度

### 3. 错误处理
- 设置合理的超时时间
- 实现优雅降级机制
- 监控和记录异常情况

### 4. 资源管理
- 及时清理临时文件
- 限制内存使用
- 定期清理缓存

## 🚨 注意事项

1. **资源限制**
   - 高并发可能触发API限制
   - 监控服务器资源使用
   - 避免影响其他服务

2. **网络礼仪**
   - 遵守robots.txt规则
   - 设置合理的请求间隔
   - 避免对目标网站造成压力

3. **准确性平衡**
   - 智能预筛选可能影响检测准确率
   - 根据业务需求调整阈值
   - 定期验证检测质量

## 📚 进阶配置

### 动态配置调整

```python
class AdaptiveConfig:
    def __init__(self):
        self.base_config = DEFAULT_CONFIG
    
    def adjust_for_domain_size(self, estimated_subdomains):
        if estimated_subdomains > 100:
            self.base_config['dns_concurrency'] = 200
            self.base_config['ai_skip_threshold'] = 0.2
        elif estimated_subdomains < 20:
            self.base_config['dns_concurrency'] = 50
            self.base_config['ai_skip_threshold'] = 0.5
    
    def adjust_for_cost_budget(self, max_cost):
        estimated_ai_calls = self.estimate_ai_calls()
        if estimated_ai_calls * 0.01 > max_cost:
            # 提高AI跳过率
            self.base_config['ai_skip_threshold'] = 0.1
```

### 自定义预筛选规则

```python
class CustomPrefilter(SmartAIPrefilter):
    def _make_analysis_decision(self, image_features, url_features, content_features):
        # 添加自定义业务规则
        if 'company-internal' in url_features.get('domain', ''):
            return {'needs_ai': False, 'reason': 'internal_domain'}
        
        return super()._make_analysis_decision(image_features, url_features, content_features)
```

通过这些优化，系统性能预期可提升3-10倍，AI成本节省70-90%，为大规模安全扫描提供了坚实的技术基础。