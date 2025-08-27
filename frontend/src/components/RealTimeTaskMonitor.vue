<template>
  <div class="real-time-monitor">
    <el-card>
      <template #header>
        <div class="monitor-header">
          <span>实时任务监控</span>
          <div class="header-actions">
            <el-tag :type="connectionStatus === 'connected' ? 'success' : 'danger'" size="small">
              {{ connectionStatus === 'connected' ? '已连接' : '未连接' }}
            </el-tag>
            <el-button
              size="small"
              @click="refreshTasks"
              :loading="loading"
              style="margin-left: 10px;"
            >
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- 任务列表 -->
      <div class="task-monitor-list">
        <div v-if="runningTasks.length === 0 && !loading" class="empty-state">
          <el-empty description="暂无运行中的任务" :image-size="80" />
        </div>

        <div
          v-for="task in runningTasks"
          :key="task.id"
          class="task-monitor-item"
        >
          <div class="task-header">
            <div class="task-info">
              <span class="task-domain">{{ task.target_domain }}</span>
              <el-tag :type="getStatusType(task.status)" size="small">
                {{ getStatusText(task.status) }}
              </el-tag>
            </div>
            <div class="task-actions">
              <el-button
                type="text"
                size="small"
                @click="viewTaskDetail(task)"
              >
                查看详情
              </el-button>
              <el-button
                type="text"
                size="small"
                @click="stopTask(task)"
                v-if="task.status === 'running'"
              >
                停止任务
              </el-button>
            </div>
          </div>

          <!-- 进度条 -->
          <div class="task-progress">
            <div class="progress-info">
              <span class="progress-text">
                {{ task.current_stage || '准备中' }}
              </span>
              <span class="progress-percentage">
                {{ Math.round(task.progress || 0) }}%
              </span>
            </div>
            <el-progress
              :percentage="task.progress || 0"
              :color="getProgressColor(task.progress || 0)"
              :show-text="false"
            />
          </div>

          <!-- 详细状态 -->
          <div class="task-details">
            <div class="detail-row">
              <span class="detail-label">子域名发现:</span>
              <span class="detail-value">
                {{ task.subdomains_found || 0 }} 个
              </span>
            </div>
            <div class="detail-row">
              <span class="detail-label">页面爬取:</span>
              <span class="detail-value">
                {{ task.pages_crawled || 0 }} / {{ task.total_pages || 0 }}
              </span>
            </div>
            <div class="detail-row">
              <span class="detail-label">违规检测:</span>
              <span class="detail-value">
                {{ task.violations_found || 0 }} 个
              </span>
            </div>
            <div class="detail-row">
              <span class="detail-label">运行时间:</span>
              <span class="detail-value">
                {{ formatDuration(task.start_time) }}
              </span>
            </div>
          </div>

          <!-- 实时日志 -->
          <div class="task-logs" v-if="showLogs[task.id]">
            <div class="logs-header">
              <span>实时日志</span>
              <el-button
                type="text"
                size="small"
                @click="clearLogs(task.id)"
              >
                清空
              </el-button>
            </div>
            <div class="logs-content">
              <div
                v-for="(log, index) in taskLogs[task.id] || []"
                :key="index"
                class="log-item"
                :class="'log-' + log.level"
              >
                <span class="log-time">{{ formatLogTime(log.timestamp) }}</span>
                <span class="log-level">{{ log.level.toUpperCase() }}</span>
                <span class="log-message">{{ log.message }}</span>
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="task-footer">
            <el-button
              type="text"
              size="small"
              @click="toggleLogs(task.id)"
            >
              {{ showLogs[task.id] ? '隐藏日志' : '显示日志' }}
            </el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useTaskStore } from '@/stores/task'
import { useWebSocketStore } from '@/stores/websocket'
import { useRouter } from 'vue-router'
import { TaskStatus } from '@/types/api'
import dayjs from 'dayjs'
import duration from 'dayjs/plugin/duration'

dayjs.extend(duration)

