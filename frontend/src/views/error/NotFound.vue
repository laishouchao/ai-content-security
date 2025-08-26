<template>
  <div class="not-found">
    <div class="error-container">
      <div class="error-content">
        <div class="error-code">404</div>
        <div class="error-title">页面未找到</div>
        <div class="error-description">
          抱歉，您访问的页面不存在或已被移除。
        </div>
        <div class="error-actions">
          <el-button type="primary" @click="goHome">
            <el-icon><House /></el-icon>
            返回首页
          </el-button>
          <el-button @click="goBack">
            <el-icon><ArrowLeft /></el-icon>
            返回上页
          </el-button>
        </div>
      </div>
      <div class="error-image">
        <el-icon><Warning /></el-icon>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { House, ArrowLeft, Warning } from '@element-plus/icons-vue'

const router = useRouter()

const goHome = () => {
  router.push('/')
}

const goBack = () => {
  router.back()
}
</script>

<style scoped>
.not-found {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f5f5;
}

.error-container {
  display: flex;
  align-items: center;
  max-width: 800px;
  padding: 40px;
}

.error-content {
  flex: 1;
  text-align: center;
}

.error-code {
  font-size: 120px;
  font-weight: bold;
  color: #409eff;
  line-height: 1;
  margin-bottom: 20px;
}

.error-title {
  font-size: 32px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}

.error-description {
  font-size: 16px;
  color: #666;
  margin-bottom: 32px;
  line-height: 1.6;
}

.error-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
}

.error-image {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 200px;
  color: #ddd;
}

@media (max-width: 768px) {
  .error-container {
    flex-direction: column;
    text-align: center;
  }
  
  .error-code {
    font-size: 80px;
  }
  
  .error-title {
    font-size: 24px;
  }
  
  .error-image {
    margin-top: 20px;
    font-size: 120px;
  }
}
</style>