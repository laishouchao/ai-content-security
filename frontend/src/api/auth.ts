import http from './http'
import type { 
  LoginRequest, 
  LoginResponse, 
  RegisterRequest, 
  User,
  ApiResponse 
} from '@/types'

// 认证API接口
export const authApi = {
  // 用户登录
  login(data: LoginRequest): Promise<ApiResponse<LoginResponse>> {
    return http.post('/auth/login', data)
  },
  
  // 用户注册
  register(data: RegisterRequest): Promise<ApiResponse<User>> {
    return http.post('/auth/register', data)
  },
  
  // 刷新令牌
  refreshToken(refreshToken: string): Promise<ApiResponse<{ access_token: string; expires_in: number }>> {
    return http.post('/auth/refresh', { refresh_token: refreshToken })
  },
  
  // 用户登出
  logout(): Promise<ApiResponse<void>> {
    return http.post('/auth/logout')
  },
  
  // 获取当前用户信息
  getCurrentUser(): Promise<ApiResponse<User>> {
    return http.get('/auth/me')
  },
  
  // 修改密码
  changePassword(data: {
    current_password: string
    new_password: string
  }): Promise<ApiResponse<void>> {
    return http.post('/auth/change-password', data)
  },
  
  // 忘记密码
  forgotPassword(email: string): Promise<ApiResponse<void>> {
    return http.post('/auth/forgot-password', { email })
  },
  
  // 重置密码
  resetPassword(data: {
    token: string
    new_password: string
  }): Promise<ApiResponse<void>> {
    return http.post('/auth/reset-password', data)
  },
  
  // 更新用户信息
  updateProfile(data: Partial<User>): Promise<ApiResponse<User>> {
    return http.put('/auth/profile', data)
  },
  
  // 上传头像
  uploadAvatar(file: File): Promise<ApiResponse<{ avatar_url: string }>> {
    const formData = new FormData()
    formData.append('file', file)
    return http.post('/auth/avatar', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  }
}