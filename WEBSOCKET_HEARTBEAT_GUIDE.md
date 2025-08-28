# WebSocket心跳机制和自动重连功能

## 功能概述

本次更新为AI内容安全监控系统的WebSocket连接添加了完善的心跳机制和智能自动重连功能，大大提升了实时通信的稳定性和用户体验。

## 新增功能

### 1. 服务端心跳机制优化

#### 主要改进
- **主动心跳发送**: 服务器每25秒主动向客户端发送ping消息
- **精细化超时控制**: 
  - 心跳间隔: 30秒
  - 心跳超时: 90秒  
  - Ping间隔: 25秒
  - 最大未响应次数: 3次
- **连接状态监控**: 实时监控每个连接的ping/pong响应情况
- **详细统计信息**: 记录心跳发送、接收、超时等统计数据

#### 新增配置参数
```python
# WebSocket管理器心跳配置
self.heartbeat_interval = 30  # 心跳间隔（30秒）
self.heartbeat_timeout = 90   # 心跳超时（90秒）
self.ping_interval = 25       # 主动ping间隔（25秒）
self.max_missed_pings = 3     # 最大未响应ping数
```

#### 统计信息
- 总ping发送数
- 总pong接收数
- 超时断开连接数
- 最后清理时间
- 连接详细信息（ping计数、响应时间等）

### 2. 客户端智能重连机制

#### 主要特性
- **指数退避重连**: 重连间隔逐步增加，避免频繁重连
- **自动重连控制**: 可启用/禁用自动重连功能
- **连接状态监控**: 实时显示连接状态和重连进度
- **心跳保活**: 客户端主动发送ping保持连接活跃

#### 重连策略
```typescript
// 重连配置
maxReconnectAttempts: 5        // 最大重连次数
reconnectInterval: 5000        // 基础重连间隔（5秒）
backoffMultiplier: 1.5         // 退避倍数
maxReconnectInterval: 30000    // 最大重连间隔（30秒）
```

#### 心跳配置
```typescript
// 心跳配置
pingInterval: 30000            // Ping间隔（30秒）
pongTimeout: 10000             // Pong超时（10秒）
maxMissedPongs: 3              // 最大未响应次数
```

### 3. WebSocket状态监控组件

#### 功能特性
- **实时状态显示**: 连接状态、心跳信息、重连进度
- **详细信息面板**: 连接时间、ping/pong统计、错误信息
- **手动控制**: 立即重连、断开连接、发送ping、重置状态
- **自动重连开关**: 可手动启用/禁用自动重连

#### 状态指示器
- 🟢 **已连接**: 绿色圆点，连接正常
- 🟡 **连接中**: 黄色圆点，正在建立连接
- 🔴 **连接错误**: 红色圆点，连接失败
- ⚪ **已断开**: 灰色圆点，连接已断开

## 使用方法

### 1. 基本使用

WebSocket连接会在应用启动时自动建立，并启用自动重连功能：

```typescript
// 应用启动时
const wsStore = useWebSocketStore()
wsStore.connect()
wsStore.enableAutoReconnect()
```

### 2. 监控连接状态

使用新的WebSocket状态组件监控连接：

```vue
<template>
  <WebSocketStatus 
    :show-details="true" 
    :show-reconnect="true" 
  />
</template>
```

### 3. 手动控制连接

```typescript
const wsStore = useWebSocketStore()

// 手动重连
await wsStore.connect()

// 断开连接
wsStore.disconnect()

// 启用/禁用自动重连
wsStore.enableAutoReconnect()
wsStore.disableAutoReconnect()

// 重置重连状态
wsStore.resetReconnectState()

// 手动发送ping
wsStore.sendPing()
```

### 4. 监听连接事件

```typescript
const wsStore = useWebSocketStore()

// 监听连接状态变化
wsStore.on('connection_established', (data) => {
  console.log('连接建立:', data)
})

wsStore.on('connection_lost', (data) => {
  console.log('连接丢失:', data)
})
```

## 技术实现细节

### 1. 服务端心跳循环

