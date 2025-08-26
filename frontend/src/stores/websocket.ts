import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
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
  const connect = () => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      console.log('WebSocket已连接，无需重复连接')
      return
    }

    try {
      status.value = WebSocketStatus.CONNECTING
      
      // 开发环境使用mock连接
      if (import.meta.env.DEV) {
        console.log('🔌 开发模式：模拟WebSocket连接')
        simulateConnection()
        return
      }
      
      // 生产环境真实连接
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/ws`
      ws.value = new WebSocket(wsUrl)
      
      setupEventHandlers()
    } catch (error) {
      console.error('WebSocket连接失败:', error)
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
    }

    ws.value.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        handleMessage(message)
      } catch (error) {
        console.error('WebSocket消息解析失败:', error)
      }
    }

    ws.value.onclose = (event) => {
      console.log('❌ WebSocket连接关闭:', event.code, event.reason)
      status.value = WebSocketStatus.DISCONNECTED
      
      // 自动重连
      if (reconnectAttempts.value < maxReconnectAttempts.value) {
        scheduleReconnect()
      }
    }

    ws.value.onerror = (error) => {
      console.error('❌ WebSocket错误:', error)
      status.value = WebSocketStatus.ERROR
    }
  }

  // 模拟连接（开发环境）
  const simulateConnection = () => {
    setTimeout(() => {
      status.value = WebSocketStatus.CONNECTED
      console.log('✅ 模拟WebSocket连接成功')
      
      // 模拟定期发送消息
      setInterval(() => {
        if (status.value === WebSocketStatus.CONNECTED) {
          simulateMessage()
        }
      }, 10000) // 每10秒发送一条模拟消息
    }, 1000)
  }

  // 模拟消息
  const simulateMessage = () => {
    const mockMessages = [
      {
        type: 'task_progress',
        task_id: '1',
        progress: Math.floor(Math.random() * 100),
        stage: '子域名发现',
        message: '正在发现子域名...',
        timestamp: new Date().toISOString()
      },
      {
        type: 'violation_detected',
        task_id: '2',
        violation: {
          domain: 'example.com',
          violation_type: '敏感信息泄露',
          risk_level: '高',
          confidence_score: 85,
          description: '检测到可能的API密钥泄露'
        },
        message: '发现新的违规内容',
        timestamp: new Date().toISOString()
      }
    ]
    
    const randomMessage = mockMessages[Math.floor(Math.random() * mockMessages.length)]
    handleMessage(randomMessage as WebSocketMessage)
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
        break
      case 'task_completed':
        handleTaskCompleted(message as TaskCompletedMessage, taskStore)
        break
      case 'violation_detected':
        handleViolationDetected(message as ViolationDetectedMessage)
        break
      default:
        console.log('未知消息类型:', message.type)
    }
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
    // 刷新任务数据
    taskStore.fetchTasks()
    taskStore.fetchStats()
    
    // 显示通知
    ElNotification({
      title: '任务完成',
      message: message.message,
      type: message.status === 'completed' ? 'success' : 'error',
      duration: 5000
    })
    
    console.log(`✅ 任务完成: ${message.task_id} - ${message.status}`)
  }

  // 处理违规检测消息
  const handleViolationDetected = (message: ViolationDetectedMessage) => {
    // 显示警告通知
    ElNotification({
      title: '发现违规内容',
      message: `${message.violation.domain}: ${message.violation.description}`,
      type: 'warning',
      duration: 8000
    })
    
    console.log(`⚠️ 发现违规: ${message.violation.domain}`)
  }

  // 安排重连
  const scheduleReconnect = () => {
    reconnectAttempts.value++
    
    console.log(`🔄 准备重连 (${reconnectAttempts.value}/${maxReconnectAttempts.value})`)
    
    setTimeout(() => {
      connect()
    }, reconnectInterval.value)
  }

  // 断开连接
  const disconnect = () => {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    status.value = WebSocketStatus.DISCONNECTED
    reconnectAttempts.value = 0
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

  return {
    // 状态
    status: computed(() => status.value),
    reconnectAttempts: computed(() => reconnectAttempts.value),
    messages: computed(() => messages.value),
    
    // 计算属性
    isConnected,
    isConnecting,
    connectionStatusText,
    connectionStatusType,
    
    // 方法
    connect,
    disconnect,
    send,
    clearMessages
  }
})