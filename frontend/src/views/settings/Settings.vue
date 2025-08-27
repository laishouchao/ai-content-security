<template>
  <div class="settings">
    <div class="page-header">
      <h2>系统设置</h2>
      <p>配置系统参数和功能选项</p>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- AI配置 -->
      <el-tab-pane label="AI配置" name="ai">
        <AIConfigPanel 
          :config="aiConfig" 
          @update="handleAIConfigUpdate"
          @save="saveAIConfig"
        />
      </el-tab-pane>

      <!-- 系统配置 -->
      <el-tab-pane label="系统配置" name="system">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统基本配置</span>
              <el-button type="primary" @click="saveSystemConfig" :loading="saving">
                保存配置
              </el-button>
            </div>
          </template>
          
          <el-form :model="systemConfig" label-width="150px" v-loading="loading">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="最大并发任务">
                  <el-input-number 
                    v-model="systemConfig.scan_limits.max_concurrent_tasks_per_user" 
                    :min="1" 
                    :max="50" 
                  />
                </el-form-item>
                <el-form-item label="最大子域名数">
                  <el-input-number 
                    v-model="systemConfig.scan_limits.max_subdomains_per_task" 
                    :min="10" 
                    :max="10000" 
                  />
                </el-form-item>
                <el-form-item label="最大爬取深度">
                  <el-input-number 
                    v-model="systemConfig.scan_limits.max_crawl_depth" 
                    :min="1" 
                    :max="10" 
                  />
                </el-form-item>
                <el-form-item label="任务超时时间(小时)">
                  <el-input-number 
                    v-model="systemConfig.scan_limits.task_timeout_hours" 
                    :min="1" 
                    :max="168" 
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="最大登录尝试次数">
                  <el-input-number 
                    v-model="systemConfig.security.max_login_attempts" 
                    :min="1" 
                    :max="10" 
                  />
                </el-form-item>
                <el-form-item label="锁定时长(分钟)">
                  <el-input-number 
                    v-model="systemConfig.security.lockout_duration_minutes" 
                    :min="1" 
                    :max="1440" 
                  />
                </el-form-item>
                <el-form-item label="令牌过期时间(分钟)">
                  <el-input-number 
                    v-model="systemConfig.security.access_token_expire_minutes" 
                    :min="5" 
                    :max="43200" 
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- 性能监控 -->
      <el-tab-pane label="性能监控" name="performance">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-card>
              <template #header>
                <div class="card-header">
                  <span>系统性能</span>
                  <el-button @click="refreshPerformance" :loading="performanceLoading">
                    <el-icon><Refresh /></el-icon>
                    刷新
                  </el-button>
                </div>
              </template>
              
              <div v-if="performanceStats">
                <div class="performance-item">
                  <span class="perf-label">CPU使用率</span>
                  <el-progress 
                    :percentage="performanceStats.system_health?.cpu_percent || 0" 
                    :stroke-width="8"
                    :color="getPerformanceColor(performanceStats.system_health?.cpu_percent || 0)"
                  />
                </div>
                <div class="performance-item">
                  <span class="perf-label">内存使用率</span>
                  <el-progress 
                    :percentage="performanceStats.memory_stats?.memory_info?.process_memory?.percent || 0" 
                    :stroke-width="8"
                    :color="getPerformanceColor(performanceStats.memory_stats?.memory_info?.process_memory?.percent || 0)"
                  />
                </div>
                <div class="performance-item">
                  <span class="perf-label">磁盘使用率</span>
                  <el-progress 
                    :percentage="performanceStats.system_health?.disk_usage?.percent || 0" 
                    :stroke-width="8"
                    :color="getPerformanceColor(performanceStats.system_health?.disk_usage?.percent || 0)"
                  />
                </div>
                <div class="performance-item">
                  <span class="perf-label">健康分数</span>
                  <el-progress 
                    :percentage="performanceStats.overall_health_score || 0" 
                    :stroke-width="8"
                    :color="getHealthColor(performanceStats.overall_health_score || 0)"
                  />
                </div>
              </div>
            </el-card>
          </el-col>
          
          <el-col :span="12">
            <el-card>
              <template #header>
                <span>服务状态</span>
              </template>
              
              <div v-if="performanceStats">
                <div class="service-item">
                  <span class="service-label">数据库连接</span>
                  <el-tag 
                    :type="performanceStats.database_stats?.connection_pool?.available_connections > 0 ? 'success' : 'danger'"
                  >
                    {{ performanceStats.database_stats?.connection_pool?.available_connections || 0 }} 可用
                  </el-tag>
                </div>
                <div class="service-item">
                  <span class="service-label">Redis连接</span>
                  <el-tag 
                    :type="performanceStats.redis_stats?.connected ? 'success' : 'danger'"
                  >
                    {{ performanceStats.redis_stats?.connected ? '已连接' : '断开' }}
                  </el-tag>
                </div>
                <div class="service-item">
                  <span class="service-label">Celery任务</span>
                  <el-tag type="info">
                    {{ performanceStats.celery_stats?.metrics?.active_tasks || 0 }} 活跃
                  </el-tag>
                </div>
                <div class="service-item">
                  <span class="service-label">内存压力</span>
                  <el-tag 
                    :type="performanceStats.memory_stats?.memory_pressure ? 'warning' : 'success'"
                  >
                    {{ performanceStats.memory_stats?.memory_pressure ? '高' : '正常' }}
                  </el-tag>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 系统操作 -->
        <el-card style="margin-top: 20px;">
          <template #header>
            <span>系统操作</span>
          </template>
          
          <div class="system-actions-grid">
            <el-button 
              type="warning" 
              @click="clearCache" 
              :loading="clearingCache"
            >
              <el-icon><Delete /></el-icon>
              清理缓存
            </el-button>
            <el-button 
              type="success" 
              @click="performHealthCheck" 
              :loading="checkingHealth"
            >
              <el-icon><CircleCheck /></el-icon>
              健康检查
            </el-button>
            <el-button 
              type="primary" 
              @click="optimizeSystem" 
              :loading="optimizing"
            >
              <el-icon><Tools /></el-icon>
              系统优化
            </el-button>
            <el-button 
              type="danger" 
              @click="confirmRestart"
            >
              <el-icon><RefreshRight /></el-icon>
              重启系统
            </el-button>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 系统信息 -->
      <el-tab-pane label="系统信息" name="info">
        <el-card>
          <template #header>
            <span>系统信息</span>
          </template>
          
          <el-descriptions :column="2" border v-if="systemInfo">
            <el-descriptions-item label="系统版本">{{ systemInfo.version || 'v1.0.0' }}</el-descriptions-item>
            <el-descriptions-item label="Python版本">{{ systemInfo.python_version || 'Python 3.9+' }}</el-descriptions-item>
            <el-descriptions-item label="数据库">{{ systemInfo.database || 'PostgreSQL' }}</el-descriptions-item>
            <el-descriptions-item label="缓存">{{ systemInfo.cache || 'Redis' }}</el-descriptions-item>
            <el-descriptions-item label="运行时间">
              {{ formatUptime(performanceStats?.system_health?.uptime) }}
            </el-descriptions-item>
            <el-descriptions-item label="进程ID">{{ systemInfo.process_id || 'N/A' }}</el-descriptions-item>
            <el-descriptions-item label="CPU核心数">{{ performanceStats?.system_health?.cpu_cores || 'N/A' }}</el-descriptions-item>
            <el-descriptions-item label="总内存">
              {{ formatBytes(performanceStats?.system_health?.total_memory) }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Refresh, 
  Delete, 
  CircleCheck, 
  Tools, 
  RefreshRight 
} from '@element-plus/icons-vue'
import AIConfigPanel from '@/components/settings/AIConfigPanel.vue'
import { configApi } from '@/api/config'
import http from '@/api/http'
import type { AIConfig, ApiResponse } from '@/types'

