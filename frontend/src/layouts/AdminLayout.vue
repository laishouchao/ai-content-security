<template>
  <div class="admin-layout">
    <el-container>
      <!-- 侧边栏 -->
      <el-aside :width="collapsed ? '64px' : '200px'">
        <div class="logo">
          <el-icon v-if="collapsed" size="24"><Monitor /></el-icon>
          <template v-else>
            <el-icon size="24"><Monitor /></el-icon>
            <span>AI内容安全</span>
          </template>
        </div>
        
        <el-menu
          :default-active="activeMenu"
          :collapse="collapsed"
          :unique-opened="true"
          class="sidebar-menu"
          background-color="#001529"
          text-color="#fff"
          active-text-color="#1890ff"
          router
        >
          <el-menu-item 
            v-for="item in menuItems" 
            :key="item.path"
            :index="item.path"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主内容区域 -->
      <el-container>
        <!-- 顶部导航栏 -->
        <el-header>
          <div class="header-left">
            <el-button 
              type="text" 
              @click="toggleSidebar"
              class="sidebar-toggle"
            >
              <el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon>
            </el-button>
            
            <el-breadcrumb separator="/">
              <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
              <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
            </el-breadcrumb>
          </div>
          
          <div class="header-right">
            <!-- WebSocket连接状态 -->
            <div class="connection-status">
              <el-tooltip 
                :content="wsStore.connectionStatusText" 
                placement="bottom"
              >
                <el-badge 
                  :type="wsStore.connectionStatusType as 'info' | 'warning' | 'success' | 'danger'"
                  is-dot
                  class="status-badge"
                >
                  <el-icon><Connection /></el-icon>
                </el-badge>
              </el-tooltip>
            </div>
            
            <!-- 通知 -->
            <el-badge :value="12" class="notification-badge">
              <el-button type="text">
                <el-icon><Bell /></el-icon>
              </el-button>
            </el-badge>
            
            <!-- 用户菜单 -->
            <el-dropdown @command="handleUserCommand">
              <div class="user-info">
                <el-avatar :size="32" :src="authStore.userAvatar">
                  {{ authStore.userName.charAt(0) || 'U' }}
                </el-avatar>
                <span class="username">{{ authStore.userName || '用户' }}</span>
                <el-icon><ArrowDown /></el-icon>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">
                    <el-icon><User /></el-icon>
                    个人资料
                  </el-dropdown-item>
                  <el-dropdown-item command="logout" divided>
                    <el-icon><SwitchButton /></el-icon>
                    退出登录
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>

        <!-- 主内容 -->
        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useWebSocketStore } from '@/stores/websocket'
import { ElMessage } from 'element-plus'
import {
  DataBoard,
  List,
  Plus,
  User,
  Setting,
  Expand,
  Fold,
  Bell,
  ArrowDown,
  SwitchButton,
  Monitor,
  Connection
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const wsStore = useWebSocketStore()

// 响应式状态
const collapsed = ref(false)

// 计算属性
const activeMenu = computed(() => route.path)
const currentPageTitle = computed(() => route.meta.title || '未知页面')

// 菜单项（根据用户权限显示）
const menuItems = computed(() => {
  const items = [
    { path: '/dashboard', title: '仪表板', icon: 'DataBoard' },
    { path: '/tasks', title: '任务列表', icon: 'List' },
    { path: '/tasks/create', title: '创建任务', icon: 'Plus' },
    { path: '/domains', title: '域名库', icon: 'Link' },
    { path: '/profile', title: '个人资料', icon: 'User' }
  ]
  
  // 只有管理员才能看到系统设置
  if (authStore.isAdmin) {
    items.push({ path: '/settings', title: '系统设置', icon: 'Setting' })
  }
  
  return items
})

// 方法
const toggleSidebar = () => {
  collapsed.value = !collapsed.value
}

const handleUserCommand = async (command: string) => {
  switch (command) {
    case 'profile':
      router.push('/profile')
      break
    case 'logout':
      authStore.logout()
      router.push('/login')
      break
  }
}

// 组件挂载时初始化认证状态和WebSocket连接
onMounted(() => {
  authStore.initAuth()
  
  // 认证成功后连接WebSocket
  if (authStore.isAuthenticated) {
    wsStore.connect()
  }
})

// 组件卸载时断开WebSocket连接
onUnmounted(() => {
  wsStore.disconnect()
})
</script>

<style scoped>
.admin-layout {
  height: 100vh;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #002140;
  color: white;
  font-size: 16px;
  font-weight: bold;
  gap: 8px;
}

.logo .el-icon {
  color: #1890ff;
}

.sidebar-menu {
  border-right: none;
}

.header-left {
  display: flex;
  align-items: center;
}

.sidebar-toggle {
  margin-right: 16px;
  font-size: 16px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.notification-badge {
  cursor: pointer;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: #f5f5f5;
}

.username {
  color: #333;
  font-size: 14px;
}
</style>