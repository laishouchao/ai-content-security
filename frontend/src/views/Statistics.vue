<template>
  <div class="statistics-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2>统计报表</h2>
        <p>查看系统的各项统计数据和性能指标</p>
      </div>
      <div class="header-right">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          @change="handleDateRangeChange"
        />
        <el-button type="primary" @click="refreshAllData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
        <el-button @click="exportReport('excel')">
          <el-icon><Download /></el-icon>
          导出Excel
        </el-button>
        <el-button @click="exportReport('pdf')">
          <el-icon><Document /></el-icon>
          导出PDF
        </el-button>
      </div>
    </div>

    <!-- 统计概览卡片 -->
    <el-row :gutter="20" class="overview-cards">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #409eff;">
              <el-icon><List /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ overviewStats.total_tasks || 0 }}</div>
              <div class="stat-label">总任务数</div>
              <div class="stat-trend" :class="getTrendClass(overviewStats.task_trend)">
                <el-icon><TrendCharts /></el-icon>
                {{ formatTrend(overviewStats.task_trend) }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #67c23a;">
              <el-icon><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ overviewStats.completed_tasks || 0 }}</div>
              <div class="stat-label">已完成任务</div>
              <div class="stat-trend" :class="getTrendClass(overviewStats.completion_trend)">
                <el-icon><TrendCharts /></el-icon>
                {{ formatTrend(overviewStats.completion_trend) }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #e6a23c;">
              <el-icon><Link /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ overviewStats.total_domains || 0 }}</div>
              <div class="stat-label">扫描域名数</div>
              <div class="stat-trend" :class="getTrendClass(overviewStats.domain_trend)">
                <el-icon><TrendCharts /></el-icon>
                {{ formatTrend(overviewStats.domain_trend) }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #f56c6c;">
              <el-icon><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ overviewStats.total_violations || 0 }}</div>
              <div class="stat-label">违规检测数</div>
              <div class="stat-trend" :class="getTrendClass(overviewStats.violation_trend)">
                <el-icon><TrendCharts /></el-icon>
                {{ formatTrend(overviewStats.violation_trend) }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 任务趋势图 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>任务执行趋势</span>
              <el-radio-group v-model="taskTrendPeriod" size="small" @change="refreshTaskTrend">
                <el-radio-button label="7d">最近7天</el-radio-button>
                <el-radio-button label="30d">最近30天</el-radio-button>
                <el-radio-button label="90d">最近90天</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div style="height: 350px;">
            <v-chart :option="taskTrendChartOptions" style="height: 100%;" />
          </div>
        </el-card>
      </el-col>

      <!-- 违规类型分布 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>违规类型分布</span>
          </template>
          <div style="height: 350px;">
            <v-chart :option="violationDistributionOptions" style="height: 100%;" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 性能监控图表 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统性能监控</span>
              <div>
                <el-switch
                  v-model="autoRefresh"
                  active-text="自动刷新"
                  @change="handleAutoRefreshChange"
                />
                <el-button size="small" @click="refreshPerformanceData" :loading="performanceLoading">
                  <el-icon><Refresh /></el-icon>
                  刷新
                </el-button>
              </div>
            </div>
          </template>
          <div style="height: 400px;">
            <v-chart :option="performanceChartOptions" style="height: 100%;" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 详细统计表格 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 任务统计 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>任务执行统计</span>
          </template>
          <el-table :data="taskStatistics" style="width: 100%">
            <el-table-column prop="date" label="日期" width="120" />
            <el-table-column prop="total" label="总数" width="80" />
            <el-table-column prop="completed" label="完成" width="80" />
            <el-table-column prop="failed" label="失败" width="80" />
            <el-table-column prop="success_rate" label="成功率" width="100">
              <template #default="{ row }">
                <el-tag :type="getSuccessRateType(row.success_rate)">
                  {{ row.success_rate }}%
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 性能指标 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>系统性能指标</span>
          </template>
          <div class="performance-metrics">
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-name">平均响应时间</span>
                <span class="metric-value">{{ performanceMetrics.avg_response_time || 0 }}ms</span>
              </div>
              <el-progress 
                :percentage="getResponseTimePercentage(performanceMetrics.avg_response_time)" 
                :color="getResponseTimeColor(performanceMetrics.avg_response_time)"
              />
            </div>
            
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-name">系统可用性</span>
                <span class="metric-value">{{ performanceMetrics.uptime_percentage || 0 }}%</span>
              </div>
              <el-progress 
                :percentage="performanceMetrics.uptime_percentage || 0" 
                :color="getUptimeColor(performanceMetrics.uptime_percentage)"
              />
            </div>
            
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-name">错误率</span>
                <span class="metric-value">{{ performanceMetrics.error_rate || 0 }}%</span>
              </div>
              <el-progress 
                :percentage="performanceMetrics.error_rate || 0" 
                :color="getErrorRateColor(performanceMetrics.error_rate)"
              />
            </div>

            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-name">并发任务数</span>
                <span class="metric-value">{{ performanceMetrics.concurrent_tasks || 0 }}</span>
              </div>
              <el-progress 
                :percentage="getConcurrentTasksPercentage(performanceMetrics.concurrent_tasks)" 
                color="#409eff"
              />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 用户活跃度统计 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <span>用户活跃度统计</span>
      </template>
      <el-row :gutter="20">
        <el-col :span="8">
          <div style="height: 300px;">
            <v-chart :option="userActivityOptions" style="height: 100%;" />
          </div>
        </el-col>
        <el-col :span="16">
          <el-table :data="userActivityTable" style="width: 100%">
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="total_tasks" label="任务总数" />
            <el-table-column prop="completed_tasks" label="完成任务" />
            <el-table-column prop="last_active" label="最后活跃" />
            <el-table-column prop="success_rate" label="成功率">
              <template #default="{ row }">
                <el-tag :type="getSuccessRateType(row.success_rate)">
                  {{ row.success_rate }}%
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  Refresh, 
  Download, 
  Document,
  List,
  CircleCheck,
  Link,
  Warning,
  TrendCharts
} from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import http from '@/api/http'
import { statisticsAPI } from '@/api/statistics'
import { formatTime } from '@/utils/date'

