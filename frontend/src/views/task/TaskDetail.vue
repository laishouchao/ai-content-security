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
              <div class="task-actions">
                <el-tag :type="getStatusType(task.status)">
                  {{ getStatusText(task.status) }}
                </el-tag>
                <!-- 任务操作按钮 -->
                <div class="action-buttons">
                  <el-button 
                    v-if="canCancelTask(task.status)" 
                    type="warning" 
                    size="small" 
                    :loading="cancelling"
                    @click="cancelTask"
                  >
                    <el-icon><Close /></el-icon>
                    取消任务
                  </el-button>
                  <el-button 
                    v-if="canRetryTask(task.status)" 
                    type="primary" 
                    size="small" 
                    :loading="retrying"
                    @click="retryTask"
                  >
                    <el-icon><Refresh /></el-icon>
                    重试任务
                  </el-button>
                  <el-button 
                    v-if="canDeleteTask(task.status)" 
                    type="danger" 
                    size="small" 
                    :loading="deleting"
                    @click="deleteTask"
                  >
                    <el-icon><Delete /></el-icon>
                    删除任务
                  </el-button>
                </div>
              </div>
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
              <el-tag type="info">{{ (task.total_subdomains || 0) }}个</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="扫描页面">
              <el-tag type="info">{{ (task.total_pages_crawled || 0) }}个</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="检测违规">
              <el-tag :type="(task.total_violations || 0) > 0 ? 'danger' : 'success'">
                {{ (task.total_violations || 0) }}个
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
            <span>发现的子域名 ({{ subdomains.length || task.total_subdomains || 0 }})</span>
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

      <!-- 第三方域名列表 -->
      <el-col :span="12">
        <el-card v-loading="domainsLoading">
          <template #header>
            <span>第三方域名 ({{ thirdPartyDomains.length || task.total_third_party_domains || 0 }})</span>
          </template>
          <div class="domain-list">
            <div 
              v-for="domain in thirdPartyDomains" 
              :key="domain.id"
              class="domain-item"
            >
              <div class="domain-header">
                <span class="domain-name">{{ domain.domain }}</span>
                <div class="domain-tags">
                  <!-- 违规标签 -->
                  <el-tag 
                    v-if="domain.has_violations" 
                    :type="getRiskType(domain.risk_level)" 
                    size="small"
                  >
                    {{ getRiskText(domain.risk_level) }}风险
                  </el-tag>
                  <!-- 未违规标签 -->
                  <el-tag v-else type="success" size="small">合规</el-tag>
                  <!-- 域名类型标签 -->
                  <el-tag type="info" size="small">{{ getDomainTypeText(domain.domain_type) }}</el-tag>
                </div>
              </div>
              <div class="domain-content">
                <p class="domain-desc">{{ domain.page_title || '无标题' }}</p>
                <div class="domain-meta">
                  <span class="found-url">发现于: {{ domain.found_on_url }}</span>
                  <span class="analyzed-status">
                    {{ domain.is_analyzed ? '已分析' : '未分析' }}
                  </span>
                </div>
                <!-- 违规详情 -->
                <div v-if="domain.has_violations && domain.violations && domain.violations.length > 0" class="violation-details">
                  <div 
                    v-for="violation in domain.violations" 
                    :key="violation.id"
                    class="violation-item"
                  >
                    <div class="violation-header">
                      <span class="violation-title">{{ violation.title }}</span>
                      <el-tag :type="getRiskType(violation.risk_level)" size="small">
                        {{ getRiskText(violation.risk_level) }}风险
                      </el-tag>
                    </div>
                    <p class="violation-desc">{{ violation.description }}</p>
                    <div class="violation-meta">
                      <span class="confidence">置信度: {{ Math.round(violation.confidence_score * 100) }}%</span>
                      <span class="violation-type">{{ getViolationTypeText(violation.violation_type) }}</span>
                    </div>
                  </div>
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
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Close, Refresh, Delete } from '@element-plus/icons-vue'
import { taskAPI, type Task } from '@/api/task'
import type { SubdomainRecord, ViolationRecord, TaskLog, ThirdPartyDomain } from '@/types/api'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id

// 响应式状态
const loading = ref(false)
const subdomainsLoading = ref(false)
const domainsLoading = ref(false)
const logsLoading = ref(false)
const cancelling = ref(false)
const retrying = ref(false)
const deleting = ref(false)

const task = ref<Task>({} as Task)
const subdomains = ref<SubdomainRecord[]>([])
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