const router = useRouter()
const taskStore = useTaskStore()
const wsStore = useWebSocketStore()

// 响应式数据
const loading = ref(false)
const runningTasks = ref<any[]>([])
const taskLogs = reactive<Record<string, any[]>>({})
const showLogs = reactive<Record<string, boolean>>({})

// 连接状态
const connectionStatus = computed(() => wsStore.isConnected ? 'connected' : 'disconnected')

// 方法
const refreshTasks = async () => {
  try {
    loading.value = true
    await taskStore.fetchTasks({
      status: TaskStatus.RUNNING,
      limit: 50
    })
    
    runningTasks.value = taskStore.tasks.filter(task => 
      ['running', 'pending'].includes(task.status)
    )
  } catch (error) {
    console.error('刷新任务失败:', error)
    ElMessage.error('刷新任务失败')
  } finally {
    loading.value = false
  }
}

const getStatusType = (status: string) => {
  switch (status) {
    case 'running':
      return 'warning'
    case 'pending':
      return 'info'
    case 'completed':
      return 'success'
    case 'failed':
      return 'danger'
    default:
      return 'info'
  }
}

const getStatusText = (status: string) => {
  switch (status) {
    case 'running':
      return '运行中'
    case 'pending':
      return '等待中'
    case 'completed':
      return '已完成'
    case 'failed':
      return '失败'
    default:
      return status
  }
}

const getProgressColor = (progress: number) => {
  if (progress < 30) return '#f56c6c'
  if (progress < 70) return '#e6a23c'
  return '#67c23a'
}

const formatDuration = (startTime: string) => {
  if (!startTime) return '0秒'
  
  const start = dayjs(startTime)
  const now = dayjs()
  const diff = now.diff(start)
  const dur = dayjs.duration(diff)
  
  const hours = Math.floor(dur.asHours())
  const minutes = dur.minutes()
  const seconds = dur.seconds()
  
  if (hours > 0) {
    return `${hours}时${minutes}分${seconds}秒`
  } else if (minutes > 0) {
    return `${minutes}分${seconds}秒`
  } else {
    return `${seconds}秒`
  }
}

const formatLogTime = (timestamp: string) => {
  return dayjs(timestamp).format('HH:mm:ss')
}

const viewTaskDetail = (task: any) => {
  router.push(`/tasks/${task.id}`)
}

