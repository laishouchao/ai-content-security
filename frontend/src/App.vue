<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

onMounted(() => {
  console.log('🎯 AI内容安全监控系统已加载')
  
  // 隐藏加载动画
  setTimeout(() => {
    const loadingElement = document.getElementById('loading-screen')
    if (loadingElement) {
      loadingElement.style.transition = 'opacity 0.5s ease-out'
      loadingElement.style.opacity = '0'
      setTimeout(() => {
        loadingElement.style.display = 'none'
      }, 500)
    }
  }, 1000)
})
</script>

<style>
#app {
  height: 100vh;
  width: 100vw;
}
</style>