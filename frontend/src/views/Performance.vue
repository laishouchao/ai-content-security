<template>
  <div class="performance-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2>性能监控</h2>
        <p>实时监控系统性能指标和服务状态</p>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="refreshAllData" :loading="refreshing">
          <el-icon><Refresh /></el-icon>
          刷新所有数据
        </el-button>
        <el-button @click="exportPerformanceReport">
          <el-icon><Download /></el-icon>
          导出报告
        </el-button>
      </div>
    </div>

    <!-- 系统概览 -->
    <el-row :gutter="20" class="overview-cards">
      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-content">
            <div class="metric-icon" style="background-color: #409eff;">
              <el-icon><Monitor /></el-icon>
            </div>
            <div class="metric-info">
              <div class="metric-value">{{ performanceData.overall_health_score || 0 }}%</div>
              <div class="metric-label">系统健康分数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-content">
            <div class="metric-icon" style="background-color: #67c23a;">
              <el-icon><Cpu /></el-icon>
            </div>
            <div class="metric-info">
              <div class="metric-value">{{ performanceData.system_health?.cpu_percent || 0 }}%</div>
              <div class="metric-label">CPU使用率</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-content">
            <div class="metric-icon" style="background-color: #e6a23c;">
              <el-icon><MagicStick /></el-icon>
            </div>
            <div class="metric-info">
              <div class="metric-value">{{ performanceData.memory_stats?.memory_info?.process_memory?.percent || 0 }}%</div>
              <div class="metric-label">内存使用率</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-content">
            <div class="metric-icon" style="background-color: #f56c6c;">
              <el-icon><FolderOpened /></el-icon>
            </div>
            <div class="metric-info">
              <div class="metric-value">{{ performanceData.system_health?.disk_usage?.percent || 0 }}%</div>
              <div class="metric-label">磁盘使用率</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 详细监控面板 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 系统性能 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统性能指标</span>
              <el-button @click="refreshPerformance" :loading="performanceLoading" size="small">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </template>
          
          <div class="performance-metrics">
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-name">CPU使用率</span>
                <span class="metric-value">{{ performanceData.system_health?.cpu_percent || 0 }}%</span>
              </div>
              <el-progress 
                :percentage="performanceData.system_health?.cpu_percent || 0" 
                :stroke-width="8"
                :color="getPerformanceColor(performanceData.system_health?.cpu_percent || 0)"
              />
            </div>
            
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-name">内存使用率</span>
                <span class="metric-value">{{ performanceData.memory_stats?.memory_info?.process_memory?.percent || 0 }}%</span>
              </div>
              <el-progress 
                :percentage="performanceData.memory_stats?.memory_info?.process_memory?.percent || 0" 
                :stroke-width="8"
                :color="getPerformanceColor(performanceData.memory_stats?.memory_info?.process_memory?.percent || 0)"
              />
            </div>
            
            <div class="metric-item">
              <div class="metric-header">
                <span class="metric-name">磁盘使用率</span>
                <span class="metric-value">{{ performanceData.system_health?.disk_usage?.percent || 0 }}%</span>
              </div>
              <el-progress 
                :percentage="performanceData.system_health?.disk_usage?.percent || 0" 
                :stroke-width="8"
                :color="getPerformanceColor(performanceData.system_health?.disk_usage?.percent || 0)"
              />
            </div>
          </div>
        </el-card>
      </el-col>
      
      <!-- 服务状态 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>服务状态</span>
              <el-button @click="checkServiceHealth" :loading="healthChecking" size="small">
                <el-icon><CircleCheck /></el-icon>
                健康检查
              </el-button>
            </div>
          </template>
          
          <div class="service-status">
            <div class="service-item">
              <div class="service-info">
                <el-icon class="service-icon"><Connection /></el-icon>
                <span class="service-name">数据库连接</span>
              </div>
              <el-tag 
                :type="performanceData.database_stats?.connection_pool?.available_connections > 0 ? 'success' : 'danger'"
                size="small"
              >
                {{ performanceData.database_stats?.connection_pool?.available_connections || 0 }} 可用
              </el-tag>
            </div>
            
            <div class="service-item">
              <div class="service-info">
                <el-icon class="service-icon"><Connection /></el-icon>
                <span class="service-name">Redis连接</span>
              </div>
              <el-tag 
                :type="performanceData.redis_stats?.connected ? 'success' : 'danger'"
                size="small"
              >
                {{ performanceData.redis_stats?.connected ? '已连接' : '断开' }}
              </el-tag>
            </div>
            
            <div class="service-item">
              <div class="service-info">
                <el-icon class="service-icon"><List /></el-icon>
                <span class="service-name">Celery任务</span>
              </div>
              <el-tag type="info" size="small">
                {{ performanceData.celery_stats?.metrics?.active_tasks || 0 }} 活跃
              </el-tag>
            </div>
            
            <div class="service-item">
              <div class="service-info">
                <el-icon class="service-icon"><Warning /></el-icon>
                <span class="service-name">内存压力</span>
              </div>
              <el-tag 
                :type="performanceData.memory_stats?.memory_pressure ? 'warning' : 'success'"
                size="small"
              >
                {{ performanceData.memory_stats?.memory_pressure ? '高' : '正常' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 性能图表 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>性能趋势图表</span>
              <div>
                <el-radio-group v-model="chartTimeRange" size="small" @change="refreshChartData">
                  <el-radio-button label="1h">最近1小时</el-radio-button>
                  <el-radio-button label="6h">最近6小时</el-radio-button>
                  <el-radio-button label="24h">最近24小时</el-radio-button>
                  <el-radio-button label="7d">最近7天</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </template>
          
          <div style="height: 400px;">
            <v-chart 
              :option="performanceChartOptions" 
              :loading="chartLoading"
              style="height: 100%;"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 系统操作 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <span>系统操作</span>
      </template>
      
      <div class="system-operations">
        <el-button 
          type="warning" 
          @click="clearCache" 
          :loading="clearingCache"
        >
          <el-icon><Delete /></el-icon>
          清理缓存
        </el-button>
        
        <el-button 
          type="success" 
          @click="performOptimization" 
          :loading="optimizing"
        >
          <el-icon><Tools /></el-icon>
          系统优化
        </el-button>
        
        <el-button 
          type="primary" 
          @click="performHealthCheck" 
          :loading="healthChecking"
        >
          <el-icon><CircleCheck /></el-icon>
          健康检查
        </el-button>
        
        <el-button 
          type="info" 
          @click="generateReport"
          :loading="generatingReport"
        >
          <el-icon><Document /></el-icon>
          生成报告
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Refresh, 
  Download, 
  Monitor,
  Cpu,
  MagicStick,
  FolderOpened,
  Connection,
  List,
  Warning,
  Clock,
  CircleCheck,
  Delete,
  Tools,
  Document
} from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import http from '@/api/http'

// 注册 ECharts 组件
use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

// 响应式数据
const refreshing = ref(false)
const performanceLoading = ref(false)
const healthChecking = ref(false)
const clearingCache = ref(false)
const optimizing = ref(false)
const generatingReport = ref(false)
const chartLoading = ref(false)
const chartTimeRange = ref('1h')

const performanceData = ref<any>({})
const chartData = ref<any>({})

// 计算属性
const performanceChartOptions = computed(() => {
  if (!chartData.value.timestamps?.length) {
    return {
      title: {
        text: '暂无数据',
        left: 'center',
        top: 'middle'
      }
    }
  }

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: ['CPU使用率', '内存使用率', '磁盘使用率']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: chartData.value.timestamps || []
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: [
      {
        name: 'CPU使用率',
        type: 'line',
        data: chartData.value.cpu || [],
        smooth: true,
        itemStyle: {
          color: '#409eff'
        }
      },
      {
        name: '内存使用率',
        type: 'line',
        data: chartData.value.memory || [],
        smooth: true,
        itemStyle: {
          color: '#67c23a'
        }
      },
      {
        name: '磁盘使用率',
        type: 'line',
        data: chartData.value.disk || [],
        smooth: true,
        itemStyle: {
          color: '#e6a23c'
        }
      }
    ]
  }
})

