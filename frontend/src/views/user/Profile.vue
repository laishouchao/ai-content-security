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
            <el-avatar :size="120" src="/avatar.jpg">
              Admin
            </el-avatar>
            <el-button type="primary" size="small" style="margin-top: 16px;">
              更换头像
            </el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card>
          <template #header>
            <span>基本信息</span>
          </template>
          <el-form :model="profile" label-width="100px">
            <el-form-item label="用户名">
              <el-input v-model="profile.username" disabled />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="profile.email" />
            </el-form-item>
            <el-form-item label="姓名">
              <el-input v-model="profile.fullName" />
            </el-form-item>
            <el-form-item label="角色">
              <el-tag type="primary">{{ profile.role }}</el-tag>
            </el-form-item>
            <el-form-item label="注册时间">
              <span>{{ profile.createdAt }}</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveProfile" :loading="authStore.loading">
                保存更改
              </el-button>
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
          <el-form :model="passwordForm" label-width="100px" style="max-width: 400px;">
            <el-form-item label="当前密码">
              <el-input v-model="passwordForm.current" type="password" />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="passwordForm.new" type="password" />
            </el-form-item>
            <el-form-item label="确认密码">
              <el-input v-model="passwordForm.confirm" type="password" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="changePassword" :loading="authStore.loading">
                修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()

const profile = reactive({
  username: '',
  email: '',
  fullName: '',
  role: '',
  createdAt: ''
})

const passwordForm = reactive({
  current: '',
  new: '',
  confirm: ''
})

// 加载用户数据
const loadUserData = () => {
  if (authStore.user) {
    profile.username = authStore.user.username
    profile.email = authStore.user.email
    profile.fullName = authStore.user.full_name || ''
    profile.role = authStore.user.role === 'admin' ? '管理员' : '普通用户'
    profile.createdAt = new Date(authStore.user.created_at).toLocaleString('zh-CN')
  }
}

// 保存更改
const saveProfile = async () => {
  const success = await authStore.updateProfile({
    email: profile.email,
    full_name: profile.fullName
  })
  
  if (success) {
    loadUserData() // 重新加载数据
  }
}

// 修改密码
const changePassword = async () => {
  if (passwordForm.new !== passwordForm.confirm) {
    ElMessage.error('两次输入的密码不一致')
    return
  }
  
  const success = await authStore.changePassword(passwordForm.current, passwordForm.new)
  
  if (success) {
    // 清空表单
    passwordForm.current = ''
    passwordForm.new = ''
    passwordForm.confirm = ''
  }
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
</style>