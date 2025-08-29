import http, { type ApiResponse } from './http'
import { type AxiosResponse } from 'axios'
import type { ThirdPartyDomain } from '@/types/api'

// 任务相关类型定义
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

export enum TaskStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

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
  
  // 性能优化配置
  use_parallel_executor?: boolean
  dns_concurrency?: number
  multi_viewport_capture?: boolean
  enable_aggressive_caching?: boolean
  
  // 高级配置
  certificate_discovery_enabled?: boolean
  passive_dns_enabled?: boolean
  max_concurrent_ai_calls?: number
  batch_size?: number
  screenshot_optimization?: boolean
  max_crawl_iterations?: number
  
  // 无限爬取模式配置
  enable_infinite_discovery?: boolean
}

export interface PerformanceMetrics {
  execution_time: number
  subdomains_discovered: number
  pages_crawled: number
  ai_calls_made: number
  ai_calls_skipped: number
  cost_saved: number
  ai_skip_rate: number
  efficiency_score: number
}

export interface CreateTaskRequest {
  target_domain: string
  task_name?: string
  description?: string
  config: Partial<TaskConfig>
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

export interface PaginationParams {
  skip?: number
  limit?: number
  sort?: string
  order?: 'asc' | 'desc'
}

export interface TaskFilter {
  status?: TaskStatus
  domain?: string
  start_date?: string
  end_date?: string
}

export interface PaginatedResponse<T> {
  total: number
  items: T[]
  skip: number
  limit: number
}

// 任务API接口
class TaskAPI {
  // 获取任务列表
  async getTasks(params: TaskFilter & PaginationParams = {}): Promise<AxiosResponse<ApiResponse<PaginatedResponse<Task>>>> {
    return http.get('/tasks', { params })
  }
  
  // 获取任务详情
  async getTask(taskId: string): Promise<AxiosResponse<ApiResponse<Task>>> {
    return http.get(`/tasks/${taskId}`)
  }
  
  // 创建任务
  async createTask(data: CreateTaskRequest): Promise<AxiosResponse<ApiResponse<Task>>> {
    return http.post('/tasks', data)
  }
  
  // 停止任务
  async stopTask(taskId: string): Promise<AxiosResponse<ApiResponse<void>>> {
    return http.post(`/tasks/${taskId}/cancel`)
  }
  
  // 重试任务
  async retryTask(taskId: string): Promise<AxiosResponse<ApiResponse<Task>>> {
    return http.post(`/tasks/${taskId}/retry`)
  }
  
  // 删除任务
  async deleteTask(taskId: string): Promise<AxiosResponse<ApiResponse<void>>> {
    return http.delete(`/tasks/${taskId}`)
  }
  
  // 获取任务日志
  async getTaskLogs(taskId: string, params: PaginationParams = {}): Promise<AxiosResponse<ApiResponse<PaginatedResponse<TaskLog>>>> {
    return http.get(`/tasks/${taskId}/logs`, { params })
  }
  
  // 获取子域名记录
  async getSubdomains(taskId: string, params: PaginationParams = {}): Promise<AxiosResponse<ApiResponse<PaginatedResponse<SubdomainRecord>>>> {
    return http.get(`/tasks/${taskId}/subdomains`, { params })
  }
  
  // 获取违规记录
  async getViolations(taskId: string, params: PaginationParams = {}): Promise<AxiosResponse<ApiResponse<PaginatedResponse<ViolationRecord>>>> {
    return http.get(`/tasks/${taskId}/violations`, { params })
  }
  
  // 获取第三方域名
  async getThirdPartyDomains(taskId: string, params: PaginationParams = {}): Promise<AxiosResponse<ApiResponse<PaginatedResponse<ThirdPartyDomain>>>> {
    return http.get(`/tasks/${taskId}/domains`, { params })
  }
  
  // 获取域名统计信息
  async getDomainStats(taskId: string): Promise<AxiosResponse<ApiResponse<{
    total_domains: number
    target_domains: number
    subdomain_count: number
    third_party_count: number
    accessible_count: number
    analyzed_count: number
    violation_count: number
  }>>> {
    return http.get(`/tasks/${taskId}/domain-stats`)
  }
  
  // 获取任务统计
  async getTaskStats(): Promise<AxiosResponse<ApiResponse<{
    total_tasks: number
    completed_tasks: number
    running_tasks: number
    failed_tasks: number
    total_violations: number
    violation_distribution: Record<string, number>
    recent_tasks: Task[]
    task_trends: Array<{
      date: string
      total: number
      completed: number
      failed: number
      violations: number
    }>
    risk_level_distribution: Array<{
      risk_level: string
      count: number
    }>
    system_status: Record<string, any>
  }>>> {
    return http.get('/tasks/stats')
  }
  
  // 获取任务性能指标
  async getTaskPerformanceMetrics(taskId: string): Promise<AxiosResponse<ApiResponse<{
    metrics: PerformanceMetrics
    ai_skip_rate: string
    efficiency_score: string
    performance_optimizations: {
      parallel_executor_enabled: boolean
      dns_concurrency: number
    }
  }>>> {
    return http.post(`/tasks/${taskId}/performance-metrics`)
  }
}

export const taskAPI = new TaskAPI()