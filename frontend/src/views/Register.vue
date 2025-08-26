<template>
  <div class="register-page">
    <div class="register-container">
      <div class="register-form">
        <div class="form-header">
          <h2>用户注册</h2>
          <p>创建您的账户，开始使用AI内容安全监控系统</p>
        </div>

        <el-form
          ref="registerFormRef"
          :model="registerForm"
          :rules="registerRules"
          label-width="0"
          @submit.prevent="handleRegister"
        >
          <el-form-item prop="fullName">
            <el-input
              v-model="registerForm.fullName"
              placeholder="请输入真实姓名"
              size="large"
              prefix-icon="User"
            />
          </el-form-item>

          <el-form-item prop="username">
            <el-input
              v-model="registerForm.username"
              placeholder="请输入用户名"
              size="large"
              prefix-icon="Avatar"
            />
          </el-form-item>

          <el-form-item prop="email">
            <el-input
              v-model="registerForm.email"
              placeholder="请输入邮箱地址"
              size="large"
              prefix-icon="Message"
              type="email"
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="registerForm.password"
              placeholder="请输入密码"
              size="large"
              prefix-icon="Lock"
              type="password"
              show-password
            />
          </el-form-item>

          <el-form-item prop="confirmPassword">
            <el-input
              v-model="registerForm.confirmPassword"
              placeholder="请确认密码"
              size="large"
              prefix-icon="Lock"
              type="password"
              show-password
            />
          </el-form-item>

          <el-form-item>
            <el-checkbox v-model="agreeToTerms" size="large">
              我已阅读并同意
              <el-link type="primary" @click="showTerms">用户协议</el-link>
              和
              <el-link type="primary" @click="showPrivacy">隐私政策</el-link>
            </el-checkbox>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              @click="handleRegister"
              :loading="authStore.loading"
              :disabled="!agreeToTerms"
              class="register-button"
            >
              注册账户
            </el-button>
          </el-form-item>

          <div class="form-footer">
            <span>已有账户？</span>
            <el-link type="primary" @click="goToLogin">立即登录</el-link>
          </div>
        </el-form>
      </div>
      
      <div class="register-image">
        <div class="image-content">
          <el-icon size="120"><UserFilled /></el-icon>
          <h3>加入我们</h3>
          <p>体验先进的AI内容安全监控解决方案</p>
          <ul class="features">
            <li>✨ 智能内容检测</li>
            <li>🔍 全面域名扫描</li>
            <li>📊 实时监控报告</li>
            <li>🛡️ 安全合规保障</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 用户协议对话框 -->
    <el-dialog v-model="termsVisible" title="用户协议" width="60%">
      <div class="terms-content">
        <h4>1. 服务条款</h4>
        <p>欢迎使用AI内容安全监控系统。通过注册和使用本服务，您同意遵守以下条款。</p>
        
        <h4>2. 用户责任</h4>
        <p>您承诺提供真实、准确的注册信息，并对您的账户安全负责。</p>
        
        <h4>3. 服务使用</h4>
        <p>本系统仅用于合法的内容安全监控目的，禁止用于非法活动。</p>
        
        <h4>4. 数据安全</h4>
        <p>我们承诺保护您的数据安全，不会未经授权泄露您的个人信息。</p>
      </div>
      <template #footer>
        <el-button @click="termsVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 隐私政策对话框 -->
    <el-dialog v-model="privacyVisible" title="隐私政策" width="60%">
      <div class="privacy-content">
        <h4>1. 信息收集</h4>
        <p>我们收集您提供的注册信息和使用系统过程中产生的数据。</p>
        
        <h4>2. 信息使用</h4>
        <p>收集的信息仅用于提供服务、改进产品和保障系统安全。</p>
        
        <h4>3. 信息保护</h4>
        <p>我们采用行业标准的安全措施保护您的个人信息。</p>
        
        <h4>4. 信息共享</h4>
        <p>除法律要求外，我们不会向第三方分享您的个人信息。</p>
      </div>
      <template #footer>
        <el-button @click="privacyVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Avatar, Message, Lock, UserFilled } from '@element-plus/icons-vue'

