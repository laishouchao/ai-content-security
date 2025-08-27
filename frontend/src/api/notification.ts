/**
 * 通知配置API
 */

import { http } from './http'

// 类型定义
export interface NotificationConfig {
  id?: string
  email_enabled: boolean
  email_recipients: string[]
  email_smtp_host: string
  email_smtp_port: number
  email_smtp_username: string
  email_smtp_password: string
  email_smtp_use_tls: boolean
  
  webhook_enabled: boolean
  webhook_url: string
  webhook_secret: string
  webhook_events: string[]
  
  task_completion_notification: boolean
  violation_detection_notification: boolean
  system_error_notification: boolean
  daily_report_notification: boolean
  
  notification_threshold: number
  notification_quiet_hours_start: string
  notification_quiet_hours_end: string
  
  created_at?: string
  updated_at?: string
}

export interface TestNotificationRequest {
  type: 'email' | 'webhook'
  message: string
}

export interface NotificationTestResult {
  success: boolean
  message: string
  response_time?: number
  error_details?: string
}

// API函数
export const notificationAPI = {
  // 获取通知配置
  getNotificationConfig: () => {
    return http.get('/api/v1/config/notification')
  },

  // 更新通知配置
  updateNotificationConfig: (data: NotificationConfig) => {
    return http.put('/api/v1/config/notification', data)
  },

  // 测试通知配置
  testNotification: (data: TestNotificationRequest) => {
    return http.post('/api/v1/config/notification/test', data)
  },

  // 获取通知历史
  getNotificationHistory: (params: {
    skip?: number
    limit?: number
    type?: string
    status?: string
    start_date?: string
    end_date?: string
  } = {}) => {
    return http.get('/api/v1/config/notification/history', { params })
  },

  // 重新发送失败的通知
  resendNotification: (notificationId: string) => {
    return http.post(`/api/v1/config/notification/resend/${notificationId}`)
  }
}

export default notificationAPI