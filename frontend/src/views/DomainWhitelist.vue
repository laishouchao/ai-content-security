<template>
  <div class="domain-whitelist">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2>域名列表管理</h2>
        <p>管理白名单和黑名单，控制扫描范围和安全策略</p>
      </div>
      <div class="header-right">
        <el-button @click="showCheckDialog = true">
          <el-icon><Search /></el-icon>
          域名检查
        </el-button>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新建列表
        </el-button>
        <el-button @click="refreshLists">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-cards">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon whitelist">
              <el-icon><Lock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.whitelistCount }}</div>
              <div class="stat-label">白名单</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon blacklist">
              <el-icon><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.blacklistCount }}</div>
              <div class="stat-label">黑名单</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon domains">
              <el-icon><Link /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.totalDomains }}</div>
              <div class="stat-label">总域名数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon matches">
              <el-icon><Check /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.totalMatches }}</div>
              <div class="stat-label">总匹配次数</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选器 -->
    <el-card class="filter-card">
      <el-form :model="filters" inline>
        <el-form-item label="列表类型">
          <el-select v-model="filters.list_type" placeholder="选择类型" clearable style="width: 60px">
            <el-option label="全部" value="" />
            <el-option label="白名单" value="whitelist" />
            <el-option label="黑名单" value="blacklist" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="作用域">
          <el-select v-model="filters.scope" placeholder="选择作用域" clearable style="width: 60px">
            <el-option label="全部" value="" />
            <el-option label="全局" value="global" />
            <el-option label="用户" value="user" />
            <el-option label="任务" value="task" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="状态">
          <el-select v-model="filters.is_active" placeholder="选择状态" clearable style="width: 60px">
            <el-option label="全部" value="" />
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="searchLists">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 域名列表表格 -->
    <el-card>
      <!-- 批量操作工具栏 -->
      <div v-if="selectedLists.length > 0" class="batch-toolbar">
        <div class="selected-info">
          已选中 {{ selectedLists.length }} 个列表
        </div>
        <div class="batch-actions">
          <el-button type="warning" @click="batchToggleStatus">
            <el-icon><Switch /></el-icon>
            批量切换状态
          </el-button>
          <el-button type="danger" @click="batchDeleteLists">
            <el-icon><Delete /></el-icon>
            批量删除
          </el-button>
          <el-button @click="clearSelection">取消选择</el-button>
        </div>
      </div>
      <el-table
        :data="domainLists"
        v-loading="loading"
        style="width: 100%"
        @row-click="viewListDetail"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column prop="name" label="列表名称" min-width="150">
          <template #default="{ row }">
            <div class="list-name-cell">
              <el-icon v-if="row.list_type === 'whitelist'" class="list-icon whitelist"><Lock /></el-icon>
              <el-icon v-else class="list-icon blacklist"><CircleClose /></el-icon>
              <span class="list-name">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="list_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.list_type === 'whitelist' ? 'success' : 'danger'" size="small">
              {{ row.list_type === 'whitelist' ? '白名单' : '黑名单' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="scope" label="作用域" width="100">
          <template #default="{ row }">
            <el-tag type="info" size="small">
              {{ getScopeText(row.scope) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="domain_count" label="域名数量" width="100" align="center" />
        
        <el-table-column prop="match_count" label="匹配次数" width="100" align="center" />
        
        <el-table-column prop="priority" label="优先级" width="100" align="center" />
        
        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_active"
              @change="toggleListStatus(row)"
            />
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              type="text"
              size="small"
              @click.stop="viewListDetail(row)"
            >
              查看
            </el-button>
            <el-button
              type="text"
              size="small"
              @click.stop="editList(row)"
            >
              编辑
            </el-button>
            <el-dropdown @command="handleListAction">
              <el-button type="text" size="small">
                更多<el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :command="{action: 'export', list: row}">导出</el-dropdown-item>
                  <el-dropdown-item :command="{action: 'duplicate', list: row}">复制</el-dropdown-item>
                  <el-dropdown-item :command="{action: 'delete', list: row}" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 创建/编辑列表对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingList ? '编辑列表' : '创建列表'"
      width="600px"
      @close="resetCreateForm"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="100px"
      >
        <el-form-item label="列表名称" prop="name">
          <el-input v-model="createForm.name" placeholder="请输入列表名称" />
        </el-form-item>
        
        <el-form-item label="列表类型" prop="list_type">
          <el-radio-group v-model="createForm.list_type">
            <el-radio label="whitelist">白名单</el-radio>
            <el-radio label="blacklist">黑名单</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item label="作用域" prop="scope">
          <el-select v-model="createForm.scope" placeholder="选择作用域" style="width: 60px">
            <el-option label="用户级别" value="user" />
            <el-option label="全局级别" value="global" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="优先级" prop="priority">
          <el-input-number
            v-model="createForm.priority"
            :min="0"
            :max="100"
            placeholder="数字越大优先级越高"
          />
        </el-form-item>
        
        <el-form-item label="正则支持">
          <el-switch v-model="createForm.is_regex_enabled" />
          <span class="form-hint">启用后支持正则表达式匹配</span>
        </el-form-item>
        
        <el-form-item label="描述">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入列表描述"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showCreateDialog = false">取消</el-button>
          <el-button type="primary" @click="handleCreateList" :loading="submitting">
            {{ editingList ? '更新' : '创建' }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 域名检查对话框 -->
    <el-dialog v-model="showCheckDialog" title="域名检查" width="800px">
      <div class="domain-check-container">
        <el-form>
          <el-form-item label="输入域名">
            <el-input
              v-model="checkDomains"
              type="textarea"
              :rows="5"
              placeholder="请输入要检查的域名，一行一个"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="checkDomainsHandler" :loading="checking">
              检查域名
            </el-button>
          </el-form-item>
        </el-form>
        
        <div v-if="checkResults" class="check-results">
          <h4>检查结果：</h4>
          <el-table :data="checkResultsList" style="width: 100%">
            <el-table-column prop="domain" label="域名" />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag 
                  :type="row.is_allowed === true ? 'success' : row.is_allowed === false ? 'danger' : 'info'"
                >
                  {{ row.is_allowed === true ? '允许' : row.is_allowed === false ? '拦截' : '未定义' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="list_type" label="匹配列表" width="100" />
            <el-table-column prop="matched_pattern" label="匹配规则" />
            <el-table-column prop="confidence" label="置信度" width="80" />
          </el-table>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Refresh,
  Search,
  Lock,
  CircleClose,
  Link,
  Check,
  ArrowDown,
  Switch,
  Delete
} from '@element-plus/icons-vue'
import { domainListAPI, type DomainList, type CreateDomainListRequest } from '@/api/domainList'
import { formatTime } from '@/utils/date'

const router = useRouter()

// 响应式数据
const loading = ref(false)
const submitting = ref(false)
const checking = ref(false)
const domainLists = ref<DomainList[]>([])
const selectedLists = ref<DomainList[]>([])

// 分页
const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

// 筛选器
const filters = reactive({
  list_type: '',
  scope: '',
  is_active: '' as boolean | string
})

// 统计数据
const stats = computed(() => {
  const whitelistCount = domainLists.value.filter(list => list.list_type === 'whitelist').length
  const blacklistCount = domainLists.value.filter(list => list.list_type === 'blacklist').length
  const totalDomains = domainLists.value.reduce((sum, list) => sum + list.domain_count, 0)
  const totalMatches = domainLists.value.reduce((sum, list) => sum + list.match_count, 0)
  
  return {
    whitelistCount,
    blacklistCount,
    totalDomains,
    totalMatches
  }
})

// 创建表单
const showCreateDialog = ref(false)
const editingList = ref<DomainList | null>(null)
const createFormRef = ref()
const createForm = reactive<CreateDomainListRequest>({
  name: '',
  list_type: 'whitelist',
  description: '',
  scope: 'user',
  is_regex_enabled: false,
  priority: 0
})

const createRules = {
  name: [
    { required: true, message: '请输入列表名称', trigger: 'blur' }
  ],
  list_type: [
    { required: true, message: '请选择列表类型', trigger: 'change' }
  ],
  scope: [
    { required: true, message: '请选择作用域', trigger: 'change' }
  ]
}

// 域名检查
const showCheckDialog = ref(false)
const checkDomains = ref('')
const checkResults = ref<any>(null)

const checkResultsList = computed(() => {
  if (!checkResults.value) return []
  
  return Object.entries(checkResults.value).map(([domain, result]: [string, any]) => ({
    domain,
    is_allowed: result.is_allowed,
    list_type: result.list_type,
    matched_pattern: result.matched_pattern,
    confidence: result.confidence
  }))
})

// 方法
const refreshLists = async () => {
  await loadDomainLists()
}

const loadDomainLists = async () => {
  try {
    loading.value = true
    
    const params: any = {
      skip: (pagination.page - 1) * pagination.size,
      limit: pagination.size
    }
    
    // 添加筛选条件
    if (filters.list_type) params.list_type = filters.list_type
    if (filters.scope) params.scope = filters.scope
    if (filters.is_active !== '') {
      params.is_active = filters.is_active === 'true' ? true : filters.is_active === 'false' ? false : undefined
    }
    
    const response = await domainListAPI.getDomainLists(params)
    
    if (response.data.success) {
      domainLists.value = response.data.data.items
      pagination.total = response.data.data.total
    }
  } catch (error) {
    console.error('加载域名列表失败:', error)
    ElMessage.error('加载域名列表失败')
  } finally {
    loading.value = false
  }
}

const searchLists = () => {
  pagination.page = 1
  loadDomainLists()
}

const resetFilters = () => {
  filters.list_type = ''
  filters.scope = ''
  filters.is_active = ''
  searchLists()
}

const handleSelectionChange = (selection: DomainList[]) => {
  selectedLists.value = selection
}

const handleSizeChange = (size: number) => {
  pagination.size = size
  loadDomainLists()
}

const handleCurrentChange = (page: number) => {
  pagination.page = page
  loadDomainLists()
}

const getScopeText = (scope: string) => {
  const scopeMap: Record<string, string> = {
    global: '全局',
    user: '用户',
    task: '任务'
  }
  return scopeMap[scope] || scope
}

const viewListDetail = (list: DomainList) => {
  // 跳转到列表详情页面
  router.push(`/domain-lists/${list.id}`)
}

const editList = (list: DomainList) => {
  editingList.value = list
  createForm.name = list.name
  createForm.list_type = list.list_type as 'whitelist' | 'blacklist'
  createForm.description = list.description || ''
  createForm.scope = list.scope as 'user' | 'global'
  createForm.is_regex_enabled = list.is_regex_enabled
  createForm.priority = list.priority
  showCreateDialog.value = true
}

const handleCreateList = async () => {
  try {
    await createFormRef.value.validate()
    submitting.value = true
    
    if (editingList.value) {
      // 更新列表
      await domainListAPI.updateDomainList(editingList.value.id, createForm)
      ElMessage.success('列表更新成功')
    } else {
      // 创建列表
      await domainListAPI.createDomainList(createForm)
      ElMessage.success('列表创建成功')
    }
    
    showCreateDialog.value = false
    await loadDomainLists()
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

const resetCreateForm = () => {
  editingList.value = null
  createForm.name = ''
  createForm.list_type = 'whitelist'
  createForm.description = ''
  createForm.scope = 'user'
  createForm.is_regex_enabled = false
  createForm.priority = 0
  createFormRef.value?.resetFields()
}

const toggleListStatus = async (list: DomainList) => {
  try {
    await domainListAPI.updateDomainList(list.id, {
      name: list.name,
      list_type: list.list_type,
      description: list.description,
      scope: list.scope,
      is_regex_enabled: list.is_regex_enabled,
      priority: list.priority
    })
    ElMessage.success('状态更新成功')
  } catch (error) {
    // 恢复原状态
    list.is_active = !list.is_active
    console.error('状态更新失败:', error)
    ElMessage.error('状态更新失败')
  }
}

const handleListAction = async ({ action, list }: { action: string, list: DomainList }) => {
  switch (action) {
    case 'export':
      await exportList(list)
      break
    case 'duplicate':
      await duplicateList(list)
      break
    case 'delete':
      await deleteList(list)
      break
  }
}

const exportList = async (list: DomainList) => {
  try {
    // 获取列表详情和域名数据
    const response = await domainListAPI.getDomainListDetail(list.id)
    
    if (response.data.success) {
      const listData = response.data.data
      const domains = listData.domains || []
      
      // 构造导出数据
      const exportData = {
        list_info: {
          name: list.name,
          list_type: list.list_type,
          description: list.description,
          scope: list.scope,
          priority: list.priority,
          is_regex_enabled: list.is_regex_enabled,
          domain_count: list.domain_count,
          created_at: list.created_at
        },
        domains: domains.map((domain: any) => ({
          domain: domain.domain,
          pattern: domain.pattern,
          is_regex: domain.is_regex,
          notes: domain.notes,
          created_at: domain.created_at
        }))
      }
      
      // 创建并下载JSON文件
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { 
        type: 'application/json' 
      })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${list.name}_${list.list_type}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      
      ElMessage.success('列表导出成功')
    }
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败')
  }
}

const duplicateList = async (list: DomainList) => {
  try {
    const newListData: CreateDomainListRequest = {
      name: `${list.name}_副本`,
      list_type: list.list_type,
      description: list.description,
      scope: list.scope,
      is_regex_enabled: list.is_regex_enabled,
      priority: list.priority
    }
    
    await domainListAPI.createDomainList(newListData)
    ElMessage.success('列表复制成功')
    await loadDomainLists()
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制失败')
  }
}

const deleteList = async (list: DomainList) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除列表"${list.name}"吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await domainListAPI.deleteDomainList(list.id)
    ElMessage.success('列表删除成功')
    await loadDomainLists()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

const checkDomainsHandler = async () => {
  if (!checkDomains.value.trim()) {
    ElMessage.warning('请输入要检查的域名')
    return
  }
  
  try {
    checking.value = true
    const domains = checkDomains.value
      .split('\n')
      .map(domain => domain.trim())
      .filter(domain => domain)
    
    const response = await domainListAPI.checkDomains({ domains })
    
    if (response.data.success) {
      checkResults.value = response.data.data
    }
  } catch (error) {
    console.error('域名检查失败:', error)
    ElMessage.error('域名检查失败')
  } finally {
    checking.value = false
  }
}

// 批量操作方法
const batchDeleteLists = async () => {
  if (selectedLists.value.length === 0) {
    ElMessage.warning('请先选择要删除的列表')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedLists.value.length} 个列表吗？此操作不可恢复。`,
      '确认批量删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const deletePromises = selectedLists.value.map(list => 
      domainListAPI.deleteDomainList(list.id)
    )
    
    const results = await Promise.allSettled(deletePromises)
    const successful = results.filter(result => result.status === 'fulfilled').length
    const failed = results.length - successful
    
    if (successful > 0) {
      ElMessage.success(`成功删除 ${successful} 个列表`)
    }
    if (failed > 0) {
      ElMessage.warning(`${failed} 个列表删除失败`)
    }
    
    selectedLists.value = []
    await loadDomainLists()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
      ElMessage.error('批量删除失败')
    }
  }
}

const batchToggleStatus = async () => {
  if (selectedLists.value.length === 0) {
    ElMessage.warning('请先选择要操作的列表')
    return
  }

  try {
    const togglePromises = selectedLists.value.map(list => {
      const updatedData = {
        name: list.name,
        list_type: list.list_type,
        description: list.description,
        scope: list.scope,
        is_regex_enabled: list.is_regex_enabled,
        priority: list.priority,
        is_active: !list.is_active
      }
      return domainListAPI.updateDomainList(list.id, updatedData)
    })
    
    const results = await Promise.allSettled(togglePromises)
    const successful = results.filter(result => result.status === 'fulfilled').length
    const failed = results.length - successful
    
    if (successful > 0) {
      ElMessage.success(`成功切换 ${successful} 个列表状态`)
    }
    if (failed > 0) {
      ElMessage.warning(`${failed} 个列表状态切换失败`)
    }
    
    selectedLists.value = []
    await loadDomainLists()
  } catch (error) {
    console.error('批量切换状态失败:', error)
    ElMessage.error('批量切换状态失败')
  }
}

const clearSelection = () => {
  selectedLists.value = []
}

// 生命周期
onMounted(() => {
  loadDomainLists()
})
</script>

<style scoped>
.domain-whitelist {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left h2 {
  margin: 0 0 5px 0;
  color: #303133;
}

.header-left p {
  margin: 0;
  color: #606266;
  font-size: 14px;
}

.header-right {
  display: flex;
  gap: 10px;
}

.stats-cards {
  margin-bottom: 20px;
}

.stat-card {
  height: 80px;
}

.stat-content {
  display: flex;
  align-items: center;
  height: 100%;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 15px;
  color: white;
  font-size: 20px;
}

.stat-icon.whitelist {
  background-color: #67c23a;
}

.stat-icon.blacklist {
  background-color: #f56c6c;
}

.stat-icon.domains {
  background-color: #409eff;
}

.stat-icon.matches {
  background-color: #e6a23c;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-top: 4px;
}

.filter-card {
  margin-bottom: 20px;
}

.list-name-cell {
  display: flex;
  align-items: center;
}

.list-icon {
  margin-right: 8px;
}

.list-icon.whitelist {
  color: #67c23a;
}

.list-icon.blacklist {
  color: #f56c6c;
}

.list-name {
  font-weight: 500;
}

.pagination-container {
  margin-top: 20px;
  text-align: center;
}

.form-hint {
  color: #909399;
  font-size: 12px;
  margin-left: 10px;
}

.domain-check-container {
  padding: 10px 0;
}

.check-results {
  margin-top: 20px;
}

.check-results h4 {
  margin-bottom: 15px;
  color: #303133;
}

/* 批量操作工具栏样式 */
.batch-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  margin-bottom: 16px;
}

.selected-info {
  color: #606266;
  font-size: 14px;
}

.batch-actions {
  display: flex;
  gap: 8px;
}
</style>