<template>
  <el-container class="app-layout">
    <!-- 侧边栏 -->
    <el-aside 
      :width="sidebarCollapsed ? '64px' : '250px'"
      class="app-sidebar"
    >
      <div class="sidebar-header">
        <img 
          v-if="!sidebarCollapsed" 
          src="/logo.svg" 
          alt="Logo" 
          class="logo"
        >
        <h1 v-if="!sidebarCollapsed" class="app-title">
          AI内容安全
        </h1>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        :collapse="sidebarCollapsed"
        :unique-opened="true"
        router
        class="sidebar-menu"
      >
        <template v-for="item in menuItems" :key="item.id">
          <el-sub-menu 
            v-if="item.children && item.children.length > 0"
            :index="item.path || item.id"
          >
            <template #title>
              <el-icon v-if="item.icon">
                <component :is="item.icon" />
              </el-icon>
              <span>{{ item.title }}</span>
            </template>
            <el-menu-item
              v-for="child in item.children"
              :key="child.id"
              :index="child.path"
            >
              <el-icon v-if="child.icon">
                <component :is="child.icon" />
              </el-icon>
              <span>{{ child.title }}</span>
            </el-menu-item>
          </el-sub-menu>
          
          <el-menu-item 
            v-else
            :index="item.path"
          >
            <el-icon v-if="item.icon">
              <component :is="item.icon" />
            </el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <!-- 主要内容区域 -->
    <el-container class="app-main">
      <!-- 顶部导航栏 -->
      <el-header class="app-header">
        <div class="header-left">
          <el-button
            type="text"
            @click="toggleSidebar"
            class="sidebar-toggle"
          >
            <el-icon><Menu /></el-icon>
          </el-button>
          
          <!-- 面包屑导航 -->
          <el-breadcrumb 
            v-if="showBreadcrumb && breadcrumbItems.length > 0"
            separator="/"
            class="breadcrumb"
          >
            <el-breadcrumb-item
              v-for="item in breadcrumbItems"
              :key="item.path"
              :to="item.path"
            >
              {{ item.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <div class="header-right">
          <!-- WebSocket连接状态 -->
          <WebSocketStatus 
            :show-details="true" 
            :show-reconnect="true" 
            class="websocket-status-widget"
          />
          
          <!-- 通知 -->
          <el-badge :value="unreadNotifications" class="notification-badge">
            <el-button type="text" @click="showNotifications">
              <el-icon><Bell /></el-icon>
            </el-button>
          </el-badge>
          
          <!-- 用户下拉菜单 -->
          <el-dropdown @command="handleUserCommand">
            <div class="user-info">
              <el-avatar 
                :src="userStore.user?.avatar_url" 
                :size="32"
              >
                {{ userStore.user?.username?.charAt(0).toUpperCase() }}
              </el-avatar>
              <span v-if="!sidebarCollapsed" class="username">
                {{ userStore.user?.username }}
              </span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>
                  个人资料
                </el-dropdown-item>
                <el-dropdown-item command="settings" v-if="userStore.isAdmin">
                  <el-icon><Setting /></el-icon>
                  系统设置
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容区域 -->
      <el-main class="app-content">
        <router-view v-slot="{ Component, route }">
          <transition name="fade-transform" mode="out-in">
            <keep-alive :include="cachedViews">
              <component :is="Component" :key="route.path" />
            </keep-alive>
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useWebSocketStore } from '@/stores/websocket'
import WebSocketStatus from '@/components/WebSocketStatus.vue'
import type { MenuItem, BreadcrumbItem } from '@/types'
import {
  Menu,
  List,
  User,
  Setting,
  Bell,
  Connection,
  ArrowDown,
  SwitchButton,
  Odometer
} from '@element-plus/icons-vue'

// Stores
const userStore = useAuthStore()
const wsStore = useWebSocketStore()
const route = useRoute()
const router = useRouter()

// 响应式状态
const sidebarCollapsed = ref(false)
const showBreadcrumb = ref(true)
const unreadNotifications = ref(0)
const cachedViews = ref<string[]>([])

// 菜单项配置
const menuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = [
    {
      id: 'dashboard',
      title: '仪表板',
      icon: 'Odometer',
      path: '/dashboard'
    },
    {
      id: 'tasks',
      title: '任务管理',
      icon: 'List',
      path: '/tasks',
      children: [
        {
          id: 'task-list',
          title: '任务列表',
          path: '/tasks'
        },
        {
          id: 'create-task',
          title: '创建任务',
          path: '/tasks/create'
        }
      ]
    },
    {
      id: 'user',
      title: '用户中心',
      icon: 'User',
      path: '/user/profile'
    }
  ]
  
  // 管理员菜单
  if (userStore.isAdmin) {
    items.push({
      id: 'settings',
      title: '系统设置',
      icon: 'Setting',
      path: '/settings'
    })
  }
  
  return items
})

// 当前激活的菜单项
const activeMenu = computed(() => {
  const { meta, path } = route
  if (meta.activeMenu) {
    return meta.activeMenu as string
  }
  return path
})

// 面包屑导航
const breadcrumbItems = computed<BreadcrumbItem[]>(() => {
  const matched = route.matched.filter(item => item.meta.title)
  const items: BreadcrumbItem[] = []
  
  matched.forEach((item, index) => {
    items.push({
      title: item.meta.title as string,
      path: index === matched.length - 1 ? undefined : item.path
    })
  })
  
  return items
})

// 切换侧边栏
const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

// 处理用户下拉菜单命令
const handleUserCommand = (command: string) => {
  switch (command) {
    case 'profile':
      router.push('/user/profile')
      break
    case 'settings':
      router.push('/settings')
      break
    case 'logout':
      userStore.logout()
      break
  }
}

// 显示通知
const showNotifications = () => {
  // TODO: 实现通知弹窗
  console.log('显示通知')
}

// 监听路由变化，更新缓存视图
watch(
  () => route.name,
  (newName) => {
    if (newName && !route.meta.noCache) {
      const name = newName as string
      if (!cachedViews.value.includes(name)) {
        cachedViews.value.push(name)
      }
    }
  }
)

// 组件挂载时启动WebSocket连接
wsStore.connect()
wsStore.enableAutoReconnect()
</script>

<style scoped>
.app-layout {
  height: 100vh;
}

.app-sidebar {
  background-color: #304156;
  transition: width 0.3s;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  padding: 16px;
  background-color: #263445;
  height: 64px;
  box-sizing: border-box;
}

.logo {
  width: 32px;
  height: 32px;
  margin-right: 12px;
}

.app-title {
  color: white;
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.sidebar-menu {
  border: none;
  background-color: #304156;
}

.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  color: #bfcbd9;
  border-bottom: none;
}

.sidebar-menu :deep(.el-menu-item:hover),
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background-color: #263445 !important;
  color: #409eff;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background-color: #409eff !important;
  color: white;
}

.app-main {
  background-color: #f0f2f5;
}

.app-header {
  background-color: white;
  border-bottom: 1px solid #e8eaec;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.sidebar-toggle {
  font-size: 18px;
  color: #5a6169;
}

.breadcrumb {
  font-size: 14px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.websocket-status-widget {
  display: flex;
  align-items: center;
}

.status-badge :deep(.el-badge__content) {
  border: 2px solid white;
}

.notification-badge :deep(.el-badge__content) {
  background-color: #f56c6c;
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
  background-color: #f5f7fa;
}

.username {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.app-content {
  padding: 20px;
}

/* 路由过渡动画 */
.fade-transform-enter-active,
.fade-transform-leave-active {
  transition: all 0.3s;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(-30px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
</style>