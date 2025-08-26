import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/auth'
import type { User, LoginRequest, RegisterRequest, LoginResponse } from '@/types'
import type { ApiResponse } from '@/types/api'

// 登录响应类型（与后端API响应格式匹配）
interface AuthLoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const user = ref<User | null>(null)
  const loading = ref(false)

  // 计算属性
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const userName = computed(() => user.value?.full_name || user.value?.username || '')
  const userAvatar = computed(() => user.value?.avatar_url || '')

  // 保存令牌到本地存储
  const saveTokens = (accessToken: string, refreshTokenValue: string) => {
    token.value = accessToken
    refreshToken.value = refreshTokenValue
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('refresh_token', refreshTokenValue)
  }

  // 清除令牌
  const clearTokens = () => {
    token.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  // 用户登录
  const login = async (loginData: LoginRequest): Promise<boolean> => {
    try {
      loading.value = true
      
      const response: ApiResponse<AuthLoginResponse> = await authApi.login(loginData)
      
      if (response.data?.access_token && response.data?.user) {
        const { access_token, refresh_token, user: userData } = response.data
        
        saveTokens(access_token, refresh_token)
        user.value = userData
        
        ElMessage.success('登录成功')
        return true
      } else {
        ElMessage.error(response.message || '登录失败')
        return false
      }
    } catch (error: any) {
      console.error('Login error:', error)
      ElMessage.error(error.message || '登录失败，请重试')
      return false
    } finally {
      loading.value = false
    }
  }

  // 用户登出
  const logout = () => {
    clearTokens()
    ElMessage.success('已退出登录')
  }

  // 用户注册
  const register = async (registerData: RegisterRequest): Promise<boolean> => {
    try {
      loading.value = true
      
      // 注册用户
      const response: ApiResponse<User> = await authApi.register(registerData)
      
      if (response.data?.id) {
        ElMessage.success('注册成功')
        return true
      } else {
        ElMessage.error(response.message || '注册失败')
        return false
      }
    } catch (error: any) {
      console.error('Register error:', error)
      ElMessage.error(error.message || '注册失败，请重试')
      return false
    } finally {
      loading.value = false
    }
  }

  // 检查认证状态
  const checkAuth = async (): Promise<boolean> => {
    try {
      if (!token.value) {
        return false
      }

      // 获取当前用户信息
      const response: ApiResponse<User> = await authApi.getCurrentUser()
      
      if (response.data?.id) {
        user.value = response.data
        return true
      } else {
        clearTokens()
        return false
      }
    } catch (error) {
      console.error('Check auth error:', error)
      clearTokens()
      return false
    }
  }

  // 更新用户信息
  const updateProfile = async (profileData: Partial<User>): Promise<boolean> => {
    try {
      loading.value = true
      
      const response: ApiResponse<User> = await authApi.updateProfile(profileData)
      
      if (response.data?.id) {
        user.value = response.data
        ElMessage.success('个人信息更新成功')
        return true
      } else {
        ElMessage.error(response.message || '更新失败')
        return false
      }
    } catch (error: any) {
      console.error('Update profile error:', error)
      ElMessage.error(error.message || '更新失败，请重试')
      return false
    } finally {
      loading.value = false
    }
  }

  // 修改密码
  const changePassword = async (currentPassword: string, newPassword: string): Promise<boolean> => {
    try {
      loading.value = true
      
      const response: ApiResponse<void> = await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword
      })
      
      if (response.data !== undefined) {
        ElMessage.success('密码修改成功')
        return true
      } else {
        ElMessage.error(response.message || '密码修改失败')
        return false
      }
    } catch (error: any) {
      console.error('Change password error:', error)
      ElMessage.error(error.message || '密码修改失败，请重试')
      return false
    } finally {
      loading.value = false
    }
  }

  // 初始化认证状态
  const initAuth = async () => {
    if (token.value) {
      await checkAuth()
    }
  }

  return {
    // 状态
    token: computed(() => token.value),
    user: computed(() => user.value),
    loading: computed(() => loading.value),
    
    // 计算属性
    isAuthenticated,
    isAdmin,
    userName,
    userAvatar,
    
    // 方法
    login,
    register,
    logout,
    checkAuth,
    updateProfile,
    changePassword,
    initAuth
  }
})