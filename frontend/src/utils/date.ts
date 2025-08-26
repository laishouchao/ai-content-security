/**
 * 格式化时间戳为本地时间字符串
 * @param timestamp 时间戳或日期字符串
 * @returns 格式化后的时间字符串
 */
export function formatTime(timestamp: string | number | Date): string {
  if (!timestamp) return '-';
  
  try {
    const date = new Date(timestamp);
    
    // 检查日期是否有效
    if (isNaN(date.getTime())) {
      return '-';
    }
    
    // 格式化为本地时间字符串
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  } catch (error) {
    console.error('时间格式化错误:', error);
    return '-';
  }
}

/**
 * 格式化时间为相对时间（如：几分钟前）
 * @param timestamp 时间戳或日期字符串
 * @returns 相对时间字符串
 */
export function formatRelativeTime(timestamp: string | number | Date): string {
  if (!timestamp) return '-';
  
  try {
    const date = new Date(timestamp);
    
    // 检查日期是否有效
    if (isNaN(date.getTime())) {
      return '-';
    }
    
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) {
      return '刚刚';
    } else if (diffMins < 60) {
      return `${diffMins}分钟前`;
    } else if (diffHours < 24) {
      return `${diffHours}小时前`;
    } else if (diffDays < 30) {
      return `${diffDays}天前`;
    } else {
      return formatTime(timestamp);
    }
  } catch (error) {
    console.error('相对时间格式化错误:', error);
    return '-';
  }
}