// 注册 ECharts 组件
use([
  CanvasRenderer,
  LineChart,
  BarChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

// 响应式数据
const loading = ref(false)
const performanceLoading = ref(false)
const autoRefresh = ref(false)
const taskTrendPeriod = ref('7d')
const dateRange = ref<[string, string] | null>(null)

// 统计数据
const overviewStats = ref<any>({})
const taskStatistics = ref<any[]>([])
const performanceMetrics = ref<any>({})
const userActivityTable = ref<any[]>([])

// 图表数据
const taskTrendData = ref<any>({})
const violationDistributionData = ref<any>({})
const performanceData = ref<any>({})
const userActivityData = ref<any>({})

// 自动刷新定时器
let refreshTimer: number

// 计算属性
const taskTrendChartOptions = computed(() => {
  if (!taskTrendData.value.dates?.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'middle' } }
  }

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['总任务', '完成任务', '失败任务']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: taskTrendData.value.dates || []
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '总任务',
        type: 'line',
        data: taskTrendData.value.total || [],
        smooth: true,
        itemStyle: { color: '#409eff' }
      },
      {
        name: '完成任务',
        type: 'line',
        data: taskTrendData.value.completed || [],
        smooth: true,
        itemStyle: { color: '#67c23a' }
      },
      {
        name: '失败任务',
        type: 'line',
        data: taskTrendData.value.failed || [],
        smooth: true,
        itemStyle: { color: '#f56c6c' }
      }
    ]
  }
})

const violationDistributionOptions = computed(() => {
  if (!violationDistributionData.value.types?.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'middle' } }
  }

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
        data: violationDistributionData.value.types || [],
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

