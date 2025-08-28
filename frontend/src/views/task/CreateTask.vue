<template>
  <div class="create-task">
    <div class="page-header">
      <h2>创建扫描任务</h2>
      <p>配置新的域名安全扫描任务</p>
    </div>

    <el-card>
      <el-form
        ref="taskFormRef"
        :model="taskForm"
        :rules="taskRules"
        label-width="120px"
        @submit.prevent="handleSubmit"
      >
        <!-- 基本配置 -->
        <el-divider content-position="left">基本配置</el-divider>
        
        <!-- 配置预设 -->
        <el-form-item label="配置预设">
          <el-select 
            v-model="selectedPreset" 
            placeholder="选择预设配置" 
            @change="handlePresetChange"
            style="width: 60px"
          >
            <el-option
              v-for="preset in configPresets"
              :key="preset.name"
              :label="preset.name"
              :value="preset.name"
            >
              <div style="display: flex; flex-direction: column">
                <span style="font-weight: 500">{{ preset.name }}</span>
                <span style="font-size: 12px; color: #999">{{ preset.description }}</span>
              </div>
            </el-option>
          </el-select>
          <div class="form-tip">
            🎯 选择预设配置快速设置参数，或手动调整配置
          </div>
        </el-form-item>
        
        <el-form-item label="目标域名" prop="domain">
          <el-input
            v-model="taskForm.domain"
            placeholder="请输入要扫描的域名，如: example.com"
          />
        </el-form-item>
        
        <el-form-item label="任务名称" prop="name">
          <el-input
            v-model="taskForm.name"
            placeholder="为任务设置一个名称（可选）"
          />
        </el-form-item>
        
        <el-form-item label="任务描述">
          <el-input
            v-model="taskForm.description"
            type="textarea"
            :rows="3"
            placeholder="描述此次扫描的目的或备注信息（可选）"
          />
        </el-form-item>

        <!-- 扫描配置 -->
        <el-divider content-position="left">扫描配置</el-divider>
        
        <el-form-item label="扫描模式">
          <el-radio-group v-model="taskForm.scanMode">
            <el-radio value="quick">快速扫描</el-radio>
            <el-radio value="standard">标准扫描</el-radio>
            <el-radio value="deep">深度扫描</el-radio>
          </el-radio-group>
          <div class="form-tip">
            快速：仅扫描主域名 | 标准：包含子域名发现 | 深度：全面扫描所有功能
          </div>
        </el-form-item>
        
        <el-form-item label="子域名发现">
          <el-switch v-model="taskForm.enableSubdomain" />
          <span class="form-label">启用子域名发现功能</span>
        </el-form-item>
        
        <el-form-item label="链接爬取" v-if="taskForm.enableSubdomain">
          <el-switch v-model="taskForm.enableCrawling" />
          <span class="form-label">递归爬取页面链接</span>
        </el-form-item>
        
        <el-form-item label="内容抓取">
          <el-switch v-model="taskForm.enableCapture" />
          <span class="form-label">抓取页面内容和截图</span>
        </el-form-item>
        
        <el-form-item label="AI分析">
          <el-switch v-model="taskForm.enableAI" />
          <span class="form-label">使用AI进行内容违规检测</span>
        </el-form-item>

        <!-- 高级配置 -->
        <el-divider content-position="left">高级配置</el-divider>
        
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="最大子域名">
              <el-input-number
                v-model="taskForm.maxSubdomains"
                :min="1"
                :max="1000"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          
          <el-col :span="8">
            <el-form-item label="爬取深度">
              <el-input-number
                v-model="taskForm.crawlDepth"
                :min="1"
                :max="10"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          
          <el-col :span="8">
            <el-form-item label="页面限制">
              <el-input-number
                v-model="taskForm.maxPages"
                :min="1"
                :max="10000"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="请求间隔">
          <el-slider
            v-model="taskForm.requestDelay"
            :min="100"
            :max="5000"
            :step="100"
            show-input
            input-size="small"
            style="width: 300px"
          />
          <span class="form-unit">毫秒</span>
        </el-form-item>
        
        <el-form-item label="超时设置">
          <el-input-number
            v-model="taskForm.timeout"
            :min="5"
            :max="300"
            style="width: 200px"
          />
          <span class="form-unit">秒</span>
        </el-form-item>

        <!-- 性能优化配置 -->
        <el-divider content-position="left">
          <el-icon><Lightning /></el-icon>
          性能优化配置
        </el-divider>
        
        <el-form-item label="并行执行器">
          <el-switch v-model="taskForm.useParallelExecutor" />
          <span class="form-label">启用三轨并行流水线架构</span>
          <div class="form-tip">
            🚀 启用后可提升3-5倍执行速度，适合大规模扫描任务
          </div>
        </el-form-item>
        
        <el-form-item label="智能AI预筛选">
          <el-switch v-model="taskForm.smartPrefilterEnabled" />
          <span class="form-label">启用AI调用优化</span>
          <div class="form-tip">
            💰 可减少70-90%的AI调用，大幅降低成本同时提升速度
          </div>
        </el-form-item>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="DNS并发数">
              <el-input-number
                v-model="taskForm.dnsConcurrency"
                :min="10"
                :max="200"
                :step="10"
                style="width: 100%"
              />
              <div class="form-tip">
                子域名发现的DNS查询并发数，建议100-150
              </div>
            </el-form-item>
          </el-col>
          
          <el-col :span="12">
            <el-form-item label="AI预筛选阈值">
              <el-slider
                v-model="taskForm.aiSkipThreshold"
                :min="0.1"
                :max="0.8"
                :step="0.1"
                show-input
                input-size="small"
                :format-tooltip="(val) => `${(val * 100).toFixed(0)}%`"
                style="width: 100%"
              />
              <div class="form-tip">
                阈值越低，AI跳过率越高，成本越低
              </div>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="多视角截图">
          <el-switch v-model="taskForm.multiViewportCapture" />
          <span class="form-label">启用桌面/移动/平板多视角截图</span>
          <div class="form-tip">
            📱 同时抓取多种设备视角的页面截图，提供更全面的分析
          </div>
        </el-form-item>
        
        <el-form-item label="激进缓存">
          <el-switch v-model="taskForm.enableAggressiveCaching" />
          <span class="form-label">启用激进缓存策略</span>
          <div class="form-tip">
            ⚡ 大幅减少重复计算，适合批量扫描相似域名
          </div>
        </el-form-item>

        <!-- 提交按钮 -->
        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            创建任务
          </el-button>
          <el-button @click="handleReset">重置</el-button>
          <el-button @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Lightning } from '@element-plus/icons-vue'
