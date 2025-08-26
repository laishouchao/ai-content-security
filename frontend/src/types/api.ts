// 用户相关类型
export interface User {
  id: string
  username: string
  email: string
  role: 'admin' | 'user'
  is_active: boolean
  full_name?: string
  avatar_url?: string
  bio?: string
  created_at: string
  updated_at: string
  last_login?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  full_name?: string
}

// AI配置相关类型
export interface AIConfig {
  id: string
  user_id: string
  openai_base_url: string
  openai_organization?: string
  model_name: string
  max_tokens: number
  temperature: number
  system_prompt?: string
  custom_prompt_template?: string
  request_timeout: number
  retry_count: number
  enable_streaming: boolean
  has_valid_config: boolean
  created_at: string
  updated_at: string
  last_tested?: string
}

export interface AIConfigRequest {
  openai_api_key?: string
  openai_base_url?: string
  openai_organization?: string
  model_name?: string
  max_tokens?: number
  temperature?: number
  system_prompt?: string
  custom_prompt_template?: string
  request_timeout?: number
  retry_count?: number
  enable_streaming?: boolean
}

export interface AIConfigTestResponse {
  is_successful: boolean
  response_message?: string
  error_message?: string
  response_time?: number
  model_used?: string
}

// 扫描任务相关类型
export interface Task {
  id: string
  user_id: string
  target_domain: string
  task_name: string | null
  status: TaskStatus
  progress: number
  config: Record<string, any>
  
  // 统计信息
  total_subdomains: number
  total_pages_crawled: number
  total_third_party_domains: number
  total_violations: number
  critical_violations: number
  high_violations: number
  medium_violations: number
  low_violations: number
  
  // 时间戳
  created_at: string
  started_at?: string
  completed_at?: string
  
  error_message?: string
}

export enum TaskStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

export interface CreateTaskRequest {
  target_domain: string
  config?: {
    subdomain_discovery_enabled?: boolean
    link_crawling_enabled?: boolean
    third_party_identification_enabled?: boolean
    content_capture_enabled?: boolean
    ai_analysis_enabled?: boolean
    max_subdomains?: number
    max_crawl_depth?: number
    max_pages_per_domain?: number
  }
}

export interface TaskLog {
  id: string
  task_id: string
  level: string
  module: string
  message: string
  extra_data?: Record<string, any>
  created_at: string
}

// 子域名记录
export interface SubdomainRecord {
  id: string
  task_id: string
  subdomain: string
  ip_address?: string
  discovery_method: string
  is_accessible: boolean
  response_code?: number
  response_time?: number
  server_header?: string
  content_type?: string
  page_title?: string
  created_at: string
}

// 第三方域名
export interface ThirdPartyDomain {
  id: string
  task_id: string
  domain: string
  found_on_url: string
  domain_type: string
  risk_level: string
  page_title?: string
  page_description?: string
  content_hash?: string
  screenshot_path?: string
  html_content_path?: string
  is_analyzed: boolean
  analysis_error?: string
  created_at: string
  analyzed_at?: string
  violations?: ViolationRecord[]
}

// 违规记录
export interface ViolationRecord {
  id: string
  task_id: string
  domain_id: string
  violation_type: string
  confidence_score: number
  risk_level: string
  title: string
  description: string
  content_snippet?: string
  ai_analysis_result: Record<string, any>
  ai_model_used?: string
  evidence?: string[]
  recommendations?: string[]
  detected_at: string
}

// WebSocket消息类型
export interface WebSocketMessage {
  type: string
  timestamp: string
  [key: string]: any
}

export interface TaskProgressMessage extends WebSocketMessage {
  type: 'task_progress'
  task_id: string
  progress: number
  stage: string
  message: string
}

export interface TaskCompletedMessage extends WebSocketMessage {
  type: 'task_completed'
  task_id: string
  status: string
  statistics: Record<string, any>
  message: string
}

export interface ViolationDetectedMessage extends WebSocketMessage {
  type: 'violation_detected'
  task_id: string
  violation: {
    domain: string
    violation_type: string
    risk_level: string
    confidence_score: number
    description: string
  }
  message: string
}

// 通用API响应类型
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  message?: string
  error_code?: string
  request_id?: string
}

export interface PaginationParams {
  skip?: number
  limit?: number
}

export interface TaskFilter {
  status?: TaskStatus
  domain?: string
}

export interface PaginatedResponse<T> {
  total: number
  items: T[]
  skip: number
  limit: number
}

// 系统配置
export interface SystemConfig {
  scan_limits: {
    max_concurrent_tasks_per_user: number
    max_subdomains_per_task: number
    max_crawl_depth: number
    task_timeout_hours: number
  }
  ai_settings: {
    default_model: string
    default_max_tokens: number
    default_temperature: number
    request_timeout: number
    retry_count: number
  }
  security: {
    max_login_attempts: number
    lockout_duration_minutes: number
    rate_limit_per_minute: number
    access_token_expire_minutes: number
  }
}

// 统计信息
export interface Statistics {
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  total_violations: number
  violation_distribution: Record<string, number>
  domain_type_distribution: Record<string, number>
  risk_level_distribution: Record<string, number>
}

// 表单验证规则
export interface FormRule {
  required?: boolean
  message: string
  trigger?: string | string[]
  validator?: (rule: any, value: any, callback: any) => void
  min?: number
  max?: number
  pattern?: RegExp
}