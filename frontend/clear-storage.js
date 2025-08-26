// 清理本地存储中的认证令牌脚本
// 在浏览器控制台中运行此脚本

(function() {
  try {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    console.log('✅ 已成功清理本地存储中的认证令牌');
    console.log('请刷新页面后重新登录');
  } catch (error) {
    console.error('清理本地存储时出错:', error);
  }
})();