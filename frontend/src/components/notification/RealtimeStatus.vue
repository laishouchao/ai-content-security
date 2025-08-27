<template>
  <div class="realtime-status">
    <!-- WebSocket连接状态 -->
    <div class="status-item">
      <el-tooltip :content="connectionTooltip" placement="bottom">
        <div class="connection-indicator" :class="connectionClass">
          <el-icon :size="12">
            <component :is="connectionIcon" />
          </el-icon>
          <span class="status-text">{{ connectionText }}</span>
        </div>
      </el-tooltip>
    </div>

    <!-- 活跃任务数量 -->
    <div class="status-item" v-if="activeTasks > 0">
      <el-tooltip content="当前活跃任务数" placement="bottom">
        <div class="task-indicator">
          <el-icon :size="12">
            <Loading />
          </el-icon>
          <span class="status-text">{{ activeTasks }} 个任务</span>
        </div>
      </el-tooltip>
    </div>

    <!-- 系统状态 -->
    <div class="status-item" v-if="systemHealth">
      <el-tooltip :content="systemHealthTooltip" placement="bottom">
        <div class="health-indicator" :class="healthClass">
          <el-icon :size="12">
            <component :is="healthIcon" />
          </el-icon>
          <span class="status-text">{{ systemHealth.status }}</span>
        </div>
      </el-tooltip>
    </div>

    <!-- 最近通知 -->
    <div class="status-item" v-if="recentNotification">
      <el-tooltip :content="recentNotification.message" placement="bottom">
        <div class="notification-preview" @click="showNotifications">
          <el-icon :size="12">
            <Bell />
          </el-icon>
          <span class="status-text">{{ recentNotification.title }}</span>
        </div>
      </el-tooltip>
    </div>

    <!-- 性能指标（可选显示） -->
    <div class="status-item" v-if="showPerformance && performance">
      <el-tooltip :content="`CPU: ${performance.cpu}%, 内存: ${performance.memory}%`" placement="bottom">
        <div class="performance-indicator" :class="getPerformanceClass(performance.cpu)">
          <el-icon :size="12">
            <Monitor />
          </el-icon>
          <span class="status-text">{{ performance.cpu }}%</span>
        </div>
      </el-tooltip>
    </div>

    <!-- 当前用户在线状态 -->
    <div class="status-item">
      <el-tooltip :content="`在线用户: ${onlineUsers} 人`" placement="bottom">
        <div class="users-indicator">
          <el-icon :size="12">
            <User />
          </el-icon>
          <span class="status-text">{{ onlineUsers }}</span>
        </div>
      </el-tooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { 
  Connection, 
  Close, 
  Loading, 
  Warning, 
  CircleCheck, 
  CircleClose,
  Bell,
  Monitor,
  User
} from '@element-plus/icons-vue'
import { useWebSocketStore } from '@/stores/websocket'
import { useAuthStore } from '@/stores/auth'

// Props
interface Props {
  showPerformance?: boolean
  showSystemHealth?: boolean
  compact?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showPerformance: false,
  showSystemHealth: true,
  compact: false
})

// Emits
interface Emits {
  (e: 'notification-click'): void
}

const emit = defineEmits<Emits>()

const wsStore = useWebSocketStore()
const authStore = useAuthStore()

// 响应式数据
const activeTasks = ref(0)
const onlineUsers = ref(1)
const systemHealth = ref<any>(null)
const performance = ref<any>(null)
const recentNotification = ref<any>(null)

// 计算属性
const connectionClass = computed(() => {
  switch (wsStore.status) {
    case 'connected': return 'connected'
    case 'connecting': return 'connecting'
    case 'error': return 'error'
    default: return 'disconnected'
  }
})

const connectionIcon = computed(() => {
  switch (wsStore.status) {
    case 'connected': return Connection
    case 'connecting': return Loading
    default: return Close
  }
})

const connectionText = computed(() => {
  if (props.compact) {
    switch (wsStore.status) {
      case 'connected': return '在线'
      case 'connecting': return '连接中'
      case 'error': return '错误'
      default: return '离线'
    }
  }
  
  switch (wsStore.status) {
    case 'connected': return '实时连接'
    case 'connecting': return '正在连接'
    case 'error': return '连接错误'
    default: return '已断开'
  }
})

const connectionTooltip = computed(() => {
  const baseInfo = `WebSocket状态: ${connectionText.value}`
  
  if (wsStore.status === 'connected') {
    return `${baseInfo}\n连接时间: ${wsStore.connectedAt ? new Date(wsStore.connectedAt).toLocaleString() : '未知'}`
  } else if (wsStore.status === 'error') {
    return `${baseInfo}\n错误信息: ${wsStore.lastError || '未知错误'}`
  }
  
  return baseInfo
})

const healthClass = computed(() => {
  if (!systemHealth.value) return 'unknown'
  
  switch (systemHealth.value.status) {
    case 'healthy': return 'healthy'
    case 'warning': return 'warning'
    case 'critical': return 'critical'
    default: return 'unknown'
  }
})

const healthIcon = computed(() => {
  if (!systemHealth.value) return CircleClose
  
  switch (systemHealth.value.status) {
    case 'healthy': return CircleCheck
    case 'warning': return Warning
    case 'critical': return CircleClose
    default: return Warning
  }
})

const systemHealthTooltip = computed(() => {
  if (!systemHealth.value) return '系统状态未知'
  
  const status = systemHealth.value
  return `系统状态: ${status.status}\nCPU: ${status.cpu_usage || 'N/A'}%\n内存: ${status.memory_usage || 'N/A'}%\n磁盘: ${status.disk_usage || 'N/A'}%`
})

