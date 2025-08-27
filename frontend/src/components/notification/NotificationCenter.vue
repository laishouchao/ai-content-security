<template>
  <div class="notification-center">
    <!-- 通知触发按钮 -->
    <el-badge :value="unreadCount" :hidden="unreadCount === 0" class="notification-badge">
      <el-button 
        type="text" 
        @click="toggleDrawer"
        class="notification-trigger"
      >
        <el-icon :size="20">
          <Bell />
        </el-icon>
      </el-button>
    </el-badge>

    <!-- 通知抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      title="通知中心"
      :size="400"
      direction="rtl"
      :close-on-click-modal="false"
    >
      <template #header>
        <div class="drawer-header">
          <span>通知中心</span>
          <div class="header-actions">
            <el-button 
              type="text" 
              size="small" 
              @click="markAllAsRead"
              :disabled="unreadCount === 0"
            >
              全部已读
            </el-button>
            <el-button 
              type="text" 
              size="small" 
              @click="clearAll"
            >
              清空全部
            </el-button>
          </div>
        </div>
      </template>

      <!-- 通知筛选 -->
      <div class="notification-filter">
        <el-radio-group v-model="activeFilter" size="small">
          <el-radio-button label="all">全部</el-radio-button>
          <el-radio-button label="unread">未读</el-radio-button>
          <el-radio-button label="task">任务</el-radio-button>
          <el-radio-button label="system">系统</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 通知列表 -->
      <div class="notification-list">
        <div v-if="filteredNotifications.length === 0" class="empty-state">
          <el-empty description="暂无通知" :image-size="80" />
        </div>
        
        <div 
          v-for="notification in filteredNotifications" 
          :key="notification.id"
          class="notification-item"
          :class="{ 'unread': !notification.read }"
          @click="handleNotificationClick(notification)"
        >
          <div class="notification-icon">
            <el-icon 
              :color="getNotificationColor(notification.type)"
              :size="16"
            >
              <component :is="getNotificationIcon(notification.type)" />
            </el-icon>
          </div>
          
          <div class="notification-content">
            <div class="notification-title">
              {{ notification.title }}
            </div>
            <div class="notification-message">
              {{ notification.message }}
            </div>
            <div class="notification-time">
              {{ formatTime(notification.timestamp) }}
            </div>
          </div>

          <div class="notification-actions">
            <el-button 
              type="text" 
              size="small"
              @click.stop="markAsRead(notification)"
              v-if="!notification.read"
            >
              标记已读
            </el-button>
            <el-button 
              type="text" 
              size="small"
              @click.stop="removeNotification(notification)"
            >
              删除
            </el-button>
          </div>
        </div>
      </div>

      <!-- 通知设置 -->
      <div class="notification-settings">
        <el-divider>通知设置</el-divider>
        <div class="setting-item">
          <span>任务完成通知</span>
          <el-switch v-model="settings.taskCompletion" />
        </div>
        <div class="setting-item">
          <span>违规检测通知</span>
          <el-switch v-model="settings.violationDetection" />
        </div>
        <div class="setting-item">
          <span>系统状态通知</span>
          <el-switch v-model="settings.systemStatus" />
        </div>
        <div class="setting-item">
          <span>声音提醒</span>
          <el-switch v-model="settings.soundAlert" />
        </div>
        <div class="setting-item">
          <span>桌面通知</span>
          <el-switch v-model="settings.desktopNotification" @change="handleDesktopPermission" />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Bell, 
  CircleCheck, 
  Warning, 
  InfoFilled, 
  CircleClose,
  Document,
  Setting
} from '@element-plus/icons-vue'
import { useWebSocketStore } from '@/stores/websocket'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const router = useRouter()
const wsStore = useWebSocketStore()

// 响应式数据
const drawerVisible = ref(false)
const activeFilter = ref('all')
const notifications = ref<NotificationItem[]>([])

