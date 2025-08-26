// 用户相关类型
export interface User {
  id: string
  username: string
  email: string
  role: string
  is_active: boolean
  created_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

// 任务相关类型
export interface TaskConfig {
  subdomain_discovery_enabled: boolean
  link_crawling_enabled: boolean
  third_party_identification_enabled: boolean
  content_capture_enabled: boolean
  ai_analysis_enabled: boolean
  max_subdomains: number
  max_crawl_depth: number
  max_pages_per_domain: number
  request_delay: number
  timeout: number
  max_crawl_iterations?: number // 添加迭代爬取最大次数配置
}

export interface CreateTaskRequest {
  target_domain: string
  task_name?: string
  description?: string
  config: Partial<TaskConfig>
}

export enum TaskStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

export interface Task {
  id: string
  user_id: string
  target_domain: string
  task_name?: string
  description?: string
  status: TaskStatus
  progress: number
  config: TaskConfig
  
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

export interface TaskLog {
  id: string
  task_id: string
  level: string
  module: string
  message: string
  extra_data?: Record<string, any>
  created_at: string
}

export interface TaskFilter {
  status?: TaskStatus
  domain?: string
  start_date?: string
  end_date?: string
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
  // 添加一个计算属性用于判断是否有违规
  has_violations?: boolean
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

// 域名库筛选条件
export interface DomainFilter {
  domain?: string
  domain_type?: string
  risk_level?: string
  has_violations?: boolean
}

// 分页参数
export interface PaginationParams {
  skip?: number
  limit?: number
  sort?: string
  order?: 'asc' | 'desc'
}

// 分页响应
export interface PaginatedResponse<T> {
  total: number
  items: T[]
  skip: number
  limit: number
}

// WebSocket消息类型
export interface WebSocketMessage {
  type: string
  timestamp: string
  [key: string]: any
}