<template>
  <div class="scan-config-panel">
    <div class="panel-header">
      <h3>扫描配置</h3>
      <p>配置网站扫描相关参数和规则</p>
    </div>

    <el-form
      ref="formRef"
      :model="localConfig"
      :rules="rules"
      label-width="150px"
      class="config-form"
    >
      <!-- 扫描深度 -->
      <el-form-item label="扫描深度" prop="max_depth">
        <el-input-number
          v-model="localConfig.max_depth"
          :min="1"
          :max="10"
          @change="handleConfigChange"
        />
        <div class="form-tip">
          扫描网站的最大深度级别，建议1-5级
        </div>
      </el-form-item>

      <!-- 每域名最大页面数 -->
      <el-form-item label="每域名最大页面" prop="max_pages_per_domain">
        <el-input-number
          v-model="localConfig.max_pages_per_domain"
          :min="1"
          :max="1000"
          @change="handleConfigChange"
        />
        <div class="form-tip">
          单个域名扫描的最大页面数量
        </div>
      </el-form-item>

      <!-- 请求延迟 -->
      <el-form-item label="请求延迟" prop="request_delay">
        <el-input-number
          v-model="localConfig.request_delay"
          :min="0.1"
          :max="10"
          :step="0.1"
          @change="handleConfigChange"
        >
          <template #append>秒</template>
        </el-input-number>
        <div class="form-tip">
          请求之间的延迟时间，避免对目标服务器造成压力
        </div>
      </el-form-item>

      <!-- 超时时间 -->
      <el-form-item label="请求超时" prop="timeout">
        <el-input-number
          v-model="localConfig.timeout"
          :min="5"
          :max="120"
          @change="handleConfigChange"
        >
          <template #append>秒</template>
        </el-input-number>
        <div class="form-tip">
          单个页面请求的超时时间
        </div>
      </el-form-item>

      <!-- User Agent -->
      <el-form-item label="User Agent" prop="user_agent">
        <el-input
          v-model="localConfig.user_agent"
          type="textarea"
          :rows="2"
          placeholder="请输入User Agent字符串"
          @input="handleConfigChange"
        />
        <div class="form-tip">
          模拟浏览器访问的User Agent标识
        </div>
      </el-form-item>

      <!-- 自定义请求头 -->
      <el-form-item label="自定义请求头">
        <div class="headers-config">
          <div
            v-for="(header, index) in headersList"
            :key="index"
            class="header-item"
          >
            <el-input
              v-model="header.key"
              placeholder="Header名称"
              class="header-key"
              @input="updateHeaders"
            />
            <el-input
              v-model="header.value"
              placeholder="Header值"
              class="header-value"
              @input="updateHeaders"
            />
            <el-button
              type="danger"
              icon="Delete"
              @click="removeHeader(index)"
            />
          </div>
          
          <el-button
            type="primary"
            icon="Plus"
            @click="addHeader"
            class="add-header-btn"
          >
            添加请求头
          </el-button>
        </div>
      </el-form-item>

      <!-- 允许的域名 -->
      <el-form-item label="允许的域名">
        <el-select
          v-model="localConfig.allowed_domains"
          multiple
          filterable
          allow-create
          placeholder="输入允许扫描的域名"
          class="domain-select"
          style="width: 60px"
          @change="handleConfigChange"
        >
          <el-option
            v-for="domain in localConfig.allowed_domains"
            :key="domain"
            :label="domain"
            :value="domain"
          />
        </el-select>
        <div class="form-tip">
          留空表示不限制，可输入域名后回车添加
        </div>
      </el-form-item>

      <!-- 阻止的域名 -->
      <el-form-item label="阻止的域名">
        <el-select
          v-model="localConfig.blocked_domains"
          multiple
          filterable
          allow-create
          placeholder="输入需要阻止的域名"
          class="domain-select"
          style="width: 60px"
          @change="handleConfigChange"
        >
          <el-option
            v-for="domain in localConfig.blocked_domains"
            :key="domain"
            :label="domain"
            :value="domain"
          />
        </el-select>
        <div class="form-tip">
          这些域名将被跳过，不进行扫描
        </div>
      </el-form-item>

      <!-- 文件扩展名 -->
      <el-form-item label="扫描文件类型">
        <el-checkbox-group
          v-model="localConfig.file_extensions"
          @change="handleConfigChange"
        >
          <el-checkbox label=".html">HTML文件</el-checkbox>
          <el-checkbox label=".php">PHP文件</el-checkbox>
          <el-checkbox label=".asp">ASP文件</el-checkbox>
          <el-checkbox label=".aspx">ASPX文件</el-checkbox>
          <el-checkbox label=".jsp">JSP文件</el-checkbox>
          <el-checkbox label=".js">JavaScript文件</el-checkbox>
          <el-checkbox label=".css">CSS文件</el-checkbox>
        </el-checkbox-group>
        <div class="form-tip">
          选择需要扫描的文件类型
        </div>
      </el-form-item>

      <!-- 截图设置 -->
      <el-form-item label="启用截图" prop="enable_screenshots">
        <el-switch
          v-model="localConfig.enable_screenshots"
          @change="handleConfigChange"
        />
        <div class="form-tip">
          是否对页面进行截图，用于AI视觉分析
        </div>
      </el-form-item>

      <!-- 截图尺寸 -->
      <el-form-item
        v-if="localConfig.enable_screenshots"
        label="截图尺寸"
      >
        <div class="screenshot-size">
          <el-input-number
            v-model="localConfig.screenshot_width"
            :min="800"
            :max="1920"
            @change="handleConfigChange"
          />
          <span class="size-separator">×</span>
          <el-input-number
            v-model="localConfig.screenshot_height"
            :min="600"
            :max="1080"
            @change="handleConfigChange"
          />
        </div>
        <div class="form-tip">
          截图的宽度和高度（像素）
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import type { ScanConfig } from '@/types'

