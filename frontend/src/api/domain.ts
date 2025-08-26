import http, { type ApiResponse } from './http'
import { type AxiosResponse } from 'axios'
import type { ThirdPartyDomain, ViolationRecord, PaginationParams, PaginatedResponse, DomainFilter } from '@/types/api'

// 域名库相关类型定义
export interface DomainFilter {
  domain?: string
  domain_type?: string
  risk_level?: string
  has_violations?: boolean
}

// 域名库API接口
class DomainAPI {
  // 获取所有第三方域名（全局域名库）
  async getAllDomains(params: DomainFilter & PaginationParams = {}): Promise<AxiosResponse<ApiResponse<PaginatedResponse<ThirdPartyDomain>>>> {
    return http.get('/domains', { params })
  }
  
  // 获取域名详情
  async getDomain(domainId: string): Promise<AxiosResponse<ApiResponse<ThirdPartyDomain>>> {
    return http.get(`/domains/${domainId}`)
  }
  
  // 获取域名的违规记录
  async getDomainViolations(domainId: string, params: PaginationParams = {}): Promise<AxiosResponse<ApiResponse<PaginatedResponse<ViolationRecord>>>> {
    return http.get(`/domains/${domainId}/violations`, { params })
  }
  
  // 获取域名统计信息
  async getDomainStats(): Promise<AxiosResponse<ApiResponse<{
    total_domains: number
    analyzed_domains: number
    unanalyzed_domains: number
    violation_domains: number
    domain_type_distribution: Record<string, number>
    risk_level_distribution: Record<string, number>
    recent_domains: ThirdPartyDomain[]
  }>>> {
    return http.get('/domains/stats')
  }
  
  // 重新分析域名
  async reanalyzeDomain(domainId: string): Promise<AxiosResponse<ApiResponse<ThirdPartyDomain>>> {
    return http.post(`/domains/${domainId}/reanalyze`)
  }
  
  // 批量删除域名
  async deleteDomains(domainIds: string[]): Promise<AxiosResponse<ApiResponse<void>>> {
    return http.post('/domains/batch-delete', { domain_ids: domainIds })
  }
  
  // 导出域名数据
  async exportDomains(format: 'json' | 'csv' | 'excel' = 'json', filters: DomainFilter = {}): Promise<AxiosResponse<Blob>> {
    const params: any = { format }
    
    // 添加筛选条件
    if (filters.domain) params.domain = filters.domain
    if (filters.domain_type) params.domain_type = filters.domain_type
    if (filters.risk_level) params.risk_level = filters.risk_level
    if (filters.has_violations !== undefined) params.has_violations = filters.has_violations
    
    return http.get(`/domains/export`, {
      params,
      responseType: 'blob'
    })
  }
}

export const domainAPI = new DomainAPI()