import { taskAPI } from '@/api/task'
import type { CreateTaskRequest, TaskConfigPreset } from '@/api/task'

const router = useRouter()

// 响应式状态
const submitting = ref(false)
const taskFormRef = ref<FormInstance>()
const selectedPreset = ref('')
const configPresets = ref<TaskConfigPreset[]>([])

const taskForm = reactive({
  domain: '',
  name: '',
  description: '',
  scanMode: 'standard',
  enableSubdomain: true,
  enableCrawling: true,
  enableCapture: true,
  enableAI: true,
  maxSubdomains: 100,
  crawlDepth: 3,
  maxPages: 1000,
  requestDelay: 1000,
  timeout: 30,
  // 性能优化配置
  useParallelExecutor: true,      // 默认启用并行执行器
  smartPrefilterEnabled: true,    // 默认启用智能预筛选
  dnsConcurrency: 100,            // DNS并发数
  aiSkipThreshold: 0.3,           // AI跳过阈值
  multiViewportCapture: false,    // 多视角截图
  enableAggressiveCaching: false  // 激进缓存
})

// 表单验证规则
const taskRules: FormRules = {
  domain: [
    { required: true, message: '请输入目标域名', trigger: 'blur' },
    {
      pattern: /^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$/,
      message: '请输入有效的域名格式',
      trigger: 'blur'
    }
  ],
  name: [
    { max: 100, message: '任务名称不能超过100个字符', trigger: 'blur' }
  ]
}

// 加载配置预设
const loadConfigPresets = async () => {
  try {
    const response = await taskAPI.getConfigPresets()
    if (response.data.success && response.data.data) {
      configPresets.value = response.data.data
    }
  } catch (error) {
    console.error('加载配置预设失败:', error)
  }
}

// 处理预设配置变化
const handlePresetChange = (presetName: string) => {
  const preset = configPresets.value.find(p => p.name === presetName)
  if (preset) {
    // 应用预设配置到表单
    const config = preset.config
    taskForm.enableSubdomain = config.subdomain_discovery_enabled
    taskForm.enableCrawling = config.link_crawling_enabled
    taskForm.enableCapture = config.content_capture_enabled
    taskForm.enableAI = config.ai_analysis_enabled
    taskForm.maxSubdomains = config.max_subdomains
    taskForm.crawlDepth = config.max_crawl_depth
    taskForm.maxPages = config.max_pages_per_domain
    taskForm.requestDelay = config.request_delay
    taskForm.timeout = config.timeout
    
    // 性能优化配置
    taskForm.useParallelExecutor = config.use_parallel_executor ?? true
    taskForm.smartPrefilterEnabled = config.smart_prefilter_enabled ?? true
    taskForm.dnsConcurrency = config.dns_concurrency ?? 100
    taskForm.aiSkipThreshold = config.ai_skip_threshold ?? 0.3
    taskForm.multiViewportCapture = config.multi_viewport_capture ?? false
    taskForm.enableAggressiveCaching = config.enable_aggressive_caching ?? false
    
    ElMessage.success(`已应用预设配置: ${presetName}`)
  }
}