// Props和Emits
interface Props {
  config: ScanConfig
}

interface Emits {
  (e: 'update', config: Partial<ScanConfig>): void
  (e: 'save'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 表单引用
const formRef = ref<FormInstance>()

// 响应式数据
const saving = ref(false)
const localConfig = reactive<ScanConfig>({ ...props.config })

// 请求头列表
const headersList = computed({
  get: () => {
    return Object.entries(localConfig.headers || {}).map(([key, value]) => ({
      key,
      value
    }))
  },
  set: (newHeaders) => {
    const headers: Record<string, string> = {}
    newHeaders.forEach(header => {
      if (header.key && header.value) {
        headers[header.key] = header.value
      }
    })
    localConfig.headers = headers
    handleConfigChange()
  }
})

// 表单验证规则
const rules = {
  max_depth: [
    { required: true, message: '请设置扫描深度', trigger: 'blur' },
    { type: 'number', min: 1, max: 10, message: '扫描深度应在1-10之间', trigger: 'blur' }
  ],
  max_pages_per_domain: [
    { required: true, message: '请设置每域名最大页面数', trigger: 'blur' },
    { type: 'number', min: 1, max: 1000, message: '页面数应在1-1000之间', trigger: 'blur' }
  ],
  request_delay: [
    { required: true, message: '请设置请求延迟', trigger: 'blur' },
    { type: 'number', min: 0.1, max: 10, message: '延迟时间应在0.1-10秒之间', trigger: 'blur' }
  ],
  timeout: [
    { required: true, message: '请设置超时时间', trigger: 'blur' },
    { type: 'number', min: 5, max: 120, message: '超时时间应在5-120秒之间', trigger: 'blur' }
  ],
  user_agent: [
    { required: true, message: '请输入User Agent', trigger: 'blur' },
    { min: 10, message: 'User Agent长度不能少于10个字符', trigger: 'blur' }
  ]
}

// 处理配置变更
const handleConfigChange = () => {
  emit('update', { ...localConfig })
}

// 添加请求头
const addHeader = () => {
  const newHeaders = [...headersList.value, { key: '', value: '' }]
  headersList.value = newHeaders
}

// 移除请求头
const removeHeader = (index: number) => {
  const newHeaders = headersList.value.filter((_, i) => i !== index)
  headersList.value = newHeaders
}

// 更新请求头
const updateHeaders = () => {
  const headers: Record<string, string> = {}
  headersList.value.forEach(header => {
    if (header.key && header.value) {
      headers[header.key] = header.value
    }
  })
  localConfig.headers = headers
  handleConfigChange()
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
      '确定要恢复扫描配置的默认值吗？',
      '恢复默认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const defaultConfig: ScanConfig = {
      max_depth: 3,
      max_pages_per_domain: 100,
      request_delay: 1,
      timeout: 30,
      user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
      headers: {},
      allowed_domains: [],
      blocked_domains: [],
      file_extensions: ['.html', '.php', '.asp', '.jsp'],
      enable_screenshots: true,
      screenshot_width: 1280,
      screenshot_height: 720
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
    Object.assign(localConfig, newConfig)
  },
  { deep: true }
)
</script>

<style scoped>
.scan-config-panel {
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

.headers-config {
  width: 100%;
}

.header-item {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
}

.header-key {
  width: 200px;
  flex-shrink: 0;
}

.header-value {
  flex: 1;
}

.add-header-btn {
  width: 100%;
  margin-top: 8px;
}

.domain-select {
  width: 100%;
}

.screenshot-size {
  display: flex;
  align-items: center;
  gap: 8px;
}

.size-separator {
  font-size: 16px;
  color: #909399;
}

.panel-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .config-form :deep(.el-form-item__label) {
    width: 100px !important;
  }
  
  .header-item {
    flex-direction: column;
    align-items: stretch;
  }
  
  .header-key {
    width: 100%;
  }
  
  .screenshot-size {
    flex-direction: column;
    align-items: stretch;
  }
  
  .panel-actions {
    flex-direction: column;
  }
}
</style>