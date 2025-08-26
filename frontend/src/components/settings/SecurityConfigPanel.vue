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
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'

// 配置数据
const config = reactive({
  ip_whitelist_enabled: false,
  allowed_ips: [] as string[],
  min_password_length: 8,
  password_requirements: ['lowercase', 'numbers'],
  password_expiry_days: 90,
  max_login_attempts: 5,
  lockout_duration_minutes: 30,
  session_timeout_hours: 8,
  two_factor_enabled: false,
  api_rate_limit: 100,
  api_key_expiry_days: 30,
  api_logging_enabled: true,
  data_encryption_enabled: true,
  data_retention_days: 365,
  auto_backup_enabled: true,
  backup_frequency: 'weekly'
})

// IP输入相关
const ipInputVisible = ref(false)
const ipInputValue = ref('')
const ipInputRef = ref()
const saving = ref(false)
const resetting = ref(false)

// 显示IP输入框
const showIPInput = () => {
  ipInputVisible.value = true
  nextTick(() => {
    ipInputRef.value?.focus()
  })
}

// 确认添加IP
const handleIPInputConfirm = () => {
  if (ipInputValue.value && !config.allowed_ips.includes(ipInputValue.value)) {
    // 简单的IP格式验证
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/
    if (ipRegex.test(ipInputValue.value)) {
      config.allowed_ips.push(ipInputValue.value)
      ipInputValue.value = ''
    } else {
      ElMessage.error('请输入有效的IP地址或CIDR格式')
    }
  }
  ipInputVisible.value = false
}

// 移除IP
const removeIP = (ip: string) => {
  const index = config.allowed_ips.indexOf(ip)
  if (index > -1) {
    config.allowed_ips.splice(index, 1)
  }
}

// 保存配置
const saveConfig = async () => {
  saving.value = true
  try {
    // TODO: 调用API保存配置
    await new Promise(resolve => setTimeout(resolve, 1000)) // 模拟API调用
    ElMessage.success('安全配置保存成功')
  } catch (error) {
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

// 恢复默认设置
const resetToDefaults = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要恢复默认安全设置吗？这将覆盖所有当前配置。',
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    resetting.value = true
    // TODO: 调用API重置配置
    await new Promise(resolve => setTimeout(resolve, 1000)) // 模拟API调用
    
    // 重置为默认值
    Object.assign(config, {
      ip_whitelist_enabled: false,
      allowed_ips: [],
      min_password_length: 8,
      password_requirements: ['lowercase', 'numbers'],
      password_expiry_days: 90,
      max_login_attempts: 5,
      lockout_duration_minutes: 30,
      session_timeout_hours: 8,
      two_factor_enabled: false,
      api_rate_limit: 100,
      api_key_expiry_days: 30,
      api_logging_enabled: true,
      data_encryption_enabled: true,
      data_retention_days: 365,
      auto_backup_enabled: true,
      backup_frequency: 'weekly'
    })
    
    ElMessage.success('已恢复默认安全设置')
  } catch {
    // 用户取消操作
  } finally {
    resetting.value = false
  }
}

// 加载配置
const loadConfig = async () => {
  try {
    // TODO: 调用API加载配置
    // const response = await api.getSecurityConfig()
    // Object.assign(config, response.data)
  } catch (error) {
    ElMessage.error('加载安全配置失败')
  }
}

onMounted(() => {
  loadConfig()
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