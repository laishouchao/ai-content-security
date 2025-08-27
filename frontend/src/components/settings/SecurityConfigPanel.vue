<template>
  <el-card class="security-config-panel" shadow="hover">
    <template #header>
      <div class="card-header">
        <h3>
          <el-icon><Lock /></el-icon>
          安全配置
        </h3>
        <p>配置系统安全和访问控制设置</p>
      </div>
    </template>

    <el-form :model="config" label-width="160px" @submit.prevent="saveConfig">
      <!-- 访问控制 -->
      <el-divider content-position="left">访问控制</el-divider>
      
      <el-form-item label="启用IP白名单">
        <el-switch v-model="config.ip_whitelist_enabled" />
      </el-form-item>

      <el-form-item label="允许的IP地址" v-if="config.ip_whitelist_enabled">
        <el-tag
          v-for="ip in config.allowed_ips"
          :key="ip"
          closable
          @close="removeIP(ip)"
          class="mr-2 mb-2"
        >
          {{ ip }}
        </el-tag>
        <el-input
          v-if="ipInputVisible"
          ref="ipInputRef"
          v-model="ipInputValue"
          size="small"
          @keyup.enter="handleIPInputConfirm"
          @blur="handleIPInputConfirm"
          placeholder="192.168.1.100 或 192.168.1.0/24"
          style="width: 220px"
        />
        <el-button v-else size="small" @click="showIPInput">
          + 添加IP地址
        </el-button>
      </el-form-item>

      <!-- 密码策略 -->
      <el-divider content-position="left">密码策略</el-divider>

      <el-form-item label="最小密码长度">
        <el-input-number v-model="config.min_password_length" :min="6" :max="20" />
      </el-form-item>

      <el-form-item label="密码复杂度要求">
        <el-checkbox-group v-model="config.password_requirements">
          <el-checkbox label="uppercase">包含大写字母</el-checkbox>
          <el-checkbox label="lowercase">包含小写字母</el-checkbox>
          <el-checkbox label="numbers">包含数字</el-checkbox>
          <el-checkbox label="special">包含特殊字符</el-checkbox>
        </el-checkbox-group>
      </el-form-item>

      <el-form-item label="密码有效期(天)">
        <el-input-number v-model="config.password_expiry_days" :min="0" :max="365" />
        <el-text type="info" size="small">设置为0表示密码永不过期</el-text>
      </el-form-item>

      <!-- 登录安全 -->
      <el-divider content-position="left">登录安全</el-divider>

      <el-form-item label="最大登录尝试次数">
        <el-input-number v-model="config.max_login_attempts" :min="3" :max="10" />
      </el-form-item>

      <el-form-item label="账户锁定时间(分钟)">
        <el-input-number v-model="config.lockout_duration_minutes" :min="5" :max="1440" />
      </el-form-item>

      <el-form-item label="会话超时时间(小时)">
        <el-input-number v-model="config.session_timeout_hours" :min="1" :max="24" />
      </el-form-item>

      <el-form-item label="启用双因素认证">
        <el-switch v-model="config.two_factor_enabled" />
      </el-form-item>

      <!-- API安全 -->
      <el-divider content-position="left">API安全</el-divider>

      <el-form-item label="API速率限制">
        <el-input-number 
          v-model="config.api_rate_limit" 
          :min="10" 
          :max="1000"
          controls-position="right"
        />
        <el-text type="info" size="small">每分钟最大请求次数</el-text>
      </el-form-item>

      <el-form-item label="API密钥过期时间(天)">
        <el-input-number v-model="config.api_key_expiry_days" :min="1" :max="365" />
      </el-form-item>

      <el-form-item label="启用API日志记录">
        <el-switch v-model="config.api_logging_enabled" />
      </el-form-item>

      <!-- 数据保护 -->
      <el-divider content-position="left">数据保护</el-divider>

      <el-form-item label="敏感数据加密">
        <el-switch v-model="config.data_encryption_enabled" />
      </el-form-item>

      <el-form-item label="数据保留期(天)">
        <el-input-number v-model="config.data_retention_days" :min="30" :max="3650" />
      </el-form-item>

      <el-form-item label="自动备份">
        <el-switch v-model="config.auto_backup_enabled" />
      </el-form-item>

      <el-form-item label="备份频率" v-if="config.auto_backup_enabled">
        <el-select v-model="config.backup_frequency">
          <el-option label="每日" value="daily" />
          <el-option label="每周" value="weekly" />
          <el-option label="每月" value="monthly" />
        </el-select>
      </el-form-item>

      <!-- 保存按钮 -->
      <el-form-item>
        <el-button type="primary" @click="saveConfig" :loading="saving">
          保存配置
        </el-button>
        <el-button @click="resetToDefaults" :loading="resetting">
          恢复默认
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Shield } from '@element-plus/icons-vue'
import { securityAPI, type SecurityConfig } from '@/api/security'

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const checkingStatus = ref(false)