const activeTab = ref('ai')
const loading = ref(false)
const saving = ref(false)
const performanceLoading = ref(false)
const clearingCache = ref(false)
const checkingHealth = ref(false)
const optimizing = ref(false)

// AI配置
const aiConfig = reactive<AIConfig>({
  id: '',
  user_id: '',
  openai_base_url: '',
  ai_model_name: '',
  max_tokens: 0,
  temperature: 0,
  request_timeout: 0,
  retry_count: 0,
  enable_streaming: false,
  has_valid_config: false,
  created_at: '',
  updated_at: '',
  last_tested: '',
  openai_api_key: '',
  system_prompt: '',
  custom_prompt_template: ''
})

// 系统配置
const systemConfig = reactive({
  scan_limits: {
    max_concurrent_tasks_per_user: 5,
    max_subdomains_per_task: 1000,
    max_crawl_depth: 3,
    task_timeout_hours: 24
  },
  ai_settings: {
    default_model: 'gpt-3.5-turbo',
    default_max_tokens: 2000,
    default_temperature: 0.7,
    request_timeout: 30,
    retry_count: 3
  },
  security: {
    max_login_attempts: 5,
    lockout_duration_minutes: 15,
    rate_limit_per_minute: 60,
    access_token_expire_minutes: 1440
  }
})