// 通知类型
interface NotificationItem {
  id: string
  type: 'success' | 'warning' | 'info' | 'error' | 'task' | 'system'
  title: string
  message: string
  timestamp: string
  read: boolean
  data?: any
  action?: {
    text: string
    handler: () => void
  }
}

// 通知设置
const settings = ref({
  taskCompletion: true,
  violationDetection: true,
  systemStatus: true,
  soundAlert: true,
  desktopNotification: false
})

// 计算属性
const unreadCount = computed(() => {
  return notifications.value.filter(n => !n.read).length
})

const filteredNotifications = computed(() => {
  let filtered = notifications.value

  switch (activeFilter.value) {
    case 'unread':
      filtered = filtered.filter(n => !n.read)
      break
    case 'task':
      filtered = filtered.filter(n => ['success', 'warning', 'task'].includes(n.type))
      break
    case 'system':
      filtered = filtered.filter(n => ['system', 'info', 'error'].includes(n.type))
      break
  }

  return filtered.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
})

// 方法
const toggleDrawer = () => {
  drawerVisible.value = !drawerVisible.value
}

const addNotification = (notification: Omit<NotificationItem, 'id' | 'read'>) => {
  const newNotification: NotificationItem = {
    ...notification,
    id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
    read: false
  }

  notifications.value.unshift(newNotification)

  // 限制通知数量
  if (notifications.value.length > 100) {
    notifications.value = notifications.value.slice(0, 100)
  }

  // 桌面通知
  if (settings.value.desktopNotification && Notification.permission === 'granted') {
    new Notification(notification.title, {
      body: notification.message,
      icon: '/favicon.ico'
    })
  }

  // 声音提醒
  if (settings.value.soundAlert) {
    playNotificationSound()
  }
}

const markAsRead = (notification: NotificationItem) => {
  notification.read = true
}

const markAllAsRead = () => {
  notifications.value.forEach(n => n.read = true)
}

const removeNotification = (notification: NotificationItem) => {
  const index = notifications.value.findIndex(n => n.id === notification.id)
  if (index !== -1) {
    notifications.value.splice(index, 1)
  }
}

const clearAll = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有通知吗？',
      '确认清空',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    notifications.value = []
  } catch (error) {
    // 用户取消
  }
}

const handleNotificationClick = (notification: NotificationItem) => {
  markAsRead(notification)
  
  if (notification.action) {
    notification.action.handler()
  } else if (notification.data?.task_id) {
    router.push(`/tasks/${notification.data.task_id}`)
    drawerVisible.value = false
  }
}

const getNotificationIcon = (type: string) => {
  switch (type) {
    case 'success': return CircleCheck
    case 'warning': return Warning
    case 'error': return CircleClose
    case 'task': return Document
    case 'system': return Setting
    default: return InfoFilled
  }
}

const getNotificationColor = (type: string) => {
  switch (type) {
    case 'success': return '#67c23a'
    case 'warning': return '#e6a23c'
    case 'error': return '#f56c6c'
    case 'task': return '#409eff'
    case 'system': return '#909399'
    default: return '#409eff'
  }
}

const formatTime = (timestamp: string) => {
  return dayjs(timestamp).fromNow()
}

const playNotificationSound = () => {
  try {
    const audio = new Audio('/notification.mp3')
    audio.volume = 0.3
    audio.play().catch(() => {
      // 忽略音频播放失败
    })
  } catch (error) {
    // 忽略音频播放失败
  }
}

const handleDesktopPermission = (enabled: string | number | boolean) => {
  if (enabled && Notification.permission === 'default') {
    Notification.requestPermission().then(permission => {
      if (permission !== 'granted') {
        settings.value.desktopNotification = false
        ElMessage.warning('桌面通知权限被拒绝')
      }
    })
  }
}