// 方法
const getPerformanceClass = (cpu: number) => {
  if (cpu > 80) return 'critical'
  if (cpu > 60) return 'warning'
  return 'normal'
}

const showNotifications = () => {
  emit('notification-click')
}

const updateStats = (data: any) => {
  if (data.active_tasks !== undefined) {
    activeTasks.value = data.active_tasks
  }
  
  if (data.online_users !== undefined) {
    onlineUsers.value = data.online_users
  }
  
  if (data.system_health) {
    systemHealth.value = data.system_health
  }
  
  if (data.performance) {
    performance.value = data.performance
  }
}

const addRecentNotification = (notification: any) => {
  recentNotification.value = {
    title: notification.title,
    message: notification.message,
    timestamp: notification.timestamp
  }
  
  // 5秒后清除显示
  setTimeout(() => {
    if (recentNotification.value?.timestamp === notification.timestamp) {
      recentNotification.value = null
    }
  }, 5000)
}

// WebSocket事件处理
const setupWebSocketListeners = () => {
  // 系统状态更新
  wsStore.on('system_stats_update', updateStats)
  
  // 任务状态更新
  wsStore.on('task_status_update', (data: any) => {
    // 可以根据需要更新活跃任务数
  })
  
  // 用户连接状态更新
  wsStore.on('user_stats_update', (data: any) => {
    if (data.online_users !== undefined) {
      onlineUsers.value = data.online_users
    }
  })
  
  // 性能监控更新
  wsStore.on('performance_update', (data: any) => {
    if (props.showPerformance) {
      performance.value = data
    }
  })
  
  // 新通知
  wsStore.on('task_completed', addRecentNotification)
  wsStore.on('violation_detected', addRecentNotification)
  wsStore.on('task_error', addRecentNotification)
}

const removeWebSocketListeners = () => {
  wsStore.off('system_stats_update')
  wsStore.off('task_status_update')
  wsStore.off('user_stats_update')
  wsStore.off('performance_update')
  wsStore.off('task_completed')
  wsStore.off('violation_detected')
  wsStore.off('task_error')
}

// 定期获取状态（作为WebSocket的补充）
let statusInterval: number

const startStatusPolling = () => {
  statusInterval = window.setInterval(() => {
    // 如果WebSocket未连接，通过HTTP API获取状态
    if (!wsStore.isConnected) {
      fetchSystemStatus()
    }
  }, 30000) // 每30秒检查一次
}

const fetchSystemStatus = async () => {
  try {
    // 可以调用API获取系统状态
    // const response = await http.get('/system/status')
    // updateStats(response.data)
  } catch (error) {
    console.error('获取系统状态失败:', error)
  }
}

// 生命周期
onMounted(() => {
  setupWebSocketListeners()
  startStatusPolling()
  
  // 初始设置在线用户数为1（当前用户）
  onlineUsers.value = 1
})

onUnmounted(() => {
  removeWebSocketListeners()
  if (statusInterval) {
    window.clearInterval(statusInterval)
  }
})
</script>

<style scoped>
.realtime-status {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
}

.status-item {
  display: flex;
  align-items: center;
  cursor: pointer;
  transition: opacity 0.3s;
}

.status-item:hover {
  opacity: 0.8;
}

.connection-indicator,
.task-indicator,
.health-indicator,
.notification-preview,
.performance-indicator,
.users-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.status-text {
  font-size: 11px;
  font-weight: 500;
}

/* 连接状态样式 */
.connection-indicator.connected {
  color: #67c23a;
  background-color: rgba(103, 194, 58, 0.1);
}

.connection-indicator.connecting {
  color: #e6a23c;
  background-color: rgba(230, 162, 60, 0.1);
}

.connection-indicator.error,
.connection-indicator.disconnected {
  color: #f56c6c;
  background-color: rgba(245, 108, 108, 0.1);
}

/* 任务指示器 */
.task-indicator {
  color: #409eff;
  background-color: rgba(64, 158, 255, 0.1);
}

/* 健康状态样式 */
.health-indicator.healthy {
  color: #67c23a;
  background-color: rgba(103, 194, 58, 0.1);
}

.health-indicator.warning {
  color: #e6a23c;
  background-color: rgba(230, 162, 60, 0.1);
}

.health-indicator.critical {
  color: #f56c6c;
  background-color: rgba(245, 108, 108, 0.1);
}

.health-indicator.unknown {
  color: #909399;
  background-color: rgba(144, 147, 153, 0.1);
}

/* 通知预览 */
.notification-preview {
  color: #909399;
  background-color: rgba(144, 147, 153, 0.1);
}

.notification-preview:hover {
  background-color: rgba(144, 147, 153, 0.2);
}

/* 性能指示器 */
.performance-indicator.normal {
  color: #67c23a;
  background-color: rgba(103, 194, 58, 0.1);
}

.performance-indicator.warning {
  color: #e6a23c;
  background-color: rgba(230, 162, 60, 0.1);
}

.performance-indicator.critical {
  color: #f56c6c;
  background-color: rgba(245, 108, 108, 0.1);
}

/* 用户指示器 */
.users-indicator {
  color: #606266;
  background-color: rgba(96, 98, 102, 0.1);
}

/* 动画效果 */
.connection-indicator.connecting .el-icon,
.task-indicator .el-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 紧凑模式 */
.realtime-status.compact {
  gap: 8px;
}

.compact .status-text {
  display: none;
}

@media (max-width: 768px) {
  .realtime-status {
    gap: 8px;
  }
  
  .status-text {
    display: none;
  }
}
</style>