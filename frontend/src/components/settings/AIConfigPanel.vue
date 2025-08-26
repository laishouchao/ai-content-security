<template>
  <div class="ai-config-panel">
    <div class="panel-header">
      <h3>AI服务配置</h3>
      <p>配置OpenAI API相关参数，用于违规内容检测</p>
    </div>

    <el-form
      ref="formRef"
      :model="localConfig"
      :rules="rules"
      label-width="150px"
      class="config-form"
    >
      <!-- API基础URL -->
      <el-form-item label="API基础URL" prop="openai_base_url">
        <el-input
          v-model="localConfig.openai_base_url"
          placeholder="https://api.openai.com/v1"
          clearable
          @input="handleConfigChange"
        />
        <div class="form-tip">
          如使用代理服务或本地模型，请修改为对应的基础URL
        </div>
      </el-form-item>

      <!-- API密钥 -->
      <el-form-item label="API密钥" prop="openai_api_key" required>
        <el-input
          v-model="localConfig.openai_api_key"
          type="password"
          placeholder="请输入OpenAI API密钥"
          show-password
          clearable
          @input="handleConfigChange"
        />
        <div class="form-tip">
          获取API密钥：<el-link href="https://platform.openai.com/api-keys" target="_blank">OpenAI Platform</el-link>
        </div>
      </el-form-item>

      <!-- 模型选择 -->
      <el-form-item label="AI模型" prop="ai_model_name">
        <div style="display: flex; gap: 10px;">
          <el-input
            v-model="localConfig.ai_model_name"
            placeholder="请输入AI模型名称"
            clearable
            @input="handleConfigChange"
          />
          <el-button @click="testConnection" :loading="testing" type="primary">
            测试连接
          </el-button>
        </div>
        <div class="form-tip">
          请输入AI模型名称，支持本地兼容OpenAI API的模型
        </div>
      </el-form-item>

      <!-- 最大令牌数 -->
      <el-form-item label="最大令牌数" prop="max_tokens">
        <el-input-number
          v-model="localConfig.max_tokens"
          :min="0"
          :max="32768"
          :step="100"
          @change="handleConfigChange"
        />
        <div class="form-tip">
          控制AI响应的最大长度，设置为0表示无限制，建议2048-8192
        </div>
      </el-form-item>

      <!-- 温度参数 -->
      <el-form-item label="温度参数" prop="temperature">
        <el-slider
          v-model="localConfig.temperature"
          :min="0"
          :max="2"
          :step="0.1"
          show-tooltip
          @change="handleConfigChange"
        />
        <div class="form-tip">
          控制AI响应的随机性，0=确定性，2=高随机性，推荐0.1-0.3
        </div>
      </el-form-item>

      <!-- 超时时间 -->
      <el-form-item label="超时时间" prop="request_timeout">
        <el-input-number
          v-model="localConfig.request_timeout"
          :min="5"
          :max="300"
          :step="5"
          @change="handleConfigChange"
        >
          <template #append>秒</template>
        </el-input-number>
        <div class="form-tip">
          API请求超时时间，建议30-60秒
        </div>
      </el-form-item>

      <!-- 重试次数 -->
      <el-form-item label="重试次数" prop="retry_count">
        <el-input-number
          v-model="localConfig.retry_count"
          :min="1"
          :max="10"
          :step="1"
          @change="handleConfigChange"
        />
        <div class="form-tip">
          API请求失败时的重试次数
        </div>
      </el-form-item>

      <!-- 系统提示词 -->
      <el-form-item label="系统提示词" prop="system_prompt">
        <el-input
          v-model="localConfig.system_prompt"
          type="textarea"
          :rows="6"
          placeholder="请输入系统提示词"
          @input="handleConfigChange"
        />
        <div class="form-tip">
          用于指导AI进行违规内容检测的系统提示词
        </div>
      </el-form-item>

      <!-- 自定义提示词模板 -->
      <el-form-item label="自定义提示词模板" prop="custom_prompt_template">
        <el-input
          v-model="localConfig.custom_prompt_template"
          type="textarea"
          :rows="4"
          placeholder="请输入自定义提示词模板"
          @input="handleConfigChange"
        />
        <div class="form-tip">
          自定义提示词模板，将覆盖系统提示词
        </div>
      </el-form-item>
    </el-form>

    <!-- 操作按钮 -->
    <div class="panel-actions">
      <el-button @click="resetToDefault">恢复默认</el-button>
      <el-button type="primary" @click="saveConfig" :loading="saving">
        保存配置
      </el-button>
    </div>

    <!-- 连接测试结果 -->
    <el-dialog
      v-model="testDialogVisible"
      title="连接测试结果"
      width="500px"
    >
      <div class="test-result">
        <el-result
          :icon="testResult.success ? 'success' : 'error'"
          :title="testResult.success ? '连接成功' : '连接失败'"
          :sub-title="testResult.message"
        />
        
        <div v-if="testResult.details" class="test-details">
          <h4>详细信息：</h4>
          <pre>{{ testResult.details }}</pre>
        </div>
      </div>
      
      <template #footer>
        <el-button @click="testDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { configApi } from '@/api/config'
