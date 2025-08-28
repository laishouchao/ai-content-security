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
        <el-select v-model="config.high_risk_threshold" style="width: 60px">
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
import { notificationAPI, type NotificationConfig } from '@/api/notification'

// 配置数据
const config = reactive<NotificationConfig>({
  email_enabled: false,
  email_recipients: [],
  email_smtp_host: '',
  email_smtp_port: 587,
  email_smtp_username: '',
  email_smtp_password: '',
  email_smtp_use_tls: true,
  
  webhook_enabled: false,
  webhook_url: '',
  webhook_secret: '',
  webhook_events: [],
  
  task_completion_notification: true,
  violation_detection_notification: true,
  system_error_notification: true,
  daily_report_notification: false,
  
  notification_threshold: 3,
  notification_quiet_hours_start: '22:00',
  notification_quiet_hours_end: '08:00'
})

// 添加邮箱相关
const inputVisible = ref(false)
const inputValue = ref('')
const inputRef = ref()
const saving = ref(false)
const testing = ref(false)
const loading = ref(false)

// 显示输入框
const showInput = () => {
  inputVisible.value = true
  nextTick(() => {
    inputRef.value?.focus()
  })
}

// 确认添加邮箱
const handleInputConfirm = () => {
  if (inputValue.value && !config.email_recipients.includes(inputValue.value)) {
    // 简单的邮箱格式验证
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (emailRegex.test(inputValue.value)) {
      config.email_recipients.push(inputValue.value)
      inputValue.value = ''
    } else {
      ElMessage.error('请输入有效的邮箱地址')
    }
  }
  inputVisible.value = false
}

// 移除邮箱
const removeRecipient = (email: string) => {
  const index = config.email_recipients.indexOf(email)
  if (index > -1) {
    config.email_recipients.splice(index, 1)
  }
}

// 保存配置
const saveConfig = async () => {
  saving.value = true
  try {
    await notificationAPI.updateNotificationConfig(config)
    ElMessage.success('通知配置保存成功')
  } catch (error) {
    console.error('保存通知配置失败:', error)
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
  
  if (config.email_recipients.length === 0) {
    ElMessage.warning('请至少添加一个接收人邮箱')
    return
  }

  testing.value = true
  try {
    await notificationAPI.testNotification({
      type: 'email',
      message: '这是一条测试通知消息'
    })
    ElMessage.success('测试通知发送成功，请检查邮箱')
  } catch (error) {
    console.error('发送测试通知失败:', error)
    ElMessage.error('发送测试通知失败')
  } finally {
    testing.value = false
  }
}

// 加载配置
const loadConfig = async () => {
  loading.value = true
  try {
    const response = await notificationAPI.getNotificationConfig()
    if (response.data.success && response.data.data) {
      Object.assign(config, response.data.data)
    }
  } catch (error) {
    console.error('加载通知配置失败:', error)
    ElMessage.error('加载通知配置失败')
  } finally {
    loading.value = false
  }
}

// 生命周期
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