<template>
  <div class="task-list">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2>扫描任务</h2>
        <p>管理和监控所有的域名扫描任务</p>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="$router.push('/tasks/create')">
          <el-icon><Plus /></el-icon>
          创建任务
        </el-button>
      </div>
    </div>

    <!-- 筛选器 -->
    <el-card class="filter-card">
      <el-form inline>
        <el-form-item label="任务状态">
          <el-select v-model="filters.status" placeholder="选择状态" clearable>
            <el-option label="全部" value="" />
            <el-option label="等待中" value="pending" />
            <el-option label="运行中" value="running" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="域名">
          <el-input
            v-model="filters.domain"
            placeholder="搜索域名"
            clearable
          />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="searchTasks">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 任务表格 -->
    <el-card>
      <el-table
        :data="tasks"
        v-loading="loading"
        style="width: 100%"
        @row-click="goToTaskDetail"
      >
        <el-table-column label="任务名称" width="150">
          <template #default="{ row }">
            <span v-if="row.task_name">{{ row.task_name }}</span>
            <span v-else class="task-id-display">#{{ row.id.substring(0, 8) }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="target_domain" label="目标域名" min-width="200">
          <template #default="{ row }">
            <div class="domain-cell">
              <span class="domain-name">{{ row.target_domain }}</span>
              <el-tag v-if="row.total_violations > 0" type="danger" size="small">
                {{ row.total_violations }}个违规
              </el-tag>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="progress" label="进度" width="150">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress"
              :status="row.status === 'failed' ? 'exception' : undefined"
              :stroke-width="6"
            />
          </template>
        </el-table-column>
        
        <el-table-column prop="total_subdomains" label="子域名" width="100" align="center" />
        
        <el-table-column prop="total_pages_crawled" label="页面" width="100" align="center" />
        
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              type="text"
              size="small"
              @click.stop="viewTask(row)"
            >
              查看
            </el-button>
            <el-button
              v-if="row.status === 'running'"
              type="text"
              size="small"
              @click.stop="stopTask(row)"
            >
              停止
            </el-button>
            <el-button
              v-if="row.status === 'failed'"
              type="text"
              size="small"
              @click.stop="retryTask(row)"
            >
              重试
            </el-button>
            <el-button
              type="text"
              size="small"
              @click.stop="deleteTask(row)"
              style="color: #f56c6c;"
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
import { Plus, Search } from '@element-plus/icons-vue'
import { taskAPI } from '@/api/task'
import type { Task, TaskFilter } from '@/types/api'

const router = useRouter()

// 响应式状态
const loading = ref(false)
const filters = reactive<TaskFilter>({
  status: undefined,
  domain: undefined
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const tasks = ref<Task[]>([])

// 方法
const getStatusType = (status: string): 'info' | 'warning' | 'success' | 'danger' => {
  const statusMap: Record<string, 'info' | 'warning' | 'success' | 'danger'> = {
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

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

const searchTasks = async () => {
  try {
    loading.value = true
    const params = {
      status: filters.status,
      domain: filters.domain,
      skip: (pagination.page - 1) * pagination.size,
      limit: pagination.size
    }
    
    const response = await taskAPI.getTasks(params)
    if (response.data.success && response.data.data) {
      tasks.value = response.data.data.items
      pagination.total = response.data.data.total
    } else {
      tasks.value = []
      pagination.total = 0
    }
  } catch (error) {
    console.error('获取任务列表失败:', error)
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.status = undefined
  filters.domain = undefined
  pagination.page = 1
  searchTasks()
}

const goToTaskDetail = (row: Task) => {
  router.push(`/tasks/${row.id}`)
}

const viewTask = (row: Task) => {
  router.push(`/tasks/${row.id}`)
}

const stopTask = async (row: Task) => {
  try {
    await ElMessageBox.confirm('确定要停止此任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    // 实际调用API停止任务
    const response = await taskAPI.stopTask(row.id)
    if (response.data.success) {
      ElMessage.success('任务已停止')
      // 重新加载任务列表
      searchTasks()
    } else {
      ElMessage.error(response.data.message || '停止任务失败')
    }
  } catch (error) {
    console.error('停止任务失败:', error)
    ElMessage.error('停止任务失败')
  }
}

const retryTask = async (row: Task) => {
  try {
    await ElMessageBox.confirm('确定要重试此任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })
    
    // 实际调用API重试任务
    const response = await taskAPI.retryTask(row.id)
    if (response.data.success) {
      ElMessage.success('任务已重新启动')
      // 重新加载任务列表
      searchTasks()
    } else {
      ElMessage.error(response.data.message || '重试任务失败')
    }
  } catch (error) {
    console.error('重试任务失败:', error)
    ElMessage.error('重试任务失败')
  }
}

const deleteTask = async (row: Task) => {
  try {
    await ElMessageBox.confirm('确定要删除此任务吗？此操作不可恢复！', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'error'
    })
    
    const response = await taskAPI.deleteTask(row.id)
    if (response.data.success) {
      ElMessage.success('任务已删除')
      // 重新加载任务列表
      searchTasks()
    } else {
      ElMessage.error(response.data.message || '删除任务失败')
    }
  } catch (error) {
    console.error('删除任务失败:', error)
    ElMessage.error('删除任务失败')
  }
}

const handleSizeChange = (size: number) => {
  pagination.size = size
  searchTasks()
}

const handleCurrentChange = (page: number) => {
  pagination.page = page
  searchTasks()
}

onMounted(() => {
  searchTasks()
})
</script>

<style scoped>
.task-list {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 20px;
}

.header-left h2 {
  margin: 0 0 4px 0;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.header-left p {
  margin: 0;
  color: #666;
  font-size: 14px;
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
}

.task-id-display {
  font-family: monospace;
  font-size: 12px;
  color: #999;
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.el-table__row:hover) {
  background-color: #f8f9fa;
}

:deep(.el-table__row:hover) {
  background-color: #f8f9fa;
}
</style>