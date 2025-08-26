<template>
  <el-card class="system-config-panel" shadow="hover">
    <template #header>
      <div class="card-header">
        <h3>
          <el-icon><Setting /></el-icon>
          系统配置
        </h3>
        <p>配置系统运行参数和性能设置</p>
      </div>
    </template>

    <el-form :model="config" label-width="160px" @submit.prevent="saveConfig">
      <!-- 基础设置 -->
      <el-divider content-position="left">基础设置</el-divider>
      
      <el-form-item label="系统名称">
        <el-input v-model="config.system_name" placeholder="域名合规扫描系统" />
      </el-form-item>

      <el-form-item label="系统版本">
        <el-input v-model="config.system_version" readonly />
      </el-form-item>

      <el-form-item label="管理员邮箱">
        <el-input v-model="config.admin_email" placeholder="admin@example.com" />
      </el-form-item>

      <el-form-item label="系统时区">
        <el-select v-model="config.timezone" placeholder="选择时区">
          <el-option label="北京时间 (UTC+8)" value="Asia/Shanghai" />
          <el-option label="纽约时间 (UTC-5)" value="America/New_York" />
          <el-option label="伦敦时间 (UTC+0)" value="Europe/London" />
          <el-option label="东京时间 (UTC+9)" value="Asia/Tokyo" />
        </el-select>
      </el-form-item>

      <!-- 性能设置 -->
      <el-divider content-position="left">性能设置</el-divider>

      <el-form-item label="最大并发任务数">
        <el-input-number v-model="config.max_concurrent_tasks" :min="1" :max="20" />
      </el-form-item>

      <el-form-item label="任务超时时间(小时)">
        <el-input-number v-model="config.task_timeout_hours" :min="1" :max="48" />
      </el-form-item>

      <el-form-item label="数据库连接池大小">
        <el-input-number v-model="config.db_pool_size" :min="5" :max="50" />
      </el-form-item>

      <el-form-item label="缓存过期时间(分钟)">
        <el-input-number v-model="config.cache_expiry_minutes" :min="5" :max="1440" />
      </el-form-item>

      <!-- 日志设置 -->
      <el-divider content-position="left">日志设置</el-divider>

      <el-form-item label="日志级别">
        <el-select v-model="config.log_level">
          <el-option label="DEBUG" value="DEBUG" />
          <el-option label="INFO" value="INFO" />
          <el-option label="WARNING" value="WARNING" />
          <el-option label="ERROR" value="ERROR" />
        </el-select>
      </el-form-item>

      <el-form-item label="日志保留天数">
        <el-input-number v-model="config.log_retention_days" :min="7" :max="365" />
      </el-form-item>

      <el-form-item label="启用详细日志">
        <el-switch v-model="config.verbose_logging" />
      </el-form-item>

      <!-- 存储设置 -->
      <el-divider content-position="left">存储设置</el-divider>

      <el-form-item label="截图存储路径">
        <el-input v-model="config.screenshot_path" placeholder="./storage/screenshots" />
      </el-form-item>

      <el-form-item label="最大文件大小(MB)">
        <el-input-number v-model="config.max_file_size_mb" :min="1" :max="100" />
      </el-form-item>

      <el-form-item label="自动清理旧文件">
        <el-switch v-model="config.auto_cleanup_enabled" />
      </el-form-item>

      <el-form-item label="文件保留天数" v-if="config.auto_cleanup_enabled">
        <el-input-number v-model="config.file_retention_days" :min="7" :max="365" />
      </el-form-item>

      <!-- 监控设置 -->
      <el-divider content-position="left">监控设置</el-divider>

      <el-form-item label="启用性能监控">
        <el-switch v-model="config.monitoring_enabled" />
      </el-form-item>

      <el-form-item label="监控数据采集间隔(秒)" v-if="config.monitoring_enabled">
        <el-input-number v-model="config.monitoring_interval_seconds" :min="10" :max="300" />
      </el-form-item>

      <el-form-item label="CPU使用率告警阈值(%)" v-if="config.monitoring_enabled">
        <el-input-number v-model="config.cpu_alert_threshold" :min="50" :max="95" />
      </el-form-item>

      <el-form-item label="内存使用率告警阈值(%)" v-if="config.monitoring_enabled">
        <el-input-number v-model="config.memory_alert_threshold" :min="50" :max="95" />
      </el-form-item>

      <!-- 维护模式 -->
      <el-divider content-position="left">维护模式</el-divider>

      <el-form-item label="启用维护模式">
        <el-switch v-model="config.maintenance_mode" />
      </el-form-item>

      <el-form-item label="维护提示信息" v-if="config.maintenance_mode">
        <el-input
          v-model="config.maintenance_message"
          type="textarea"
          :rows="3"
          placeholder="系统正在维护中，请稍后再试..."
        />
      </el-form-item>

      <!-- 系统信息 -->
      <el-divider content-position="left">系统信息</el-divider>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="服务器时间">
          {{ new Date().toLocaleString() }}
        </el-descriptions-item>
        <el-descriptions-item label="运行时长">
          {{ systemInfo.uptime }}
        </el-descriptions-item>
        <el-descriptions-item label="CPU使用率">
          <el-progress :percentage="systemInfo.cpu_usage" />
        </el-descriptions-item>
        <el-descriptions-item label="内存使用率">
          <el-progress :percentage="systemInfo.memory_usage" />
        </el-descriptions-item>
        <el-descriptions-item label="磁盘使用率">
          <el-progress :percentage="systemInfo.disk_usage" />
        </el-descriptions-item>
        <el-descriptions-item label="活跃任务数">
          {{ systemInfo.active_tasks }}
        </el-descriptions-item>
      </el-descriptions>

      <!-- 保存按钮 -->
      <el-form-item style="margin-top: 20px;">
        <el-button type="primary" @click="saveConfig" :loading="saving">
          保存配置
        </el-button>
        <el-button @click="restartSystem" :loading="restarting" type="warning">
          重启系统
        </el-button>
        <el-button @click="refreshSystemInfo" :loading="refreshing">
          刷新系统信息
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Setting } from '@element-plus/icons-vue'

