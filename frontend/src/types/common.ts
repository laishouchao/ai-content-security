// 通用工具类型
export type Nullable<T> = T | null
export type Optional<T> = T | undefined
export type RequiredKeys<T, K extends keyof T> = T & Required<Pick<T, K>>

// 组件Props类型
export interface BaseComponentProps {
  class?: string
  style?: string | Record<string, string>
}

// 表格列配置
export interface TableColumn {
  prop: string
  label: string
  width?: string | number
  minWidth?: string | number
  fixed?: boolean | 'left' | 'right'
  sortable?: boolean | 'custom'
  formatter?: (row: any, column: any, cellValue: any, index: number) => string
  showOverflowTooltip?: boolean
  align?: 'left' | 'center' | 'right'
  headerAlign?: 'left' | 'center' | 'right'
}

// 表单项配置
export interface FormItemConfig {
  prop: string
  label: string
  type: 'input' | 'password' | 'textarea' | 'select' | 'radio' | 'checkbox' | 'switch' | 'slider' | 'date' | 'number'
  placeholder?: string
  required?: boolean
  rules?: any[]
  options?: Array<{ label: string; value: any }>
  props?: Record<string, any>
  span?: number
  disabled?: boolean
  readonly?: boolean
}

// 路由元信息
export interface RouteMeta {
  title?: string
  icon?: string
  hidden?: boolean
  requiresAuth?: boolean
  roles?: string[]
  breadcrumb?: boolean
  activeMenu?: string
  noCache?: boolean
}

// 菜单项
export interface MenuItem {
  id: string
  title: string
  icon?: string
  path?: string
  children?: MenuItem[]
  hidden?: boolean
  roles?: string[]
  badge?: string | number
  external?: boolean
}

// 面包屑项
export interface BreadcrumbItem {
  title: string
  path?: string
  disabled?: boolean
}

// 分页配置
export interface PaginationConfig {
  currentPage: number
  pageSize: number
  total: number
  pageSizes?: number[]
  layout?: string
  background?: boolean
  small?: boolean
}

// 搜索表单配置
export interface SearchFormConfig {
  model: Record<string, any>
  items: FormItemConfig[]
  labelWidth?: string
  inline?: boolean
  size?: 'large' | 'default' | 'small'
}

// 对话框配置
export interface DialogConfig {
  visible: boolean
  title: string
  width?: string | number
  fullscreen?: boolean
  modal?: boolean
  closeOnClickModal?: boolean
  closeOnPressEscape?: boolean
  showClose?: boolean
  beforeClose?: (done: () => void) => void
}

// 抽屉配置
export interface DrawerConfig {
  visible: boolean
  title: string
  size?: string | number
  direction?: 'rtl' | 'ltr' | 'ttb' | 'btt'
  modal?: boolean
  closeOnClickModal?: boolean
  closeOnPressEscape?: boolean
  showClose?: boolean
  beforeClose?: (done: () => void) => void
}

// 标签页配置
export interface TabConfig {
  name: string
  label: string
  content?: any
  disabled?: boolean
  closable?: boolean
}

// 图表配置
export interface ChartConfig {
  title?: string
  type: 'line' | 'bar' | 'pie' | 'scatter' | 'radar' | 'gauge'
  data: any[]
  xAxis?: string
  yAxis?: string | string[]
  legend?: boolean
  tooltip?: boolean
  grid?: any
  color?: string[]
  height?: string | number
}

// 状态标签配置
export interface StatusTagConfig {
  status: string
  text: string
  type?: 'success' | 'info' | 'warning' | 'danger'
  effect?: 'dark' | 'light' | 'plain'
}

// 操作按钮配置
export interface ActionButton {
  text: string
  type?: 'primary' | 'success' | 'info' | 'warning' | 'danger'
  icon?: string
  disabled?: boolean
  loading?: boolean
  onClick: (row?: any) => void
  permission?: string[]
}

// 文件上传配置
export interface UploadConfig {
  action: string
  multiple?: boolean
  accept?: string
  maxSize?: number
  maxCount?: number
  autoUpload?: boolean
  showFileList?: boolean
  beforeUpload?: (file: File) => boolean | Promise<boolean>
  onSuccess?: (response: any, file: File) => void
  onError?: (error: any, file: File) => void
}

// 主题配置
export interface ThemeConfig {
  primaryColor: string
  isDark: boolean
  sidebarCollapsed: boolean
  showBreadcrumb: boolean
  showTabs: boolean
  showFooter: boolean
  layout: 'default' | 'top' | 'mix'
}

// WebSocket连接状态
export enum WebSocketStatus {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  ERROR = 'error'
}

// 通知类型
export enum NotificationType {
  SUCCESS = 'success',
  WARNING = 'warning',
  INFO = 'info',
  ERROR = 'error'
}

// 加载状态
export interface LoadingState {
  loading: boolean
  text?: string
}

// 错误状态
export interface ErrorState {
  hasError: boolean
  message?: string
  code?: string | number
}

// 空状态
export interface EmptyState {
  isEmpty: boolean
  description?: string
  image?: string
}

// 网络请求状态
export interface RequestState<T = any> {
  loading: boolean
  data: T | null
  error: string | null
  success: boolean
}

// 表单验证状态
export interface FormValidateState {
  valid: boolean
  errors: Record<string, string[]>
}

// 组件尺寸
export type ComponentSize = 'large' | 'default' | 'small'

// 响应式断点
export interface ResponsiveBreakpoints {
  xs: number
  sm: number
  md: number
  lg: number
  xl: number
  xxl: number
}

// 扫描配置
export interface ScanConfig {
  max_depth: number
  max_pages_per_domain: number
  request_delay: number
  timeout: number
  user_agent: string
  headers: Record<string, string>
  allowed_domains: string[]
  blocked_domains: string[]
  file_extensions: string[]
  enable_screenshots: boolean
  screenshot_width: number
  screenshot_height: number
}