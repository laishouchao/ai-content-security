<template>
  <div class="domain-library">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2>域名库</h2>
        <p>管理和查看所有第三方域名及其识别结果</p>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="refreshDomains">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button @click="exportDomains('json')">
          <el-icon><Download /></el-icon>
          导出JSON
        </el-button>
        <el-button @click="exportDomains('csv')">
          <el-icon><Download /></el-icon>
          导出CSV
        </el-button>
        <el-button @click="exportDomains('excel')">
          <el-icon><Download /></el-icon>
          导出Excel
        </el-button>
        <el-button type="danger" @click="batchDelete" :disabled="selectedDomains.length === 0">
          <el-icon><Delete /></el-icon>
          批量删除
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-cards" v-if="stats">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #409eff;">
              <el-icon><Link /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total_domains }}</div>
              <div class="stat-label">总域名数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #67c23a;">
              <el-icon><Check /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.analyzed_domains }}</div>
              <div class="stat-label">已分析</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #e6a23c;">
              <el-icon><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.violation_domains }}</div>
              <div class="stat-label">有违规</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background-color: #f56c6c;">
              <el-icon><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.unanalyzed_domains }}</div>
              <div class="stat-label">未分析</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选器 -->
    <el-card class="filter-card">
      <el-form :model="filters" inline>
        <el-form-item label="域名">
          <el-input
            v-model="filters.domain"
            placeholder="搜索域名"
            clearable
            @keyup.enter="searchDomains"
          />
        </el-form-item>
        
        <el-form-item label="域名类型">
          <el-select v-model="filters.domain_type" placeholder="选择类型" clearable style="width: 60px">
            <el-option label="全部" value="" />
            <el-option label="CDN" value="cdn" />
            <el-option label="分析服务" value="analytics" />
            <el-option label="广告服务" value="advertising" />
            <el-option label="社交媒体" value="social" />
            <el-option label="API服务" value="api" />
            <el-option label="支付服务" value="payment" />
            <el-option label="安全服务" value="security" />
            <el-option label="地图服务" value="maps" />
            <el-option label="未知类型" value="unknown" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="风险等级">
          <el-select v-model="filters.risk_level" placeholder="选择风险等级" clearable style="width: 60px">
            <el-option label="全部" value="" />
            <el-option label="低风险" value="low" />
            <el-option label="中风险" value="medium" />
            <el-option label="高风险" value="high" />
            <el-option label="严重风险" value="critical" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="是否违规">
          <el-select v-model="filters.has_violations" placeholder="选择违规状态" clearable style="width: 60px">
            <el-option label="全部" value="" />
            <el-option label="有违规" value="true" />
            <el-option label="无违规" value="false" />
          </el-select>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="searchDomains">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 域名表格 -->
    <el-card>
      <el-table
        :data="domains"
        v-loading="loading"
        style="width: 100%"
        @row-click="viewDomainDetail"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="domain" label="域名" min-width="200">
          <template #default="{ row }">
            <div class="domain-cell">
              <span class="domain-name">{{ row.domain }}</span>
              <el-tag v-if="row.has_violations" type="danger" size="small">
                {{ row.violations?.length || 0 }}个违规
              </el-tag>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="domain_type" label="域名类型" width="120">
          <template #default="{ row }">
            <el-tag type="info" size="small">
              {{ getDomainTypeText(row.domain_type) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="risk_level" label="风险等级" width="120">
          <template #default="{ row }">
            <el-tag :type="getRiskType(row.risk_level)" size="small">
              {{ getRiskText(row.risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="is_analyzed" label="分析状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_analyzed ? 'success' : 'info'" size="small">
              {{ row.is_analyzed ? '已分析' : '未分析' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="识别时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              type="text"
              size="small"
              @click.stop="viewDomainDetail(row)"
            >
              查看详情
            </el-button>
            <el-button
              type="text"
              size="small"
              @click.stop="viewTask(row)"
            >
              查看任务
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search, Link, Check, Warning, CircleClose, Download, Delete } from '@element-plus/icons-vue'
import { domainAPI } from '@/api'
import type { ThirdPartyDomain, DomainFilter } from '@/types/api'
import { formatTime } from '@/utils/date'

const router = useRouter()

// 响应式状态
const loading = ref(false)
const stats = ref<any>(null)
const selectedDomains = ref<ThirdPartyDomain[]>([])

const filters = reactive<DomainFilter>({
  domain: undefined,
  domain_type: undefined,
  risk_level: undefined,
  has_violations: undefined
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const domains = ref<ThirdPartyDomain[]>([])

// 方法
const getDomainTypeText = (type: string) => {
  const typeMap: Record<string, string> = {
    cdn: 'CDN',
    analytics: '分析服务',
    advertising: '广告服务',
    social: '社交媒体',
    api: 'API服务',
    payment: '支付服务',
    security: '安全服务',
    maps: '地图服务',
    unknown: '未知类型'
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
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    critical: '严重风险'
  }
  return riskMap[risk] || risk
}

const fetchStats = async () => {
  try {
    const response = await domainAPI.getDomainStats()
    if (response.data.success) {
      stats.value = response.data.data
    }
  } catch (error) {
    console.error('获取域名统计失败:', error)
    ElMessage.error('获取域名统计失败')
  }
}

const searchDomains = async () => {
  try {
    loading.value = true
    
    // 构造查询参数
    const params: any = {
      skip: (pagination.page - 1) * pagination.size,
      limit: pagination.size
    }
    
    if (filters.domain) params.domain = filters.domain
    if (filters.domain_type) params.domain_type = filters.domain_type
    if (filters.risk_level) params.risk_level = filters.risk_level
    if (filters.has_violations !== undefined) {
      params.has_violations = filters.has_violations
    }
    
    const response = await domainAPI.getAllDomains(params)
    
    if (response.data.success) {
      domains.value = response.data.data?.items || []
      pagination.total = response.data.data?.total || 0
      
      // 为每个域名添加违规状态计算属性
      domains.value = domains.value.map(domain => ({
        ...domain,
        has_violations: domain.violations && domain.violations.length > 0
      }))
    }
  } catch (error) {
    console.error('获取域名库数据失败:', error)
    ElMessage.error('获取域名库数据失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.domain = undefined
  filters.domain_type = undefined
  filters.risk_level = undefined
  filters.has_violations = undefined
  pagination.page = 1
  searchDomains()
}

const refreshDomains = () => {
  pagination.page = 1
  searchDomains()
}

const handleSizeChange = (size: number) => {
  pagination.size = size
  pagination.page = 1
  searchDomains()
}

const handleCurrentChange = (page: number) => {
  pagination.page = page
  searchDomains()
}

const viewDomainDetail = (domain: ThirdPartyDomain) => {
  // 跳转到域名详情页面
  router.push(`/domains/${domain.id}`)
}

const viewTask = (domain: ThirdPartyDomain) => {
  // 跳转到任务详情页面
  router.push(`/tasks/${domain.task_id}`)
}

const handleSelectionChange = (selection: ThirdPartyDomain[]) => {
  selectedDomains.value = selection
}

const batchDelete = async () => {
  if (selectedDomains.value.length === 0) {
    ElMessage.warning('请先选择要删除的域名')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedDomains.value.length} 个域名吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const domainIds = selectedDomains.value.map(domain => domain.id)
    const response = await domainAPI.deleteDomains(domainIds)

    if (response.data.success) {
      ElMessage.success(`成功删除 ${selectedDomains.value.length} 个域名`)
      selectedDomains.value = []
      refreshDomains()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('批量删除域名失败:', error)
      ElMessage.error('批量删除域名失败')
    }
  }
}

const exportDomains = async (format: 'json' | 'csv' | 'excel') => {
  try {
    loading.value = true
    
    // 构造导出参数
    const params: any = {}
    if (filters.domain) params.domain = filters.domain
    if (filters.domain_type) params.domain_type = filters.domain_type
    if (filters.risk_level) params.risk_level = filters.risk_level
    if (filters.has_violations !== undefined) {
      params.has_violations = filters.has_violations
    }
    
    const response = await domainAPI.exportDomains(format, params)
    
    // 创建下载链接
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `domains.${format}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success(`域名数据已导出为 ${format.toUpperCase()} 格式`)
  } catch (error) {
    console.error('导出域名数据失败:', error)
    ElMessage.error('导出域名数据失败')
  } finally {
    loading.value = false
  }
}

// 生命周期
onMounted(() => {
  fetchStats()
  searchDomains()
})
</script>

<style scoped>
.domain-library {
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
}

.header-left p {
  margin: 4px 0 0 0;
  color: #666;
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
}

.stat-content {
  display: flex;
  align-items: center;
  height: 100%;
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
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 4px;
}

.filter-card {
  margin-bottom: 20px;
}

.domain-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.domain-name {
  font-weight: 500;
  color: #409eff;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>