```python
async def _heartbeat_loop(self):
    """心跳检查循环"""
    while self.is_running:
        current_time = time.time()
        
        # 检查需要发送ping的连接
        for connection_info in self.all_connections.values():
            if current_time - connection_info.last_heartbeat_send >= self.ping_interval:
                await self._send_heartbeat_ping(connection_info)
        
        # 检查超时连接
        timeout_connections = [
            conn for conn in self.all_connections.values()
            if current_time - max(conn.last_ping, conn.last_pong) > self.heartbeat_timeout
        ]
        
        # 断开超时连接
        for connection_info in timeout_connections:
            await self._disconnect_internal(connection_info)
        
        await asyncio.sleep(self.heartbeat_interval)
```

### 2. 客户端重连策略

```typescript
const scheduleReconnect = () => {
  if (reconnectAttempts.value >= maxReconnectAttempts.value) {
    return // 达到最大重连次数
  }
  
  const interval = getNextReconnectInterval() // 指数退避
  
  setTimeout(async () => {
    try {
      await connect()
      resetReconnectState() // 重连成功后重置状态
    } catch (error) {
      scheduleReconnect() // 继续重连
    }
  }, interval)
}
```

### 3. 心跳消息格式

**Ping消息**:
```json
{
  "type": "ping",
  "timestamp": "2024-01-01T12:00:00.000Z",
  "server_time": 1704110400000,
  "sequence": 123
}
```

**Pong响应**:
```json
{
  "type": "pong", 
  "timestamp": "2024-01-01T12:00:00.000Z",
  "client_time": 1704110400000,
  "sequence": 123,
  "ping_count": 10
}
```

## 配置说明

### 1. 服务端配置

在`app/websocket/manager.py`中可调整以下参数：

```python
# 心跳配置
self.heartbeat_interval = 30  # 心跳检查间隔
self.heartbeat_timeout = 90   # 连接超时时间
self.ping_interval = 25       # 主动ping间隔
self.max_missed_pings = 3     # 最大未响应次数
```

### 2. 客户端配置

在`frontend/src/stores/websocket.ts`中可调整：

```typescript
// 重连配置
const maxReconnectAttempts = ref(5)     // 最大重连次数
const reconnectInterval = ref(5000)     // 基础重连间隔
const backoffMultiplier = ref(1.5)      // 退避倍数
const maxReconnectInterval = ref(30000) // 最大重连间隔

// 心跳配置  
const pingInterval = ref(30000)         // Ping间隔
const pongTimeout = ref(10000)          // Pong超时
const maxMissedPongs = ref(3)           // 最大未响应次数
```

## 监控和诊断

### 1. WebSocket状态组件

点击顶部导航栏的WebSocket状态指示器，可查看详细信息：

- **连接信息**: 状态、连接时间、重连次数
- **心跳统计**: Ping次数、未响应次数、最后ping/pong时间
- **错误信息**: 显示连接错误和诊断信息
- **操作按钮**: 重连、断开、发送ping、重置状态

### 2. 服务端统计

通过WebSocket管理器获取详细统计：

```python
stats = websocket_manager.get_stats()
print(stats['heartbeat_stats'])  # 心跳统计
print(stats['connection_details'])  # 连接详情
```

### 3. 客户端调试

在浏览器控制台可查看详细的WebSocket日志：

```javascript
// 查看连接状态
console.log(wsStore.status)

// 查看心跳统计
console.log(wsStore.pingCount, wsStore.missedPongs)

// 查看重连状态  
console.log(wsStore.reconnectAttempts, wsStore.isReconnecting)
```

## 最佳实践

### 1. 网络环境适配

- **稳定网络**: 使用默认配置即可
- **不稳定网络**: 增加重连次数，延长超时时间
- **移动网络**: 启用自动重连，增加心跳频率

### 2. 性能优化

- 合理设置心跳间隔，避免过于频繁
- 监控连接数量，及时清理无效连接
- 使用连接池管理大量并发连接

### 3. 错误处理

- 监听连接错误事件，及时响应
- 记录详细的错误日志便于排查
- 为用户提供友好的错误提示

## 故障排除

### 1. 连接频繁断开

- 检查网络稳定性
- 调整心跳超时时间
- 查看服务器资源使用情况

### 2. 重连失败

- 检查服务器是否正常运行
- 验证用户认证token是否有效
- 查看浏览器控制台错误信息

### 3. 心跳异常

- 检查客户端和服务端时间同步
- 验证心跳消息格式是否正确
- 查看网络延迟和丢包情况

通过这些改进，WebSocket连接的稳定性和用户体验得到了显著提升。系统现在能够自动处理各种网络异常情况，为用户提供可靠的实时通信服务。