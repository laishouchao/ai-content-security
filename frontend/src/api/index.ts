// 导出所有API接口
export * from './auth'
export * from './task'
export * from './config'
export * from './domain'
export * from './report'
export * from './statistics'
export { default as http } from './http'
export { axiosInstance } from './http'

// 统一导出
export const api = {
  auth: authApi,
  task: taskApi,
  config: configApi
}

export default api