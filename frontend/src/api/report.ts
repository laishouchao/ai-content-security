import http from './http'
import type { AxiosResponse } from 'axios'
import type { 
  ApiResponse, 
  ScanReport, 
  ReportSummary, 
  ViolationRecord, 
  ReportFilter 
} from '@/types/api'

class ReportAPI {
  // 获取报告列表
  async getReports(
    skip: number = 0,
    limit: number = 20,
    filters: ReportFilter = {}
  ): Promise<AxiosResponse<ApiResponse<{
    items: ScanReport[]
    total: number
    skip: number
    limit: number
  }>>> {
    const params: any = { skip, limit }
    
    if (filters.task_name) params.task_name = filters.task_name
    if (filters.status) params.status = filters.status
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to
    
    return http.get('/reports', { params })
  }

  // 获取扫描报告
  async getScanReport(
    taskId: string,
    format: 'json' | 'pdf' | 'excel' = 'json'
  ): Promise<AxiosResponse<ApiResponse<ScanReport>>> {
    return http.get(`/reports/${taskId}`, {
      params: { format }
    })
  }

  // 获取报告摘要
  async getReportSummary(taskId: string): Promise<AxiosResponse<ApiResponse<ReportSummary>>> {
    return http.get(`/reports/${taskId}/summary`)
  }

  // 获取违规记录
  async getViolations(
    taskId: string,
    skip: number = 0,
    limit: number = 20,
    riskLevel?: string,
    violationType?: string
  ): Promise<AxiosResponse<ApiResponse<{
    items: ViolationRecord[]
    total: number
    skip: number
    limit: number
  }>>> {
    const params: any = { skip, limit }
    
    if (riskLevel) params.risk_level = riskLevel
    if (violationType) params.violation_type = violationType
    
    return http.get(`/reports/${taskId}/violations`, { params })
  }

  // 导出报告
  async exportReport(
    taskId: string,
    format: 'json' | 'pdf' | 'excel' | 'csv'
  ): Promise<AxiosResponse<Blob>> {
    return http.get(`/reports/${taskId}/export`, {
      params: { format },
      responseType: 'blob'
    })
  }

  // 获取统计信息
  async getStatistics(taskId: string): Promise<AxiosResponse<ApiResponse<any>>> {
    return http.get(`/reports/${taskId}/statistics`)
  }

  // 获取扫描时间线
  async getScanTimeline(taskId: string): Promise<AxiosResponse<ApiResponse<any>>> {
    return http.get(`/reports/${taskId}/timeline`)
  }

  // 生成新报告
  async generateReport(taskId: string): Promise<AxiosResponse<ApiResponse<ScanReport>>> {
    return http.post(`/reports/${taskId}/generate`)
  }

  // 删除报告
  async deleteReport(taskId: string): Promise<AxiosResponse<ApiResponse<void>>> {
    return http.delete(`/reports/${taskId}`)
  }

  // 批量导出报告
  async batchExportReports(
    taskIds: string[],
    format: 'json' | 'pdf' | 'excel' | 'csv'
  ): Promise<AxiosResponse<Blob>> {
    return http.post('/reports/batch-export', {
      task_ids: taskIds,
      format
    }, {
      responseType: 'blob'
    })
  }
}

export const reportAPI = new ReportAPI()