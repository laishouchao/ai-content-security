import axios, { type AxiosInstance, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

// API响应类型
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  message?: string
  error_code?: string
  request_id?: string
}

// 创建axios实例
const http: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
http.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    
    // 添加认证令牌
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    
    // 添加请求ID用于调试
    config.headers['X-Request-ID'] = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    
    console.log(`🚀 API请求: ${config.method?.toUpperCase()} ${config.baseURL || ''}${config.url || ''}`, config.data)
    
    return config
  },
  (error) => {
    console.error('请求拦截器错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
http.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const { data } = response
    
    console.log(`✅ API响应: ${response.config.method?.toUpperCase()} ${response.config.baseURL || ''}${response.config.url || ''}`, data)
    
    // 检查业务状态码
    if (data && typeof data === 'object') {
      // 如果响应中包含success字段且为false，则视为错误
      if ('success' in data && data.success === false) {
        const message = data.message || '请求失败'
        ElMessage.error(message)
        return Promise.reject(new Error(message))
      }
    }
    
    // 确保返回完整的响应对象
    return response
  },
  (error) => {
    console.error('❌ API错误:', error)
    
    const authStore = useAuthStore()
    
    // 处理HTTP状态码
    if (error.response) {
      const { status, data } = error.response
      
      // 检查是否为登录请求
      const isLoginRequest = error.config?.url?.includes('/auth/login')
      
      switch (status) {
        case 401:
          // 如果是登录请求返回的401错误，不执行登出操作，只显示错误信息
          if (isLoginRequest) {
            const message = data?.message || '用户名或密码错误'
            ElMessage.error(message)
          } else {
            ElMessage.error('登录已过期，请重新登录')
            authStore.logout()
            window.location.href = '/login'
          }
          break
        case 403:
          ElMessage.error('权限不足')
          break
        case 404:
          ElMessage.error('请求的资源不存在')
          break
        case 429:
          ElMessage.error('请求过于频繁，请稍后重试')
          break
        case 500:
          ElMessage.error('服务器内部错误')
          break
        default:
          const message = data?.message || `请求失败 (${status})`
          ElMessage.error(message)
      }
    } else if (error.request) {
      ElMessage.error('网络连接失败，请检查网络设置')
    } else {
      ElMessage.error('请求配置错误')
    }
    
    return Promise.reject(error)
  }
)

export default http