<template>
  <div class="profile">
    <div class="page-header">
      <h2>个人资料</h2>
      <p>管理您的账户信息和系统设置</p>
    </div>

    <el-row :gutter="20">
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>头像</span>
          </template>
          <div class="avatar-section">
            <el-avatar :size="120" :src="profile.avatarUrl">
              {{ profile.username.charAt(0).toUpperCase() }}
            </el-avatar>
            <el-upload
              ref="uploadRef"
              :action="uploadAction"
              :headers="uploadHeaders"
              :show-file-list="false"
              :before-upload="beforeAvatarUpload"
              :on-success="handleAvatarSuccess"
              :on-error="handleAvatarError"
              accept="image/*"
            >
              <el-button type="primary" size="small" :loading="avatarUploading" style="margin-top: 16px;">
                {{ avatarUploading ? '上传中...' : '更换头像' }}
              </el-button>
            </el-upload>
            <div class="avatar-tip">
              <p>支持 JPG、PNG 格式</p>
              <p>文件大小不超过 2MB</p>
            </div>
          </div>
        </el-card>

        <!-- 用户统计信息 -->
        <el-card style="margin-top: 20px;">
          <template #header>
            <span>账户统计</span>
          </template>
          <div class="stats-list">
            <div class="stat-item">
              <span class="stat-label">注册时间</span>
              <span class="stat-value">{{ profile.createdAt }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">最后登录</span>
              <span class="stat-value">{{ profile.lastLogin || '从未登录' }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">账户状态</span>
              <el-tag :type="profile.isActive ? 'success' : 'danger'" size="small">
                {{ profile.isActive ? '活跃' : '禁用' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card>
          <template #header>
            <span>基本信息</span>
          </template>
          <el-form 
            ref="profileFormRef"
            :model="profile" 
            :rules="profileRules"
            label-width="100px"
          >
            <el-form-item label="用户名">
              <el-input v-model="profile.username" disabled>
                <template #prefix>
                  <el-icon><User /></el-icon>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="profile.email">
                <template #prefix>
                  <el-icon><Message /></el-icon>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="姓名" prop="fullName">
              <el-input v-model="profile.fullName" placeholder="请输入真实姓名">
                <template #prefix>
                  <el-icon><User /></el-icon>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="个人简介" prop="bio">
              <el-input 
                v-model="profile.bio" 
                type="textarea" 
                :rows="4" 
                placeholder="请输入个人简介"
                maxlength="500"
                show-word-limit
              />
            </el-form-item>
            <el-form-item label="角色">
              <el-tag type="primary">{{ profile.role }}</el-tag>
            </el-form-item>
            <el-form-item>
              <el-button 
                type="primary" 
                @click="saveProfile" 
                :loading="authStore.loading"
              >
                保存更改
              </el-button>
              <el-button @click="resetProfile">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-row style="margin-top: 20px;">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>修改密码</span>
          </template>
          <el-form 
            ref="passwordFormRef"
            :model="passwordForm" 
            :rules="passwordRules"
            label-width="100px" 
            style="max-width: 500px;"
          >
            <el-form-item label="当前密码" prop="current">
              <el-input 
                v-model="passwordForm.current" 
                type="password" 
                placeholder="请输入当前密码"
                show-password
              >
                <template #prefix>
                  <el-icon><Lock /></el-icon>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="新密码" prop="new">
              <el-input 
                v-model="passwordForm.new" 
                type="password" 
                placeholder="请输入新密码"
                show-password
              >
                <template #prefix>
                  <el-icon><Lock /></el-icon>
                </template>
              </el-input>
              <div class="password-strength">
                <span :class="passwordStrengthClass">{{ passwordStrengthText }}</span>
              </div>
            </el-form-item>
            <el-form-item label="确认密码" prop="confirm">
              <el-input 
                v-model="passwordForm.confirm" 
                type="password" 
                placeholder="请再次输入新密码"
                show-password
              >
                <template #prefix>
                  <el-icon><Lock /></el-icon>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item>
              <el-button 
                type="primary" 
                @click="changePassword" 
                :loading="authStore.loading"
              >
                修改密码
              </el-button>
              <el-button @click="resetPasswordForm">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import { ElMessage, ElNotification, type FormInstance, type FormRules, type UploadProps } from 'element-plus'
import { User, Message, Lock } from '@element-plus/icons-vue'

const authStore = useAuthStore()

// 表单引用
const profileFormRef = ref<FormInstance>()
const passwordFormRef = ref<FormInstance>()
const uploadRef = ref()

// 头像上传相关
const avatarUploading = ref(false)
const uploadAction = '/api/v1/auth/avatar'
const uploadHeaders = computed(() => ({
  'Authorization': `Bearer ${authStore.token}`
}))

// 用户资料表单
const profile = reactive({
  username: '',
  email: '',
  fullName: '',
  bio: '',
  role: '',
  avatarUrl: '',
  createdAt: '',
  lastLogin: '',
  isActive: true
})

// 密码表单
const passwordForm = reactive({
  current: '',
  new: '',
  confirm: ''
})

// 表单验证规则
const profileRules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  fullName: [
    { max: 50, message: '姓名长度不能超过50个字符', trigger: 'blur' }
  ],
  bio: [
    { max: 500, message: '个人简介长度不能超过500个字符', trigger: 'blur' }
  ]
}

const passwordRules: FormRules = {
  current: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  new: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少8位', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value && value === passwordForm.current) {
          callback(new Error('新密码不能与当前密码相同'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  confirm: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value && value !== passwordForm.new) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 密码强度检测
const passwordStrength = computed(() => {
  const password = passwordForm.new
  if (!password) return 0
  
  let score = 0
  
  // 长度检测
  if (password.length >= 8) score += 1
  if (password.length >= 12) score += 1
  
  // 字符类型检测
  if (/[a-z]/.test(password)) score += 1
  if (/[A-Z]/.test(password)) score += 1
  if (/[0-9]/.test(password)) score += 1
  if (/[^\w\s]/.test(password)) score += 1
  
  return Math.min(score, 5)
})

const passwordStrengthText = computed(() => {
  const strength = passwordStrength.value
  if (strength === 0) return ''
  if (strength <= 2) return '弱'
  if (strength <= 3) return '中'
  if (strength <= 4) return '强'
  return '非常强'
})

const passwordStrengthClass = computed(() => {
  const strength = passwordStrength.value
  if (strength === 0) return ''
  if (strength <= 2) return 'weak'
  if (strength <= 3) return 'medium'
  if (strength <= 4) return 'strong'
  return 'very-strong'
})

// 加载用户数据
const loadUserData = () => {
  if (authStore.user) {
    profile.username = authStore.user.username
    profile.email = authStore.user.email
    profile.fullName = (authStore.user as any).full_name || ''
    profile.bio = (authStore.user as any).bio || ''
    profile.role = authStore.user.role === 'admin' ? '管理员' : '普通用户'
    profile.avatarUrl = (authStore.user as any).avatar_url || ''
    profile.createdAt = new Date(authStore.user.created_at).toLocaleString('zh-CN')
    profile.lastLogin = (authStore.user as any).last_login ? new Date((authStore.user as any).last_login).toLocaleString('zh-CN') : ''
    profile.isActive = authStore.user.is_active
  }
}

// 保存用户资料
const saveProfile = async () => {
  if (!profileFormRef.value) return
  
  try {
    const valid = await profileFormRef.value.validate()
    if (!valid) return
    
    const success = await authStore.updateProfile({
      email: profile.email,
      full_name: profile.fullName,
      bio: profile.bio
    } as any)
    
    if (success) {
      loadUserData() // 重新加载数据
      ElNotification({
        title: '成功',
        message: '个人信息更新成功',
        type: 'success'
      })
    }
  } catch (error) {
    console.error('更新个人信息失败:', error)
  }
}

// 重置用户资料表单
const resetProfile = () => {
  loadUserData()
  profileFormRef.value?.clearValidate()
}

// 修改密码
const changePassword = async () => {
  if (!passwordFormRef.value) return
  
  try {
    const valid = await passwordFormRef.value.validate()
    if (!valid) return
    
    const success = await authStore.changePassword(passwordForm.current, passwordForm.new)
    
    if (success) {
      resetPasswordForm()
      ElNotification({
        title: '成功',
        message: '密码修改成功',
        type: 'success'
      })
    }
  } catch (error) {
    console.error('修改密码失败:', error)
  }
}

// 重置密码表单
const resetPasswordForm = () => {
  passwordForm.current = ''
  passwordForm.new = ''
  passwordForm.confirm = ''
  passwordFormRef.value?.clearValidate()
}

// 头像上传前验证
const beforeAvatarUpload: UploadProps['beforeUpload'] = (file) => {
  const isJPGOrPNG = file.type === 'image/jpeg' || file.type === 'image/png'
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isJPGOrPNG) {
    ElMessage.error('只能上传 JPG/PNG 格式的图片!')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB!')
    return false
  }
  
  avatarUploading.value = true
  return true
}

// 头像上传成功
const handleAvatarSuccess: UploadProps['onSuccess'] = (response) => {
  avatarUploading.value = false
  
  if (response.success && response.data?.avatar_url) {
    profile.avatarUrl = response.data.avatar_url
    // 更新store中的用户信息
    if (authStore.user) {
      (authStore.user as any).avatar_url = response.data.avatar_url
    }
    ElMessage.success('头像上传成功')
  } else {
    ElMessage.error('头像上传失败')
  }
}

// 头像上传失败
const handleAvatarError: UploadProps['onError'] = () => {
  avatarUploading.value = false
  ElMessage.error('头像上传失败，请稍后重试')
}

onMounted(() => {
  loadUserData()
})
</script>

<style scoped>
.profile {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 4px 0;
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.page-header p {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.avatar-section {
  text-align: center;
  padding: 20px;
}

.avatar-tip {
  margin-top: 15px;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

.avatar-tip p {
  margin: 2px 0;
}

.stats-list {
  padding: 0;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-label {
  color: #666;
  font-size: 14px;
}

.stat-value {
  font-weight: 500;
  color: #333;
  font-size: 14px;
}

.password-strength {
  margin-top: 5px;
  font-size: 12px;
}

.password-strength .weak {
  color: #f56c6c;
}

.password-strength .medium {
  color: #e6a23c;
}

.password-strength .strong {
  color: #409eff;
}

.password-strength .very-strong {
  color: #67c23a;
}

/* 表单样式优化 */
.el-form-item {
  margin-bottom: 20px;
}

.el-input .el-input__inner {
  transition: all 0.3s ease;
}

.el-input:hover .el-input__inner {
  border-color: #c0c4cc;
}

.el-input.is-focus .el-input__inner {
  border-color: #409eff;
}

/* 卡片样式 */
.el-card {
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.el-card__header {
  padding: 18px 20px;
  border-bottom: 1px solid #f0f0f0;
  font-weight: 600;
  color: #303133;
}

.el-card__body {
  padding: 20px;
}

/* 按钮样式 */
.el-button {
  transition: all 0.3s ease;
}

.el-button:hover {
  transform: translateY(-1px);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .el-row {
    margin: 0 !important;
  }
  
  .el-col {
    padding: 0 10px !important;
  }
  
  .profile {
    padding: 10px;
  }
  
  .page-header h2 {
    font-size: 20px;
  }
  
  .el-form {
    max-width: 100% !important;
  }
}
</style>