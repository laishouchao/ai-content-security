// 导出所有API接口
export { authApi } from './auth'
export { taskApi } from './task'
export { configApi } from './config'
export { default as http } from './http'
export { axiosInstance } from './http'

// 统一导出
export const api = {
  auth: authApi,
  task: taskApi,
  config: configApi
}

export default api