const stopTask = async (task: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要停止任务"${task.target_domain}"吗？`,
      '确认停止',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await taskStore.stopTask(task.id)
    ElMessage.success('任务已停止')
    await refreshTasks()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('停止任务失败:', error)
      ElMessage.error('停止任务失败')
    }
  }
}

const toggleLogs = (taskId: string) => {
  showLogs[taskId] = !showLogs[taskId]
  
  // 如果是第一次显示日志，初始化日志数组
  if (showLogs[taskId] && !taskLogs[taskId]) {
    taskLogs[taskId] = []
  }
}

const clearLogs = (taskId: string) => {
  taskLogs[taskId] = []
}

// WebSocket 事件处理
const setupWebSocketListeners = () => {
  // 任务状态更新
  wsStore.on('task_status_update', (data: any) => {
    const taskIndex = runningTasks.value.findIndex(task => task.id === data.task_id)
    if (taskIndex !== -1) {
      runningTasks.value[taskIndex] = { ...runningTasks.value[taskIndex], ...data }
    }
  })

  // 任务进度更新
  wsStore.on('task_progress_update', (data: any) => {
    const taskIndex = runningTasks.value.findIndex(task => task.id === data.task_id)
    if (taskIndex !== -1) {
      Object.assign(runningTasks.value[taskIndex], {
        progress: data.progress,
        current_stage: data.stage,
        subdomains_found: data.subdomains_found,
        pages_crawled: data.pages_crawled,
        total_pages: data.total_pages,
        violations_found: data.violations_found
      })
    }
  })

  // 任务日志更新
  wsStore.on('task_log', (data: any) => {
    if (showLogs[data.task_id]) {
      if (!taskLogs[data.task_id]) {
        taskLogs[data.task_id] = []
      }
      
      taskLogs[data.task_id].push({
        timestamp: data.timestamp,
        level: data.level,
        message: data.message
      })
      
      // 限制日志数量，避免内存溢出
      if (taskLogs[data.task_id].length > 100) {
        taskLogs[data.task_id] = taskLogs[data.task_id].slice(-100)
      }
    }
  })

  // 新任务开始
  wsStore.on('task_started', (data: any) => {
    const existingTaskIndex = runningTasks.value.findIndex(task => task.id === data.task_id)
    if (existingTaskIndex === -1) {
      runningTasks.value.unshift(data)
    }
  })

  // 任务完成
  wsStore.on('task_completed', (data: any) => {
    const taskIndex = runningTasks.value.findIndex(task => task.id === data.task_id)
    if (taskIndex !== -1) {
      // 延迟移除，让用户看到完成状态
      setTimeout(() => {
        runningTasks.value.splice(taskIndex, 1)
        // 清理日志
        delete taskLogs[data.task_id]
        delete showLogs[data.task_id]
      }, 3000)
    }
  })
}

const removeWebSocketListeners = () => {
  wsStore.off('task_status_update')
  wsStore.off('task_progress_update')
  wsStore.off('task_log')
  wsStore.off('task_started')
  wsStore.off('task_completed')
}

// 生命周期
onMounted(async () => {
  await refreshTasks()
  
  // 确保WebSocket连接
  if (!wsStore.isConnected) {
    try {
      await wsStore.connect()
    } catch (error) {
      console.error('WebSocket连接失败:', error)
      ElMessage.warning('实时监控连接失败，只能查看静态数据')
    }
  }
  
  setupWebSocketListeners()
  
  // 定时刷新任务列表（作为WebSocket的备用）
  const refreshInterval = setInterval(() => {
    if (!wsStore.isConnected) {
      refreshTasks()
    }
  }, 10000) // 每10秒刷新一次
  
  // 组件卸载时清理
  onUnmounted(() => {
    clearInterval(refreshInterval)
  })
})

onUnmounted(() => {
  removeWebSocketListeners()
})
</script>

<style scoped>
.real-time-monitor {
  height: 100%;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}

.task-monitor-list {
  max-height: 600px;
  overflow-y: auto;
}

.task-monitor-item {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  background-color: #fff;
  transition: box-shadow 0.3s;
}

.task-monitor-item:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.task-domain {
  font-weight: 500;
  font-size: 16px;
  color: #303133;
}

.task-progress {
  margin-bottom: 12px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.progress-text {
  font-size: 14px;
  color: #606266;
}

.progress-percentage {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.task-details {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-bottom: 12px;
  padding: 12px;
  background-color: #f8f9fa;
  border-radius: 6px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-label {
  font-size: 13px;
  color: #909399;
}

.detail-value {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.task-logs {
  margin-bottom: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  overflow: hidden;
}

.logs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-size: 14px;
  font-weight: 500;
}

.logs-content {
  max-height: 200px;
  overflow-y: auto;
  background-color: #2d3748;
  color: #e2e8f0;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.log-item {
  padding: 4px 12px;
  border-bottom: 1px solid #4a5568;
  display: flex;
  gap: 8px;
}

.log-item:last-child {
  border-bottom: none;
}

.log-time {
  color: #a0aec0;
  min-width: 60px;
}

.log-level {
  min-width: 50px;
  font-weight: bold;
}

.log-info .log-level {
  color: #63b3ed;
}

.log-warn .log-level {
  color: #f6e05e;
}

.log-error .log-level {
  color: #fc8181;
}

.log-success .log-level {
  color: #68d391;
}

.log-message {
  flex: 1;
  word-break: break-all;
}

.task-footer {
  text-align: center;
}

.empty-state {
  padding: 60px 0;
  text-align: center;
}
</style>