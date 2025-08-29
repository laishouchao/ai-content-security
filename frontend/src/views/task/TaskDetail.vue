<template>
  <div class="task-detail">
    <div class="page-header">
      <el-button @click="$router.back()" type="text">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <h2>任务详情 #{{ taskId }}</h2>
    </div>

    <!-- 任务基本信息卡片 -->
    <el-card v-loading="loading" class="task-info-card">
      <template #header>
        <div class="card-header">
          <span>基本信息</span>
          <div class="task-actions">
            <el-tag :type="getStatusType(task.status)" size="large">
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
      
      <el-row :gutter="20">
        <el-col :span="18">
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
              <el-progress :percentage="task.progress || 0" />
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
          </el-descriptions>
        </el-col>
        <el-col :span="6">
          <!-- 实时统计 -->
          <div class="stats-summary">
            <div class="stat-item">
              <div class="stat-value">{{ domainStats.total_domains || 0 }}</div>
              <div class="stat-label">发现域名总数</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ domainStats.accessible_count || 0 }}</div>
              <div class="stat-label">可访问域名</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ domainStats.violation_count || 0 }}</div>
              <div class="stat-label">违规域名</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ task.total_pages_crawled || 0 }}</div>
              <div class="stat-label">爬取页面</div>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 主要内容选项卡 -->
    <el-card class="content-tabs-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        
        <!-- 需要扫描的域名选项卡 -->
        <el-tab-pane label="需要扫描的域名" name="scan-domains">
          <div class="tab-content">
            <div class="filter-section">
              <el-row :gutter="16" align="middle">
                <el-col :span="6">
                  <el-select v-model="scanDomainFilters.status" placeholder="状态筛选" clearable>
                    <el-option label="已发现" value="discovered" />
                    <el-option label="可访问" value="accessible" />
                    <el-option label="不可访问" value="inaccessible" />
                  </el-select>
                </el-col>
                <el-col :span="6">
                  <el-select v-model="scanDomainFilters.category" placeholder="类型筛选" clearable>
                    <el-option label="目标主域名" value="target_main" />
                    <el-option label="目标子域名" value="target_subdomain" />
                  </el-select>
                </el-col>
                <el-col :span="8">
                  <el-input
                    v-model="scanDomainFilters.search"
                    placeholder="搜索域名..."
                    clearable
                  />
                </el-col>
                <el-col :span="4">
                  <el-button type="primary" @click="refreshScanDomains" :loading="scanDomainsLoading">
                    <el-icon><Refresh /></el-icon>
                    刷新
                  </el-button>
                </el-col>
              </el-row>
            </div>

            <div class="stats-row">
              <el-tag type="info">待扫描: {{ filteredScanDomains.length }}</el-tag>
              <el-tag type="success">可访问: {{ scanDomainStats.accessible }}</el-tag>
              <el-tag type="warning">不可访问: {{ scanDomainStats.inaccessible }}</el-tag>
            </div>

            <el-table :data="paginatedScanDomains" v-loading="scanDomainsLoading" stripe>
              <el-table-column prop="domain" label="域名" sortable />
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="getDomainStatusType(row.status)" size="small">
                    {{ getDomainStatusText(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="is_accessible" label="可访问性" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.is_accessible ? 'success' : 'danger'" size="small">
                    {{ row.is_accessible ? '是' : '否' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="discovery_method" label="发现方式" width="120" />
              <el-table-column prop="ip_address" label="IP地址" width="120" />
              <el-table-column prop="first_discovered_at" label="发现时间" width="150">
                <template #default="{ row }">
                  {{ row.first_discovered_at ? formatTime(row.first_discovered_at) : '-' }}
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 检测到的所有域名选项卡 -->
        <el-tab-pane label="检测到的所有域名" name="all-domains">
          <div class="tab-content">
            <div class="filter-section">
              <el-row :gutter="16" align="middle">
                <el-col :span="5">
                  <el-select v-model="allDomainFilters.category" placeholder="域名类型" clearable>
                    <el-option label="目标主域名" value="target_main" />
                    <el-option label="目标子域名" value="target_subdomain" />
                    <el-option label="第三方域名" value="third_party" />
                  </el-select>
                </el-col>
                <el-col :span="5">
                  <el-select v-model="allDomainFilters.risk_level" placeholder="风险等级" clearable>
                    <el-option label="高" value="high" />
                    <el-option label="中" value="medium" />
                    <el-option label="低" value="low" />
                  </el-select>
                </el-col>
                <el-col :span="6">
                  <el-input
                    v-model="allDomainFilters.search"
                    placeholder="搜索域名..."
                    clearable
                  />
                </el-col>
                <el-col :span="4">
                  <el-button type="primary" @click="refreshAllDomains" :loading="allDomainsLoading">
                    <el-icon><Refresh /></el-icon>
                    刷新
                  </el-button>
                </el-col>
              </el-row>
            </div>

            <div class="stats-row">
              <el-tag type="info">总计: {{ filteredAllDomains.length }}</el-tag>
              <el-tag type="warning">目标相关: {{ allDomainStats.target_related }}</el-tag>
              <el-tag type="primary">第三方: {{ allDomainStats.third_party }}</el-tag>
              <el-tag type="danger">有违规: {{ allDomainStats.violations }}</el-tag>
            </div>

            <el-table :data="paginatedAllDomains" v-loading="allDomainsLoading" stripe>
              <el-table-column prop="domain" label="域名" sortable />
              <el-table-column prop="category" label="类型" width="100">
                <template #default="{ row }">
                  <el-tag :type="getCategoryType(row.category)" size="small">
                    {{ getCategoryText(row.category) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="risk_level" label="风险" width="80">
                <template #default="{ row }">
                  <el-tag :type="getRiskType(row.risk_level)" size="small">
                    {{ getRiskText(row.risk_level) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="违规" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.has_violations ? 'danger' : 'success'" size="small">
                    {{ row.has_violations ? '是' : '否' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="page_title" label="页面标题" show-overflow-tooltip />
              <el-table-column prop="first_discovered_at" label="发现时间" width="150">
                <template #default="{ row }">
                  {{ row.first_discovered_at ? formatTime(row.first_discovered_at) : '-' }}
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 运行日志选项卡 -->
        <el-tab-pane label="运行日志" name="logs">
          <div class="tab-content">
            <div class="filter-section">
              <el-row :gutter="16" align="middle">
                <el-col :span="4">
                  <el-select v-model="logFilters.level" placeholder="日志级别" clearable>
                    <el-option label="INFO" value="info" />
                    <el-option label="WARN" value="warn" />
                    <el-option label="ERROR" value="error" />
                  </el-select>
                </el-col>
                <el-col :span="8">
                  <el-input
                    v-model="logFilters.search"
                    placeholder="搜索日志内容..."
                    clearable
                  />
                </el-col>
                <el-col :span="4">
                  <el-button type="primary" @click="refreshLogs" :loading="logsLoading">
                    <el-icon><Refresh /></el-icon>
                    刷新
                  </el-button>
                </el-col>
                <el-col :span="4">
                  <el-switch
                    v-model="autoRefreshLogs"
                    active-text="自动刷新"
                    @change="toggleAutoRefresh"
                  />
                </el-col>
              </el-row>
            </div>

            <div class="stats-row">
              <el-tag type="info">总计: {{ filteredLogs.length }}</el-tag>
              <el-tag type="success">INFO: {{ logStats.info }}</el-tag>
              <el-tag type="warning">WARN: {{ logStats.warn }}</el-tag>
              <el-tag type="danger">ERROR: {{ logStats.error }}</el-tag>
            </div>

            <div class="log-container">
              <div 
                v-for="log in paginatedLogs" 
                :key="log.id"
                class="log-item"
                :class="log.level.toLowerCase()"
              >
                <span class="log-time">{{ formatTime(log.created_at) }}</span>
                <span class="log-level">{{ log.level }}</span>
                <span class="log-message">{{ log.message }}</span>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Close, Refresh, Delete, Search } from '@element-plus/icons-vue'
import { taskAPI, type Task } from '@/api/task'
import type { SubdomainRecord, ViolationRecord, TaskLog, ThirdPartyDomain } from '@/types/api'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id

// 基本状态
const loading = ref(false)
const cancelling = ref(false)
const retrying = ref(false)
const deleting = ref(false)
const task = ref<Task>({} as Task)

// 选项卡状态
const activeTab = ref('scan-domains')

// 域名数据和加载状态
const scanDomainsLoading = ref(false)
const allDomainsLoading = ref(false)
const logsLoading = ref(false)
const scanDomains = ref<any[]>([])
const allDomains = ref<any[]>([])
const logs = ref<TaskLog[]>([])

// 过滤器
const scanDomainFilters = ref({
  status: '',
  category: '',
  search: ''
})

const allDomainFilters = ref({
  category: '',
  risk_level: '',
  has_violations: null as boolean | null,
  search: ''
})

const logFilters = ref({
  level: '',
  search: ''
})

// 分页状态
const scanDomainPagination = ref({
  page: 1,
  size: 20
})

const allDomainPagination = ref({
  page: 1,
  size: 20
})

const logPagination = ref({
  page: 1,
  size: 50
})

// 日志自动刷新
const autoRefreshLogs = ref(false)
let autoRefreshTimer: number | null = null

// 统计数据
const domainStats = ref({
  total_domains: 0,
  target_domains: 0,
  subdomain_count: 0,
  third_party_count: 0,
  accessible_count: 0,
  analyzed_count: 0,
  violation_count: 0
})

// 过滤和分页的计算属性
const filteredScanDomains = computed(() => {
  let filtered = scanDomains.value
  
  if (scanDomainFilters.value.status) {
    filtered = filtered.filter(d => d.status === scanDomainFilters.value.status)
  }
  if (scanDomainFilters.value.category) {
    filtered = filtered.filter(d => d.category === scanDomainFilters.value.category)
  }
  if (scanDomainFilters.value.search) {
    filtered = filtered.filter(d => d.domain.toLowerCase().includes(scanDomainFilters.value.search.toLowerCase()))
  }
  
  return filtered
})

const paginatedScanDomains = computed(() => {
  const start = (scanDomainPagination.value.page - 1) * scanDomainPagination.value.size
  const end = start + scanDomainPagination.value.size
  return filteredScanDomains.value.slice(start, end)
})

const filteredAllDomains = computed(() => {
  let filtered = allDomains.value
  
  if (allDomainFilters.value.category) {
    filtered = filtered.filter(d => d.category === allDomainFilters.value.category)
  }
  if (allDomainFilters.value.risk_level) {
    filtered = filtered.filter(d => d.risk_level === allDomainFilters.value.risk_level)
  }
  if (allDomainFilters.value.has_violations !== null) {
    filtered = filtered.filter(d => d.has_violations === allDomainFilters.value.has_violations)
  }
  if (allDomainFilters.value.search) {
    filtered = filtered.filter(d => d.domain.toLowerCase().includes(allDomainFilters.value.search.toLowerCase()))
  }
  
  return filtered
})

const paginatedAllDomains = computed(() => {
  const start = (allDomainPagination.value.page - 1) * allDomainPagination.value.size
  const end = start + allDomainPagination.value.size
  return filteredAllDomains.value.slice(start, end)
})

const filteredLogs = computed(() => {
  let filtered = logs.value
  
  if (logFilters.value.level) {
    filtered = filtered.filter(l => l.level.toLowerCase() === logFilters.value.level)
  }
  if (logFilters.value.search) {
    filtered = filtered.filter(l => l.message.toLowerCase().includes(logFilters.value.search.toLowerCase()))
  }
  
  return filtered
})

const paginatedLogs = computed(() => {
  const start = (logPagination.value.page - 1) * logPagination.value.size
  const end = start + logPagination.value.size
  return filteredLogs.value.slice(start, end)
})

// 统计计算属性
const scanDomainStats = computed(() => {
  return {
    accessible: filteredScanDomains.value.filter(d => d.is_accessible).length,
    inaccessible: filteredScanDomains.value.filter(d => !d.is_accessible).length,
    analyzed: filteredScanDomains.value.filter(d => d.is_analyzed).length
  }
})

const allDomainStats = computed(() => {
  return {
    target_related: filteredAllDomains.value.filter(d => d.category === 'target_main' || d.category === 'target_subdomain').length,
    third_party: filteredAllDomains.value.filter(d => d.category === 'third_party').length,
    violations: filteredAllDomains.value.filter(d => d.has_violations).length
  }
})

const logStats = computed(() => {
  return {
    info: filteredLogs.value.filter(l => l.level.toLowerCase() === 'info').length,
    warn: filteredLogs.value.filter(l => l.level.toLowerCase() === 'warn').length,
    error: filteredLogs.value.filter(l => l.level.toLowerCase() === 'error').length
  }
})
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

// 新的域名相关方法
const getDomainStatusType = (status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const statusMap: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    discovered: 'info',
    accessible: 'success',
    inaccessible: 'danger',
    analyzing: 'warning',
    analyzed: 'primary'
  }
  return statusMap[status] || 'info'
}

const getDomainStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    discovered: '已发现',
    accessible: '可访问',
    inaccessible: '不可访问',
    analyzing: '分析中',
    analyzed: '已分析'
  }
  return statusMap[status] || status
}

const getCategoryType = (category: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const categoryMap: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    target_main: 'danger',
    target_subdomain: 'warning',
    third_party: 'primary',
    unknown: 'info'
  }
  return categoryMap[category] || 'info'
}

const getCategoryText = (category: string) => {
  const categoryMap: Record<string, string> = {
    target_main: '主域名',
    target_subdomain: '子域名',
    third_party: '第三方',
    unknown: '未知'
  }
  return categoryMap[category] || category
}

const getDiscoveryMethodText = (method: string) => {
  const methodMap: Record<string, string> = {
    subdomain_enum: '子域名枚举',
    dns_lookup: 'DNS查询',
    certificate: '证书',
    link_crawling: '链接爬取',
    manual: '手动',
    third_party_scan: '第三方扫描'
  }
  return methodMap[method] || method
}

// 新的数据加载方法
const fetchScanDomains = async () => {
  try {
    scanDomainsLoading.value = true
    const response = await fetch(`/api/v1/tasks/${taskId}/scan-domains?${new URLSearchParams({
      skip: String((scanDomainPagination.value.page - 1) * scanDomainPagination.value.size),
      limit: String(scanDomainPagination.value.size),
      ...(scanDomainFilters.value.status && { status: scanDomainFilters.value.status }),
      ...(scanDomainFilters.value.category && { category: scanDomainFilters.value.category }),
      ...(scanDomainFilters.value.search && { search: scanDomainFilters.value.search })
    })}`)
    
    if (response.ok) {
      const data = await response.json()
      if (data.success) {
        scanDomains.value = data.data.items || []
      }
    }
  } catch (error) {
    console.error('获取扫描域名失败:', error)
    ElMessage.error('获取扫描域名失败')
  } finally {
    scanDomainsLoading.value = false
  }
}

const fetchAllDomains = async () => {
  try {
    allDomainsLoading.value = true
    const response = await fetch(`/api/v1/tasks/${taskId}/all-domains?${new URLSearchParams({
      skip: String((allDomainPagination.value.page - 1) * allDomainPagination.value.size),
      limit: String(allDomainPagination.value.size),
      ...(allDomainFilters.value.category && { category: allDomainFilters.value.category }),
      ...(allDomainFilters.value.risk_level && { risk_level: allDomainFilters.value.risk_level }),
      ...(allDomainFilters.value.search && { search: allDomainFilters.value.search })
    })}`)
    
    if (response.ok) {
      const data = await response.json()
      if (data.success) {
        allDomains.value = data.data.items || []
      }
    }
  } catch (error) {
    console.error('获取所有域名失败:', error)
    ElMessage.error('获取所有域名失败')
  } finally {
    allDomainsLoading.value = false
  }
}

// 获取统计数据
const fetchDomainStats = async () => {
  try {
    const response = await taskAPI.getDomainStats(taskId as string)
    if (response.data.success && response.data.data) {
      domainStats.value = {
        ...domainStats.value,
        ...response.data.data
      }
    }
  } catch (error) {
    console.error('获取域名统计失败:', error)
  }
}

// 刷新方法
const refreshScanDomains = () => {
  fetchScanDomains()
}

const refreshAllDomains = () => {
  fetchAllDomains()
}

const refreshLogs = () => {
  fetchLogs()
}

// 选项卡切换
const handleTabChange = (tabName: string | number) => {
  const name = String(tabName)
  if (name === 'scan-domains' && scanDomains.value.length === 0) {
    fetchScanDomains()
  } else if (name === 'all-domains' && allDomains.value.length === 0) {
    fetchAllDomains()
  } else if (name === 'logs' && logs.value.length === 0) {
    fetchLogs()
  }
}

// 分页处理
const handleScanDomainPageChange = (page: number) => {
  scanDomainPagination.value.page = page
}

const handleScanDomainSizeChange = (size: number) => {
  scanDomainPagination.value.size = size
  scanDomainPagination.value.page = 1
}

const handleAllDomainPageChange = (page: number) => {
  allDomainPagination.value.page = page
}

const handleAllDomainSizeChange = (size: number) => {
  allDomainPagination.value.size = size
  allDomainPagination.value.page = 1
}

// 排序处理
const handleScanDomainSort = (sort: any) => {
  // TODO: 实现排序逻辑
}

const handleAllDomainSort = (sort: any) => {
  // TODO: 实现排序逻辑
}

// 操作方法
const viewDomainDetail = (domain: any) => {
  // TODO: 实现域名详情查看
  ElMessage.info(`查看域名详情: ${domain.domain}`)
}

const viewViolations = (domain: any) => {
  // TODO: 实现违规详情查看
  ElMessage.info(`查看违规详情: ${domain.domain}`)
}

// 自动刷新日志
const toggleAutoRefresh = (enabled: string | number | boolean) => {
  const isEnabled = Boolean(enabled)
  if (isEnabled) {
    autoRefreshTimer = window.setInterval(() => {
      if (activeTab.value === 'logs') {
        fetchLogs()
      }
    }, 5000) // 每5秒刷新一次
  } else {
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer)
      autoRefreshTimer = null
    }
  }
}

// 清空过滤器
const clearLogFilters = () => {
  logFilters.value = {
    level: '',
    search: ''
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
    fetchDomainStats() // 加载域名统计数据
    fetchLogs() // 默认加载日志
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

.task-info-card {
  margin-bottom: 20px;
}

.content-tabs-card {
  min-height: 600px;
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

/* 统计卡片样式 */
.stats-summary {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  color: white;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  opacity: 0.9;
}

/* 选项卡内容样式 */
.tab-content {
  padding: 20px 0;
}

.filter-section {
  margin-bottom: 20px;
  padding: 16px;
  background-color: #f8f9fa;
  border-radius: 6px;
}

.stats-row {
  margin-bottom: 20px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

/* 域名链接样式 */
.domain-link {
  color: #409eff;
  font-weight: 500;
  cursor: pointer;
}

.domain-link:hover {
  text-decoration: underline;
}

/* 日志容器样式 */
.log-container {
  max-height: 500px;
  overflow-y: auto;
  background-color: #f8f9fa;
  padding: 16px;
  border-radius: 6px;
  font-family: 'Courier New', 'Monaco', 'Menlo', monospace;
  font-size: 13px;
  line-height: 1.4;
}

.log-item {
  display: flex;
  gap: 12px;
  margin-bottom: 4px;
  padding: 4px 0;
  border-bottom: 1px solid #e9ecef;
}

.log-item:last-child {
  border-bottom: none;
}

.log-time {
  color: #6c757d;
  min-width: 140px;
  font-size: 11px;
}

.log-level {
  min-width: 60px;
  font-weight: 600;
  text-transform: uppercase;
}

.log-item.info .log-level {
  color: #17a2b8;
}

.log-item.warn .log-level {
  color: #ffc107;
}

.log-item.error .log-level {
  color: #dc3545;
}

.log-item.debug .log-level {
  color: #6c757d;
}

.log-message {
  flex: 1;
  color: #212529;
  word-break: break-word;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .stats-summary {
    flex-direction: row;
    justify-content: space-around;
  }
  
  .filter-section .el-row {
    flex-direction: column;
  }
  
  .filter-section .el-col {
    margin-bottom: 12px;
  }
}

/* 表格样式优化 */
:deep(.el-table) {
  font-size: 13px;
}

:deep(.el-table .el-table__header th) {
  background-color: #f8f9fa;
  color: #495057;
  font-weight: 600;
}

:deep(.el-table .el-table__row:hover > td) {
  background-color: #f8f9fa;
}

/* 选项卡样式优化 */
:deep(.el-tabs__header) {
  margin-bottom: 0;
}

:deep(.el-tabs__nav-wrap) {
  padding: 0 20px;
  background-color: #fafafa;
}

:deep(.el-tabs__item) {
  font-weight: 500;
  color: #606266;
}

:deep(.el-tabs__item.is-active) {
  color: #409eff;
  font-weight: 600;
}

:deep(.el-tabs__content) {
  padding: 0 20px 20px;
}
</style>