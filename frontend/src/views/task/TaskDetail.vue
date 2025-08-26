<template>
  <div class="task-detail">
    <div class="page-header">
      <el-button @click="$router.back()" type="text">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <h2>任务详情 #{{ taskId }}</h2>
    </div>

    <el-row :gutter="20">
      <!-- 任务基本信息 -->
      <el-col :span="24">
        <el-card v-loading="loading">
          <template #header>
            <div class="card-header">
              <span>基本信息</span>
              <el-tag :type="getStatusType(task.status)">
                {{ getStatusText(task.status) }}
              </el-tag>
            </div>
          </template>
          
          <el-descriptions :column="3" border>
            <el-descriptions-item label="目标域名">
              <span class="domain-name">{{ task.target_domain }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="任务状态">
              <el-tag :type="getStatusType(task.status)" size="small">
                {{ getStatusText(task.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="执行进度">
              <el-progress :percentage="task.progress" />
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ task.created_at ? formatTime(task.created_at) : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="开始时间">
              {{ task.started_at ? formatTime(task.started_at) : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="完成时间">
              {{ task.completed_at ? formatTime(task.completed_at) : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="发现子域名">
              <el-tag type="info">{{ (task.total_subdomains || task.statistics?.total_subdomains || 0) }}个</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="扫描页面">
              <el-tag type="info">{{ (task.total_pages_crawled || task.statistics?.total_pages_crawled || 0) }}个</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="检测违规">
              <el-tag :type="(task.total_violations || task.statistics?.total_violations || 0) > 0 ? 'danger' : 'success'">
                {{ (task.total_violations || task.statistics?.total_violations || 0) }}个
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 子域名列表 -->
      <el-col :span="12">
        <el-card v-loading="subdomainsLoading">
          <template #header>
            <span>发现的子域名 ({{ subdomains.length || task.total_subdomains || task.statistics?.total_subdomains || 0 }})</span>
          </template>
          <div class="subdomain-list">
            <div 
              v-for="subdomain in subdomains" 
              :key="subdomain.id"
              class="subdomain-item"
            >
              <div class="subdomain-info">
                <span class="subdomain-name">{{ subdomain.subdomain }}</span>
                <el-tag :type="subdomain.is_accessible ? 'success' : 'danger'" size="small">
                  {{ subdomain.is_accessible ? '可访问' : '不可访问' }}
                </el-tag>
              </div>
              <div class="subdomain-meta">
                <span class="ip">{{ subdomain.ip_address || '-' }}</span>
                <span class="method">{{ subdomain.discovery_method }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 违规检测结果 -->
      <el-col :span="12">
        <el-card v-loading="violationsLoading">
          <template #header>
            <span>违规检测结果 ({{ violations.length || task.total_violations || task.statistics?.total_violations || 0 }})</span>
          </template>
          <div class="violation-list">
            <div 
              v-for="violation in violations" 
              :key="violation.id"
              class="violation-item"
            >
              <div class="violation-header">
                <span class="violation-title">{{ violation.title }}</span>
                <el-tag :type="getRiskType(violation.risk_level)" size="small">
                  {{ getRiskText(violation.risk_level) }}风险
                </el-tag>
              </div>
              <div class="violation-content">
                <p class="violation-desc">{{ violation.description }}</p>
                <div class="violation-meta">
                  <span class="confidence">置信度: {{ Math.round(violation.confidence_score * 100) }}%</span>
                  <span class="domain">域名: {{ getDomainName(violation.domain_id) }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 执行日志 -->
    <el-row style="margin-top: 20px;">
      <el-col :span="24">
        <el-card v-loading="logsLoading">
          <template #header>
            <span>执行日志</span>
          </template>
          <div class="log-container">
            <div 
              v-for="log in logs" 
              :key="log.id"
              class="log-item"
              :class="log.level.toLowerCase()"
            >
              <span class="log-time">{{ formatTime(log.created_at) }}</span>
              <span class="log-level">{{ log.level }}</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { taskAPI } from '@/api/task'
import type { Task, SubdomainRecord, ViolationRecord, TaskLog, ThirdPartyDomain } from '@/types/api'

const route = useRoute()
const taskId = route.params.id

// 响应式状态
const loading = ref(false)
const subdomainsLoading = ref(false)
const violationsLoading = ref(false)
const logsLoading = ref(false)

const task = ref<Task>({} as Task)
const subdomains = ref<SubdomainRecord[]>([])
const violations = ref<ViolationRecord[]>([])
const logs = ref<TaskLog[]>([])
const thirdPartyDomains = ref<ThirdPartyDomain[]>([])

// 方法
const getStatusType = (status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const statusMap: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return statusMap[status] || status
}

const getRiskType = (risk: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const riskMap: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    'critical': 'danger',
    'high': 'danger',
    'medium': 'warning',
    'low': 'info'
  }
  return riskMap[risk] || 'info'
}

const getRiskText = (risk: string) => {
  const riskMap: Record<string, string> = {
    'critical': '严重',
    'high': '高',
    'medium': '中',
    'low': '低'
  }
  return riskMap[risk] || risk
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

// 根据domain_id获取域名名称
const getDomainName = (domainId: string) => {
  const domain = thirdPartyDomains.value.find(d => d.id === domainId)
  return domain ? domain.domain : '-'
}

// 获取任务详情
const fetchTaskDetail = async () => {
  try {
    loading.value = true
    const response = await taskAPI.getTask(taskId as string)
    if (response.data.success) {
      task.value = response.data.data || {} as Task
    }
  } catch (error) {
    console.error('获取任务详情失败:', error)
    ElMessage.error('获取任务详情失败')
  } finally {
    loading.value = false
  }
}

// 获取子域名列表
const fetchSubdomains = async () => {
  try {
    subdomainsLoading.value = true
    const response = await taskAPI.getSubdomains(taskId as string)
    if (response.data.success) {
      subdomains.value = response.data.data?.items || []
    }
  } catch (error) {
    console.error('获取子域名列表失败:', error)
    ElMessage.error('获取子域名列表失败')
  } finally {
    subdomainsLoading.value = false
  }
}

// 获取违规记录
const fetchViolations = async () => {
  try {
    violationsLoading.value = true
    const response = await taskAPI.getViolations(taskId as string)
    if (response.data.success) {
      violations.value = response.data.data?.items || []
    }
  } catch (error) {
    console.error('获取违规记录失败:', error)
    ElMessage.error('获取违规记录失败')
  } finally {
    violationsLoading.value = false
  }
}

// 获取任务日志
const fetchLogs = async () => {
  try {
    logsLoading.value = true
    const response = await taskAPI.getTaskLogs(taskId as string)
    if (response.data.success) {
      logs.value = response.data.data?.items || []
    }
  } catch (error) {
    console.error('获取任务日志失败:', error)
    ElMessage.error('获取任务日志失败')
  } finally {
    logsLoading.value = false
  }
}

// 获取第三方域名
const fetchThirdPartyDomains = async () => {
  try {
    const response = await taskAPI.getThirdPartyDomains(taskId as string)
    if (response.data.success) {
      thirdPartyDomains.value = response.data.data?.items || []
    }
  } catch (error) {
    console.error('获取第三方域名失败:', error)
    ElMessage.error('获取第三方域名失败')
  }
}

onMounted(() => {
  if (taskId) {
    fetchTaskDetail()
    fetchSubdomains()
    fetchViolations()
    fetchLogs()
    fetchThirdPartyDomains()
  }
})
</script>

<style scoped>
.task-detail {
  padding: 0;
}

.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  gap: 12px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.domain-name {
  font-weight: 500;
  color: #409eff;
}

.subdomain-list {
  max-height: 400px;
  overflow-y: auto;
}

.subdomain-item {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.subdomain-item:last-child {
  border-bottom: none;
}

.subdomain-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.subdomain-name {
  font-weight: 500;
  color: #333;
}

.subdomain-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #999;
}

.violation-list {
  max-height: 400px;
  overflow-y: auto;
}

.violation-item {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.violation-item:last-child {
  border-bottom: none;
}

.violation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.violation-title {
  font-weight: 500;
  color: #333;
}

.violation-desc {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #666;
  line-height: 1.4;
}

.violation-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #999;
}

.log-container {
  max-height: 400px;
  overflow-y: auto;
  background-color: #f8f9fa;
  padding: 12px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.log-item {
  display: flex;
  gap: 12px;
  margin-bottom: 4px;
  padding: 2px 0;
}

.log-time {
  color: #999;
  min-width: 120px;
}

.log-level {
  min-width: 50px;
  font-weight: 600;
}

.log-item.info .log-level {
  color: #409eff;
}

.log-item.warn .log-level {
  color: #e6a23c;
}

.log-item.error .log-level {
  color: #f56c6c;
}

.log-message {
  flex: 1;
  color: #333;
}
</style>