// 域名类型文本映射
const getDomainTypeText = (type: string) => {
  const typeMap: Record<string, string> = {
    'cdn': 'CDN',
    'analytics': '分析',
    'advertising': '广告',
    'social': '社交',
    'api': 'API',
    'payment': '支付',
    'security': '安全',
    'unknown': '未知'
  }
  return typeMap[type] || type
}

// 违规类型文本映射
const getViolationTypeText = (type: string) => {
  const typeMap: Record<string, string> = {
    'nsfw': '色情内容',
    'violence': '暴力内容',
    'gambling': '赌博',
    'fraud': '诈骗',
    'malware': '恶意软件',
    'hate_speech': '仇恨言论',
    'copyright': '侵权',
    'other': '其他'
  }
  return typeMap[type] || type
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

// 获取任务详情
const fetchTaskDetail = async () => {
  try {
    loading.value = true
    const response = await taskAPI.getTask(taskId as string)
    if (response.data.success) {
      task.value = response.data.data || ({} as Partial<Task> as Task)
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

// 获取第三方域名列表
const fetchThirdPartyDomains = async () => {
  try {
    domainsLoading.value = true
    const response = await taskAPI.getThirdPartyDomains(taskId as string)
    if (response.data.success) {
      // 获取第三方域名列表
      const domains = response.data.data?.items || []
      
      // 为每个域名添加has_violations属性
      const domainsWithViolations = domains.map(domain => ({
        ...domain,
        has_violations: domain.violations && domain.violations.length > 0
      }))
      
      thirdPartyDomains.value = domainsWithViolations
    }
  } catch (error) {
    console.error('获取第三方域名失败:', error)
    ElMessage.error('获取第三方域名失败')
  } finally {
    domainsLoading.value = false
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

// 任务状态判断方法
const canCancelTask = (status: string) => {
  return status === 'pending' || status === 'running'
}

const canRetryTask = (status: string) => {
  return status === 'failed' || status === 'cancelled'
}

const canDeleteTask = (status: string) => {
  return status === 'completed' || status === 'failed' || status === 'cancelled'
}

// 任务操作方法
const cancelTask = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要取消这个任务吗？取消后任务将停止执行。',
      '确认取消任务',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    cancelling.value = true
    const response = await taskAPI.stopTask(taskId as string)
    
    if (response.data.success) {
      ElMessage.success('任务已成功取消')
      // 刷新任务详情
      await fetchTaskDetail()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('取消任务失败:', error)
      ElMessage.error('取消任务失败')
    }
  } finally {
    cancelling.value = false
  }
}

const retryTask = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要重试这个任务吗？任务将重新开始执行。',
      '确认重试任务',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
    
    retrying.value = true
    const response = await taskAPI.retryTask(taskId as string)
    
    if (response.data.success) {
      ElMessage.success('任务已重新启动')
      // 刷新任务详情
      await fetchTaskDetail()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('重试任务失败:', error)
      ElMessage.error('重试任务失败')
    }
  } finally {
    retrying.value = false
  }
}

const deleteTask = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个任务吗？删除后任务的所有数据将被永久移除，此操作不可撤销。',
      '确认删除任务',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'error'
      }
    )
    
    deleting.value = true
    const response = await taskAPI.deleteTask(taskId as string)
    
    if (response.data.success) {
      ElMessage.success('任务已成功删除')
      // 返回任务列表页面
      router.push('/tasks')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除任务失败:', error)
      ElMessage.error('删除任务失败')
    }
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  if (taskId) {
    fetchTaskDetail()
    fetchSubdomains()
    fetchThirdPartyDomains()
    fetchLogs()
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

.task-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.action-buttons {
  display: flex;
  gap: 8px;
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

.domain-list {
  max-height: 400px;
  overflow-y: auto;
}

.domain-item {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.domain-item:last-child {
  border-bottom: none;
}

.domain-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.domain-name {
  font-weight: 500;
  color: #333;
}

.domain-tags {
  display: flex;
  gap: 6px;
}

.domain-content {
  margin-left: 12px;
}

.domain-desc {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #666;
  line-height: 1.4;
}

.domain-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.found-url {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.analyzed-status {
  min-width: 50px;
}

.violation-details {
  margin-top: 12px;
  padding: 10px;
  background-color: #fff5f5;
  border-radius: 4px;
  border-left: 3px solid #f56c6c;
}

.violation-item {
  padding: 8px 0;
}

.violation-item:not(:last-child) {
  border-bottom: 1px solid #f0f0f0;
}

.violation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.violation-title {
  font-weight: 500;
  color: #333;
}

.violation-desc {
  margin: 0 0 8px 0;
  font-size: 13px;
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