import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElNotification } from 'element-plus'
import { useTaskStore } from './task'

// WebSocket消息类型
export interface WebSocketMessage {
  type: string
  timestamp: string
  [key: string]: any
}

export interface TaskProgressMessage extends WebSocketMessage {
  type: 'task_progress'
  task_id: string
  progress: number
  stage: string
  message: string
}

export interface TaskCompletedMessage extends WebSocketMessage {
  type: 'task_completed'
  task_id: string
  status: string
  statistics: Record<string, any>
  message: string
}

export interface ViolationDetectedMessage extends WebSocketMessage {
  type: 'violation_detected'
  task_id: string
  violation: {
    domain: string
    violation_type: string
    risk_level: string
    confidence_score: number
    description: string
  }
  message: string
}

export enum WebSocketStatus {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  ERROR = 'error'
}

export const useWebSocketStore = defineStore('websocket', () => {
  // 状态
  const ws = ref<WebSocket | null>(null)
  const status = ref<WebSocketStatus>(WebSocketStatus.DISCONNECTED)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = ref(5)
  const reconnectInterval = ref(5000)
  const messages = ref<WebSocketMessage[]>([])
  const lastError = ref<string>('')
  const connectedAt = ref<string>('')
  
  // 心跳相关状态
  const heartbeatInterval = ref<number | null>(null)
  const pingInterval = ref(30000) // 30秒发送一次ping
  const pongTimeout = ref(10000)  // 10秒等待pong响应
  const lastPingTime = ref<number>(0)
  const lastPongTime = ref<number>(0)
  const pingCount = ref(0)
  const missedPongs = ref(0)
  const maxMissedPongs = ref(3)
  
  // 重连相关状态
  const isReconnecting = ref(false)
  const reconnectTimer = ref<number | null>(null)
  const autoReconnectEnabled = ref(true)
  const backoffMultiplier = ref(1.5)
  const maxReconnectInterval = ref(30000)
  
  // 计算属性
  const isConnected = computed(() => status.value === WebSocketStatus.CONNECTED)
  const isConnecting = computed(() => status.value === WebSocketStatus.CONNECTING)
  const connectionStatusText = computed(() => {
    const statusMap = {
      [WebSocketStatus.CONNECTING]: '连接中',
      [WebSocketStatus.CONNECTED]: '已连接',
      [WebSocketStatus.DISCONNECTED]: '已断开',
      [WebSocketStatus.ERROR]: '连接错误'
    }
    return statusMap[status.value]
  })
  
  const connectionStatusType = computed(() => {
    const typeMap = {
      [WebSocketStatus.CONNECTING]: 'warning',
      [WebSocketStatus.CONNECTED]: 'success',
      [WebSocketStatus.DISCONNECTED]: 'info',
      [WebSocketStatus.ERROR]: 'danger'
    }
    return typeMap[status.value]
  })

  // 连接WebSocket
  const connect = async () => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      console.log('WebSocket已连接，无需重复连接')
      return
    }

    try {
      status.value = WebSocketStatus.CONNECTING
      
      // 获取用户令牌用于认证
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token')
      if (!token) {
        const errorMsg = '用户未登录，无法建立 WebSocket 连接'
        console.warn('WebSocket连接失败：未找到用户令牌，请先登录')
        lastError.value = '用户未登录'
        status.value = WebSocketStatus.ERROR
        
        // 如果用户未登录，不建立连接
        if (import.meta.env.DEV) {
          console.log('🔄 开发环境：用户未登录，跳过WebSocket连接')
        } else {
          // 生产环境下提示用户登录
          ElNotification({
            title: 'WebSocket连接失败',
            message: '请先登录再使用实时功能',
            type: 'warning',
            duration: 5000
          })
        }
        return
      }
      
      // 构建WebSocket URL
      const baseUrl = import.meta.env.DEV ? 'localhost:8000' : window.location.host
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${baseUrl}/api/v1/ws?token=${token}`
      
      console.log('🔌 尝试连接WebSocket服务:', wsUrl.replace(/token=[^&]+/, 'token=***'))
      
      // 先检查后端服务是否可用
      if (import.meta.env.DEV) {
        try {
          const healthCheck = await fetch(`http://${baseUrl}/api/v1/health`, {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${token}`
            }
          })
          if (!healthCheck.ok) {
            throw new Error(`后端服务不可用: ${healthCheck.status}`)
          }
          console.log('✅ 后端服务可用')
        } catch (healthError) {
          console.warn('⚠️ 后端服务检查失败:', healthError)
          lastError.value = '后端服务不可用'
          status.value = WebSocketStatus.ERROR
          return
        }
      }
      
      // 创建WebSocket连接
      ws.value = new WebSocket(wsUrl)
      
      // 设置连接超时
      const connectTimeout = setTimeout(() => {
        if (ws.value && ws.value.readyState === WebSocket.CONNECTING) {
          console.error('❌ WebSocket连接超时')
          lastError.value = '连接超时'
          ws.value.close()
          status.value = WebSocketStatus.ERROR
        }
      }, 10000) // 10秒超时
      
      // 连接成功或失败时清除超时定时器
      const clearConnectTimeout = () => {
        clearTimeout(connectTimeout)
      }
      
      setupEventHandlers()
      
      // 监听连接成功或失败
      const originalOnOpen = ws.value.onopen
      const originalOnError = ws.value.onerror
      
      ws.value.onopen = (event) => {
        clearConnectTimeout()
        lastError.value = ''
        connectedAt.value = new Date().toISOString()
        if (originalOnOpen && ws.value) originalOnOpen.call(ws.value, event)
      }
      
      ws.value.onerror = (event) => {
        clearConnectTimeout()
        lastError.value = 'WebSocket连接错误'
        if (originalOnError && ws.value) originalOnError.call(ws.value, event)
      }
      
    } catch (error) {
      console.error('WebSocket连接初始化失败:', error)
      lastError.value = `连接初始化失败: ${error}`
      status.value = WebSocketStatus.ERROR
    }
  }

  // 设置事件处理器
  const setupEventHandlers = () => {
    if (!ws.value) return

    ws.value.onopen = () => {
      console.log('✅ WebSocket连接成功')
      status.value = WebSocketStatus.CONNECTED
      reconnectAttempts.value = 0
      isReconnecting.value = false
      lastError.value = ''
      
      // 重置心跳相关状态
      pingCount.value = 0
      missedPongs.value = 0
      lastPingTime.value = 0
      lastPongTime.value = Date.now()
      
      // 启动心跳
      startHeartbeat()
    }

    ws.value.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        
        // 处理心跳消息
        if (message.type === 'ping') {
          // 收到服务器ping，自动响应pong
          const pongMessage = {
            type: 'pong',
            timestamp: new Date().toISOString(),
            client_time: Date.now(),
            sequence: message.sequence || 0
          }
          ws.value?.send(JSON.stringify(pongMessage))
          console.log('🏓 收到服务器ping，已响应pong')
          return
        } else if (message.type === 'pong') {
          // 收到服务器pong响应
          handlePong(message)
          return
        }
        
        console.log('📨 收到后端WebSocket消息:', message)
        handleMessage(message)
      } catch (error) {
        console.error('WebSocket消息解析失败:', error)
      }
    }

    ws.value.onclose = (event) => {
      console.log('❌ WebSocket连接关闭:', {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean
      })
      
      status.value = WebSocketStatus.DISCONNECTED
      
      // 停止心跳
      stopHeartbeat()
      
      // 根据关闭代码判断是否需要重连
      const shouldReconnect = autoReconnectEnabled.value && 
                             event.code !== 1000 && // 正常关闭
                             event.code !== 1001 && // 用户离开
                             event.code !== 1005 && // 无状态码
                             reconnectAttempts.value < maxReconnectAttempts.value
      
      if (shouldReconnect) {
        console.log('🔄 准备自动重连...')
        scheduleReconnect()
      } else if (event.code === 1008) {
        console.error('❌ WebSocket认证失败，请重新登录')
        lastError.value = '认证失败，请重新登录'
        status.value = WebSocketStatus.ERROR
      } else if (!autoReconnectEnabled.value) {
        console.log('🔄 自动重连已禁用')
      } else {
        console.log('🔄 已达最大重连次数，停止重连')
        lastError.value = '连接失败，已达最大重连次数'
        status.value = WebSocketStatus.ERROR
      }
    }

    ws.value.onerror = (error) => {
      console.error('❌ WebSocket连接错误:', {
        error,
        readyState: ws.value?.readyState,
        url: ws.value?.url
      })
      
      if (status.value === WebSocketStatus.CONNECTING) {
        status.value = WebSocketStatus.ERROR
        lastError.value = 'WebSocket连接错误'
      }
    }
  }

  // 处理消息
  const handleMessage = (message: WebSocketMessage) => {
    console.log('📨 收到WebSocket消息:', message)
    
    // 添加到消息历史
    messages.value.unshift(message)
    if (messages.value.length > 100) {
      messages.value = messages.value.slice(0, 100) // 只保留最新100条消息
    }

    const taskStore = useTaskStore()

    // 根据消息类型处理
    switch (message.type) {
      case 'task_progress':
        handleTaskProgress(message as TaskProgressMessage, taskStore)
        emit('task_progress', message)
        break
      case 'task_completed':
        handleTaskCompleted(message as TaskCompletedMessage, taskStore)
        emit('task_completed', message)
        break
      case 'violation_detected':
        handleViolationDetected(message as ViolationDetectedMessage)
        emit('violation_detected', message)
        break
      default:
        console.log('未知消息类型:', message.type)
        emit('unknown_message', message)
    }
    
    // 触发通用消息事件
    emit('message', message)
  }

  // 处理任务进度消息
  const handleTaskProgress = (message: TaskProgressMessage, taskStore: any) => {
    // 如果当前查看的是这个任务，更新进度
    if (taskStore.currentTask?.id === message.task_id) {
      taskStore.fetchTask(message.task_id)
    }
    
    // 刷新任务列表中的对应任务
    taskStore.fetchTasks()
    
    console.log(`📊 任务进度更新: ${message.task_id} - ${message.progress}%`)
  }

  // 处理任务完成消息
  const handleTaskCompleted = (message: TaskCompletedMessage, taskStore: any) => {
    console.log('🚀 处理任务完成消息:', message)
    
    // 刷新任务数据
    taskStore.fetchTasks()
    taskStore.fetchStats()
    
    // 显示基于后端真实数据的通知
    ElNotification({
      title: '任务完成',
      message: message.message, // 使用后端返回的真实消息
      type: message.status === 'completed' ? 'success' : 'error',
      duration: 5000,
      customClass: 'websocket-notification',
      onClick: () => {
        // 可以跳转到任务详情页面
        console.log('点击查看任务详情:', message.task_id)
      }
    })
    
    console.log(`✅ 任务完成: ${message.task_id} - ${message.status}`)
  }

  // 处理违规检测消息
  const handleViolationDetected = (message: ViolationDetectedMessage) => {
    console.log('⚠️ 处理违规检测消息:', message)
    
    // 显示基于后端真实数据的警告通知
    ElNotification({
      title: '发现违规内容',
      message: `域名: ${message.violation.domain}\n违规类型: ${message.violation.violation_type}\n风险等级: ${message.violation.risk_level}\n置信度: ${Math.round(message.violation.confidence_score)}%\n描述: ${message.violation.description}`,
      type: 'warning',
      duration: 8000,
      dangerouslyUseHTMLString: false,
      customClass: 'violation-notification',
      onClick: () => {
        // 可以跳转到违规详情或任务详情页面
        console.log('点击查看违规详情:', message.task_id, message.violation.domain)
      }
    })
    
    console.log(`⚠️ 发现违规: ${message.violation.domain} - ${message.violation.violation_type}`)
  }

  // 安排重连
  const scheduleReconnect = () => {
    // 检查是否启用自动重连
    if (!autoReconnectEnabled.value) {
      console.log('🔄 自动重连已禁用，不进行重连')
      return
    }
    
    // 检查重连次数是否超过限制
    if (reconnectAttempts.value >= maxReconnectAttempts.value) {
      console.error(`❌ 重连次数已达上限 (${maxReconnectAttempts.value})，停止重连`)
      status.value = WebSocketStatus.ERROR
      lastError.value = `重连失败，已尝试 ${maxReconnectAttempts.value} 次`
      isReconnecting.value = false
      return
    }
    
    // 防止重复调度
    if (isReconnecting.value) {
      console.log('🔄 已有重连在进行中，跳过')
      return
    }
    
    reconnectAttempts.value++
    isReconnecting.value = true
    
    const interval = getNextReconnectInterval()
    
    console.log(
      `🔄 安排第 ${reconnectAttempts.value} 次重连，` +
      `${interval / 1000}秒后尝试 (${reconnectAttempts.value}/${maxReconnectAttempts.value})`
    )
    
    reconnectTimer.value = window.setTimeout(async () => {
      try {
        isReconnecting.value = true
        console.log(`🔄 开始第 ${reconnectAttempts.value} 次重连尝试...`)
        
        await connect()
        
        // 如果连接成功，重置状态
        if (status.value === WebSocketStatus.CONNECTED) {
          console.log('✅ 重连成功')
          resetReconnectState()
        }
        
      } catch (error) {
        console.error(`❌ 第 ${reconnectAttempts.value} 次重连失败:`, error)
        lastError.value = `重连失败: ${error}`
        
        // 继续尝试下一次重连
        isReconnecting.value = false
        scheduleReconnect()
        
      } finally {
        reconnectTimer.value = null
      }
    }, interval)
  }

  // 断开连接
  const disconnect = () => {
    console.log('🔌 手动断开WebSocket连接')
    
    // 停止心跳
    stopHeartbeat()
    
    // 取消重连
    cancelReconnect()
    
    if (ws.value) {
      ws.value.close(1000, '用户主动断开') // 正常关闭
      ws.value = null
    }
    status.value = WebSocketStatus.DISCONNECTED
    reconnectAttempts.value = 0
    isReconnecting.value = false
  }
  
  // 启动心跳
  const startHeartbeat = () => {
    console.log('💖 启动WebSocket心跳机制')
    
    stopHeartbeat() // 先停止已有的心跳
    
    heartbeatInterval.value = window.setInterval(() => {
      if (ws.value && ws.value.readyState === WebSocket.OPEN) {
        const now = Date.now()
        
        // 检查是否有未响应的ping
        if (lastPingTime.value > 0 && lastPongTime.value < lastPingTime.value) {
          const timeSinceLastPing = now - lastPingTime.value
          if (timeSinceLastPing > pongTimeout.value) {
            missedPongs.value++
            console.warn(`⚠️ 未收到pong响应，未响应次数: ${missedPongs.value}/${maxMissedPongs.value}`)
            
            if (missedPongs.value >= maxMissedPongs.value) {
              console.error('❌ 连续多次未收到pong响应，视为连接已断开')
              lastError.value = '心跳超时'
              ws.value.close(1002, '心跳超时')
              return
            }
          }
        }
        
        // 发送ping
        sendPing()
      }
    }, pingInterval.value)
  }
  
  // 停止心跳
  const stopHeartbeat = () => {
    if (heartbeatInterval.value) {
      clearInterval(heartbeatInterval.value)
      heartbeatInterval.value = null
      console.log('💖 心跳机制已停止')
    }
  }
  
  // 发送ping
  const sendPing = () => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      const now = Date.now()
      pingCount.value++
      lastPingTime.value = now
      
      const pingMessage = {
        type: 'ping',
        timestamp: new Date().toISOString(),
        client_time: now,
        sequence: pingCount.value
      }
      
      ws.value.send(JSON.stringify(pingMessage))
      console.log(`🏓 发送ping (${pingCount.value})`)
    }
  }
  
  // 处理pong响应
  const handlePong = (message: any) => {
    const now = Date.now()
    lastPongTime.value = now
    missedPongs.value = 0 // 重置未响应计数
    
    const latency = now - (message.client_time || lastPingTime.value)
    console.log(`🏓 收到pong响应，延迟: ${latency}ms`)
  }

  // 取消重连
  const cancelReconnect = () => {
    if (reconnectTimer.value) {
      clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
      isReconnecting.value = false
      console.log('🔄 已取消重连')
    }
  }
  
  // 启用自动重连
  const enableAutoReconnect = () => {
    autoReconnectEnabled.value = true
    console.log('🔄 已启用自动重连')
  }
  
  // 禁用自动重连
  const disableAutoReconnect = () => {
    autoReconnectEnabled.value = false
    cancelReconnect()
    console.log('🔄 已禁用自动重连')
  }
  
  // 重置重连状态
  const resetReconnectState = () => {
    reconnectAttempts.value = 0
    isReconnecting.value = false
    cancelReconnect()
    // 重置重连间隔为初始值
    reconnectInterval.value = 5000
  }
  
  // 计算下次重连间隔（指数退避）
  const getNextReconnectInterval = () => {
    const baseInterval = 5000
    const currentInterval = Math.min(
      baseInterval * Math.pow(backoffMultiplier.value, reconnectAttempts.value),
      maxReconnectInterval.value
    )
    return currentInterval
  }

  // 发送消息
  const send = (message: any) => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket未连接，无法发送消息')
    }
  }

  // 清空消息历史
  const clearMessages = () => {
    messages.value = []
  }

  // 事件监听器
  const eventListeners = ref<Map<string, Function[]>>(new Map())

  // 注册事件监听器
  const on = (event: string, callback: Function) => {
    if (!eventListeners.value.has(event)) {
      eventListeners.value.set(event, [])
    }
    eventListeners.value.get(event)!.push(callback)
  }

  // 注销事件监听器
  const off = (event: string, callback?: Function) => {
    if (!eventListeners.value.has(event)) return
    
    if (callback) {
      const listeners = eventListeners.value.get(event)!
      const index = listeners.indexOf(callback)
      if (index > -1) {
        listeners.splice(index, 1)
      }
    } else {
      eventListeners.value.set(event, [])
    }
  }

  // 触发事件
  const emit = (event: string, data?: any) => {
    if (eventListeners.value.has(event)) {
      eventListeners.value.get(event)!.forEach(callback => {
        try {
          callback(data)
        } catch (error) {
          console.error(`事件监听器执行错误 (${event}):`, error)
        }
      })
    }
  }

  // 订阅任务状态更新
  const subscribeToTask = (taskId: string) => {
    if (!isConnected.value) {
      console.warn('WebSocket未连接，无法订阅任务')
      return
    }
    
    send({
      type: 'subscribe_task',
      task_id: taskId
    })
    
    console.log(`📡 订阅任务: ${taskId}`)
  }

  // 取消订阅任务状态更新
  const unsubscribeFromTask = (taskId: string) => {
    if (!isConnected.value) {
      console.warn('WebSocket未连接，无法取消订阅任务')
      return
    }
    
    send({
      type: 'unsubscribe_task',
      task_id: taskId
    })
    
    console.log(`📡 取消订阅任务: ${taskId}`)
  }

  return {
    // 状态
    status: computed(() => status.value),
    reconnectAttempts: computed(() => reconnectAttempts.value),
    messages: computed(() => messages.value),
    lastError: computed(() => lastError.value),
    connectedAt: computed(() => connectedAt.value),
    
    // 心跳状态
    pingCount: computed(() => pingCount.value),
    missedPongs: computed(() => missedPongs.value),
    lastPingTime: computed(() => lastPingTime.value),
    lastPongTime: computed(() => lastPongTime.value),
    
    // 重连状态
    isReconnecting: computed(() => isReconnecting.value),
    autoReconnectEnabled: computed(() => autoReconnectEnabled.value),
    maxReconnectAttempts: computed(() => maxReconnectAttempts.value),
    
    // 计算属性
    isConnected,
    isConnecting,
    connectionStatusText,
    connectionStatusType,
    
    // 连接管理方法
    connect,
    disconnect,
    
    // 心跳方法
    startHeartbeat,
    stopHeartbeat,
    sendPing,
    
    // 重连方法
    enableAutoReconnect,
    disableAutoReconnect,
    resetReconnectState,
    scheduleReconnect,
    
    // 消息方法
    send,
    clearMessages,
    
    // 任务订阅方法
    subscribeToTask,
    unsubscribeFromTask,
    
    // 事件方法
    on,
    off,
    emit
  }
})