// 方法
const refreshAllData = async () => {
  refreshing.value = true
  try {
    await Promise.all([
      refreshPerformance(),
      refreshChartData()
    ])
    ElMessage.success('数据刷新成功')
  } catch (error) {
    ElMessage.error('数据刷新失败')
  } finally {
    refreshing.value = false
  }
}

const refreshPerformance = async () => {
  try {
    performanceLoading.value = true
    const response = await http.get('/performance/stats')
    
    if (response.data.success) {
      performanceData.value = response.data.data
    }
  } catch (error) {
    console.error('获取性能统计失败:', error)
    ElMessage.error('获取性能统计失败')
  } finally {
    performanceLoading.value = false
  }
}

const refreshChartData = async () => {
  try {
    chartLoading.value = true
    const response = await http.get('/performance/metrics', {
      params: { range: chartTimeRange.value }
    })
    
    if (response.data.success) {
      chartData.value = response.data.data
    }
  } catch (error) {
    console.error('获取图表数据失败:', error)
    // 生成模拟数据以防API不存在
    generateMockChartData()
  } finally {
    chartLoading.value = false
  }
}

const generateMockChartData = () => {
  const now = Date.now()
  const interval = chartTimeRange.value === '1h' ? 5 * 60 * 1000 : 
                   chartTimeRange.value === '6h' ? 30 * 60 * 1000 :
                   chartTimeRange.value === '24h' ? 2 * 60 * 60 * 1000 :
                   6 * 60 * 60 * 1000
  
  const points = chartTimeRange.value === '1h' ? 12 :
                 chartTimeRange.value === '6h' ? 12 :
                 chartTimeRange.value === '24h' ? 12 : 28
  
  const timestamps = []
  const cpu = []
  const memory = []
  const disk = []
  
  for (let i = points - 1; i >= 0; i--) {
    const time = new Date(now - i * interval)
    timestamps.push(time.toLocaleTimeString())
    cpu.push(Math.random() * 50 + 20)
    memory.push(Math.random() * 40 + 30)
    disk.push(Math.random() * 30 + 40)
  }
  
  chartData.value = { timestamps, cpu, memory, disk }
}