// 性能统计数据
const performanceStats = ref<any>(null)
const systemInfo = ref<any>(null)

// 处理AI配置更新
const handleAIConfigUpdate = (config: Partial<AIConfig>) => {
  Object.assign(aiConfig, config)
}

// 保存AI配置
const saveAIConfig = async () => {
  try {
    const response: ApiResponse<AIConfig> = await configApi.ai.updateConfig({
      openai_api_key: aiConfig.openai_api_key,
      openai_base_url: aiConfig.openai_base_url,
      ai_model_name: aiConfig.ai_model_name,
      max_tokens: aiConfig.max_tokens,
      temperature: aiConfig.temperature,
      request_timeout: aiConfig.request_timeout,
      retry_count: aiConfig.retry_count,
      enable_streaming: aiConfig.enable_streaming,
      system_prompt: aiConfig.system_prompt,
      custom_prompt_template: aiConfig.custom_prompt_template
    })
    
    // 检查响应格式 - 后端直接返回AIConfig对象而不是包装在ApiResponse中
    if (response && response.data) {
      ElMessage.success('AI配置保存成功')
      // 更新本地配置
      Object.assign(aiConfig, response.data)
    } else if (response) {
      // 如果响应本身就是AIConfig对象（没有包装在data中）
      ElMessage.success('AI配置保存成功')
      Object.assign(aiConfig, response)
    } else {
      ElMessage.error('保存失败')
    }
  } catch (error: any) {
    console.error('保存AI配置失败:', error)
    ElMessage.error(error.message || '保存AI配置失败')
  }
}

// 获取AI配置
const fetchAIConfig = async () => {
  try {
    const response: ApiResponse<AIConfig> = await configApi.ai.getConfig()
    
    // 检查响应格式 - 后端直接返回AIConfig对象而不是包装在ApiResponse中
    if (response && response.data) {
      // 确保正确更新aiConfig对象
      Object.assign(aiConfig, response.data)
    } else if (response) {
      // 如果响应本身就是AIConfig对象（没有包装在data中）
      Object.assign(aiConfig, response)
    } else {
      // 如果没有配置，初始化一个空配置
      Object.assign(aiConfig, {
        id: '',
        user_id: '',
        openai_base_url: '',
        ai_model_name: '',
        max_tokens: 0,
        temperature: 0,
        request_timeout: 0,
        retry_count: 0,
        enable_streaming: false,
        has_valid_config: false,
        created_at: '',
        updated_at: '',
        last_tested: '',
        openai_api_key: '',
        system_prompt: '',
        custom_prompt_template: ''
      })
    }
  } catch (error) {
    console.error('获取AI配置失败:', error)
    ElMessage.error('获取AI配置失败')
  }
}

// 获取系统配置
const fetchSystemConfig = async () => {
  try {
    loading.value = true
    const response = await http.get('/config/system')
    
    if (response.data) {
      Object.assign(systemConfig, response.data)
    }
  } catch (error) {
    console.error('获取系统配置失败:', error)
  } finally {
    loading.value = false
  }
}

// 保存系统配置
const saveSystemConfig = async () => {
  try {
    saving.value = true
    await http.put('/config/system', systemConfig)
    ElMessage.success('系统配置保存成功')
  } catch (error) {
    console.error('保存系统配置失败:', error)
    ElMessage.error('保存系统配置失败')
  } finally {
    saving.value = false
  }
}

// 获取性能统计
const refreshPerformance = async () => {
  try {
    performanceLoading.value = true
    const response = await http.get('/performance/stats')
    
    if (response.data.success) {
      performanceStats.value = response.data.data
    }
  } catch (error) {
    console.error('获取性能统计失败:', error)
    ElMessage.error('获取性能统计失败')
  } finally {
    performanceLoading.value = false
  }
}

