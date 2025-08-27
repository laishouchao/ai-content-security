// 导出所有API接口
export * from './auth'
export * from './task'
export * from './config'
export * from './domain'
export * from './report'
export * from './statistics'
export { default as http } from './http'

// 导入API实例
import { authApi } from './auth'
import { taskAPI } from './task'
import { configApi } from './config'
import { domainAPI } from './domain'
import { reportAPI } from './report'
import { statisticsAPI } from './statistics'

// 统一导出
export const api = {
  auth: authApi,
  task: taskAPI,
  config: configApi,
  domain: domainAPI,
  report: reportAPI,
  statistics: statisticsAPI
}

export default api