import type { AIConfig, AIConfigTestResponse, ApiResponse } from '@/types'

// Props和Emits
interface Props {
  config: AIConfig
}

interface Emits {
  (e: 'update', config: Partial<AIConfig>): void
  (e: 'save'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 表单引用
const formRef = ref<FormInstance>()

// 响应式数据
const saving = ref(false)
const testing = ref(false)
const testDialogVisible = ref(false)
// 使用传入的配置初始化localConfig
const localConfig = reactive<AIConfig>({ ...props.config })

// 测试结果
const testResult = reactive({
  success: false,
  message: '',
  details: ''
})

// 表单验证规则
const rules = {
  openai_api_key: [
    { required: true, message: '请输入OpenAI API密钥', trigger: 'blur' },
    { min: 10, message: 'API密钥长度不能少于10个字符', trigger: 'blur' }
  ],
  openai_base_url: [
    { required: true, message: '请输入API基础URL', trigger: 'blur' },
    { type: 'url' as const, message: '请输入有效的URL', trigger: 'blur' }
  ],
  ai_model_name: [
    { required: true, message: '请输入AI模型名称', trigger: 'blur' }
  ],
  max_tokens: [
    { required: true, message: '请设置最大令牌数', trigger: 'blur' },
    { type: 'number' as const, min: 0, max: 32768, message: '令牌数应在0-32768之间，0表示无限制', trigger: 'blur' }
  ],
  temperature: [
    { required: true, message: '请设置温度参数', trigger: 'blur' },
    { type: 'number' as const, min: 0, max: 2, message: '温度参数应在0-2之间', trigger: 'blur' }
  ],
  request_timeout: [
    { required: true, message: '请设置超时时间', trigger: 'blur' },
    { type: 'number' as const, min: 5, max: 300, message: '超时时间应在5-300秒之间', trigger: 'blur' }
  ]
}

// 处理配置变更
const handleConfigChange = () => {
  emit('update', { ...localConfig })
}

// 测试连接
const testConnection = async () => {
  if (!localConfig.openai_api_key) {
    ElMessage.warning('请先输入API密钥')
    return
  }

  if (!localConfig.ai_model_name) {
    ElMessage.warning('请先选择或输入AI模型名称')
    return
  }

  try {
    testing.value = true
    
    // 构建符合OpenAI API格式的测试请求
    const testPayload = {
      model: localConfig.ai_model_name,
      messages: [
        {
          role: "user",
          content: "Hello, this is a test message. Please respond with 'Test successful' in English."
        }
      ],
      max_tokens: localConfig.max_tokens > 0 ? localConfig.max_tokens : undefined,
      temperature: localConfig.temperature
    }
    
    // 直接调用OpenAI API进行测试
    const response = await fetch(`${localConfig.openai_base_url}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localConfig.openai_api_key}`
      },
      body: JSON.stringify(testPayload)
    })
    
    if (response.ok) {
      const data = await response.json()
      testResult.success = true
      testResult.message = '连接测试成功'
      testResult.details = data.choices?.[0]?.message?.content || '测试成功但无内容返回'
    } else {
      const errorData = await response.json()
      testResult.success = false
      testResult.message = `连接测试失败: ${response.status} ${response.statusText}`
      testResult.details = errorData.error?.message || '未知错误'
    }
    
    testDialogVisible.value = true
    
  } catch (error: any) {
    testResult.success = false
    testResult.message = '连接测试失败'
    testResult.details = error.message || '网络错误或服务器无响应'
    testDialogVisible.value = true
  } finally {
    testing.value = false
  }
}

