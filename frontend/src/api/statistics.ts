import { AxiosResponse } from 'axios'
import http from './http'
import type { ApiResponse } from '@/types/api'

// 统计数据接口定义
export interface OverviewStats {
  total_tasks: number
  completed_tasks: number
  running_tasks: number
  failed_tasks: number
  pending_tasks: number
  cancelled_tasks: number
  total_violations: number
  critical_violations: number
  high_violations: number
  medium_violations: number
  low_violations: number
  today_tasks: number
  task_trend?: number
  completion_trend?: number
  domain_trend?: number
  violation_trend?: number
  total_domains?: number
}

export interface TaskTrendData {
  date: string
  total: number
  completed: number
  failed: number
  violations: number
}

export interface ViolationDistribution {
  type: string
  count: number
  name: string
}

export interface RiskDistribution {
  level: string
  count: number
  name: string
}

export interface SystemStatus {
  running_tasks: number
  today_completed: number
  avg_execution_time: number
  queue_status: string
  api_status: string
  database_status: string
}

export interface RecentTask {
  id: string
  target_domain: string
  status: string
  progress: number
  created_at: string
  completed_at?: string
  total_violations: number
  error_message?: string
}

export interface DashboardStats extends OverviewStats {
  task_trends: TaskTrendData[]
  violation_distribution: ViolationDistribution[]
  risk_level_distribution: RiskDistribution[]
  recent_tasks: RecentTask[]
  system_status: SystemStatus
}

export interface TaskStatistics {
  date: string
  total: number
  completed: number
  failed: number
  success_rate: number
}

export interface PerformanceMetrics {
  cpu_usage: number
  memory_usage: number
  disk_usage: number
  network_io: number
  active_connections: number
  response_time: number
  timestamp: string
}

export interface UserActivityData {
  active_users: number
  new_users: number
  user_retention: number
  peak_concurrent: number
}

// 统计API类
class StatisticsAPI {
  // 获取仪表板统计数据（从任务统计接口获取）
  async getDashboardStats(): Promise<AxiosResponse<ApiResponse<DashboardStats>>> {
    return http.get('/tasks/stats')
  }

  // 获取概览统计
  async getOverviewStats(params?: {
    start_date?: string
    end_date?: string
  }): Promise<AxiosResponse<ApiResponse<OverviewStats>>> {
    return http.get('/tasks/stats', { params })
  }

  // 获取任务统计
  async getTaskStatistics(params?: {
    start_date?: string
    end_date?: string
  }): Promise<AxiosResponse<ApiResponse<TaskStatistics[]>>> {
    return http.get('/tasks/stats/daily', { params })
  }

  // 获取任务趋势
  async getTaskTrend(params?: {
    period?: '7d' | '30d' | '90d'
  }): Promise<AxiosResponse<ApiResponse<TaskTrendData[]>>> {
    return http.get('/tasks/stats/trend', { params })
  }

  // 获取违规分布
  async getViolationDistribution(params?: {
    start_date?: string
    end_date?: string
  }): Promise<AxiosResponse<ApiResponse<ViolationDistribution[]>>> {
    return http.get('/tasks/stats/violations', { params })
  }

  // 获取性能监控数据（从性能接口获取）
  async getPerformanceStats(): Promise<AxiosResponse<ApiResponse<PerformanceMetrics>>> {
    return http.get('/performance/stats')
  }

  // 获取性能趋势
  async getPerformanceTrend(params?: {
    hours?: number
  }): Promise<AxiosResponse<ApiResponse<PerformanceMetrics[]>>> {
    return http.get('/performance/stats/trend', { params })
  }

  // 获取用户活跃度
  async getUserActivity(params?: {
    start_date?: string
    end_date?: string
  }): Promise<AxiosResponse<ApiResponse<{
    table: any[]
    chart: UserActivityData
  }>>> {
    // 暂时返回模拟数据，等后端实现
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          data: {
            success: true,
            data: {
              table: [
                { date: '2024-01-15', active_users: 25, new_users: 3, retention: 85 },
                { date: '2024-01-14', active_users: 23, new_users: 2, retention: 87 },
                { date: '2024-01-13', active_users: 28, new_users: 5, retention: 82 }
              ],
              chart: {
                active_users: 25,
                new_users: 10,
                user_retention: 85,
                peak_concurrent: 15
              }
            },
            message: 'Success'
          }
        } as any)
      }, 500)
    })
  }

  // 导出统计报告
  async exportReport(params: {
    format: 'excel' | 'pdf'
    start_date?: string
    end_date?: string
  }): Promise<AxiosResponse<Blob>> {
    return http.get('/statistics/export', {
      params,
      responseType: 'blob'
    })
  }
}

export const statisticsAPI = new StatisticsAPI()