<template>
  <div class="report-detail" v-loading="loading">
    <div v-if="reportData">
      <!-- 基本信息 -->
      <el-card class="info-card">
        <template #header>
          <span>扫描报告 - {{ reportData.task_name }}</span>
        </template>
        
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务ID">{{ reportData.task_id }}</el-descriptions-item>
          <el-descriptions-item label="任务名称">{{ reportData.task_name }}</el-descriptions-item>
          <el-descriptions-item label="扫描开始时间">
            {{ formatTime(reportData.scan_start_time) }}
          </el-descriptions-item>
          <el-descriptions-item label="扫描结束时间">
            {{ reportData.scan_end_time ? formatTime(reportData.scan_end_time) : '进行中' }}
          </el-descriptions-item>
          <el-descriptions-item label="总域名数">
            <el-text type="primary">{{ reportData.total_domains }}</el-text>
          </el-descriptions-item>
          <el-descriptions-item label="已分析域名">
            <el-text type="success">{{ reportData.analyzed_domains }}</el-text>
          </el-descriptions-item>
          <el-descriptions-item label="违规域名">
            <el-text type="danger">{{ reportData.violation_domains }}</el-text>
          </el-descriptions-item>
          <el-descriptions-item label="报告状态">
            <el-tag :type="getStatusType(reportData.report_status)">
              {{ getStatusText(reportData.report_status) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 违规记录列表 -->
      <el-card class="violations-card">
        <template #header>
          <div class="card-header">
            <span>违规记录</span>
            <div class="header-controls">
              <el-select v-model="violationFilter.risk_level" placeholder="风险等级" clearable size="small">
                <el-option label="严重" value="critical" />
                <el-option label="高" value="high" />
                <el-option label="中" value="medium" />
                <el-option label="低" value="low" />
              </el-select>
              <el-select v-model="violationFilter.violation_type" placeholder="违规类型" clearable size="small">
                <el-option label="恶意软件" value="malware" />
                <el-option label="钓鱼网站" value="phishing" />
                <el-option label="违法内容" value="illegal_content" />
                <el-option label="版权侵犯" value="copyright_violation" />
                <el-option label="其他" value="other" />
              </el-select>
              <el-button type="primary" size="small" @click="searchViolations">
                <el-icon><Search /></el-icon>
                搜索
              </el-button>
            </div>
          </div>
        </template>

        <el-table :data="violations" v-loading="violationsLoading">
          <el-table-column prop="domain" label="域名" min-width="200">
            <template #default="{ row }">
              <el-text class="domain-id-text">域名ID: {{ row.domain_id }}</el-text>
            </template>
          </el-table-column>

          <el-table-column prop="violation_type" label="违规类型" width="120">
            <template #default="{ row }">
              <el-tag size="small">{{ getViolationTypeText(row.violation_type) }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="risk_level" label="风险等级" width="100">
            <template #default="{ row }">
              <el-tag :type="getRiskType(row.risk_level)" size="small">
                {{ getRiskText(row.risk_level) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="confidence_score" label="置信度" width="100">
            <template #default="{ row }">
              <el-progress 
                :percentage="Math.round(row.confidence_score * 100)" 
                :stroke-width="6"
                :color="getConfidenceColor(row.confidence_score)"
              />
            </template>
          </el-table-column>

          <el-table-column prop="description" label="描述" min-width="300">
            <template #default="{ row }">
              <el-text class="reasoning-text">{{ row.description }}</el-text>
            </template>
          </el-table-column>

          <el-table-column prop="evidence" label="证据" width="150">
            <template #default="{ row }">
              <el-tag 
                v-for="(evidence, index) in (row.evidence || []).slice(0, 2)" 
                :key="index"
                size="small"
                class="evidence-tag"
              >
                {{ evidence }}
              </el-tag>
              <el-text v-if="(row.evidence || []).length > 2" type="info" size="small">
                +{{ (row.evidence || []).length - 2 }} 更多
              </el-text>
            </template>
          </el-table-column>

          <el-table-column prop="detected_at" label="发现时间" width="150">
            <template #default="{ row }">
              {{ formatTime(row.detected_at) }}
            </template>
          </el-table-column>

          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button 
                type="text" 
                size="small"
                @click="viewViolationDetail(row)"
              >
                查看详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 违规记录分页 -->
        <div class="pagination-container">
          <el-pagination
            v-model:current-page="violationPagination.page"
            v-model:page-size="violationPagination.size"
            :page-sizes="[10, 20, 50]"
            :total="violationPagination.total"
            layout="total, sizes, prev, pager, next"
            @size-change="handleViolationSizeChange"
            @current-change="handleViolationCurrentChange"
          />
        </div>
      </el-card>
    </div>

    <!-- 违规详情对话框 -->
    <el-dialog
      v-model="violationDetailVisible"
      title="违规详情"
      width="70%"
      :close-on-click-modal="false"
    >
      <div v-if="selectedViolation">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="域名ID">
            <el-text>{{ selectedViolation.domain_id }}</el-text>
          </el-descriptions-item>
          <el-descriptions-item label="违规类型">
            <el-tag>{{ getViolationTypeText(selectedViolation.violation_type) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag :type="getRiskType(selectedViolation.risk_level)">
              {{ getRiskText(selectedViolation.risk_level) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="置信度">
            {{ Math.round(selectedViolation.confidence_score * 100) }}%
          </el-descriptions-item>
          <el-descriptions-item label="描述">
            {{ selectedViolation.description }}
          </el-descriptions-item>
          <el-descriptions-item label="证据列表">
            <el-tag 
              v-for="(evidence, index) in selectedViolation.evidence || []" 
              :key="index"
              size="small"
              class="evidence-tag"
            >
              {{ evidence }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="发现时间">
            {{ formatTime(selectedViolation.detected_at) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>

    <!-- 截图查看对话框 -->
    <!-- 注意：当前违规记录类型中不包含screenshot_url属性，此功能暂时禁用 -->
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { reportAPI } from '@/api/report'
import type { ScanReport, ViolationRecord } from '@/types/api'
import { formatTime } from '@/utils/date'

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
const violationsLoading = ref(false)
const violationDetailVisible = ref(false)

const reportData = ref<ScanReport | null>(null)
const violations = ref<ViolationRecord[]>([])
const selectedViolation = ref<ViolationRecord | null>(null)

// 违规记录筛选和分页
const violationFilter = reactive({
  risk_level: undefined as string | undefined,
  violation_type: undefined as string | undefined
})

const violationPagination = reactive({
  page: 1,
  size: 20,
  total: 0
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

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return '#67c23a'
  if (confidence >= 0.6) return '#e6a23c'
  return '#f56c6c'
}

const fetchReportData = async () => {
  try {
    loading.value = true
    const response = await reportAPI.getScanReport(props.taskId)
    
    if (response.data.success) {
      reportData.value = response.data.data || null
    }
  } catch (error) {
    console.error('获取报告数据失败:', error)
    ElMessage.error('获取报告数据失败')
  } finally {
    loading.value = false
  }
}

const fetchViolations = async () => {
  try {
    violationsLoading.value = true
    
    const response = await reportAPI.getViolations(
      props.taskId,
      (violationPagination.page - 1) * violationPagination.size,
      violationPagination.size,
      violationFilter.risk_level,
      violationFilter.violation_type
    )
    
    if (response.data.success) {
      violations.value = response.data.data?.items || []
      violationPagination.total = response.data.data?.total || 0
    }
  } catch (error) {
    console.error('获取违规记录失败:', error)
    ElMessage.error('获取违规记录失败')
  } finally {
    violationsLoading.value = false
  }
}

const searchViolations = () => {
  violationPagination.page = 1
  fetchViolations()
}

const handleViolationSizeChange = (size: number) => {
  violationPagination.size = size
  violationPagination.page = 1
  fetchViolations()
}

const handleViolationCurrentChange = (page: number) => {
  violationPagination.page = page
  fetchViolations()
}

const viewViolationDetail = (violation: ViolationRecord) => {
  selectedViolation.value = violation
  violationDetailVisible.value = true
}

// 监听 taskId 变化
watch(
  () => props.taskId,
  () => {
    if (props.taskId) {
      fetchReportData()
      fetchViolations()
    }
  },
  { immediate: true }
)

// 生命周期
onMounted(() => {
  if (props.taskId) {
    fetchReportData()
    fetchViolations()
  }
})
</script>

<style scoped>
.report-detail {
  min-height: 400px;
}

.info-card {
  margin-bottom: 20px;
}

.violations-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

.reasoning-text {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  line-height: 1.4;
  max-width: 300px;
}

.evidence-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.screenshot-container {
  text-align: center;
}

.screenshot-image {
  max-width: 100%;
  max-height: 600px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
    gap: 12px;
  }
  
  .header-controls {
    width: 100%;
    flex-wrap: wrap;
  }
  
  .reasoning-text {
    max-width: 200px;
  }
}
</style>