<template>
  <div class="report-management">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2>报告管理</h2>
        <p>管理和查看所有扫描任务的报告</p>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="refreshReports">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button @click="batchExportReports('json')" :disabled="selectedReports.length === 0">
          <el-icon><Download /></el-icon>
          批量导出JSON
        </el-button>
        <el-button @click="batchExportReports('excel')" :disabled="selectedReports.length === 0">
          <el-icon><Download /></el-icon>
          批量导出Excel
        </el-button>
        <el-button @click="batchExportReports('pdf')" :disabled="selectedReports.length === 0">
          <el-icon><Download /></el-icon>
          批量导出PDF
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-cards">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #409eff;">
              <el-icon><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ reportStats.total_reports || 0 }}</div>
              <div class="stat-label">总报告数</div>
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
              <div class="stat-value">{{ reportStats.completed_reports || 0 }}</div>
              <div class="stat-label">已完成报告</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #e6a23c;">
              <el-icon><Loading /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ reportStats.generating_reports || 0 }}</div>
              <div class="stat-label">生成中报告</div>
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
              <div class="stat-value">{{ reportStats.total_violations || 0 }}</div>
              <div class="stat-label">总违规数</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选器 -->
    <el-card class="filter-card">
      <el-form :model="filters" inline>
        <el-form-item label="任务名称">
          <el-input 
            v-model="filters.task_name" 
            placeholder="输入任务名称" 
            clearable
            @keyup.enter="searchReports"
          />
        </el-form-item>
        <el-form-item label="报告状态">
          <el-select v-model="filters.status" placeholder="选择状态" clearable style="width: 60px">
            <el-option label="生成中" value="generating" />
            <el-option label="已完成" value="completed" />
            <el-option label="生成失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="创建日期">
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
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="searchReports">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetFilters">
            <el-icon><RefreshLeft /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 报告列表 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>报告列表</span>
          <el-text type="info">
            共 {{ pagination.total }} 条记录
          </el-text>
        </div>
      </template>

      <el-table 
        :data="reports" 
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column prop="task_name" label="任务名称" min-width="200">
          <template #default="{ row }">
            <div class="task-info">
              <div class="task-name">{{ row.task_name }}</div>
              <div class="task-id">ID: {{ row.task_id }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="report_status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.report_status)">
              {{ getStatusText(row.report_status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="扫描结果" width="300">
          <template #default="{ row }">
            <div class="scan-results">
              <div class="result-item">
                <span>总域名：</span>
                <el-text type="primary">{{ row.total_domains }}</el-text>
              </div>
              <div class="result-item">
                <span>已分析：</span>
                <el-text type="success">{{ row.analyzed_domains }}</el-text>
              </div>
              <div class="result-item">
                <span>违规：</span>
                <el-text type="danger">{{ row.violation_domains }}</el-text>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="扫描时间" width="180">
          <template #default="{ row }">
            <div class="time-info">
              <div>开始：{{ formatTime(row.scan_start_time) }}</div>
              <div v-if="row.scan_end_time">
                结束：{{ formatTime(row.scan_end_time) }}
              </div>
              <div v-else class="scanning">
                <el-icon class="is-loading"><Loading /></el-icon>
                扫描中...
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="150">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button 
              type="text" 
              size="small"
              @click="viewReportDetail(row)"
            >
              查看详情
            </el-button>
            <el-button 
              type="text" 
              size="small"
              @click="viewReportSummary(row)"
            >
              查看摘要
            </el-button>
            <el-dropdown @command="(command) => handleExportCommand(command, row)">
              <el-button type="text" size="small">
                导出<el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="json">JSON格式</el-dropdown-item>
                  <el-dropdown-item command="excel">Excel格式</el-dropdown-item>
                  <el-dropdown-item command="pdf">PDF格式</el-dropdown-item>
                  <el-dropdown-item command="csv">CSV格式</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button 
              type="text" 
              size="small"
              :disabled="row.report_status !== 'completed'"
              @click="regenerateReport(row)"
            >
              重新生成
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 报告详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="报告详情"
      width="80%"
      :close-on-click-modal="false"
    >
      <ReportDetail
        v-if="selectedReport"
        :task-id="selectedReport.task_id"
        @close="detailDialogVisible = false"
      />
    </el-dialog>

    <!-- 报告摘要对话框 -->
    <el-dialog
      v-model="summaryDialogVisible"
      title="报告摘要"
      width="70%"
      :close-on-click-modal="false"
    >
      <ReportSummary
        v-if="selectedReport"
        :task-id="selectedReport.task_id"
        @close="summaryDialogVisible = false"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Refresh, 
  Download, 
  Search, 
  RefreshLeft,
  Document,
  CircleCheck,
  Loading,
  Warning,
  ArrowDown
} from '@element-plus/icons-vue'
import { reportAPI } from '@/api/report'
import type { ScanReport, ReportFilter } from '@/types/api'
import { formatTime } from '@/utils/date'
import ReportDetail from '@/components/report/ReportDetail.vue'
import ReportSummary from '@/components/report/ReportSummary.vue'

// 响应式状态
const loading = ref(false)
const detailDialogVisible = ref(false)
const summaryDialogVisible = ref(false)
const selectedReport = ref<ScanReport | null>(null)
const selectedReports = ref<ScanReport[]>([])
const dateRange = ref<[string, string] | null>(null)

// 报告列表和分页
const reports = ref<ScanReport[]>([])
const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

// 筛选条件
const filters = reactive<ReportFilter>({
  task_name: undefined,
  status: undefined,
  date_from: undefined,
  date_to: undefined
})

// 统计数据
const reportStats = ref<any>({
  total_reports: 0,
  completed_reports: 0,
  generating_reports: 0,
  total_violations: 0
})

// 方法
const getStatusType = (status: string): 'success' | 'warning' | 'danger' | 'info' => {
  const statusMap: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    completed: 'success',
    generating: 'warning',
    failed: 'danger'
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    completed: '已完成',
    generating: '生成中',
    failed: '生成失败'
  }
  return statusMap[status] || status
}

const handleDateRangeChange = (range: [string, string] | null) => {
  if (range) {
    filters.date_from = range[0]
    filters.date_to = range[1]
  } else {
    filters.date_from = undefined
    filters.date_to = undefined
  }
}

const fetchReports = async () => {
  try {
    loading.value = true
    
    const response = await reportAPI.getReports(
      (pagination.page - 1) * pagination.size,
      pagination.size,
      filters
    )
    
    if (response.data.success) {
      reports.value = response.data.data?.items || []
      pagination.total = response.data.data?.total || 0
      
      // 计算统计数据
      updateReportStats()
    }
  } catch (error) {
    console.error('获取报告列表失败:', error)
    ElMessage.error('获取报告列表失败')
  } finally {
    loading.value = false
  }
}

const updateReportStats = () => {
  reportStats.value = {
    total_reports: reports.value.length,
    completed_reports: reports.value.filter(r => r.report_status === 'completed').length,
    generating_reports: reports.value.filter(r => r.report_status === 'generating').length,
    total_violations: reports.value.reduce((sum, r) => sum + r.violation_domains, 0)
  }
}

const searchReports = () => {
  pagination.page = 1
  fetchReports()
}

const resetFilters = () => {
  filters.task_name = undefined
  filters.status = undefined
  filters.date_from = undefined
  filters.date_to = undefined
  dateRange.value = null
  pagination.page = 1
  fetchReports()
}

const refreshReports = () => {
  pagination.page = 1
  fetchReports()
}

const handleSizeChange = (size: number) => {
  pagination.size = size
  pagination.page = 1
  fetchReports()
}

const handleCurrentChange = (page: number) => {
  pagination.page = page
  fetchReports()
}

const handleSelectionChange = (selection: ScanReport[]) => {
  selectedReports.value = selection
}

const viewReportDetail = (report: ScanReport) => {
  selectedReport.value = report
  detailDialogVisible.value = true
}

const viewReportSummary = (report: ScanReport) => {
  selectedReport.value = report
  summaryDialogVisible.value = true
}

const handleExportCommand = async (format: string, report: ScanReport) => {
  await exportSingleReport(report, format as 'json' | 'pdf' | 'excel' | 'csv')
}

const exportSingleReport = async (
  report: ScanReport, 
  format: 'json' | 'pdf' | 'excel' | 'csv'
) => {
  try {
    const response = await reportAPI.exportReport(report.task_id, format)
    
    // 创建下载链接
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `report_${report.task_name}_${report.task_id}.${format}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success(`报告已导出为 ${format.toUpperCase()} 格式`)
  } catch (error) {
    console.error('导出报告失败:', error)
    ElMessage.error('导出报告失败')
  }
}

const batchExportReports = async (format: 'json' | 'pdf' | 'excel' | 'csv') => {
  if (selectedReports.value.length === 0) {
    ElMessage.warning('请先选择要导出的报告')
    return
  }

  try {
    const taskIds = selectedReports.value.map(report => report.task_id)
    const response = await reportAPI.batchExportReports(taskIds, format)
    
    // 创建下载链接
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `batch_reports_${new Date().toISOString().split('T')[0]}.${format}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success(`批量导出 ${selectedReports.value.length} 个报告成功`)
  } catch (error) {
    console.error('批量导出报告失败:', error)
    ElMessage.error('批量导出报告失败')
  }
}

const regenerateReport = async (report: ScanReport) => {
  try {
    await ElMessageBox.confirm(
      `确定要重新生成任务 "${report.task_name}" 的报告吗？`,
      '确认重新生成',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await reportAPI.generateReport(report.task_id)
    ElMessage.success('报告重新生成中，请稍后查看')
    await fetchReports()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('重新生成报告失败:', error)
      ElMessage.error('重新生成报告失败')
    }
  }
}

// 生命周期
onMounted(() => {
  fetchReports()
})
</script>

<style scoped>
.report-management {
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

.stats-cards {
  margin-bottom: 20px;
}

.stat-card {
  height: 120px;
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
  margin-top: 8px;
}

.filter-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-info {
  line-height: 1.4;
}

.task-name {
  font-weight: 500;
  color: #303133;
}

.task-id {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.scan-results {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.result-item {
  display: flex;
  align-items: center;
  font-size: 12px;
}

.result-item span {
  color: #606266;
  margin-right: 4px;
  min-width: 50px;
}

.time-info {
  font-size: 12px;
  line-height: 1.4;
}

.time-info > div {
  margin-bottom: 2px;
}

.scanning {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #e6a23c;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
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
  
  .stats-cards .el-col {
    margin-bottom: 12px;
  }
  
  .el-table .el-table__cell {
    padding: 8px 0;
  }
}
</style>