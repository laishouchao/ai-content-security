<template>
  <div class="report-summary" v-loading="loading">
    <div v-if="summaryData">
      <!-- 基本信息卡片 -->
      <el-card class="summary-card">
        <template #header>
          <span>扫描摘要 - {{ summaryData.task_name }}</span>
        </template>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-statistic title="扫描时长（分钟）" :value="Math.round(summaryData.scan_duration / 60)" />
          </el-col>
          <el-col :span="12">
            <el-statistic title="总域名数" :value="summaryData.total_domains" />
          </el-col>
        </el-row>
        
        <el-row :gutter="20" style="margin-top: 20px;">
          <el-col :span="12">
            <el-statistic title="已分析域名" :value="summaryData.analyzed_domains" />
          </el-col>
          <el-col :span="12">
            <el-statistic title="违规域名" :value="summaryData.violation_domains" />
          </el-col>
        </el-row>
      </el-card>

      <!-- 风险分布图表 -->
      <el-card class="chart-card">
        <template #header>
          <span>风险等级分布</span>
        </template>
        
        <div style="height: 300px;">
          <v-chart :option="riskChartOptions" style="height: 100%;" />
        </div>
      </el-card>

      <!-- 违规类型分布 -->
      <el-card class="chart-card">
        <template #header>
          <span>违规类型分布</span>
        </template>
        
        <div style="height: 300px;">
          <v-chart :option="violationTypeChartOptions" style="height: 100%;" />
        </div>
      </el-card>

      <!-- 违规域名Top10 -->
      <el-card class="top-violations-card">
        <template #header>
          <span>违规域名 Top 10</span>
        </template>
        
        <el-table :data="summaryData.top_violation_domains" max-height="400">
          <el-table-column type="index" label="排名" width="80" />
          
          <el-table-column prop="domain" label="域名" min-width="200">
            <template #default="{ row }">
              <el-link type="primary" :href="`https://${row.domain}`" target="_blank">
                {{ row.domain }}
              </el-link>
            </template>
          </el-table-column>

          <el-table-column prop="violation_count" label="违规数量" width="120">
            <template #default="{ row }">
              <el-text type="danger">{{ row.violation_count }}</el-text>
            </template>
          </el-table-column>

          <el-table-column prop="risk_level" label="风险等级" width="100">
            <template #default="{ row }">
              <el-tag :type="getRiskType(row.risk_level)" size="small">
                {{ getRiskText(row.risk_level) }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 统计数据 -->
      <el-card class="stats-card">
        <template #header>
          <span>详细统计</span>
        </template>
        
        <el-row :gutter="20">
          <el-col :span="6">
            <div class="stat-item">
              <div class="stat-number critical">{{ summaryData.risk_distribution.critical }}</div>
              <div class="stat-label">严重风险</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-item">
              <div class="stat-number high">{{ summaryData.risk_distribution.high }}</div>
              <div class="stat-label">高风险</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-item">
              <div class="stat-number medium">{{ summaryData.risk_distribution.medium }}</div>
              <div class="stat-label">中风险</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-item">
              <div class="stat-number low">{{ summaryData.risk_distribution.low }}</div>
              <div class="stat-label">低风险</div>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 导出操作 -->
      <div class="export-actions">
        <el-button type="primary" @click="exportSummary('json')">
          <el-icon><Download /></el-icon>
          导出JSON
        </el-button>
        <el-button @click="exportSummary('excel')">
          <el-icon><Download /></el-icon>
          导出Excel
        </el-button>
        <el-button @click="exportSummary('pdf')">
          <el-icon><Download /></el-icon>
          导出PDF
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import { reportAPI } from '@/api/report'
import type { ReportSummary } from '@/types/api'

// 注册 ECharts 组件
use([
  CanvasRenderer,
  PieChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

// Props
interface Props {
  taskId: string
}

const props = defineProps<Props>()

// Emits
interface Emits {
  (e: 'close'): void
}

const emit = defineEmits<Emits>()

// 响应式状态
const loading = ref(false)
const summaryData = ref<ReportSummary | null>(null)

// 计算属性
const riskChartOptions = computed(() => {
  if (!summaryData.value) return {}

  const data = [
    { name: '严重风险', value: summaryData.value.risk_distribution.critical, itemStyle: { color: '#f56c6c' } },
    { name: '高风险', value: summaryData.value.risk_distribution.high, itemStyle: { color: '#e6a23c' } },
    { name: '中风险', value: summaryData.value.risk_distribution.medium, itemStyle: { color: '#409eff' } },
    { name: '低风险', value: summaryData.value.risk_distribution.low, itemStyle: { color: '#67c23a' } }
  ]

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
        name: '风险等级',
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

const violationTypeChartOptions = computed(() => {
  if (!summaryData.value) return {}

  const violationTypes = summaryData.value.violation_types
  const data = Object.entries(violationTypes).map(([type, count]) => ({
    name: getViolationTypeText(type),
    value: count
  }))

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: data.map(item => item.name)
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '违规数量',
        type: 'bar',
        data: data.map(item => item.value),
        itemStyle: {
          color: '#409eff'
        }
      }
    ]
  }
})

// 方法
const getRiskType = (risk: string): 'info' | 'success' | 'warning' | 'danger' => {
  const riskMap: Record<string, 'info' | 'success' | 'warning' | 'danger'> = {
    low: 'success',
    medium: 'warning',
    high: 'danger',
    critical: 'danger'
  }
  return riskMap[risk] || 'info'
}

const getRiskText = (risk: string) => {
  const riskMap: Record<string, string> = {
    low: '低',
    medium: '中',
    high: '高',
    critical: '严重'
  }
  return riskMap[risk] || risk
}

const getViolationTypeText = (type: string) => {
  const typeMap: Record<string, string> = {
    malware: '恶意软件',
    phishing: '钓鱼网站',
    illegal_content: '违法内容',
    copyright_violation: '版权侵犯',
    other: '其他'
  }
  return typeMap[type] || type
}

const fetchSummaryData = async () => {
  try {
    loading.value = true
    const response = await reportAPI.getReportSummary(props.taskId)
    
    if (response.data.success) {
      summaryData.value = response.data.data || null
    }
  } catch (error) {
    console.error('获取报告摘要失败:', error)
    ElMessage.error('获取报告摘要失败')
  } finally {
    loading.value = false
  }
}

const exportSummary = async (format: 'json' | 'excel' | 'pdf') => {
  try {
    const response = await reportAPI.exportReport(props.taskId, format)
    
    // 创建下载链接
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `summary_${summaryData.value?.task_name}_${props.taskId}.${format}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success(`摘要已导出为 ${format.toUpperCase()} 格式`)
  } catch (error) {
    console.error('导出摘要失败:', error)
    ElMessage.error('导出摘要失败')
  }
}

// 监听 taskId 变化
watch(
  () => props.taskId,
  () => {
    if (props.taskId) {
      fetchSummaryData()
    }
  },
  { immediate: true }
)

// 生命周期
onMounted(() => {
  if (props.taskId) {
    fetchSummaryData()
  }
})
</script>

<style scoped>
.report-summary {
  min-height: 400px;
}

.summary-card,
.chart-card,
.top-violations-card,
.stats-card {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 20px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
}

.stat-number {
  font-size: 36px;
  font-weight: bold;
  line-height: 1;
  margin-bottom: 8px;
}

.stat-number.critical {
  color: #f56c6c;
}

.stat-number.high {
  color: #e6a23c;
}

.stat-number.medium {
  color: #409eff;
}

.stat-number.low {
  color: #67c23a;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.export-actions {
  text-align: center;
  padding: 20px;
  border-top: 1px solid #e4e7ed;
}

.export-actions .el-button {
  margin: 0 8px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .el-col {
    margin-bottom: 12px;
  }
  
  .stat-number {
    font-size: 24px;
  }
  
  .export-actions .el-button {
    display: block;
    width: 100%;
    margin: 8px 0;
  }
}
</style>