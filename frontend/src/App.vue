<script setup>
import NavBar from './components/NavBar.vue'
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <NavBar />
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
      <router-view />
    </main>
    <footer class="text-center text-xs text-gray-400 py-4">
      Hobbyland 高达模型监控 · 数据来源 hobbylandeshop.com
    </footer>
  </div>
</template>
