<template>
  <el-card class="notification-config-panel" shadow="hover">
    <template #header>
      <div class="card-header">
        <h3>
          <el-icon><Bell /></el-icon>
          通知配置
        </h3>
        <p>配置系统通知和警报设置</p>
      </div>
    </template>

    <el-form :model="config" label-width="140px" @submit.prevent="saveConfig">
      <!-- 邮件通知设置 -->
      <el-divider content-position="left">邮件通知</el-divider>
      
      <el-form-item label="启用邮件通知">
        <el-switch v-model="config.email_enabled" />
      </el-form-item>

      <el-form-item label="SMTP服务器" v-if="config.email_enabled">
        <el-input v-model="config.smtp_host" placeholder="smtp.example.com" />
      </el-form-item>

      <el-form-item label="SMTP端口" v-if="config.email_enabled">
        <el-input-number v-model="config.smtp_port" :min="1" :max="65535" />
      </el-form-item>

      <el-form-item label="发件人邮箱" v-if="config.email_enabled">
        <el-input v-model="config.sender_email" placeholder="admin@example.com" />
      </el-form-item>

      <el-form-item label="邮箱密码" v-if="config.email_enabled">
        <el-input v-model="config.sender_password" type="password" show-password />
      </el-form-item>

      <!-- 通知触发条件 -->
      <el-divider content-position="left">通知触发条件</el-divider>

      <el-form-item label="任务完成通知">
        <el-switch v-model="config.notify_task_completed" />
      </el-form-item>

      <el-form-item label="发现违规通知">
        <el-switch v-model="config.notify_violations" />
      </el-form-item>

      <el-form-item label="系统错误通知">
        <el-switch v-model="config.notify_errors" />
      </el-form-item>

      <el-form-item label="高风险违规阈值">
        <el-select v-model="config.high_risk_threshold">
          <el-option label="立即通知" value="immediate" />
          <el-option label="1小时内累计5个" value="5_per_hour" />
          <el-option label="1天内累计10个" value="10_per_day" />
        </el-select>
      </el-form-item>

      <!-- 通知接收人 -->
      <el-divider content-position="left">通知接收人</el-divider>

      <el-form-item label="接收人邮箱">
        <el-tag
          v-for="email in config.recipient_emails"
          :key="email"
          closable
          @close="removeRecipient(email)"
          class="mr-2 mb-2"
        >
          {{ email }}
        </el-tag>
        <el-input
          v-if="inputVisible"
          ref="inputRef"
          v-model="inputValue"
          size="small"
          @keyup.enter="handleInputConfirm"
          @blur="handleInputConfirm"
          style="width: 200px"
        />
        <el-button v-else size="small" @click="showInput">
          + 添加邮箱
        </el-button>
      </el-form-item>

      <!-- 保存按钮 -->
      <el-form-item>
        <el-button type="primary" @click="saveConfig" :loading="saving">
          保存配置
        </el-button>
        <el-button @click="testNotification" :loading="testing">
          发送测试通知
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Bell } from '@element-plus/icons-vue'

// 配置数据
const config = reactive({
  email_enabled: false,
  smtp_host: '',
  smtp_port: 587,
  sender_email: '',
  sender_password: '',
  notify_task_completed: true,
  notify_violations: true,
  notify_errors: true,
  high_risk_threshold: 'immediate',
  recipient_emails: [] as string[]
})

// 添加邮箱相关
const inputVisible = ref(false)
const inputValue = ref('')
const inputRef = ref()
const saving = ref(false)
const testing = ref(false)

// 显示输入框
const showInput = () => {
  inputVisible.value = true
  nextTick(() => {
    inputRef.value?.focus()
  })
}

// 确认添加邮箱
const handleInputConfirm = () => {
  if (inputValue.value && !config.recipient_emails.includes(inputValue.value)) {
    // 简单的邮箱格式验证
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (emailRegex.test(inputValue.value)) {
      config.recipient_emails.push(inputValue.value)
      inputValue.value = ''
    } else {
      ElMessage.error('请输入有效的邮箱地址')
    }
  }
  inputVisible.value = false
}

// 移除邮箱
const removeRecipient = (email: string) => {
  const index = config.recipient_emails.indexOf(email)
  if (index > -1) {
    config.recipient_emails.splice(index, 1)
  }
}

// 保存配置
const saveConfig = async () => {
  saving.value = true
  try {
    // TODO: 调用API保存配置
    await new Promise(resolve => setTimeout(resolve, 1000)) // 模拟API调用
    ElMessage.success('通知配置保存成功')
  } catch (error) {
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

// 发送测试通知
const testNotification = async () => {
  if (!config.email_enabled) {
    ElMessage.warning('请先启用邮件通知')
    return
  }
  
  if (config.recipient_emails.length === 0) {
    ElMessage.warning('请至少添加一个接收人邮箱')
    return
  }

  testing.value = true
  try {
    // TODO: 调用API发送测试通知
    await new Promise(resolve => setTimeout(resolve, 2000)) // 模拟API调用
    ElMessage.success('测试通知发送成功，请检查邮箱')
  } catch (error) {
    ElMessage.error('发送测试通知失败')
  } finally {
    testing.value = false
  }
}

// 加载配置
const loadConfig = async () => {
  try {
    // TODO: 调用API加载配置
    // const response = await api.getNotificationConfig()
    // Object.assign(config, response.data)
  } catch (error) {
    ElMessage.error('加载通知配置失败')
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.notification-config-panel {
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
</style>