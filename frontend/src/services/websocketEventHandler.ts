import { ElNotification, ElMessage } from 'element-plus'
import { useWebSocketStore } from '@/stores/websocket'
import { useTaskStore } from '@/stores/task'
import { useAuthStore } from '@/stores/auth'
import type { 
  WebSocketMessage, 
  ViolationRecord 
} from '@/types/api'

// 事件处理器类
export class WebSocketEventHandler {
  private wsStore: ReturnType<typeof useWebSocketStore>
  private taskStore: ReturnType<typeof useTaskStore>
  private authStore: ReturnType<typeof useAuthStore>
  private notificationHandlers: Map<string, Function[]> = new Map()

  constructor() {
    this.wsStore = useWebSocketStore()
    this.taskStore = useTaskStore()
    this.authStore = useAuthStore()
    this.setupEventListeners()
  }

  // 设置WebSocket事件监听器
  private setupEventListeners() {
    // 任务相关事件
    this.wsStore.on('task_created', this.handleTaskCreated.bind(this))
    this.wsStore.on('task_started', this.handleTaskStarted.bind(this))
    this.wsStore.on('task_progress', this.handleTaskProgress.bind(this))
    this.wsStore.on('task_completed', this.handleTaskCompleted.bind(this))
    this.wsStore.on('task_error', this.handleTaskError.bind(this))
    this.wsStore.on('task_warning', this.handleTaskWarning.bind(this))

    // 违规检测事件
    this.wsStore.on('violation_detected', this.handleViolationDetected.bind(this))

    // 系统状态事件
    this.wsStore.on('system_status_update', this.handleSystemStatusUpdate.bind(this))
    this.wsStore.on('performance_update', this.handlePerformanceUpdate.bind(this))

    // 管理员广播
    this.wsStore.on('admin_broadcast', this.handleAdminBroadcast.bind(this))

    // 用户连接状态
    this.wsStore.on('user_connected', this.handleUserConnected.bind(this))
    this.wsStore.on('user_disconnected', this.handleUserDisconnected.bind(this))

    // 连接状态事件
    this.wsStore.on('connection_established', this.handleConnectionEstablished.bind(this))
    this.wsStore.on('subscription_result', this.handleSubscriptionResult.bind(this))
  }

  // 任务创建事件
  private handleTaskCreated(data: any) {
    console.log('📝 任务创建:', data)
    
    this.notify('task_created', {
      type: 'success',
      title: '任务创建成功',
      message: `扫描任务 "${data.target_domain}" 已创建`,
      data
    })

    // 刷新任务列表
    this.taskStore.fetchTasks()
    this.taskStore.fetchStats()
  }

  // 任务开始事件
  private handleTaskStarted(data: any) {
    console.log('🚀 任务开始:', data)
    
    this.notify('task_started', {
      type: 'info',
      title: '任务开始执行',
      message: `任务 ${data.task_id} 开始扫描`,
      data
    })

    // 自动订阅任务进度
    this.wsStore.subscribeToTask(data.task_id)
  }

  // 任务进度事件
  private handleTaskProgress(data: any) {
    console.log('📊 任务进度:', data)
    
    // 发送进度更新事件给组件
    this.emit('task_progress_update', data)

    // 重要进度节点时显示通知
    if (data.progress % 25 === 0 && data.progress > 0) {
      this.notify('task_progress', {
        type: 'info',
        title: '任务进度更新',
        message: `${data.stage} - ${data.progress}%`,
        data,
        duration: 3000
      })
    }
  }

