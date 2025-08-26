import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 扩展路由元信息类型
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
    icon?: string
    hidden?: boolean
    roles?: string[]
  }
}

// 布局组件
const AdminLayout = () => import('@/layouts/AdminLayout.vue')

// 页面组件 
const Dashboard = () => import('@/views/Dashboard.vue')
const Login = () => import('@/views/Login.vue')
const Register = () => import('@/views/Register.vue')
const TaskList = () => import('@/views/task/TaskList.vue')
const TaskDetail = () => import('@/views/task/TaskDetail.vue')
const CreateTask = () => import('@/views/task/CreateTask.vue')
const Profile = () => import('@/views/user/Profile.vue')
const Settings = () => import('@/views/settings/Settings.vue')
const NotFound = () => import('@/views/error/NotFound.vue')

// 路由配置
const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: {
      title: '登录',
      requiresAuth: false
    }
  },
  {
    path: '/register',
    name: 'Register',
    component: Register,
    meta: {
      title: '用户注册',
      requiresAuth: false
    }
  },
  {
    path: '/',
    component: AdminLayout,
    redirect: '/dashboard',
    meta: {
      requiresAuth: true
    },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: Dashboard,
        meta: {
          title: '仪表板',
          icon: 'Dashboard'
        }
      },
      {
        path: 'tasks',
        name: 'TaskList',
        component: TaskList,
        meta: {
          title: '任务列表',
          icon: 'List'
        }
      },
      {
        path: 'tasks/create',
        name: 'CreateTask',
        component: CreateTask,
        meta: {
          title: '创建任务',
          icon: 'Plus'
        }
      },
      {
        path: 'tasks/:id',
        name: 'TaskDetail',
        component: TaskDetail,
        meta: {
          title: '任务详情',
          hidden: true
        }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: Profile,
        meta: {
          title: '个人资料',
          icon: 'User'
        }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: Settings,
        meta: {
          title: '系统设置',
          icon: 'Setting',
          roles: ['admin']
        }
      }
    ]
  },
  {
    path: '/404',
    name: 'NotFound',
    component: NotFound,
    meta: {
      title: '页面未找到'
    }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/404'
  }
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  
  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - AI内容安全监控` : 'AI内容安全监控'
  
  console.log(`🔗 导航到: ${to.path}, 需要认证: ${to.meta.requiresAuth !== false}`)
  
  // 检查是否需要认证
  if (to.meta.requiresAuth !== false) {
    // 检查是否已登录
    if (!authStore.isAuthenticated) {
      // 尝试从本地存储恢复用户信息
      console.log('🔍 尝试从本地存储恢复认证状态...')
      await authStore.checkAuth()
      
      if (!authStore.isAuthenticated) {
        console.log('❌ 未认证，重定向到登录页')
        // 未登录，跳转到登录页
        next({
          path: '/login',
          query: { redirect: to.fullPath }
        })
        return
      }
    }
    
    // 检查角色权限
    if (to.meta.roles && Array.isArray(to.meta.roles) && to.meta.roles.length > 0) {
      const userRole = authStore.user?.role
      // 修复：确保 userRole 存在后再调用 includes 方法
      const hasPermission = userRole && to.meta.roles.includes(userRole)
      
      if (!hasPermission) {
        console.log('⛔ 权限不足，重定向到仪表板')
        // 权限不足，跳转到仪表板
        next('/dashboard')
        return
      }
    }
    
    console.log('✅ 认证通过')
  } else {
    // 不需要认证的页面，如果已登录则跳转到仪表板
    if (authStore.isAuthenticated && to.path === '/login') {
      console.log('🏠 已登录，重定向到仪表板')
      next('/dashboard')
      return
    }
  }
  
  next()
})

// 路由错误处理
router.onError((error) => {
  console.error('路由错误:', error)
})

export default router