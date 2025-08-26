<template>
  <div class="register-container">
    <el-card class="register-card" shadow="always">
      <template #header>
        <div class="card-header">
          <h2>创建账户</h2>
          <p>注册新的AI内容安全检测系统账户</p>
        </div>
      </template>

      <el-form
        ref="registerFormRef"
        :model="registerForm"
        :rules="rules"
        label-width="80px"
        @submit.prevent="handleRegister"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="registerForm.username"
            placeholder="请输入用户名"
            size="large"
          >
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input
            v-model="registerForm.email"
            placeholder="请输入邮箱地址"
            size="large"
          >
            <template #prefix>
              <el-icon><Message /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            size="large"
            show-password
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="真实姓名" prop="realName">
          <el-input
            v-model="registerForm.realName"
            placeholder="请输入真实姓名"
            size="large"
          >
            <template #prefix>
              <el-icon><UserFilled /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="组织机构" prop="organization">
          <el-input
            v-model="registerForm.organization"
            placeholder="请输入组织机构名称"
            size="large"
          >
            <template #prefix>
              <el-icon><OfficeBuilding /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-checkbox v-model="registerForm.agreeToTerms">
            我已阅读并同意
            <el-link type="primary" @click="showTerms">《用户协议》</el-link>
            和
            <el-link type="primary" @click="showPrivacy">《隐私政策》</el-link>
          </el-checkbox>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            :loading="loading"
            @click="handleRegister"
          >
            注册账户
          </el-button>
        </el-form-item>

        <el-form-item>
          <div class="login-link">
            已有账户？
            <el-link type="primary" @click="goToLogin">
              立即登录
            </el-link>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 用户协议对话框 -->
    <el-dialog v-model="termsVisible" title="用户协议" width="60%">
      <div class="terms-content">
        <h3>1. 服务条款</h3>
        <p>本系统提供AI驱动的域名内容安全检测服务，用户在使用本服务时应遵守相关法律法规。</p>
        
        <h3>2. 用户责任</h3>
        <p>用户应确保提供的信息真实有效，不得利用本系统进行违法违规活动。</p>
        
        <h3>3. 服务限制</h3>
        <p>本系统对用户的使用频率和数据量可能设置合理限制，以确保服务质量。</p>
        
        <h3>4. 免责声明</h3>
        <p>本系统提供的检测结果仅供参考，最终的合规判断应由用户自行负责。</p>
      </div>
      <template #footer>
        <el-button @click="termsVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 隐私政策对话框 -->
    <el-dialog v-model="privacyVisible" title="隐私政策" width="60%">
      <div class="privacy-content">
        <h3>1. 信息收集</h3>
        <p>我们仅收集用户注册和使用服务所必需的信息。</p>
        
        <h3>2. 信息使用</h3>
        <p>收集的信息仅用于提供服务、改进产品和维护安全。</p>
        
        <h3>3. 信息保护</h3>
        <p>我们采取适当的技术和管理措施保护用户信息安全。</p>
        
        <h3>4. 信息共享</h3>
        <p>除法律要求外，我们不会向第三方共享用户个人信息。</p>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Message, Lock, UserFilled, OfficeBuilding } from '@element-plus/icons-vue'

const router = useRouter()
const registerFormRef = ref()
const loading = ref(false)
const termsVisible = ref(false)
const privacyVisible = ref(false)

// 注册表单数据
const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  realName: '',
  organization: '',
  agreeToTerms: false
})

// 表单验证规则
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度为3-20个字符', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: '用户名只能包含字母、数字、下划线和横线', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码长度不能少于8位', trigger: 'blur' },
    { 
      pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d@$!%*?&]{8,}$/, 
      message: '密码须包含大小写字母和数字', 
      trigger: 'blur' 
    }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule: any, value: any, callback: any) => {
        if (value !== registerForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  realName: [
    { required: true, message: '请输入真实姓名', trigger: 'blur' },
    { min: 2, max: 20, message: '姓名长度为2-20个字符', trigger: 'blur' }
  ],
  organization: [
    { required: true, message: '请输入组织机构名称', trigger: 'blur' }
  ]
}

// 处理注册
const handleRegister = async () => {
  if (!registerForm.agreeToTerms) {
    ElMessage.warning('请阅读并同意用户协议和隐私政策')
    return
  }

  try {
    await registerFormRef.value.validate()
    
    loading.value = true
    
    // TODO: 调用注册API
    await new Promise(resolve => setTimeout(resolve, 2000)) // 模拟API调用
    
    ElMessage.success('注册成功！请登录您的账户')
    
    // 跳转到登录页面
    router.push('/login')
  } catch (error) {
    if (error === 'validation failed') {
      ElMessage.error('请检查输入信息')
    } else {
      ElMessage.error('注册失败，请稍后重试')
    }
  } finally {
    loading.value = false
  }
}

// 跳转到登录页面
const goToLogin = () => {
  router.push('/login')
}

// 显示用户协议
const showTerms = () => {
  termsVisible.value = true
}

// 显示隐私政策
const showPrivacy = () => {
  privacyVisible.value = true
}
</script>

<style scoped>
.register-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.register-card {
  width: 100%;
  max-width: 500px;
  border-radius: 16px;
}

.card-header {
  text-align: center;
  margin-bottom: 20px;
}

.card-header h2 {
  margin: 0 0 8px 0;
  color: #303133;
  font-size: 24px;
  font-weight: 600;
}

.card-header p {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.login-link {
  text-align: center;
  font-size: 14px;
  color: #909399;
}

.terms-content,
.privacy-content {
  max-height: 400px;
  overflow-y: auto;
  padding: 0 10px;
}

.terms-content h3,
.privacy-content h3 {
  color: #409eff;
  margin-top: 20px;
  margin-bottom: 10px;
}

.terms-content p,
.privacy-content p {
  line-height: 1.6;
  margin-bottom: 10px;
  color: #606266;
}

:deep(.el-card__header) {
  padding: 30px 30px 0 30px;
}

:deep(.el-card__body) {
  padding: 0 30px 30px 30px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
}
</style>