// WebSocket事件处理
const setupWebSocketListeners = () => {
  // 任务相关通知
  wsStore.on('task_created', (data: any) => {
    if (settings.value.taskCompletion) {
      addNotification({
        type: 'task',
        title: '任务创建成功',
        message: `扫描任务 "${data.target_domain}" 已创建`,
        timestamp: new Date().toISOString(),
        data
      })
    }
  })

  wsStore.on('task_completed', (data: any) => {
    if (settings.value.taskCompletion) {
      addNotification({
        type: data.status === 'completed' ? 'success' : 'error',
        title: '任务执行完成',
        message: data.message || `任务 ${data.task_id} 执行完成`,
        timestamp: new Date().toISOString(),
        data
      })
    }
  })

  wsStore.on('task_error', (data: any) => {
    addNotification({
      type: 'error',
      title: '任务执行错误',
      message: data.message || data.error,
      timestamp: new Date().toISOString(),
      data
    })
  })

  wsStore.on('violation_detected', (data: any) => {
    if (settings.value.violationDetection) {
      addNotification({
        type: 'warning',
        title: '检测到违规内容',
        message: `在 ${data.violation?.domain} 发现 ${data.violation?.risk_level} 风险违规`,
        timestamp: new Date().toISOString(),
        data
      })
    }
  })

  // 系统状态通知
  wsStore.on('system_status_update', (data: any) => {
    if (settings.value.systemStatus && data.alert) {
      addNotification({
        type: data.alert.type,
        title: '系统状态更新',
        message: data.alert.message,
        timestamp: new Date().toISOString(),
        data
      })
    }
  })

  // 管理员广播消息
  wsStore.on('admin_broadcast', (data: any) => {
    addNotification({
      type: 'info',
      title: '系统公告',
      message: data.message,
      timestamp: new Date().toISOString(),
      data
    })
  })
}

const removeWebSocketListeners = () => {
  wsStore.off('task_created')
  wsStore.off('task_completed')
  wsStore.off('task_error')
  wsStore.off('violation_detected')
  wsStore.off('system_status_update')
  wsStore.off('admin_broadcast')
}

// 暴露给父组件的方法
defineExpose({
  addNotification
})

// 生命周期
onMounted(() => {
  setupWebSocketListeners()
  
  // 从本地存储恢复设置
  const savedSettings = localStorage.getItem('notification-settings')
  if (savedSettings) {
    try {
      Object.assign(settings.value, JSON.parse(savedSettings))
    } catch (error) {
      console.warn('恢复通知设置失败:', error)
    }
  }

  // 监听设置变化并保存
  const saveSettings = () => {
    localStorage.setItem('notification-settings', JSON.stringify(settings.value))
  }
  
  // 使用watch监听设置变化
  watch(settings, saveSettings, { deep: true })
})

onUnmounted(() => {
  removeWebSocketListeners()
})
</script>

<style scoped>
.notification-center {
  position: relative;
}

.notification-badge {
  cursor: pointer;
}

.notification-trigger {
  border: none;
  background: none;
  padding: 8px;
  border-radius: 50%;
  transition: background-color 0.3s;
}

.notification-trigger:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.notification-filter {
  margin-bottom: 16px;
  padding: 0 20px;
}

.notification-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 20px;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: background-color 0.3s;
  border: 1px solid transparent;
}

.notification-item:hover {
  background-color: #f5f7fa;
}

.notification-item.unread {
  background-color: #f0f9ff;
  border-color: #409eff;
}

.notification-icon {
  margin-right: 12px;
  margin-top: 2px;
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-title {
  font-weight: 500;
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
}

.notification-message {
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.notification-time {
  font-size: 11px;
  color: #909399;
}

.notification-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-left: 8px;
}

.notification-settings {
  margin-top: 20px;
  padding: 0 20px;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  font-size: 14px;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
}

/* 自定义滚动条 */
.notification-list::-webkit-scrollbar {
  width: 4px;
}

.notification-list::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.notification-list::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 2px;
}

.notification-list::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>