import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { taskAPI, type Task, type CreateTaskRequest, type TaskFilter, type PaginationParams, TaskStatus } from '@/api/task'

export const useTaskStore = defineStore('task', () => {
  // 状态
  const tasks = ref<Task[]>([])
  const currentTask = ref<Task | null>(null)
  const loading = ref(false)
  const pagination = ref({
    page: 1,
    size: 20,
    total: 0
  })
  const filters = ref<TaskFilter>({})
  
  // 统计数据
  const stats = ref({
    totalTasks: 0,
    completedTasks: 0,
    runningTasks: 0,
    failedTasks: 0,
    totalViolations: 0,
    violationDistribution: [] as any[],
    recentTasks: [] as Task[],
    taskTrends: [] as any[],
    riskLevelDistribution: [] as any[],
    systemStatus: {} as any
  })

  // 计算属性
  const totalTasks = computed(() => stats.value.totalTasks)
  const completedTasks = computed(() => stats.value.completedTasks)
  const runningTasks = computed(() => stats.value.runningTasks)
  const failedTasks = computed(() => stats.value.failedTasks)
  const totalViolations = computed(() => stats.value.totalViolations)
  const violationDistribution = computed(() => stats.value.violationDistribution)
  const recentTasks = computed(() => stats.value.recentTasks)

  // 获取任务列表
  const fetchTasks = async (params: TaskFilter & PaginationParams = {}) => {
    try {
      loading.value = true
      
      const response = await taskAPI.getTasks({
        ...filters.value,
        ...params,
        skip: (pagination.value.page - 1) * pagination.value.size,
        limit: pagination.value.size
      })
      
      if (response.data.success && response.data.data) {
        tasks.value = response.data.data.items
        pagination.value.total = response.data.data.total
      }
    } catch (error) {
      console.error('获取任务列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  // 获取任务详情
  const fetchTask = async (taskId: string) => {
    try {
      loading.value = true
      
      const response = await taskAPI.getTask(taskId)
      
      if (response.data.success && response.data.data) {
        currentTask.value = response.data.data
        return response.data.data
      }
      
      return null
    } catch (error) {
      console.error('获取任务详情失败:', error)
      return null
    } finally {
      loading.value = false
    }
  }

  // 创建任务
  const createTask = async (data: CreateTaskRequest): Promise<boolean> => {
    try {
      loading.value = true
      
      const response = await taskAPI.createTask(data)
      
      if (response.data.success && response.data.data) {
        ElMessage.success('任务创建成功')
        await fetchTasks() // 刷新任务列表
        await fetchStats() // 刷新统计数据
        return true
      }
      
      return false
    } catch (error) {
      console.error('创建任务失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  // 停止任务
  const stopTask = async (taskId: string): Promise<boolean> => {
    try {
      loading.value = true
      
      const response = await taskAPI.stopTask(taskId)
      
      if (response.data.success) {
        ElMessage.success('任务已停止')
        await fetchTasks() // 刷新任务列表
        
        // 如果当前查看的是这个任务，也要刷新
        if (currentTask.value?.id === taskId) {
          await fetchTask(taskId)
        }
        
        return true
      }
      
      return false
    } catch (error) {
      console.error('停止任务失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  // 重试任务
  const retryTask = async (taskId: string): Promise<boolean> => {
    try {
      loading.value = true
      
      const response = await taskAPI.retryTask(taskId)
      
      if (response.data.success) {
        ElMessage.success('任务已重新启动')
        await fetchTasks() // 刷新任务列表
        
        // 如果当前查看的是这个任务，也要刷新
        if (currentTask.value?.id === taskId) {
          await fetchTask(taskId)
        }
        
        return true
      }
      
      return false
    } catch (error) {
      console.error('重试任务失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  // 删除任务
  const deleteTask = async (taskId: string): Promise<boolean> => {
    try {
      loading.value = true
      
      const response = await taskAPI.deleteTask(taskId)
      
      if (response.data.success) {
        ElMessage.success('任务已删除')
        await fetchTasks() // 刷新任务列表
        await fetchStats() // 刷新统计数据
        
        // 如果当前查看的是被删除的任务，清空当前任务
        if (currentTask.value?.id === taskId) {
          currentTask.value = null
        }
        
        return true
      }
      
      return false
    } catch (error) {
      console.error('删除任务失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  // 获取统计数据
  const fetchStats = async () => {
    try {
      const response = await taskAPI.getTaskStats()
      
      if (response.data.success && response.data.data) {
        const data = response.data.data
        stats.value = {
          totalTasks: data.total_tasks || 0,
          completedTasks: data.completed_tasks || 0,
          runningTasks: data.running_tasks || 0,
          failedTasks: data.failed_tasks || 0,
          totalViolations: data.total_violations || 0,
          violationDistribution: Array.isArray(data.violation_distribution) 
            ? data.violation_distribution 
            : Object.entries(data.violation_distribution || {}).map(([type, count]) => ({ type, count, name: type })),
          recentTasks: data.recent_tasks || [],
          taskTrends: data.task_trends || [],
          riskLevelDistribution: data.risk_level_distribution || [],
          systemStatus: data.system_status || {}
        }
      }
    } catch (error) {
      console.error('获取统计数据失败:', error)
      throw error
    }
  }

  // 设置过滤条件
  const setFilters = (newFilters: TaskFilter) => {
    filters.value = { ...newFilters }
  }

  // 设置分页
  const setPagination = (page: number, size?: number) => {
    pagination.value.page = page
    if (size) {
      pagination.value.size = size
    }
  }

  // 重置状态
  const resetState = () => {
    tasks.value = []
    currentTask.value = null
    pagination.value = { page: 1, size: 20, total: 0 }
    filters.value = {}
  }

  // 获取任务状态文本
  const getStatusText = (status: TaskStatus): string => {
    const statusMap: Record<TaskStatus, string> = {
      [TaskStatus.PENDING]: '等待中',
      [TaskStatus.RUNNING]: '运行中',
      [TaskStatus.COMPLETED]: '已完成',
      [TaskStatus.FAILED]: '失败',
      [TaskStatus.CANCELLED]: '已取消'
    }
    return statusMap[status] || status
  }

  // 获取状态类型（用于Element Plus组件）
  const getStatusType = (status: TaskStatus): string => {
    const typeMap: Record<TaskStatus, string> = {
      [TaskStatus.PENDING]: 'info',
      [TaskStatus.RUNNING]: 'warning',
      [TaskStatus.COMPLETED]: 'success',
      [TaskStatus.FAILED]: 'danger',
      [TaskStatus.CANCELLED]: 'info'
    }
    return typeMap[status] || 'info'
  }

  return {
    // 状态
    tasks: computed(() => tasks.value),
    currentTask: computed(() => currentTask.value),
    loading: computed(() => loading.value),
    pagination: computed(() => pagination.value),
    filters: computed(() => filters.value),
    stats: computed(() => stats.value),
    
    // 计算属性
    totalTasks,
    completedTasks,
    runningTasks,
    failedTasks,
    totalViolations,
    violationDistribution,
    recentTasks,
    
    // 方法
    fetchTasks,
    fetchTask,
    createTask,
    stopTask,
    retryTask,
    deleteTask,
    fetchStats,
    setFilters,
    setPagination,
    resetState,
    getStatusText,
    getStatusType
  }
})