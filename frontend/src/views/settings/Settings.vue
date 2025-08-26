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

      <!-- 扫描配置 -->
      <el-tab-pane label="扫描配置" name="scan">
        <el-form :model="scanConfig" label-width="150px">
          <el-form-item label="默认并发数">
            <el-input-number v-model="scanConfig.concurrency" :min="1" :max="50" />
          </el-form-item>
          <el-form-item label="请求超时(秒)">
            <el-input-number v-model="scanConfig.timeout" :min="5" :max="300" />
          </el-form-item>
          <el-form-item label="重试次数">
            <el-input-number v-model="scanConfig.retries" :min="0" :max="10" />
          </el-form-item>
          <el-form-item label="用户代理">
            <el-input 
              v-model="scanConfig.userAgent" 
              placeholder="User-Agent字符串"
              style="width: 500px;"
            />
          </el-form-item>
          <el-form-item label="遵循robots.txt">
            <el-switch v-model="scanConfig.respectRobots" />
          </el-form-item>
          <el-form-item label="截图质量">
            <el-slider v-model="scanConfig.screenshotQuality" :min="10" :max="100" style="width: 200px;" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary">保存配置</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- 通知配置 -->
      <el-tab-pane label="通知配置" name="notification">
        <el-form :model="notificationConfig" label-width="150px">
          <el-form-item label="邮件通知">
            <el-switch v-model="notificationConfig.email.enabled" />
          </el-form-item>
          <el-form-item label="SMTP服务器" v-if="notificationConfig.email.enabled">
            <el-input 
              v-model="notificationConfig.email.smtp" 
              placeholder="smtp.example.com"
              style="width: 300px;"
            />
          </el-form-item>
          <el-form-item label="发送邮箱" v-if="notificationConfig.email.enabled">
            <el-input 
              v-model="notificationConfig.email.from" 
              placeholder="system@example.com"
              style="width: 300px;"
            />
          </el-form-item>
          <el-form-item label="Webhook通知">
            <el-switch v-model="notificationConfig.webhook.enabled" />
          </el-form-item>
          <el-form-item label="Webhook URL" v-if="notificationConfig.webhook.enabled">
            <el-input 
              v-model="notificationConfig.webhook.url" 
              placeholder="https://hooks.example.com/webhook"
              style="width: 400px;"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary">保存配置</el-button>
            <el-button>测试通知</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- 系统信息 -->
      <el-tab-pane label="系统信息" name="system">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="系统版本">v1.0.0</el-descriptions-item>
          <el-descriptions-item label="运行时间">3天 12小时</el-descriptions-item>
          <el-descriptions-item label="数据库">PostgreSQL 13.0</el-descriptions-item>
          <el-descriptions-item label="缓存">Redis 6.2</el-descriptions-item>
          <el-descriptions-item label="Python版本">3.9.7</el-descriptions-item>
          <el-descriptions-item label="Node.js版本">18.17.0</el-descriptions-item>
          <el-descriptions-item label="CPU使用率">
            <el-progress :percentage="25" :stroke-width="6" />
          </el-descriptions-item>
          <el-descriptions-item label="内存使用率">
            <el-progress :percentage="68" :stroke-width="6" />
          </el-descriptions-item>
        </el-descriptions>
        
        <el-divider />
        
        <div class="system-actions">
          <el-button type="warning">清理缓存</el-button>
          <el-button type="info">导出日志</el-button>
          <el-button type="danger">重启系统</el-button>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import AIConfigPanel from '@/components/settings/AIConfigPanel.vue'
import { configApi } from '@/api/config'
import type { AIConfig, ApiResponse } from '@/types'

const activeTab = ref('ai')

// AI配置
const aiConfig = reactive<AIConfig>({
  id: '',
  user_id: '',
  openai_base_url: 'https://api.openai.com/v1',
  model_name: 'gpt-4-vision-preview',
  max_tokens: 4096,
  temperature: 0.1,
  request_timeout: 30,
  retry_count: 3,
  enable_streaming: false,
  has_valid_config: false,
  created_at: '',
  updated_at: '',
  last_tested: '',
  openai_api_key: '',
  system_prompt: '',
  custom_prompt_template: ''
})

// 扫描配置
const scanConfig = reactive({
  concurrency: 10,
  timeout: 30,
  retries: 3,
  userAgent: 'AI-Content-Security-Scanner/1.0',
  respectRobots: true,
  screenshotQuality: 80
})

// 通知配置
const notificationConfig = reactive({
  email: {
    enabled: false,
    smtp: '',
    from: ''
  },
  webhook: {
    enabled: false,
    url: ''
  }
})

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
      model_name: aiConfig.model_name,
      max_tokens: aiConfig.max_tokens,
      temperature: aiConfig.temperature,
      request_timeout: aiConfig.request_timeout,
      retry_count: aiConfig.retry_count,
      enable_streaming: aiConfig.enable_streaming,
      system_prompt: aiConfig.system_prompt,
      custom_prompt_template: aiConfig.custom_prompt_template
    })
    
    if (response.success) {
      ElMessage.success('AI配置保存成功')
      // 更新本地配置
      Object.assign(aiConfig, response.data)
    } else {
      ElMessage.error(response.message || '保存失败')
    }
  } catch (error) {
    console.error('保存AI配置失败:', error)
    ElMessage.error('保存AI配置失败')
  }
}

// 获取AI配置
const fetchAIConfig = async () => {
  try {
    const response: ApiResponse<AIConfig> = await configApi.ai.getConfig()
    if (response.success && response.data) {
      Object.assign(aiConfig, response.data)
    }
  } catch (error) {
    console.error('获取AI配置失败:', error)
    ElMessage.error('获取AI配置失败')
  }
}

onMounted(() => {
  fetchAIConfig()
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

.system-actions {
  text-align: center;
  margin-top: 20px;
}

.system-actions .el-button {
  margin: 0 10px;
}
</style>