// 配置数据
const config = reactive({
  system_name: '域名合规扫描系统',
  system_version: '1.0.0',
  admin_email: '',
  timezone: 'Asia/Shanghai',
  max_concurrent_tasks: 5,
  task_timeout_hours: 24,
  db_pool_size: 10,
  cache_expiry_minutes: 60,
  log_level: 'INFO',
  log_retention_days: 30,
  verbose_logging: false,
  screenshot_path: './storage/screenshots',
  max_file_size_mb: 10,
  auto_cleanup_enabled: true,
  file_retention_days: 30,
  monitoring_enabled: true,
  monitoring_interval_seconds: 30,
  cpu_alert_threshold: 80,
  memory_alert_threshold: 85,
  maintenance_mode: false,
  maintenance_message: '系统正在维护中，请稍后再试...'
})

// 系统信息
const systemInfo = reactive({
  uptime: '0天 0小时 0分钟',
  cpu_usage: 0,
  memory_usage: 0,
  disk_usage: 0,
  active_tasks: 0
})

const saving = ref(false)
const restarting = ref(false)
const refreshing = ref(false)

// 保存配置
const saveConfig = async () => {
  saving.value = true
  try {
    // TODO: 调用API保存配置
    await new Promise(resolve => setTimeout(resolve, 1000)) // 模拟API调用
    ElMessage.success('系统配置保存成功')
  } catch (error) {
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

// 重启系统
const restartSystem = async () => {
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

    restarting.value = true
    // TODO: 调用API重启系统
    await new Promise(resolve => setTimeout(resolve, 3000)) // 模拟重启时间
    ElMessage.success('系统重启成功')
  } catch {
    // 用户取消操作
  } finally {
    restarting.value = false
  }
}

// 刷新系统信息
const refreshSystemInfo = async () => {
  refreshing.value = true
  try {
    // TODO: 调用API获取系统信息
    await new Promise(resolve => setTimeout(resolve, 1000)) // 模拟API调用
    
    // 模拟数据
    systemInfo.uptime = '2天 3小时 45分钟'
    systemInfo.cpu_usage = Math.floor(Math.random() * 30) + 20
    systemInfo.memory_usage = Math.floor(Math.random() * 40) + 30
    systemInfo.disk_usage = Math.floor(Math.random() * 20) + 40
    systemInfo.active_tasks = Math.floor(Math.random() * 5)
    
    ElMessage.success('系统信息刷新成功')
  } catch (error) {
    ElMessage.error('刷新系统信息失败')
  } finally {
    refreshing.value = false
  }
}

// 加载配置
const loadConfig = async () => {
  try {
    // TODO: 调用API加载配置
    // const response = await api.getSystemConfig()
    // Object.assign(config, response.data)
    
    // 同时加载系统信息
    await refreshSystemInfo()
  } catch (error) {
    ElMessage.error('加载系统配置失败')
  }
}

onMounted(() => {
  loadConfig()
  
  // 定时刷新系统信息
  setInterval(() => {
    if (systemInfo.cpu_usage > 0) { // 只有加载过数据才自动刷新
      refreshSystemInfo()
    }
  }, 30000) // 每30秒刷新一次
})
</script>

<style scoped>
.system-config-panel {
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

.el-descriptions {
  margin-top: 10px;
}
</style>