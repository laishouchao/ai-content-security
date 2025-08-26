import http from './http'
import type { 
  AIConfig,
  AIConfigRequest,
  AIConfigTestResponse,
  SystemConfig,
  ApiResponse 
} from '@/types'

// 配置API接口
export const configApi = {
  // AI配置相关
  ai: {
    // 获取用户AI配置
    getConfig(): Promise<ApiResponse<AIConfig>> {
      return http.get('/config/ai')
    },
    
    // 更新用户AI配置
    updateConfig(data: AIConfigRequest): Promise<ApiResponse<AIConfig>> {
      return http.put('/config/ai', data)
    },
    
    // 删除用户AI配置
    deleteConfig(): Promise<ApiResponse<void>> {
      return http.delete('/config/ai')
    },
    
    // 测试AI配置
    testConfig(data: { test_message?: string } = {}): Promise<ApiResponse<AIConfigTestResponse>> {
      return http.post('/config/ai/test', data)
    }
  },
  
  // 系统配置相关（管理员）
  system: {
    // 获取系统配置
    getConfig(): Promise<ApiResponse<SystemConfig>> {
      return http.get('/config/system')
    },
    
    // 更新系统配置
    updateConfig(data: Partial<SystemConfig>): Promise<ApiResponse<SystemConfig>> {
      return http.put('/config/system', data)
    },
    
    // 重置系统配置为默认值
    resetConfig(): Promise<ApiResponse<SystemConfig>> {
      return http.post('/config/system/reset')
    }
  },
  
  // 扫描配置相关
  scan: {
    // 获取默认扫描配置
    getDefaults(): Promise<ApiResponse<{
      subdomain_discovery: {
        max_subdomains: number
        methods: string[]
        timeout: number
      }
      link_crawling: {
        max_depth: number
        max_pages_per_domain: number
        timeout_per_page: number
        respect_robots_txt: boolean
      }
      content_capture: {
        capture_screenshots: boolean
        screenshot_quality: number
        viewport_width: number
        viewport_height: number
        wait_for_load: number
      }
      ai_analysis: {
        confidence_threshold: number
        max_content_length: number
        batch_size: number
        retry_count: number
      }
    }>> {
      return http.get('/config/scan-defaults')
    },
    
    // 更新默认扫描配置
    updateDefaults(data: Record<string, any>): Promise<ApiResponse<void>> {
      return http.put('/config/scan-defaults', data)
    },
    
    // 获取扫描模板
    getTemplates(): Promise<ApiResponse<Array<{
      id: string
      name: string
      description: string
      config: Record<string, any>
      is_default: boolean
      created_by: string
      created_at: string
    }>>> {
      return http.get('/config/scan-templates')
    },
    
    // 创建扫描模板
    createTemplate(data: {
      name: string
      description: string
      config: Record<string, any>
      is_default?: boolean
    }): Promise<ApiResponse<{ id: string }>> {
      return http.post('/config/scan-templates', data)
    },
    
    // 更新扫描模板
    updateTemplate(templateId: string, data: {
      name?: string
      description?: string
      config?: Record<string, any>
      is_default?: boolean
    }): Promise<ApiResponse<void>> {
      return http.put(`/config/scan-templates/${templateId}`, data)
    },
    
    // 删除扫描模板
    deleteTemplate(templateId: string): Promise<ApiResponse<void>> {
      return http.delete(`/config/scan-templates/${templateId}`)
    }
  },
  
  // 通知配置
  notification: {
    // 获取通知配置
    getConfig(): Promise<ApiResponse<{
      email_enabled: boolean
      email_on_task_complete: boolean
      email_on_violation_detected: boolean
      email_on_error: boolean
      webhook_enabled: boolean
      webhook_url?: string
      webhook_events: string[]
      in_app_notifications: boolean
    }>> {
      return http.get('/config/notifications')
    },
    
    // 更新通知配置
    updateConfig(data: {
      email_enabled?: boolean
      email_on_task_complete?: boolean
      email_on_violation_detected?: boolean
      email_on_error?: boolean
      webhook_enabled?: boolean
      webhook_url?: string
      webhook_events?: string[]
      in_app_notifications?: boolean
    }): Promise<ApiResponse<void>> {
      return http.put('/config/notifications', data)
    },
    
    // 测试通知配置
    testConfig(type: 'email' | 'webhook'): Promise<ApiResponse<{
      success: boolean
      message: string
    }>> {
      return http.post(`/config/notifications/test/${type}`)
    }
  }
}