// 安全配置数据
const config = reactive<SecurityConfig>({
  enable_ip_whitelist: false,
  ip_whitelist: [],
  enable_rate_limiting: true,
  rate_limit_requests_per_minute: 60,
  
  session_timeout_minutes: 30,
  max_concurrent_sessions: 5,
  enable_session_binding: false,
  
  password_min_length: 8,
  password_require_uppercase: true,
  password_require_lowercase: true,
  password_require_numbers: true,
  password_require_symbols: false,
  password_expiry_days: 90,
  password_history_count: 5,
  
  enable_2fa: false,
  require_2fa_for_admin: false,
  totp_issuer: 'AI Content Security',
  
  enable_audit_log: true,
  log_retention_days: 90,
  log_sensitive_operations: true,
  
  enable_api_key_auth: false,
  api_key_expiry_days: 365,
  enable_request_encryption: false,
  
  max_file_size_mb: 10,
  allowed_file_types: ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'txt', 'csv'],
  enable_virus_scan: false
})

// 安全状态数据
const securityStatus = ref<any>(null)

// 新IP地址输入
const newIpAddress = ref('')

// 加载安全配置
const loadConfig = async () => {
  try {
    loading.value = true
    const response = await securityAPI.getSecurityConfig()
    
    if (response.data.success && response.data.data) {
      Object.assign(config, response.data.data)
    }
  } catch (error) {
    console.error('加载安全配置失败:', error)
    ElMessage.error('加载安全配置失败')
  } finally {
    loading.value = false
  }
}

// 保存配置
const saveConfig = async () => {
  try {
    saving.value = true
    await securityAPI.updateSecurityConfig(config)
    ElMessage.success('安全配置保存成功')
  } catch (error) {
    console.error('保存安全配置失败:', error)
    ElMessage.error('保存安全配置失败')
  } finally {
    saving.value = false
  }
}

// 重置配置
const resetConfig = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要重置为默认安全配置吗？此操作不可恢复。',
      '确认重置',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await securityAPI.resetSecurityConfig()
    ElMessage.success('安全配置已重置')
    await loadConfig()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('重置安全配置失败:', error)
      ElMessage.error('重置安全配置失败')
    }
  }
}

// 检查安全状态
const checkSecurityStatus = async () => {
  try {
    checkingStatus.value = true
    const response = await securityAPI.getSecurityStatus()
    
    if (response.data.success && response.data.data) {
      securityStatus.value = response.data.data
    }
  } catch (error) {
    console.error('检查安全状态失败:', error)
    ElMessage.error('检查安全状态失败')
  } finally {
    checkingStatus.value = false
  }
}

// 添加IP地址到白名单
const addIpToWhitelist = () => {
  if (newIpAddress.value && !config.ip_whitelist.includes(newIpAddress.value)) {
    // 简单的IP地址格式验证
    const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/
    if (ipRegex.test(newIpAddress.value) || newIpAddress.value.includes('/')) {
      config.ip_whitelist.push(newIpAddress.value)
      newIpAddress.value = ''
    } else {
      ElMessage.error('请输入有效的IP地址或CIDR')
    }
  }
}

// 从白名单中移除IP地址
const removeIpFromWhitelist = (ip: string) => {
  const index = config.ip_whitelist.indexOf(ip)
  if (index > -1) {
    config.ip_whitelist.splice(index, 1)
  }
}

// 获取密码强度描述
const getPasswordStrengthDescription = () => {
  const requirements = []
  if (config.password_require_uppercase) requirements.push('大写字母')
  if (config.password_require_lowercase) requirements.push('小写字母')
  if (config.password_require_numbers) requirements.push('数字')
  if (config.password_require_symbols) requirements.push('特殊字符')
  
  return `最少${config.password_min_length}位，包含: ${requirements.join('、')}`
}

// 生命周期
onMounted(() => {
  loadConfig()
  checkSecurityStatus()
})
</script>

<style scoped>
.security-config-panel {
  margin-bottom: 20px;
}

.card-header h3 {
  margin: 0 0 8px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #409eff;
}

.card-header p {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.mr-2 {
  margin-right: 8px;
}

.mb-2 {
  margin-bottom: 8px;
}

.el-text {
  margin-left: 8px;
}
</style>