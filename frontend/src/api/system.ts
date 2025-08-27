/**
 * 系统配置API
 */

import { http } from './http'

// 类型定义
export interface SystemConfig {
  id?: string
  
  // 系统基本信息
  system_name: string
  system_description: string
  system_version: string
  system_admin_email: string
  
  // 系统运行配置
  debug_mode: boolean
  log_level: string
  max_workers: number
  worker_timeout: number
  
  // 数据库配置
  database_pool_size: number
  database_timeout: number
  database_backup_enabled: boolean
  database_backup_interval_hours: number
  
  // Redis配置
  redis_max_connections: number
  redis_timeout: number
  
  // 文件存储配置
  storage_type: string
  storage_path: string
  max_storage_size_gb: number
  auto_cleanup_enabled: boolean
  cleanup_retention_days: number
  
  // 监控配置
  monitoring_enabled: boolean
  metrics_retention_days: number
  alert_thresholds: {
    cpu_usage: number
    memory_usage: number
    disk_usage: number
    response_time: number
  }
  
  // 定时任务配置
  scheduler_enabled: boolean
  backup_schedule: string
  cleanup_schedule: string
  report_schedule: string
  
  created_at?: string
  updated_at?: string
}

export interface SystemStatus {
  system_info: {
    hostname: string
    platform: string
    architecture: string
    cpu_cores: number
    total_memory: string
    boot_time: string
  }
  performance: {
    cpu_usage: number
    memory_usage: number
    disk_usage: number
    network_io: {
      bytes_sent: number
      bytes_recv: number
    }
  }
  services: {
    database: {
      status: string
      connection_count: number
      uptime: string
    }
    redis: {
      status: string
      used_memory: string
      connected_clients: number
    }
    celery: {
      status: string
      active_tasks: number
      pending_tasks: number
    }
  }
  last_updated: string
}

export interface SystemLogs {
  application_logs: Array<{
    timestamp: string
    level: string
    message: string
    module: string
  }>
  error_logs: Array<{
    timestamp: string
    error_type: string
    message: string
    traceback: string
  }>
  access_logs: Array<{
    timestamp: string
    method: string
    url: string
    status_code: number
    response_time: number
    ip_address: string
  }>
}

// API函数
export const systemAPI = {
  // 获取系统配置
  getSystemConfig: () => {
    return http.get('/api/v1/config/system')
  },

  // 更新系统配置
  updateSystemConfig: (data: SystemConfig) => {
    return http.put('/api/v1/config/system', data)
  },

  // 获取系统状态
  getSystemStatus: () => {
    return http.get('/api/v1/config/system/status')
  },

  // 获取系统信息
  getSystemInfo: () => {
    return http.get('/api/v1/config/system/info')
  },

  // 重启系统服务
  restartSystem: () => {
    return http.post('/api/v1/config/system/restart')
  },

  // 获取系统日志
  getSystemLogs: (params: {
    log_type?: 'application' | 'error' | 'access'
    level?: string
    limit?: number
    start_date?: string
    end_date?: string
  } = {}) => {
    return http.get('/api/v1/config/system/logs', { params })
  },

  // 清理系统缓存
  clearCache: () => {
    return http.post('/api/v1/config/system/clear-cache')
  },

  // 数据库备份
  createBackup: () => {
    return http.post('/api/v1/config/system/backup')
  },

  // 获取备份列表
  getBackups: () => {
    return http.get('/api/v1/config/system/backups')
  },

  // 恢复备份
  restoreBackup: (backupId: string) => {
    return http.post(`/api/v1/config/system/backups/${backupId}/restore`)
  },

  // 删除备份
  deleteBackup: (backupId: string) => {
    return http.delete(`/api/v1/config/system/backups/${backupId}`)
  },

  // 健康检查
  healthCheck: () => {
    return http.get('/api/v1/config/system/health')
  }
}

export default systemAPI