  // 任务完成事件
  private handleTaskCompleted(data: any) {
    console.log('✅ 任务完成:', data)
    
    const notificationType = data.status === 'completed' ? 'success' : 'error'
    const title = data.status === 'completed' ? '任务完成' : '任务失败'
    
    this.notify('task_completed', {
      type: notificationType,
      title,
      message: data.message || `任务 ${data.task_id} 执行完成`,
      data,
      duration: 8000,
      action: {
        text: '查看详情',
        handler: () => {
          // 跳转到任务详情页面
          window.location.href = `/tasks/${data.task_id}`
        }
      }
    })

    // 刷新相关数据
    this.taskStore.fetchTasks()
    this.taskStore.fetchStats()

    // 取消订阅已完成的任务
    this.wsStore.unsubscribeFromTask(data.task_id)

    // 播放完成声音
    this.playNotificationSound(data.status === 'completed')
  }

  // 任务错误事件
  private handleTaskError(data: any) {
    console.error('❌ 任务错误:', data)
    
    this.notify('task_error', {
      type: 'error',
      title: '任务执行错误',
      message: data.message || data.error,
      data,
      duration: 10000
    })

    // 刷新任务状态
    this.taskStore.fetchTasks()
  }

  // 任务警告事件
  private handleTaskWarning(data: any) {
    console.warn('⚠️ 任务警告:', data)
    
    this.notify('task_warning', {
      type: 'warning',
      title: '任务运行警告',
      message: data.message,
      data,
      duration: 8000
    })
  }

  // 违规检测事件
  private handleViolationDetected(data: any) {
    console.warn('🚨 发现违规:', data)
    
    const violation = data.violation
    const riskLevel = violation.risk_level
    const notificationType = riskLevel === 'critical' || riskLevel === 'high' ? 'error' : 'warning'
    
    this.notify('violation_detected', {
      type: notificationType,
      title: '发现违规内容',
      message: `${violation.domain}: ${violation.description}`,
      data,
      duration: 10000,
      action: {
        text: '查看详情',
        handler: () => {
          // 跳转到任务详情页面
          window.location.href = `/tasks/${data.task_id}`
        }
      }
    })

    // 严重违规时播放警告声音
    if (riskLevel === 'critical' || riskLevel === 'high') {
      this.playWarningSound()
    }
  }

  // 系统状态更新事件
  private handleSystemStatusUpdate(data: any) {
    console.log('🖥️ 系统状态更新:', data)
    
    this.emit('system_stats_update', data)

    // 系统状态异常时显示通知
    if (data.system_health?.status !== 'healthy') {
      this.notify('system_status', {
        type: 'warning',
        title: '系统状态警告',
        message: `系统状态: ${data.system_health.status}`,
        data,
        duration: 5000
      })
    }

    // 资源使用率过高时提醒
    if (data.cpu_usage > 90 || data.memory_usage > 90) {
      this.notify('high_resource_usage', {
        type: 'warning',
        title: '资源使用率过高',
        message: `CPU: ${data.cpu_usage}%, 内存: ${data.memory_usage}%`,
        data,
        duration: 5000
      })
    }
  }

  // 性能更新事件
  private handlePerformanceUpdate(data: any) {
    console.log('📈 性能更新:', data)
    this.emit('performance_update', data)
  }

  // 管理员广播事件
  private handleAdminBroadcast(data: any) {
    console.log('📢 管理员广播:', data)
    
    this.notify('admin_broadcast', {
      type: 'info',
      title: '系统公告',
      message: data.message,
      data,
      duration: 15000
    })

    // 重要公告时播放提示音
    this.playNotificationSound()
  }

  // 用户连接事件
  private handleUserConnected(data: any) {
    if (data.user_id !== this.authStore.user?.id) {
      console.log('👤 用户上线:', data)
      this.emit('user_stats_update', { online_users: data.online_users })
    }
  }

  // 用户断开事件
  private handleUserDisconnected(data: any) {
    if (data.user_id !== this.authStore.user?.id) {
      console.log('👤 用户下线:', data)
      this.emit('user_stats_update', { online_users: data.online_users })
    }
  }