// 保存配置
const saveConfig = async () => {
  if (!formRef.value) return
  
  try {
    const valid = await formRef.value.validate()
    if (!valid) return
    
    saving.value = true
    emit('save')
    
  } catch (error) {
    // 验证失败
  } finally {
    saving.value = false
  }
}

// 恢复默认配置
const resetToDefault = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要恢复AI配置的默认值吗？',
      '恢复默认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const defaultConfig: Partial<AIConfig> = {
      openai_api_key: '',
      openai_base_url: 'https://api.openai.com/v1',
      ai_model_name: 'gpt-4-vision-preview',
      max_tokens: 4096,
      temperature: 0.1,
      request_timeout: 30,
      retry_count: 3,
      enable_streaming: false,
      system_prompt: `请分析这个网页的内容和截图，判断是否包含以下类型的违规内容：
1. 恶意软件、病毒、木马
2. 钓鱼网站、诈骗信息
3. 违法违规内容
4. 侵犯版权的内容
5. 其他安全风险

请以JSON格式返回分析结果：
{
  "is_violation": true/false,
  "violation_type": "类型",
  "risk_level": "critical/high/medium/low",
  "confidence": 0.0-1.0,
  "reasoning": "判断理由",
  "evidence": ["证据列表"]
}`,
      custom_prompt_template: ''
    }
    
    Object.assign(localConfig, defaultConfig)
    handleConfigChange()
    
    ElMessage.success('已恢复默认配置')
    
  } catch (error) {
    // 用户取消操作
  }
}

// 监听props变化
watch(
  () => props.config,
  (newConfig) => {
    // 只有当新配置不为空时才更新localConfig
    if (newConfig && Object.keys(newConfig).length > 0) {
      Object.assign(localConfig, newConfig)
    }
  },
  { deep: true }
)

// 组件挂载
onMounted(() => {
  // 确保使用传入的配置，而不是默认配置
  if (props.config && Object.keys(props.config).length > 0) {
    Object.assign(localConfig, props.config)
  }
  
  // 如果系统提示词为空，设置默认值（仅在创建新配置时）
  if (!localConfig.system_prompt && !localConfig.id) {
    localConfig.system_prompt = `请分析这个网页的内容和截图，判断是否包含以下类型的违规内容：
1. 恶意软件、病毒、木马
2. 钓鱼网站、诈骗信息
3. 违法违规内容
4. 侵犯版权的内容
5. 其他安全风险

请以JSON格式返回分析结果：
{
  "is_violation": true/false,
  "violation_type": "类型",
  "risk_level": "critical/high/medium/low",
  "confidence": 0.0-1.0,
  "reasoning": "判断理由",
  "evidence": ["证据列表"]
}`
    handleConfigChange()
  }
})
</script>

<style scoped>
.ai-config-panel {
  max-width: 800px;
}

.panel-header {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
}

.panel-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 8px 0;
}

.panel-header p {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.config-form {
  margin-bottom: 24px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}

.custom-prompts {
  width: 100%;
}

.prompt-item {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: flex-start;
}

.prompt-name {
  width: 200px;
  flex-shrink: 0;
}

.prompt-content {
  flex: 1;
}

.add-prompt-btn {
  width: 100%;
  margin-top: 8px;
}

.panel-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.test-result {
  text-align: center;
}

.test-details {
  margin-top: 20px;
  text-align: left;
}

.test-details h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #303133;
}

.test-details pre {
  background-color: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
  max-height: 200px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .config-form :deep(.el-form-item__label) {
    width: 100px !important;
  }
  
  .prompt-item {
    flex-direction: column;
  }
  
  .prompt-name {
    width: 100%;
  }
  
  .panel-actions {
    flex-direction: column;
  }
}
</style>