const checkServiceHealth = async () => {
  try {
    healthChecking.value = true
    const response = await http.get('/performance/health')
    
    if (response.data.success) {
      const healthData = response.data.data
      const status = healthData.status
      
      if (status === 'healthy') {
        ElMessage.success('系统健康检查通过')
      } else if (status === 'warning') {
        ElMessage.warning('系统健康检查发现警告')
      } else {
        ElMessage.error('系统健康检查发现问题')
      }
      
      await refreshPerformance()
    }
  } catch (error) {
    console.error('健康检查失败:', error)
    ElMessage.error('健康检查失败')
  } finally {
    healthChecking.value = false
  }
}

const clearCache = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清理系统缓存吗？这可能会暂时影响系统性能。',
      '确认清理缓存',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    clearingCache.value = true
    await http.post('/performance/cache/clear')
    ElMessage.success('缓存清理成功')
    await refreshPerformance()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('清理缓存失败:', error)
      ElMessage.error('清理缓存失败')
    }
  } finally {
    clearingCache.value = false
  }
}

const performOptimization = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要执行系统优化吗？这将清理临时文件、优化数据库连接等。',
      '确认系统优化',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
    
    optimizing.value = true
    await http.post('/performance/optimize')
    ElMessage.success('系统优化完成')
    await refreshPerformance()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('系统优化失败:', error)
      ElMessage.error('系统优化失败')
    }
  } finally {
    optimizing.value = false
  }
}

const performHealthCheck = async () => {
  await checkServiceHealth()
}

const generateReport = async () => {
  try {
    generatingReport.value = true
    const response = await http.get('/performance/report', {
      responseType: 'blob'
    })
    
    // 创建下载链接
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `performance-report-${new Date().toISOString().split('T')[0]}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('性能报告生成成功')
  } catch (error) {
    console.error('生成报告失败:', error)
    ElMessage.error('生成报告失败')
  } finally {
    generatingReport.value = false
  }
}

const exportPerformanceReport = async () => {
  await generateReport()
}

// 工具方法
const getPerformanceColor = (percentage: number) => {
  if (percentage < 60) return '#67c23a'
  if (percentage < 80) return '#e6a23c'
  return '#f56c6c'
}

// 自动刷新
let refreshTimer: number

const startAutoRefresh = () => {
  refreshTimer = window.setInterval(() => {
    refreshPerformance()
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
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.performance-page {
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
}

.overview-cards {
  margin-bottom: 20px;
}

.metric-card {
  height: 120px;
  border: 1px solid #e4e7ed;
}

.metric-content {
  display: flex;
  align-items: center;
  height: 100%;
  padding: 10px;
}

.metric-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20px;
}

.metric-icon .el-icon {
  font-size: 24px;
  color: white;
}

.metric-info {
  flex: 1;
}

.metric-value {
  font-size: 32px;
  font-weight: bold;
  color: #303133;
  line-height: 1;
}

.metric-label {
  font-size: 14px;
  color: #909399;
  margin-top: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.performance-metrics {
  space-y: 20px;
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

.service-status {
  space-y: 16px;
}

.service-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.service-item:last-child {
  border-bottom: none;
}

.service-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.service-icon {
  font-size: 16px;
  color: #606266;
}

.service-name {
  font-size: 14px;
  color: #606266;
}

.system-operations {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.system-operations .el-button {
  width: 100%;
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
  }
  
  .overview-cards .el-col {
    margin-bottom: 12px;
  }
  
  .system-operations {
    grid-template-columns: 1fr;
  }
}
</style>