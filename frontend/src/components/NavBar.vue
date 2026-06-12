<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { getScanStatus } from '../api/client'

const status = ref({
  is_running: false,
  state: 'idle',
  current_page: 0,
  total_pages: 0,
  fetched_count: 0,
  total_count: 0,
  processed_count: 0,
  fetch_percent: 0,
  process_percent: 0,
  finished_at: null,
})

let pollTimer = null

async function refresh() {
  try {
    status.value = await getScanStatus()
  } catch (e) {
    // ignore
  }
}

function startPolling() {
  stopPolling()
  // Fast poll while a scan is running, slow otherwise.
  const interval = status.value.is_running ? 1500 : 30000
  pollTimer = setTimeout(async () => {
    await refresh()
    startPolling()
  }, interval)
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

const showProgress = computed(() => status.value.is_running)

const progressLabel = computed(() => {
  const s = status.value
  if (s.state === 'fetching') {
    return `抓取中 ${s.current_page}/${s.total_pages} 页 (${s.fetched_count}/${s.total_count || '?'} 商品)`
  }
  if (s.state === 'processing') {
    return `入库中 ${s.processed_count}/${s.fetched_count} 商品`
  }
  return ''
})

const overallPercent = computed(() => {
  const s = status.value
  // Fetch is ~70% of work, processing ~30%
  if (s.state === 'fetching') return Math.round(s.fetch_percent * 0.7)
  if (s.state === 'processing') return 70 + Math.round(s.process_percent * 0.3)
  if (s.state === 'completed') return 100
  return 0
})

const lastScanText = computed(() => {
  const ts = status.value.finished_at
  if (!ts) return '尚未完成扫描'
  try {
    const d = new Date(ts)
    return `上次扫描: ${d.toLocaleString('zh-CN', { hour12: false })}`
  } catch {
    return `上次扫描: ${ts}`
  }
})

onMounted(() => {
  refresh().then(startPolling)
})

onUnmounted(stopPolling)
</script>

<template>
  <nav class="bg-white border-b border-gray-200 sticky top-0 z-10">
    <div class="max-w-7xl mx-auto px-4">
      <div class="flex items-center justify-between h-14">
        <div class="flex items-center gap-6">
          <router-link to="/" class="text-lg font-bold text-gray-800">
            🤖 Hobbyland 监控
          </router-link>
          <div class="flex gap-1">
            <router-link to="/" custom v-slot="{ isActive, navigate }">
              <a @click="navigate" class="px-3 py-1.5 rounded text-sm cursor-pointer transition"
                 :class="isActive ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'">
                📦 商品目录
              </a>
            </router-link>
            <router-link to="/watchlist" custom v-slot="{ isActive, navigate }">
              <a @click="navigate" class="px-3 py-1.5 rounded text-sm cursor-pointer transition"
                 :class="isActive ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'">
                ⭐ 我的关注
              </a>
            </router-link>
            <router-link to="/alerts" custom v-slot="{ isActive, navigate }">
              <a @click="navigate" class="px-3 py-1.5 rounded text-sm cursor-pointer transition"
                 :class="isActive ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'">
                🔔 告警历史
              </a>
            </router-link>
          </div>
        </div>
        <div class="text-xs text-gray-500 hidden sm:block" :title="'每天 12:00 自动扫描，启动时也会扫一次'">
          {{ lastScanText }}
        </div>
      </div>

      <!-- Progress bar (only visible during scan) -->
      <div v-if="showProgress" class="pb-2">
        <div class="flex items-center justify-between text-xs text-gray-600 mb-1">
          <span>{{ progressLabel }}</span>
          <span class="font-medium">{{ overallPercent }}%</span>
        </div>
        <div class="h-1.5 bg-gray-200 rounded overflow-hidden">
          <div
            class="h-full bg-blue-500 transition-all duration-300"
            :style="{ width: overallPercent + '%' }"
          ></div>
        </div>
      </div>
    </div>
  </nav>
</template>
