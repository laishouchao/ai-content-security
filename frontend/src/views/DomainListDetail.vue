<template>
  <div class="domain-list-detail">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button @click="$router.back()" type="text">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <div class="title-section">
          <h2>{{ listDetail.name }}</h2>
          <div class="meta-info">
            <el-tag :type="listDetail.list_type === 'whitelist' ? 'success' : 'danger'" size="small">
              {{ listDetail.list_type === 'whitelist' ? '白名单' : '黑名单' }}
            </el-tag>
            <el-tag type="info" size="small">{{ getScopeText(listDetail.scope) }}</el-tag>
            <span class="domain-count">{{ listDetail.domain_count }} 个域名</span>
          </div>
        </div>
      </div>
      <div class="header-right">
        <el-button @click="showImportDialog = true">
          <el-icon><Upload /></el-icon>
          批量导入
        </el-button>
        <el-button @click="exportListCSV">
          <el-icon><Download /></el-icon>
          导出CSV
        </el-button>
        <el-button type="primary" @click="showAddDialog = true">
          <el-icon><Plus /></el-icon>
          添加域名
        </el-button>
      </div>
    </div>

    <!-- 列表信息卡片 -->
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>
            <span>列表信息</span>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="列表名称">{{ listDetail.name }}</el-descriptions-item>
            <el-descriptions-item label="列表类型">
              <el-tag :type="listDetail.list_type === 'whitelist' ? 'success' : 'danger'">
                {{ listDetail.list_type === 'whitelist' ? '白名单' : '黑名单' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="作用域">
              <el-tag type="info">{{ getScopeText(listDetail.scope) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="优先级">{{ listDetail.priority }}</el-descriptions-item>
            <el-descriptions-item label="正则支持">
              <el-tag :type="listDetail.is_regex_enabled ? 'success' : 'info'">
                {{ listDetail.is_regex_enabled ? '启用' : '禁用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-switch
                v-model="listDetail.is_active"
                @change="toggleListStatus"
              />
            </el-descriptions-item>
            <el-descriptions-item label="域名数量">{{ listDetail.domain_count }}</el-descriptions-item>
            <el-descriptions-item label="匹配次数">{{ listDetail.match_count }}</el-descriptions-item>
            <el-descriptions-item label="创建时间" :span="2">
              {{ formatTime(listDetail.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item v-if="listDetail.description" label="描述" :span="2">
              {{ listDetail.description }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>统计信息</span>
          </template>
          <div class="stats-list">
            <div class="stat-item">
              <span class="stat-label">总域名数</span>
              <span class="stat-value">{{ listDetail.domain_count }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">正则域名</span>
              <span class="stat-value">{{ regexDomainCount }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">普通域名</span>
              <span class="stat-value">{{ normalDomainCount }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">匹配次数</span>
              <span class="stat-value">{{ listDetail.match_count }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">最后更新</span>
              <span class="stat-value">{{ formatTime(listDetail.updated_at) }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 域名列表 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <div class="domains-header">
          <span>域名列表</span>
          <div class="domain-actions">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索域名"
              clearable
              style="width: 200px; margin-right: 10px;"
              @input="filterDomains"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
        </div>
      </template>

      <!-- 批量操作工具栏 -->
      <div v-if="selectedDomains.length > 0" class="batch-toolbar">
        <div class="selected-info">
          已选中 {{ selectedDomains.length }} 个域名
        </div>
        <div class="batch-actions">
          <el-button type="danger" @click="batchDeleteDomains">
            <el-icon><Delete /></el-icon>
            批量删除
          </el-button>
          <el-button @click="clearSelection">取消选择</el-button>
        </div>
      </div>

      <el-table
        :data="filteredDomains"
        v-loading="domainsLoading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column prop="domain" label="域名/模式" min-width="200">
          <template #default="{ row }">
            <div class="domain-cell">
              <span class="domain-text" :class="{ 'regex-domain': row.is_regex }">
                {{ row.domain }}
              </span>
              <el-tag v-if="row.is_regex" type="warning" size="small">正则</el-tag>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="match_count" label="匹配次数" width="100" align="center" />
        
        <el-table-column prop="notes" label="备注" min-width="150" show-overflow-tooltip />
        
        <el-table-column prop="created_at" label="添加时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              type="text"
              size="small"
              @click="editDomain(row)"
            >
              编辑
            </el-button>
            <el-button
              type="text"
              size="small"
              @click="deleteDomain(row)"
            >
              删除
            </el-button>
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

    <!-- 添加/编辑域名对话框 -->
    <el-dialog
      v-model="showAddDialog"
      :title="editingDomain ? '编辑域名' : '添加域名'"
      width="500px"
      @close="resetDomainForm"
    >
      <el-form
        ref="domainFormRef"
        :model="domainForm"
        :rules="domainRules"
        label-width="80px"
      >
        <el-form-item label="域名" prop="domain">
          <el-input v-model="domainForm.domain" placeholder="请输入域名或模式" />
        </el-form-item>
        
        <el-form-item label="正则模式">
          <el-switch v-model="domainForm.is_regex" />
          <span class="form-hint">启用后支持正则表达式匹配</span>
        </el-form-item>
        
        <el-form-item label="备注">
          <el-input
            v-model="domainForm.notes"
            type="textarea"
            :rows="3"
            placeholder="请输入备注信息"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showAddDialog = false">取消</el-button>
          <el-button type="primary" @click="handleDomainSubmit" :loading="submitting">
            {{ editingDomain ? '更新' : '添加' }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 批量导入对话框 -->
    <el-dialog v-model="showImportDialog" title="批量导入域名" width="600px">
      <div class="import-container">
        <el-tabs v-model="importMethod">
          <el-tab-pane label="文本导入" name="text">
            <el-form>
              <el-form-item label="导入数据">
                <el-input
                  v-model="importText"
                  type="textarea"
                  :rows="10"
                  placeholder="请输入域名，一行一个。支持以下格式：&#10;example.com&#10;*.example.com (通配符)&#10;^.*\.example\.com$ (正则表达式)&#10;example.com,备注信息"
                />
              </el-form-item>
              <el-form-item>
                <el-checkbox v-model="importAsRegex">将通配符(*)自动转换为正则表达式</el-checkbox>
              </el-form-item>
            </el-form>
          </el-tab-pane>
          
          <el-tab-pane label="CSV文件" name="csv">
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :limit="1"
              accept=".csv"
              :on-change="handleFileChange"
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                将CSV文件拖到此处，或<em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  CSV格式：domain,is_regex,notes<br>
                  示例：example.com,false,测试域名
                </div>
              </template>
            </el-upload>
          </el-tab-pane>
        </el-tabs>
        
        <div class="import-preview" v-if="importPreview.length > 0">
          <h4>导入预览 ({{ importPreview.length }} 条记录)：</h4>
          <el-table :data="importPreview.slice(0, 5)" size="small">
            <el-table-column prop="domain" label="域名" />
            <el-table-column prop="is_regex" label="正则" width="60">
              <template #default="{ row }">
                <el-tag v-if="row.is_regex" type="warning" size="small">是</el-tag>
                <span v-else>否</span>
              </template>
            </el-table-column>
            <el-table-column prop="notes" label="备注" />
          </el-table>
          <div v-if="importPreview.length > 5" class="preview-more">
            还有 {{ importPreview.length - 5 }} 条记录...
          </div>
        </div>
      </div>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showImportDialog = false">取消</el-button>
          <el-button @click="previewImport">预览</el-button>
          <el-button 
            type="primary" 
            @click="executeImport" 
            :loading="importing"
            :disabled="importPreview.length === 0"
          >
            导入 ({{ importPreview.length }})
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Upload,
  Download,
  Plus,
  Search,
  Delete,
  UploadFilled
} from '@element-plus/icons-vue'
import { domainListAPI, type DomainList } from '@/api/domainList'
import { formatTime } from '@/utils/date'

const route = useRoute()
const router = useRouter()
const listId = route.params.id as string

// 响应式数据
const domainsLoading = ref(false)
const submitting = ref(false)
const importing = ref(false)
const listDetail = ref<DomainList>({} as DomainList)
const domains = ref<any[]>([])
const filteredDomains = ref<any[]>([])
const selectedDomains = ref<any[]>([])
const searchKeyword = ref('')

// 分页
const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

// 添加域名表单
const showAddDialog = ref(false)
const editingDomain = ref<any>(null)
const domainFormRef = ref()
const domainForm = reactive({
  domain: '',
  is_regex: false,
  notes: ''
})

const domainRules = {
  domain: [
    { required: true, message: '请输入域名', trigger: 'blur' }
  ]
}

// 批量导入
const showImportDialog = ref(false)
const importMethod = ref('text')
const importText = ref('')
const importAsRegex = ref(true)
const importPreview = ref<any[]>([])
const uploadRef = ref()

// 计算属性
const regexDomainCount = computed(() => {
  return domains.value.filter(domain => domain.is_regex).length
})

const normalDomainCount = computed(() => {
  return domains.value.filter(domain => !domain.is_regex).length
})

// 方法
const getScopeText = (scope: string) => {
  const scopeMap: Record<string, string> = {
    global: '全局',
    user: '用户',
    task: '任务'
  }
  return scopeMap[scope] || scope
}

const loadListDetail = async () => {
  try {
    const response = await domainListAPI.getDomainListDetail(listId)
    if (response.data.success) {
      listDetail.value = response.data.data
    }
  } catch (error) {
    console.error('获取列表详情失败:', error)
    ElMessage.error('获取列表详情失败')
  }
}

const loadDomains = async () => {
  try {
    domainsLoading.value = true
    const response = await domainListAPI.getDomainListDomains(listId, {
      skip: (pagination.page - 1) * pagination.size,
      limit: pagination.size
    })
    
    if (response.data.success) {
      domains.value = response.data.data.items
      pagination.total = response.data.data.total
      filterDomains()
    }
  } catch (error) {
    console.error('获取域名列表失败:', error)
    ElMessage.error('获取域名列表失败')
  } finally {
    domainsLoading.value = false
  }
}

const filterDomains = () => {
  if (!searchKeyword.value) {
    filteredDomains.value = domains.value
  } else {
    filteredDomains.value = domains.value.filter(domain =>
      domain.domain.toLowerCase().includes(searchKeyword.value.toLowerCase()) ||
      domain.notes?.toLowerCase().includes(searchKeyword.value.toLowerCase())
    )
  }
}

const handleSelectionChange = (selection: any[]) => {
  selectedDomains.value = selection
}

const clearSelection = () => {
  selectedDomains.value = []
}

const handleSizeChange = (size: number) => {
  pagination.size = size
  pagination.page = 1
  loadDomains()
}

const handleCurrentChange = (page: number) => {
  pagination.page = page
  loadDomains()
}

const toggleListStatus = async () => {
  try {
    await domainListAPI.updateDomainList(listId, {
      name: listDetail.value.name,
      list_type: listDetail.value.list_type,
      description: listDetail.value.description,
      scope: listDetail.value.scope,
      is_regex_enabled: listDetail.value.is_regex_enabled,
      priority: listDetail.value.priority
    })
    ElMessage.success('状态更新成功')
  } catch (error) {
    listDetail.value.is_active = !listDetail.value.is_active
    console.error('状态更新失败:', error)
    ElMessage.error('状态更新失败')
  }
}

const editDomain = (domain: any) => {
  editingDomain.value = domain
  domainForm.domain = domain.domain
  domainForm.is_regex = domain.is_regex
  domainForm.notes = domain.notes || ''
  showAddDialog.value = true
}

const deleteDomain = async (domain: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除域名"${domain.domain}"吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await domainListAPI.deleteDomainFromList(listId, domain.id)
    ElMessage.success('域名删除成功')
    await loadDomains()
    await loadListDetail()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除域名失败:', error)
      ElMessage.error('删除域名失败')
    }
  }
}

const handleDomainSubmit = async () => {
  try {
    await domainFormRef.value.validate()
    submitting.value = true
    
    if (editingDomain.value) {
      await domainListAPI.updateDomainInList(listId, editingDomain.value.id, domainForm)
      ElMessage.success('域名更新成功')
    } else {
      await domainListAPI.addDomainToList(listId, domainForm)
      ElMessage.success('域名添加成功')
    }
    
    showAddDialog.value = false
    await loadDomains()
    await loadListDetail()
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

const resetDomainForm = () => {
  editingDomain.value = null
  domainForm.domain = ''
  domainForm.is_regex = false
  domainForm.notes = ''
  domainFormRef.value?.resetFields()
}

const batchDeleteDomains = async () => {
  if (selectedDomains.value.length === 0) return
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedDomains.value.length} 个域名吗？`,
      '确认批量删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const deletePromises = selectedDomains.value.map(domain =>
      domainListAPI.deleteDomainFromList(listId, domain.id)
    )
    
    const results = await Promise.allSettled(deletePromises)
    const successful = results.filter(result => result.status === 'fulfilled').length
    
    ElMessage.success(`成功删除 ${successful} 个域名`)
    selectedDomains.value = []
    await loadDomains()
    await loadListDetail()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
      ElMessage.error('批量删除失败')
    }
  }
}

const exportListCSV = async () => {
  try {
    const response = await domainListAPI.exportDomainList(listId, 'csv')
    
    const blob = new Blob([response.data], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${listDetail.value.name}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('CSV文件导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败')
  }
}

const previewImport = () => {
  if (importMethod.value === 'text') {
    if (!importText.value.trim()) {
      ElMessage.warning('请输入导入数据')
      return
    }
    
    const lines = importText.value.trim().split('\n')
    const preview: any[] = []
    
    lines.forEach(line => {
      line = line.trim()
      if (!line) return
      
      const parts = line.split(',')
      const domain = parts[0].trim()
      let isRegex = false
      let notes = parts.slice(1).join(',').trim()
      
      // 检测通配符
      if (domain.includes('*') && importAsRegex.value) {
        isRegex = true
      }
      
      // 检测正则表达式
      if (domain.startsWith('^') || domain.endsWith('$')) {
        isRegex = true
      }
      
      preview.push({
        domain,
        is_regex: isRegex,
        notes: notes || ''
      })
    })
    
    importPreview.value = preview
  }
}

const handleFileChange = (file: any) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const csv = e.target?.result as string
      const lines = csv.split('\n')
      const preview: any[] = []
      
      lines.forEach((line, index) => {
        if (index === 0) return // 跳过标题行
        
        line = line.trim()
        if (!line) return
        
        const parts = line.split(',')
        if (parts.length >= 1) {
          preview.push({
            domain: parts[0]?.trim() || '',
            is_regex: parts[1]?.trim() === 'true',
            notes: parts[2]?.trim() || ''
          })
        }
      })
      
      importPreview.value = preview
    } catch (error) {
      ElMessage.error('CSV文件格式错误')
    }
  }
  reader.readAsText(file.raw)
}

const executeImport = async () => {
  if (importPreview.value.length === 0) {
    ElMessage.warning('没有可导入的数据')
    return
  }
  
  try {
    importing.value = true
    
    await domainListAPI.importDomainsToList(listId, {
      domains: importPreview.value
    })
    
    ElMessage.success(`成功导入 ${importPreview.value.length} 个域名`)
    showImportDialog.value = false
    importText.value = ''
    importPreview.value = []
    await loadDomains()
    await loadListDetail()
  } catch (error) {
    console.error('导入失败:', error)
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
}

onMounted(() => {
  loadListDetail()
  loadDomains()
})
</script>

<style scoped>
.domain-list-detail {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.title-section h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
}

.meta-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.domain-count {
  color: #666;
  font-size: 14px;
}

.header-right {
  display: flex;
  gap: 10px;
}

.stats-list {
  padding: 0;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-label {
  color: #666;
  font-size: 14px;
}

.stat-value {
  font-weight: 500;
  color: #333;
}

.domains-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

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

.domain-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.domain-text.regex-domain {
  font-family: 'Courier New', monospace;
  color: #e6a23c;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.form-hint {
  color: #909399;
  font-size: 12px;
  margin-left: 10px;
}

.import-container {
  padding: 10px 0;
}

.import-preview {
  margin-top: 20px;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.import-preview h4 {
  margin: 0 0 15px 0;
  color: #303133;
}

.preview-more {
  text-align: center;
  color: #999;
  margin-top: 10px;
  font-size: 14px;
}
</style>