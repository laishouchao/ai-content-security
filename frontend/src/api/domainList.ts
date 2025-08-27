/**
 * 域名白名单/黑名单管理API
 */

import { http } from './http'

// 类型定义
export interface DomainList {
  id: string
  name: string
  description?: string
  list_type: 'whitelist' | 'blacklist'
  scope: 'global' | 'user' | 'task'
  is_active: boolean
  is_regex_enabled: boolean
  priority: number
  domain_count: number
  match_count: number
  last_matched_at?: string
  created_at: string
  updated_at: string
}

export interface DomainEntry {
  id: string
  domain_pattern: string
  description?: string
  is_regex: boolean
  is_wildcard: boolean
  tags: string[]
  confidence_score: number
  match_count: number
  last_matched_at?: string
  last_matched_domain?: string
  is_active: boolean
  created_at: string
}

export interface CreateDomainListRequest {
  name: string
  list_type: 'whitelist' | 'blacklist'
  description?: string
  scope?: 'user' | 'global' | 'task'
  is_regex_enabled?: boolean
  priority?: number
}

export interface CreateDomainEntryRequest {
  domain_pattern: string
  description?: string
  is_regex?: boolean
  is_wildcard?: boolean
  tags?: string[]
  confidence_score?: number
}

export interface BatchAddDomainsRequest {
  domain_patterns: string[]
  is_regex?: boolean
  is_wildcard?: boolean
}

export interface DomainCheckRequest {
  domains: string[]
}

export interface DomainCheckResult {
  [domain: string]: {
    is_allowed: boolean | null
    list_type: string | null
    matched_pattern: string | null
    match_type: string | null
    confidence: number
    action: string
  }
}

// API函数
export const domainListAPI = {
  // 获取域名列表
  getDomainLists: (params: {
    list_type?: string
    scope?: string
    is_active?: boolean
    skip?: number
    limit?: number
  } = {}) => {
    return http.get('/api/v1/domain-lists', { params })
  },

  // 获取域名列表详情
  getDomainList: (listId: string) => {
    return http.get(`/api/v1/domain-lists/${listId}`)
  },

  // 获取域名列表详情（别名）
  getDomainListDetail: (listId: string) => {
    return http.get(`/api/v1/domain-lists/${listId}`)
  },

  // 获取域名列表中的域名
  getDomainListDomains: (listId: string, params: {
    skip?: number
    limit?: number
  } = {}) => {
    return http.get(`/api/v1/domain-lists/${listId}/entries`, { params })
  },

  // 创建域名列表
  createDomainList: (data: CreateDomainListRequest) => {
    return http.post('/api/v1/domain-lists', data)
  },

  // 更新域名列表
  updateDomainList: (listId: string, data: CreateDomainListRequest) => {
    return http.put(`/api/v1/domain-lists/${listId}`, data)
  },

  // 删除域名列表
  deleteDomainList: (listId: string) => {
    return http.delete(`/api/v1/domain-lists/${listId}`)
  },

  // 添加域名条目
  addDomainEntry: (listId: string, data: CreateDomainEntryRequest) => {
    return http.post(`/api/v1/domain-lists/${listId}/entries`, data)
  },

  // 删除域名条目
  removeDomainEntry: (entryId: string) => {
    return http.delete(`/api/v1/domain-lists/entries/${entryId}`)
  },

  // 从列表中删除域名
  deleteDomainFromList: (listId: string, entryId: string) => {
    return http.delete(`/api/v1/domain-lists/${listId}/entries/${entryId}`)
  },

  // 在列表中添加域名
  addDomainToList: (listId: string, data: {
    domain: string
    is_regex?: boolean
    notes?: string
  }) => {
    return http.post(`/api/v1/domain-lists/${listId}/entries`, {
      domain_pattern: data.domain,
      description: data.notes,
      is_regex: data.is_regex || false
    })
  },

  // 更新列表中的域名
  updateDomainInList: (listId: string, entryId: string, data: {
    domain: string
    is_regex?: boolean
    notes?: string
  }) => {
    return http.put(`/api/v1/domain-lists/${listId}/entries/${entryId}`, {
      domain_pattern: data.domain,
      description: data.notes,
      is_regex: data.is_regex || false
    })
  },

  // 对列表批量导入域名
  importDomainsToList: (listId: string, data: {
    domains: Array<{
      domain: string
      is_regex?: boolean
      notes?: string
    }>
  }) => {
    return http.post(`/api/v1/domain-lists/${listId}/batch-add`, {
      domain_patterns: data.domains.map(d => d.domain),
      entries: data.domains.map(d => ({
        domain_pattern: d.domain,
        description: d.notes,
        is_regex: d.is_regex || false
      }))
    })
  },

  // 批量添加域名
  batchAddDomains: (listId: string, data: BatchAddDomainsRequest) => {
    return http.post(`/api/v1/domain-lists/${listId}/batch-add`, data)
  },

  // CSV导入域名
  importDomainsFromCSV: (listId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return http.post(`/api/v1/domain-lists/${listId}/import-csv`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  // 检查域名
  checkDomains: (data: DomainCheckRequest) => {
    return http.post('/api/v1/domain-lists/check', data)
  },

  // 导出域名列表
  exportDomainList: (listId: string, format: 'json' | 'csv' | 'excel') => {
    return http.get(`/api/v1/domain-lists/${listId}/export`, {
      params: { format },
      responseType: 'blob'
    })
  }
}

export default domainListAPI