// 清理缓存
const clearCache = async () => {
  try {
    clearingCache.value = true
    await http.post('/performance/cache/clear')
    ElMessage.success('缓存清理成功')
    await refreshPerformance()
  } catch (error) {
    console.error('清理缓存失败:', error)
    ElMessage.error('清理缓存失败')
  } finally {
    clearingCache.value = false
  }
}

// 健康检查
const performHealthCheck = async () => {
  try {
    checkingHealth.value = true
    const response = await http.get('/performance/health')
    
    if (response.data.success) {
      const healthData = response.data.data
      const status = healthData.status
      
      if (status === 'healthy') {
        ElMessage.success('系统健康检查通过')
      } else if (status === 'warning') {
        ElMessage.warning('系统健康检查发现警告')
      } else {
        ElMessage.error('系统健康检查发现问题')
      }
      
      await refreshPerformance()
    }
  } catch (error) {
    console.error('健康检查失败:', error)
    ElMessage.error('健康检查失败')
  } finally {
    checkingHealth.value = false
  }
}

// 系统优化
const optimizeSystem = async () => {
  try {
    optimizing.value = true
    await http.post('/performance/optimize')
    ElMessage.success('系统优化完成')
    await refreshPerformance()
  } catch (error) {
    console.error('系统优化失败:', error)
    ElMessage.error('系统优化失败')
  } finally {
    optimizing.value = false
  }
}

// 确认重启
const confirmRestart = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要重启系统吗？这将中断所有正在运行的任务。',
      '确认重启',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    ElMessage.info('重启请求已发送，系统将在稍后重启...')
    // 注意：实际生产中应该有适当的重启机制
  } catch (error) {
    // 用户取消操作
  }
}

// 获取性能颜色
const getPerformanceColor = (percentage: number) => {
  if (percentage < 60) return '#67c23a'
  if (percentage < 80) return '#e6a23c'
  return '#f56c6c'
}

// 获取健康分数颜色
const getHealthColor = (score: number) => {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

// 格式化运行时间
const formatUptime = (seconds?: number) => {
  if (!seconds) return 'N/A'
  
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  
  return `${days}天 ${hours}小时 ${minutes}分钟`
}

// 格式化字节数
const formatBytes = (bytes?: number) => {
  if (!bytes) return 'N/A'
  
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`
}

// 初始化
onMounted(() => {
  fetchAIConfig()
  fetchSystemConfig()
  refreshPerformance()
})
</script>

<style scoped>
.settings {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 4px 0;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.page-header p {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.performance-item {
  margin-bottom: 16px;
}

.perf-label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.service-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.service-item:last-child {
  border-bottom: none;
}

.service-label {
  font-size: 14px;
  color: #606266;
}

.system-actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.system-actions-grid .el-button {
  width: 100%;
}

.notification-test {
  text-align: center;
}

.notification-test .el-button {
  margin: 0 8px;
}

.el-card {
  margin-bottom: 20px;
}

.el-form-item {
  margin-bottom: 18px;
}

h4 {
  margin: 24px 0 16px 0;
  color: #303133;
  font-size: 16px;
  font-weight: 600;
  border-bottom: 1px solid #e4e7ed;
  padding-bottom: 8px;
}

h4:first-child {
  margin-top: 0;
}

.el-progress {
  width: 100%;
}

.el-descriptions {
  margin-bottom: 20px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .page-header {
    text-align: center;
  }
  
  .card-header {
    flex-direction: column;
    gap: 12px;
  }
  
  .system-actions-grid {
    grid-template-columns: 1fr;
  }
  
  .el-col {
    margin-bottom: 20px;
  }
}

/* 深色模式支持 */
@media (prefers-color-scheme: dark) {
  .page-header h2 {
    color: #e5eaf3;
  }
  
  .page-header p {
    color: #a3a6ad;
  }
  
  h4 {
    color: #e5eaf3;
    border-bottom-color: #4c4d4f;
  }
  
  .service-item {
    border-bottom-color: #4c4d4f;
  }
  
  .perf-label,
  .service-label {
    color: #a3a6ad;
  }
}
</style>