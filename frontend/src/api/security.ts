/**
 * 安全配置API
 */

import { http } from './http'

// 类型定义
export interface SecurityConfig {
  id?: string
  
  // 访问控制
  enable_ip_whitelist: boolean
  ip_whitelist: string[]
  enable_rate_limiting: boolean
  rate_limit_requests_per_minute: number
  
  // 会话管理
  session_timeout_minutes: number
  max_concurrent_sessions: number
  enable_session_binding: boolean
  
  // 密码策略
  password_min_length: number
  password_require_uppercase: boolean
  password_require_lowercase: boolean
  password_require_numbers: boolean
  password_require_symbols: boolean
  password_expiry_days: number
  password_history_count: number
  
  // 双因子认证
  enable_2fa: boolean
  require_2fa_for_admin: boolean
  totp_issuer: string
  
  // 审计日志
  enable_audit_log: boolean
  log_retention_days: number
  log_sensitive_operations: boolean
  
  // API安全
  enable_api_key_auth: boolean
  api_key_expiry_days: number
  enable_request_encryption: boolean
  
  // 文件上传安全
  max_file_size_mb: number
  allowed_file_types: string[]
  enable_virus_scan: boolean
  
  created_at?: string
  updated_at?: string
}

export interface SecurityAuditLog {
  id: string
  user_id: string
  username: string
  action: string
  resource: string
  ip_address: string
  user_agent: string
  success: boolean
  details: Record<string, any>
  timestamp: string
}

export interface SecurityStatusCheck {
  ssl_certificate: {
    valid: boolean
    expires_at: string
    issuer: string
  }
  password_strength: {
    average_score: number
    weak_passwords_count: number
  }
  session_security: {
    active_sessions: number
    suspicious_sessions: number
  }
  api_security: {
    active_api_keys: number
    expired_api_keys: number
  }
  last_checked: string
}

// API函数
export const securityAPI = {
  // 获取安全配置
  getSecurityConfig: () => {
    return http.get('/api/v1/config/security')
  },

  // 更新安全配置
  updateSecurityConfig: (data: SecurityConfig) => {
    return http.put('/api/v1/config/security', data)
  },

  // 重置安全配置为默认值
  resetSecurityConfig: () => {
    return http.post('/api/v1/config/security/reset')
  },

  // 获取安全状态检查
  getSecurityStatus: () => {
    return http.get('/api/v1/config/security/status')
  },

  // 获取审计日志
  getAuditLogs: (params: {
    skip?: number
    limit?: number
    user_id?: string
    action?: string
    start_date?: string
    end_date?: string
  } = {}) => {
    return http.get('/api/v1/config/security/audit-logs', { params })
  },

  // 强制踢出所有用户会话
  forceLogoutAll: () => {
    return http.post('/api/v1/config/security/force-logout-all')
  },

  // 生成新的API密钥
  generateApiKey: (data: {
    name: string
    permissions: string[]
    expires_in_days?: number
  }) => {
    return http.post('/api/v1/config/security/api-keys', data)
  },

  // 撤销API密钥
  revokeApiKey: (keyId: string) => {
    return http.delete(`/api/v1/config/security/api-keys/${keyId}`)
  },

  // 检查IP地址是否在白名单中
  checkIpWhitelist: (ip: string) => {
    return http.post('/api/v1/config/security/check-ip', { ip })
  }
}

export default securityAPI