const performanceChartOptions = computed(() => {
  if (!performanceData.value.timestamps?.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'middle' } }
  }

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['CPU使用率', '内存使用率', '磁盘使用率', '响应时间']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: performanceData.value.timestamps || []
    },
    yAxis: [
      {
        type: 'value',
        name: '使用率(%)',
        max: 100
      },
      {
        type: 'value',
        name: '响应时间(ms)',
        position: 'right'
      }
    ],
    series: [
      {
        name: 'CPU使用率',
        type: 'line',
        data: performanceData.value.cpu || [],
        smooth: true,
        itemStyle: { color: '#409eff' }
      },
      {
        name: '内存使用率',
        type: 'line',
        data: performanceData.value.memory || [],
        smooth: true,
        itemStyle: { color: '#67c23a' }
      },
      {
        name: '磁盘使用率',
        type: 'line',
        data: performanceData.value.disk || [],
        smooth: true,
        itemStyle: { color: '#e6a23c' }
      },
      {
        name: '响应时间',
        type: 'line',
        yAxisIndex: 1,
        data: performanceData.value.response_time || [],
        smooth: true,
        itemStyle: { color: '#f56c6c' }
      }
    ]
  }
})

const userActivityOptions = computed(() => {
  if (!userActivityData.value.users?.length) {
    return { title: { text: '暂无数据', left: 'center', top: 'middle' } }
  }

  return {
    tooltip: {
      trigger: 'item'
    },
    series: [
      {
        name: '用户活跃度',
        type: 'pie',
        radius: ['40%', '70%'],
        data: userActivityData.value.users || [],
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
const getTrendClass = (trend: number) => {
  if (trend > 0) return 'trend-up'
  if (trend < 0) return 'trend-down'
  return 'trend-stable'
}

const formatTrend = (trend: number) => {
  if (!trend) return '0%'
  const prefix = trend > 0 ? '+' : ''
  return `${prefix}${trend.toFixed(1)}%`
}

const getSuccessRateType = (rate: number) => {
  if (rate >= 90) return 'success'
  if (rate >= 70) return 'warning'
  return 'danger'
}

const getResponseTimePercentage = (time: number) => {
  return Math.min((time / 1000) * 100, 100)
}

const getResponseTimeColor = (time: number) => {
  if (time < 200) return '#67c23a'
  if (time < 500) return '#e6a23c'
  return '#f56c6c'
}

const getUptimeColor = (uptime: number) => {
  if (uptime >= 99) return '#67c23a'
  if (uptime >= 95) return '#e6a23c'
  return '#f56c6c'
}

const getErrorRateColor = (rate: number) => {
  if (rate < 1) return '#67c23a'
  if (rate < 5) return '#e6a23c'
  return '#f56c6c'
}

const getConcurrentTasksPercentage = (tasks: number) => {
  return Math.min((tasks / 20) * 100, 100) // 假设最大并发20个任务
}

const handleDateRangeChange = (range: [string, string] | null) => {
  refreshAllData()
}

const handleAutoRefreshChange = (val: string | number | boolean) => {
  const enabled = Boolean(val)
  if (enabled) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}

const refreshAllData = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchOverviewStats(),
      fetchTaskStatistics(),
      fetchPerformanceMetrics(),
      fetchUserActivity(),
      refreshTaskTrend(),
      refreshViolationDistribution()
    ])
  } catch (error) {
    console.error('刷新数据失败:', error)
    ElMessage.error('刷新数据失败')
  } finally {
    loading.value = false
  }
}

const fetchOverviewStats = async () => {
  try {
    const params = dateRange.value ? {
      start_date: dateRange.value[0],
      end_date: dateRange.value[1]
    } : {}
    
    const response = await statisticsAPI.getDashboardStats()
    if (response.data.success) {
      overviewStats.value = response.data.data
    }
  } catch (error) {
    console.error('获取概览统计失败:', error)
  }
}

const fetchTaskStatistics = async () => {
  try {
    const params = dateRange.value ? {
      start_date: dateRange.value[0],
      end_date: dateRange.value[1]
    } : {}
    
    const response = await statisticsAPI.getTaskStatistics(params)
    if (response.data.success && response.data.data) {
      taskStatistics.value = response.data.data
    }
  } catch (error) {
    console.error('获取任务统计失败:', error)
  }
}

const fetchPerformanceMetrics = async () => {
  try {
    const response = await statisticsAPI.getPerformanceStats()
    if (response.data.success) {
      performanceMetrics.value = response.data.data
    }
  } catch (error) {
    console.error('获取性能指标失败:', error)
  }
}

const fetchUserActivity = async () => {
  try {
    const params = dateRange.value ? {
      start_date: dateRange.value[0],
      end_date: dateRange.value[1]
    } : {}
    
    const response = await statisticsAPI.getUserActivity(params)
    if (response.data.success && response.data.data) {
      userActivityTable.value = response.data.data.table || []
      userActivityData.value = response.data.data.chart || {}
    }
  } catch (error) {
    console.error('获取用户活跃度失败:', error)
  }
}

const refreshTaskTrend = async () => {
  try {
    const response = await statisticsAPI.getTaskTrend({
      period: taskTrendPeriod.value as '7d' | '30d' | '90d'
    })
    if (response.data.success && response.data.data) {
      const trends = response.data.data
      taskTrendData.value = {
        dates: trends.map(t => t.date),
        total: trends.map(t => t.total),
        completed: trends.map(t => t.completed),
        failed: trends.map(t => t.failed)
      }
    }
  } catch (error) {
    console.error('获取任务趋势失败:', error)
  }
}

const refreshViolationDistribution = async () => {
  try {
    const params = dateRange.value ? {
      start_date: dateRange.value[0],
      end_date: dateRange.value[1]
    } : {}
    
    const response = await statisticsAPI.getViolationDistribution(params)
    if (response.data.success && response.data.data) {
      const distributions = response.data.data
      violationDistributionData.value = {
        types: distributions.map(d => ({
          name: d.name,
          value: d.count
        }))
      }
    }
  } catch (error) {
    console.error('获取违规分布失败:', error)
  }
}

const refreshPerformanceData = async () => {
  performanceLoading.value = true
  try {
    const response = await statisticsAPI.getPerformanceTrend({ hours: 24 })
    if (response.data.success && response.data.data) {
      const trends = response.data.data
      performanceData.value = {
        timestamps: trends.map(t => formatTime(t.timestamp)),
        cpu: trends.map(t => t.cpu_usage),
        memory: trends.map(t => t.memory_usage),
        disk: trends.map(t => t.disk_usage),
        responseTime: trends.map(t => t.response_time)
      }
    }
  } catch (error) {
    console.error('获取性能趋势失败:', error)
  } finally {
    performanceLoading.value = false
  }
}

const exportReport = async (format: 'excel' | 'pdf') => {
  try {
    const params = {
      format,
      start_date: dateRange.value?.[0],
      end_date: dateRange.value?.[1]
    }
    
    const response = await statisticsAPI.exportReport(params)
    
    // 创建下载链接
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `statistics-report-${new Date().toISOString().split('T')[0]}.${format}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success(`统计报表已导出为 ${format.toUpperCase()} 格式`)
  } catch (error) {
    console.error('导出报表失败:', error)
    ElMessage.error('导出报表失败')
  }
}

const startAutoRefresh = () => {
  refreshTimer = window.setInterval(() => {
    refreshPerformanceData()
    fetchPerformanceMetrics()
  }, 30000) // 每30秒刷新一次
}

const stopAutoRefresh = () => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer)
  }
}

// 生命周期
onMounted(() => {
  refreshAllData()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.statistics-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.header-left p {
  margin: 4px 0 0 0;
  color: #909399;
  font-size: 14px;
}

.header-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

.overview-cards {
  margin-bottom: 20px;
}

.stat-card {
  height: 140px;
  border: 1px solid #e4e7ed;
}

.stat-content {
  display: flex;
  align-items: center;
  height: 100%;
  padding: 10px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20px;
}

.stat-icon .el-icon {
  font-size: 24px;
  color: white;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #303133;
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin: 8px 0 4px 0;
}

.stat-trend {
  font-size: 12px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 2px;
}

.trend-up {
  color: #67c23a;
}

.trend-down {
  color: #f56c6c;
}

.trend-stable {
  color: #909399;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-item {
  margin-bottom: 20px;
}

.metric-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.metric-name {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.metric-value {
  font-size: 14px;
  color: #303133;
  font-weight: 600;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: 12px;
  }
  
  .header-right {
    width: 100%;
    justify-content: center;
    flex-wrap: wrap;
  }
  
  .overview-cards .el-col {
    margin-bottom: 12px;
  }
  
  .stat-value {
    font-size: 24px;
  }
}
</style>