const router = useRouter()
const authStore = useAuthStore()

// 响应式状态
const registerFormRef = ref<FormInstance>()
const agreeToTerms = ref(false)
const termsVisible = ref(false)
const privacyVisible = ref(false)

// 注册表单
const registerForm = reactive({
  fullName: '',
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

// 表单验证规则
const registerRules: FormRules = {
  fullName: [
    { required: true, message: '请输入真实姓名', trigger: 'blur' },
    { min: 2, max: 20, message: '姓名长度在 2 到 20 个字符', trigger: 'blur' }
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度在 3 到 20 个字符', trigger: 'blur' },
    { 
      pattern: /^[a-zA-Z0-9_]+$/, 
      message: '用户名只能包含字母、数字和下划线', 
      trigger: 'blur' 
    }
  ],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度在 6 到 20 个字符', trigger: 'blur' },
    {
      pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
      message: '密码必须包含大小写字母和数字',
      trigger: 'blur'
    }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== registerForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 方法
const handleRegister = async () => {
  if (!registerFormRef.value) return
  
  try {
    const valid = await registerFormRef.value.validate()
    if (!valid) return
    
    if (!agreeToTerms.value) {
      ElMessage.warning('请先同意用户协议和隐私政策')
      return
    }
    
    const success = await authStore.register(registerForm)
    if (success) {
      router.push('/dashboard')
    }
  } catch (error) {
    console.error('注册失败:', error)
  }
}

const goToLogin = () => {
  router.push('/login')
}

const showTerms = () => {
  termsVisible.value = true
}

const showPrivacy = () => {
  privacyVisible.value = true
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.register-container {
  display: flex;
  max-width: 1000px;
  width: 100%;
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.register-form {
  flex: 1;
  padding: 40px;
  max-width: 400px;
}

.form-header {
  text-align: center;
  margin-bottom: 30px;
}

.form-header h2 {
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 600;
  color: #333;
}

.form-header p {
  margin: 0;
  color: #666;
  font-size: 14px;
  line-height: 1.5;
}

.register-button {
  width: 100%;
  height: 44px;
  font-size: 16px;
  font-weight: 600;
}

.form-footer {
  text-align: center;
  margin-top: 20px;
  color: #666;
  font-size: 14px;
}

.form-footer .el-link {
  margin-left: 4px;
}

.register-image {
  flex: 1;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  padding: 40px;
}

.image-content {
  text-align: center;
  max-width: 300px;
}

.image-content .el-icon {
  margin-bottom: 20px;
  opacity: 0.9;
}

.image-content h3 {
  margin: 0 0 16px 0;
  font-size: 24px;
  font-weight: 600;
}

.image-content p {
  margin: 0 0 30px 0;
  font-size: 16px;
  opacity: 0.9;
  line-height: 1.5;
}

.features {
  list-style: none;
  padding: 0;
  margin: 0;
  text-align: left;
}

.features li {
  padding: 8px 0;
  font-size: 14px;
  opacity: 0.9;
}

.terms-content,
.privacy-content {
  max-height: 400px;
  overflow-y: auto;
  padding: 0 20px;
}

.terms-content h4,
.privacy-content h4 {
  color: #333;
  margin-top: 20px;
  margin-bottom: 10px;
}

.terms-content p,
.privacy-content p {
  color: #666;
  line-height: 1.6;
  margin-bottom: 15px;
}

:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-input__wrapper) {
  border-radius: 8px;
}

:deep(.el-checkbox__label) {
  font-size: 14px;
  color: #666;
}

@media (max-width: 768px) {
  .register-container {
    flex-direction: column;
  }
  
  .register-image {
    order: -1;
    padding: 30px 20px;
  }
  
  .register-form {
    padding: 30px 20px;
  }
  
  .image-content {
    max-width: none;
  }
  
  .features {
    text-align: center;
  }
}
</style>