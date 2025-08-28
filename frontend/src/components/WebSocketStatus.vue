<template>
  <div class="websocket-status">
    <!-- 连接状态指示器 -->
    <el-badge 
      :type="statusBadgeType" 
      :value="statusText"
      class="status-badge"
    >
      <el-icon :class="statusIconClass" :size="16">
        <component :is="statusIcon" />
      </el-icon>
    </el-badge>

    <!-- 详细信息弹窗触发器 -->
    <el-button 
      v-if="showDetails"
      text 
      size="small" 
      @click="showDetailsDialog = true"
      class="details-btn"
    >
      详情
    </el-button>

    <!-- 重连按钮 -->
    <el-button 
      v-if="showReconnect && canReconnect"
      type="primary" 
      size="small" 
      @click="handleReconnect"
      :loading="wsStore.isReconnecting"
      class="reconnect-btn"
    >
      {{ wsStore.isReconnecting ? '重连中' : '重连' }}
    </el-button>

    <!-- 详细状态对话框 -->
    <el-dialog
      v-model="showDetailsDialog"
      title="WebSocket连接状态"
      width="600px"
      :show-close="true"
    >
      <div class="status-details">
        <!-- 基本连接信息 -->
        <el-descriptions :column="2" border>
          <el-descriptions-item label="连接状态">
            <el-tag :type="statusTagType">{{ statusText }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="连接时间">
            {{ connectedTime }}
          </el-descriptions-item>
          <el-descriptions-item label="重连次数">
            {{ wsStore.reconnectAttempts }} / {{ wsStore.maxReconnectAttempts }}
          </el-descriptions-item>
          <el-descriptions-item label="自动重连">
            <el-switch 
              v-model="autoReconnectEnabled" 
              @change="handleAutoReconnectChange"
            />
          </el-descriptions-item>
        </el-descriptions>

        <!-- 心跳信息 -->
        <el-divider content-position="left">心跳信息</el-divider>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="Ping次数">
            {{ wsStore.pingCount }}
          </el-descriptions-item>
          <el-descriptions-item label="未响应次数">
            {{ wsStore.missedPongs }}
          </el-descriptions-item>
          <el-descriptions-item label="最后Ping">
            {{ lastPingTime }}
          </el-descriptions-item>
          <el-descriptions-item label="最后Pong">
            {{ lastPongTime }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 错误信息 -->
        <div v-if="wsStore.lastError" class="error-section">
          <el-divider content-position="left">错误信息</el-divider>
          <el-alert
            :title="wsStore.lastError"
            type="error"
            :closable="false"
            show-icon
          />
        </div>

        <!-- 操作按钮 -->
        <div class="action-buttons">
          <el-button 
            v-if="canReconnect"
            type="primary" 
            @click="handleReconnect"
            :loading="wsStore.isReconnecting"
          >
            {{ wsStore.isReconnecting ? '重连中...' : '立即重连' }}
          </el-button>
          
          <el-button 
            v-if="wsStore.isConnected"
            type="warning" 
            @click="handleDisconnect"
          >
            断开连接
          </el-button>

          <el-button 
            v-if="wsStore.isConnected"
            type="info" 
            @click="handlePing"
          >
            发送Ping
          </el-button>

          <el-button 
            type="default" 
            @click="handleResetState"
          >
            重置状态
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useWebSocketStore } from '@/stores/websocket'
import { 
  CircleCheck, 
  Loading, 
  CircleClose, 
  Warning 
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'

// Props
interface Props {
  showDetails?: boolean
  showReconnect?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showDetails: true,
  showReconnect: true
})

// Store
const wsStore = useWebSocketStore()

// 响应式状态
const showDetailsDialog = ref(false)
const autoReconnectEnabled = ref(wsStore.autoReconnectEnabled)

// 计算属性
const statusText = computed(() => wsStore.connectionStatusText)
const statusBadgeType = computed(() => wsStore.connectionStatusType as any)
const statusTagType = computed(() => wsStore.connectionStatusType as any)

const statusIcon = computed(() => {
  switch (wsStore.status) {
    case 'connected':
      return CircleCheck
    case 'connecting':
      return Loading
    case 'error':
      return CircleClose
    default:
      return Warning
  }
})

const statusIconClass = computed(() => ({
  'status-icon': true,
  'connected': wsStore.status === 'connected',
  'connecting': wsStore.status === 'connecting',
  'error': wsStore.status === 'error',
  'disconnected': wsStore.status === 'disconnected'
}))

const canReconnect = computed(() => 
  wsStore.status !== 'connected' && 
  wsStore.status !== 'connecting' &&
  !wsStore.isReconnecting
)

const connectedTime = computed(() => {
  if (!wsStore.connectedAt) return '未连接'
  return dayjs(wsStore.connectedAt).format('YYYY-MM-DD HH:mm:ss')
})

const lastPingTime = computed(() => {
  if (!wsStore.lastPingTime) return '无'
  return dayjs(wsStore.lastPingTime).format('HH:mm:ss')
})

const lastPongTime = computed(() => {
  if (!wsStore.lastPongTime) return '无'
  return dayjs(wsStore.lastPongTime).format('HH:mm:ss')
})

// 事件处理
const handleReconnect = async () => {
  try {
    await wsStore.connect()
    ElMessage.success('重连成功')
  } catch (error) {
    ElMessage.error(`重连失败: ${error}`)
  }
}

const handleDisconnect = () => {
  wsStore.disconnect()
  ElMessage.info('已断开连接')
}

const handlePing = () => {
  if (wsStore.isConnected) {
    wsStore.sendPing()
    ElMessage.success('已发送Ping')
  } else {
    ElMessage.warning('连接未建立，无法发送Ping')
  }
}

const handleResetState = () => {
  wsStore.resetReconnectState()
  ElMessage.success('状态已重置')
}

const handleAutoReconnectChange = (val: string | number | boolean) => {
  const enabled = Boolean(val)
  if (enabled) {
    wsStore.enableAutoReconnect()
    ElMessage.success('已启用自动重连')
  } else {
    wsStore.disableAutoReconnect()
    ElMessage.info('已禁用自动重连')
  }
}
</script>

<style scoped>
.websocket-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-badge :deep(.el-badge__content) {
  font-size: 10px;
  padding: 0 4px;
  min-width: auto;
}

.status-icon {
  transition: all 0.3s ease;
}

.status-icon.connected {
  color: #67c23a;
}

.status-icon.connecting {
  color: #e6a23c;
  animation: spin 1s linear infinite;
}

.status-icon.error {
  color: #f56c6c;
}

.status-icon.disconnected {
  color: #909399;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.details-btn,
.reconnect-btn {
  font-size: 12px;
  padding: 4px 8px;
  height: auto;
}

.status-details {
  .el-descriptions {
    margin-bottom: 16px;
  }
  
  .error-section {
    margin: 16px 0;
  }
  
  .action-buttons {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #ebeef5;
  }
}
</style>