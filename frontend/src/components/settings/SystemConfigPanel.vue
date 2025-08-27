<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Setting } from '@element-plus/icons-vue'
import { systemAPI, type SystemConfig, type SystemStatus } from '@/api/system'

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const restarting = ref(false)

// 系统配置数据
const config = reactive<SystemConfig>({
  system_name: '',
  system_description: '',
  system_version: '',
  system_admin_email: '',
  
  debug_mode: false,
  log_level: 'INFO',
  max_workers: 4,
  worker_timeout: 300,
  
  database_pool_size: 10,
  database_timeout: 30,
  database_backup_enabled: true,
  database_backup_interval_hours: 24,
  
  redis_max_connections: 100,
  redis_timeout: 5,
  
  storage_type: 'local',
  storage_path: '/app/data',
  max_storage_size_gb: 100,
  auto_cleanup_enabled: true,
  cleanup_retention_days: 30,
  
  monitoring_enabled: true,
  metrics_retention_days: 7,
  alert_thresholds: {
    cpu_usage: 80,
    memory_usage: 80,
    disk_usage: 90,
    response_time: 1000
  },
  
  scheduler_enabled: true,
  backup_schedule: '0 2 * * *',
  cleanup_schedule: '0 3 * * *',
  report_schedule: '0 8 * * 1'
})

// 系统状态数据
const systemStatus = ref<SystemStatus | null>(null)

// 系统信息数据
const systemInfo = ref<any>(null)

// 表单验证规则
const rules = {
  system_name: [
    { required: true, message: '请输入系统名称', trigger: 'blur' }
  ],
  system_admin_email: [
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  max_workers: [
    { type: 'number', min: 1, max: 32, message: '工作进程数应在1-32之间', trigger: 'blur' }
  ]
}

// 加载系统配置
const loadConfig = async () => {
  try {
    loading.value = true
    const response = await systemAPI.getSystemConfig()
    
    if (response.data.success && response.data.data) {
      Object.assign(config, response.data.data)
    }
  } catch (error) {
    console.error('加载系统配置失败:', error)
    ElMessage.error('加载系统配置失败')
  } finally {
    loading.value = false
  }
}

// 保存配置
const saveConfig = async () => {
  try {
    saving.value = true
    await systemAPI.updateSystemConfig(config)
    ElMessage.success('系统配置保存成功')
  } catch (error) {
    console.error('保存系统配置失败:', error)
    ElMessage.error('保存系统配置失败')
  } finally {
    saving.value = false
  }
}

// 重启系统
const restartSystem = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要重启系统服务吗？这将中断所有正在进行的任务。',
      '确认重启',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    restarting.value = true
    await systemAPI.restartSystem()
    ElMessage.success('系统重启请求已发送，请稍等片刻')
    
    // 等待系统重启后刷新页面
    setTimeout(() => {
      window.location.reload()
    }, 10000)
  } catch (error) {
    if (error !== 'cancel') {
      console.error('重启系统失败:', error)
      ElMessage.error('重启系统失败')
      restarting.value = false
    }
  }
}

// 获取系统信息
const getSystemInfo = async () => {
  try {
    const [statusResponse, infoResponse] = await Promise.all([
      systemAPI.getSystemStatus(),
      systemAPI.getSystemInfo()
    ])
    
    if (statusResponse.data.success) {
      systemStatus.value = statusResponse.data.data
    }
    
    if (infoResponse.data.success) {
      systemInfo.value = infoResponse.data.data
    }
  } catch (error) {
    console.error('获取系统信息失败:', error)
    ElMessage.error('获取系统信息失败')
  }
}

// 清理缓存
const clearCache = async () => {
  try {
    await systemAPI.clearCache()
    ElMessage.success('缓存清理成功')
  } catch (error) {
    console.error('清理缓存失败:', error)
    ElMessage.error('清理缓存失败')
  }
}

// 创建备份
const createBackup = async () => {
  try {
    await systemAPI.createBackup()
    ElMessage.success('数据库备份已开始，请稍后检查备份状态')
  } catch (error) {
    console.error('创建备份失败:', error)
    ElMessage.error('创建备份失败')
  }
}

// 健康检查
const performHealthCheck = async () => {
  try {
    const response = await systemAPI.healthCheck()
    if (response.data.success) {
      ElMessage.success('系统健康检查通过')
    } else {
      ElMessage.warning('系统健康检查发现问题')
    }
  } catch (error) {
    console.error('健康检查失败:', error)
    ElMessage.error('健康检查失败')
  }
}

// 格式化文件大小
const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 格式化百分比
const formatPercentage = (value: number) => {
  return `${value.toFixed(1)}%`
}

// 获取状态颜色
const getStatusColor = (status: string) => {
  switch (status) {
    case 'healthy':
    case 'connected':
    case 'running':
      return 'success'
    case 'warning':
      return 'warning'
    case 'error':
    case 'disconnected':
    case 'stopped':
      return 'danger'
    default:
      return 'info'
  }
}

// 生命周期
onMounted(() => {
  loadConfig()
  getSystemInfo()
  
  // 定时更新系统状态
  const statusInterval = setInterval(() => {
    if (!loading.value) {
      getSystemInfo()
    }
  }, 30000) // 每30秒更新一次
  
  // 组件卸载时清理定时器
  onBeforeUnmount(() => {
    clearInterval(statusInterval)
  })
})
</script>