// 组件挂载时加载预设
onMounted(() => {
  loadConfigPresets()
})

// 监听扫描模式变化
watch(() => taskForm.scanMode, (newMode) => {
  switch (newMode) {
    case 'quick':
      taskForm.enableSubdomain = false
      taskForm.enableCrawling = false
      taskForm.enableCapture = true
      taskForm.enableAI = true
      taskForm.maxSubdomains = 1
      taskForm.crawlDepth = 1
      taskForm.maxPages = 50
      // 快速模式优化配置
      taskForm.dnsConcurrency = 50
      taskForm.aiSkipThreshold = 0.2
      taskForm.multiViewportCapture = false
      break
    case 'standard':
      taskForm.enableSubdomain = true
      taskForm.enableCrawling = true
      taskForm.enableCapture = true
      taskForm.enableAI = true
      taskForm.maxSubdomains = 100
      taskForm.crawlDepth = 3
      taskForm.maxPages = 1000
      // 标准模式优化配置
      taskForm.dnsConcurrency = 100
      taskForm.aiSkipThreshold = 0.3
      taskForm.multiViewportCapture = false
      break
    case 'deep':
      taskForm.enableSubdomain = true
      taskForm.enableCrawling = true
      taskForm.enableCapture = true
      taskForm.enableAI = true
      taskForm.maxSubdomains = 500
      taskForm.crawlDepth = 5
      taskForm.maxPages = 5000
      // 深度模式优化配置
      taskForm.dnsConcurrency = 150
      taskForm.aiSkipThreshold = 0.4
      taskForm.multiViewportCapture = true
      break
  }
})

// 方法
const handleSubmit = async () => {
  if (!taskFormRef.value) return
  
  try {
    const valid = await taskFormRef.value.validate()
    if (!valid) return
    
    submitting.value = true
    
    // 构造请求数据
    const requestData: CreateTaskRequest = {
      target_domain: taskForm.domain,
      task_name: taskForm.name || undefined,
      description: taskForm.description || undefined,
      config: {
        subdomain_discovery_enabled: taskForm.enableSubdomain,
        link_crawling_enabled: taskForm.enableCrawling,
        third_party_identification_enabled: true, // 始终启用第三方识别
        content_capture_enabled: taskForm.enableCapture,
        ai_analysis_enabled: taskForm.enableAI,
        max_subdomains: taskForm.maxSubdomains,
        max_crawl_depth: taskForm.crawlDepth,
        max_pages_per_domain: taskForm.maxPages,
        request_delay: taskForm.requestDelay,
        timeout: taskForm.timeout,
        // 性能优化配置
        use_parallel_executor: taskForm.useParallelExecutor,
        smart_prefilter_enabled: taskForm.smartPrefilterEnabled,
        dns_concurrency: taskForm.dnsConcurrency,
        ai_skip_threshold: taskForm.aiSkipThreshold,
        multi_viewport_capture: taskForm.multiViewportCapture,
        enable_aggressive_caching: taskForm.enableAggressiveCaching,
        
        // 高级配置
        certificate_discovery_enabled: true,
        passive_dns_enabled: false,
        max_concurrent_ai_calls: 3,
        batch_size: 10,
        screenshot_optimization: true,
        max_crawl_iterations: 5
      }
    }
    
    // 调用API创建任务
    const response = await taskAPI.createTask(requestData)
    
    if (response.data.success) {
      ElMessage.success('任务创建成功')
      router.push('/tasks')
    } else {
      ElMessage.error(response.data.message || '创建任务失败')
    }
  } catch (error: any) {
    console.error('创建任务失败:', error)
    ElMessage.error(error.response?.data?.message || '创建任务失败，请重试')
  } finally {
    submitting.value = false
  }
}

const handleReset = () => {
  if (!taskFormRef.value) return
  taskFormRef.value.resetFields()
}
</script>

<style scoped>
.create-task {
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

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
  line-height: 1.4;
}

.form-label {
  margin-left: 8px;
  font-size: 14px;
  color: #666;
}

.form-unit {
  margin-left: 8px;
  font-size: 14px;
  color: #999;
}

:deep(.el-divider__text) {
  background-color: #fff;
  font-weight: 600;
  color: #333;
}

:deep(.el-form-item) {
  margin-bottom: 22px;
}

:deep(.el-slider) {
  margin-right: 20px;
}
</style>