  // 连接建立事件
  private handleConnectionEstablished(data: any) {
    console.log('🔗 连接建立:', data)
    
    ElMessage.success('实时连接已建立')
    
    this.notify('connection_established', {
      type: 'success',
      title: '实时连接已建立',
      message: '现在可以接收实时通知',
      data,
      duration: 3000
    })
  }

  // 订阅结果事件
  private handleSubscriptionResult(data: any) {
    console.log('📡 订阅结果:', data)
    
    if (!data.success) {
      ElMessage.error(`订阅任务失败: ${data.task_id}`)
    }
  }

  // 通用通知方法
  private notify(eventType: string, options: {
    type: 'success' | 'warning' | 'info' | 'error'
    title: string
    message: string
    data?: any
    duration?: number
    action?: {
      text: string
      handler: () => void
    }
  }) {
    // 触发自定义通知事件
    this.emit('notification', {
      eventType,
      ...options,
      timestamp: new Date().toISOString()
    })

    // 显示Element Plus通知
    ElNotification({
      type: options.type,
      title: options.title,
      message: options.message,
      duration: options.duration || 5000,
      onClick: options.action?.handler
    })
  }

  // 事件发射器
  private emit(eventType: string, data: any) {
    const handlers = this.notificationHandlers.get(eventType) || []
    handlers.forEach(handler => {
      try {
        handler(data)
      } catch (error) {
        console.error(`通知事件处理器执行失败 [${eventType}]:`, error)
      }
    })
  }

  // 注册通知事件监听器
  public onNotification(eventType: string, handler: Function) {
    if (!this.notificationHandlers.has(eventType)) {
      this.notificationHandlers.set(eventType, [])
    }
    this.notificationHandlers.get(eventType)!.push(handler)
  }

  // 移除通知事件监听器
  public offNotification(eventType: string, handler?: Function) {
    if (!this.notificationHandlers.has(eventType)) return
    
    if (handler) {
      const handlers = this.notificationHandlers.get(eventType)!
      const index = handlers.indexOf(handler)
      if (index !== -1) {
        handlers.splice(index, 1)
      }
    } else {
      this.notificationHandlers.delete(eventType)
    }
  }

  // 播放通知声音
  private playNotificationSound(success: boolean = true) {
    try {
      const audioFile = success ? '/sounds/success.mp3' : '/sounds/notification.mp3'
      const audio = new Audio(audioFile)
      audio.volume = 0.3
      audio.play().catch(() => {
        // 忽略音频播放失败
      })
    } catch (error) {
      // 忽略音频播放失败
    }
  }

  // 播放警告声音
  private playWarningSound() {
    try {
      const audio = new Audio('/sounds/warning.mp3')
      audio.volume = 0.5
      audio.play().catch(() => {
        // 忽略音频播放失败
      })
    } catch (error) {
      // 忽略音频播放失败
    }
  }

  // 清理资源
  public destroy() {
    this.notificationHandlers.clear()
    // 移除WebSocket事件监听器
    this.wsStore.off('task_created')
    this.wsStore.off('task_started')
    this.wsStore.off('task_progress')
    this.wsStore.off('task_completed')
    this.wsStore.off('task_error')
    this.wsStore.off('task_warning')
    this.wsStore.off('violation_detected')
    this.wsStore.off('system_status_update')
    this.wsStore.off('performance_update')
    this.wsStore.off('admin_broadcast')
    this.wsStore.off('user_connected')
    this.wsStore.off('user_disconnected')
    this.wsStore.off('connection_established')
    this.wsStore.off('subscription_result')
  }
}

// 创建全局实例
let eventHandler: WebSocketEventHandler | null = null

// 获取事件处理器实例
export const getWebSocketEventHandler = (): WebSocketEventHandler => {
  if (!eventHandler) {
    eventHandler = new WebSocketEventHandler()
  }
  return eventHandler
}

// 销毁事件处理器
export const destroyWebSocketEventHandler = () => {
  if (eventHandler) {
    eventHandler.destroy()
    eventHandler = null
  }
}