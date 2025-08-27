<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #409eff;">
              <el-icon><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ dashboardStats.totalTasks || 0 }}</div>
              <div class="stat-label">总任务数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #67c23a;">
              <el-icon><Check /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ dashboardStats.completedTasks || 0 }}</div>
              <div class="stat-label">已完成</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #e6a23c;">
              <el-icon><Clock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ dashboardStats.runningTasks || 0 }}</div>
              <div class="stat-label">运行中</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #f56c6c;">
              <el-icon><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ dashboardStats.totalViolations || 0 }}</div>
              <div class="stat-label">发现违规</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="charts-row">
      <el-col :xs="24" :lg="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>任务趋势</span>
            </div>
          </template>
          <div class="chart-container" style="height: 300px;">
            <v-chart 
              v-if="taskTrendOptions"
              class="chart" 
              :option="taskTrendOptions" 
              autoresize
            />
            <div v-else class="chart-placeholder">
              <el-icon><TrendCharts /></el-icon>
              <p>暂无数据</p>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :lg="8">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>违规类型分布</span>
            </div>
          </template>
          <div class="chart-container" style="height: 300px;">
            <v-chart 
              v-if="violationPieOptions"
              class="chart" 
              :option="violationPieOptions" 
              autoresize
            />
            <div v-else class="chart-placeholder">
              <el-icon><PieChartIcon /></el-icon>
              <p>暂无数据</p>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近任务和系统状态 -->
    <el-row :gutter="20" class="bottom-row">
      <el-col :xs="24" :lg="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>最近任务</span>
              <el-button type="text" @click="$router.push('/tasks')">
                查看全部
              </el-button>
            </div>
          </template>
          <div class="task-list" v-loading="loading">
            <div 
              v-for="task in dashboardStats.recentTasks" 
              :key="task.id"
              class="task-item"
              @click="goToTaskDetail(task.id)"
            >
              <div class="task-info">
                <div class="task-domain">{{ task.target_domain }}</div>
                <div class="task-time">{{ formatTime(task.created_at) }}</div>
              </div>
              <div class="task-status">
                <el-tag 
                  :type="getStatusType(task.status)"
                  size="small"
                >
                  {{ getStatusText(task.status) }}
                </el-tag>
              </div>
            </div>
            
            <div v-if="!dashboardStats.recentTasks?.length && !loading" class="empty-state">
              <el-empty description="暂无任务" :image-size="80" />
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :lg="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统状态</span>
            </div>
          </template>
          <div class="status-list">
            <div class="status-item">
              <span class="status-label">API服务</span>
              <el-tag :type="dashboardStats.systemStatus?.api_status === 'healthy' ? 'success' : 'danger'" size="small">
                {{ dashboardStats.systemStatus?.api_status === 'healthy' ? '正常' : '异常' }}
              </el-tag>
            </div>
            <div class="status-item">
              <span class="status-label">数据库</span>
              <el-tag :type="dashboardStats.systemStatus?.database_status === 'connected' ? 'success' : 'danger'" size="small">
                {{ dashboardStats.systemStatus?.database_status === 'connected' ? '正常' : '异常' }}
              </el-tag>
            </div>
            <div class="status-item">
              <span class="status-label">队列服务</span>
              <el-tag :type="dashboardStats.systemStatus?.queue_status === 'normal' ? 'success' : 'warning'" size="small">
                {{ dashboardStats.systemStatus?.queue_status === 'normal' ? '正常' : '异常' }}
              </el-tag>
            </div>
            <div class="status-item">
              <span class="status-label">运行任务</span>
              <el-tag :type="dashboardStats.systemStatus?.running_tasks > 0 ? 'warning' : 'info'" size="small">
                {{ dashboardStats.systemStatus?.running_tasks || 0 }} 个
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import { useWebSocketStore } from '@/stores/websocket'
import {
  Document,
  Check,
  Clock,
  Warning,
  TrendCharts,
  PieChart as PieChartIcon
} from '@element-plus/icons-vue'
import dayjs from 'dayjs'

// 注册 ECharts 组件
use([
  CanvasRenderer,
  LineChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const router = useRouter()
const taskStore = useTaskStore()
const wsStore = useWebSocketStore()

// 状态管理
const loading = ref(false)
const dashboardStats = ref<any>({})

// 图表配置
const taskTrendOptions = computed(() => {
  if (!dashboardStats.value.task_trends?.length) return null
  
  const dates = dashboardStats.value.task_trends.map((item: any) => 
    dayjs(item.date).format('MM-DD')
  )
  const totalData = dashboardStats.value.task_trends.map((item: any) => item.total)
  const completedData = dashboardStats.value.task_trends.map((item: any) => item.completed)
  const violationsData = dashboardStats.value.task_trends.map((item: any) => item.violations)
  
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: ['总任务', '完成任务', '违规数']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates
    },
    yAxis: [
      {
        type: 'value',
        name: '任务数',
        position: 'left'
      },
      {
        type: 'value',
        name: '违规数',
        position: 'right'
      }
    ],
    series: [
      {
        name: '总任务',
        type: 'line',
        data: totalData,
        itemStyle: {
          color: '#409eff'
        }
      },
      {
        name: '完成任务',
        type: 'line',
        data: completedData,
        itemStyle: {
          color: '#67c23a'
        }
      },
      {
        name: '违规数',
        type: 'line',
        yAxisIndex: 1,
        data: violationsData,
        itemStyle: {
          color: '#f56c6c'
        }
      }
    ]
  }
})

const violationPieOptions = computed(() => {
  if (!dashboardStats.value.violation_distribution?.length) return null
  
  const data = dashboardStats.value.violation_distribution.map((item: any) => ({
    value: item.count,
    name: item.name || item.type
  }))
  
  return {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        name: '违规类型',
        type: 'pie',
        radius: '50%',
        data: data,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }
})

// 方法
const loadDashboardData = async () => {
  try {
    loading.value = true
    await taskStore.fetchStats()
    dashboardStats.value = taskStore.stats
  } catch (error) {
    console.error('加载仪表板数据失败:', error)
    ElMessage.error('加载仪表板数据失败')
  } finally {
    loading.value = false
  }
}

const getStatusType = (status: string) => {
  switch (status) {
    case 'completed':
      return 'success'
    case 'running':
      return 'warning'
    case 'failed':
      return 'danger'
    case 'pending':
      return 'info'
    case 'cancelled':
      return 'info'
    default:
      return 'info'
  }
}

const getStatusText = (status: string) => {
  switch (status) {
    case 'completed':
      return '已完成'
    case 'running':
      return '运行中'
    case 'failed':
      return '失败'
    case 'pending':
      return '等待中'
    case 'cancelled':
      return '已取消'
    default:
      return status
  }
}

const formatTime = (timeString: string) => {
  if (!timeString) return ''
  return dayjs(timeString).format('YYYY-MM-DD HH:mm')
}

const goToTaskDetail = (taskId: string | number) => {
  router.push(`/tasks/${taskId}`)
}

// WebSocket实时连接
const connectWebSocket = () => {
  if (wsStore.isConnected) {
    return
  }
  
  wsStore.connect().then(() => {
    // 监听任务状态更新
    wsStore.on('task_status_update', (data: any) => {
      console.log('任务状态更新:', data)
      // 刷新统计数据
      loadDashboardData()
    })
    
    // 监听系统状态更新
    wsStore.on('system_status_update', (data: any) => {
      console.log('系统状态更新:', data)
      if (dashboardStats.value.systemStatus) {
        Object.assign(dashboardStats.value.systemStatus, data)
      }
    })
    
    // 监听扫描进度更新
    wsStore.on('scan_progress', (data: any) => {
      console.log('扫描进度更新:', data)
      // 更新对应任务的进度
      updateTaskProgress(data)
    })
  }).catch(error => {
    console.error('WebSocket连接失败:', error)
  })
}

const updateTaskProgress = (progressData: any) => {
  if (dashboardStats.value.recentTasks) {
    const task = dashboardStats.value.recentTasks.find(t => t.id === progressData.task_id)
    if (task) {
      task.progress = progressData.progress
      task.status = progressData.status
    }
  }
}

// 定时刷新数据
const startAutoRefresh = () => {
  // 每30秒刷新一次统计数据
  setInterval(() => {
    if (!loading.value) {
      loadDashboardData()
    }
  }, 30000)
}

// 生命周期
onMounted(() => {
  loadDashboardData()
  connectWebSocket()
  startAutoRefresh()
  
  // 设置定时刷新（每5分钟）
  const refreshInterval = setInterval(loadDashboardData, 5 * 60 * 1000)
  
  // 组件卸载时清理定时器
  return () => {
    clearInterval(refreshInterval)
  }
})

// 组件卸载时清理WebSocket监听器
onUnmounted(() => {
  wsStore.off('task_status_update')
  wsStore.off('system_status_update')
  wsStore.off('scan_progress')
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  height: 120px;
}

.stat-content {
  display: flex;
  align-items: center;
  height: 100%;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
  color: white;
  font-size: 24px;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: #333;
  line-height: 1;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: #666;
}

.charts-row {
  margin-bottom: 20px;
}

.bottom-row {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-container {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.chart {
  width: 100%;
  height: 100%;
}

.chart-placeholder {
  text-align: center;
  color: #999;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.chart-placeholder .el-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.task-list {
  max-height: 320px;
  overflow-y: auto;
}

.task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background-color 0.3s;
}

.task-item:hover {
  background-color: #f8f9fa;
  margin: 0 -12px;
  padding-left: 12px;
  padding-right: 12px;
  border-radius: 4px;
}

.task-item:last-child {
  border-bottom: none;
}

.task-domain {
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
}

.task-time {
  font-size: 12px;
  color: #999;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  margin-bottom: 12px;
}

.status-item:last-child {
  margin-bottom: 0;
}

.status-label {
  color: #333;
  font-size: 14px;
}

.empty-state {
  padding: 40px 0;
}
</style>