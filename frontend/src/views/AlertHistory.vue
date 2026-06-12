<script setup>
import { ref, onMounted, watch } from 'vue'
import AlertItem from '../components/AlertItem.vue'
import { getAlerts, ALERT_TYPE_LABELS } from '../api/client'

const filter = ref({ alert_type: '' })
const page = ref(1)
const pageSize = 30
const alerts = ref([])
const total = ref(0)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await getAlerts({
      page: page.value,
      page_size: pageSize,
      alert_type: filter.value.alert_type,
    })
    alerts.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(filter, () => { page.value = 1; load() }, { deep: true })
watch(page, load)
</script>

<template>
  <div>
    <div class="mb-4">
      <h1 class="text-xl font-bold text-gray-800">🔔 告警历史</h1>
      <p class="text-sm text-gray-500 mt-1">共 {{ total }} 条历史告警</p>
    </div>

    <div class="bg-white rounded-lg border border-gray-200 p-3 mb-4 flex gap-2 items-center">
      <span class="text-sm text-gray-600">类型:</span>
      <select v-model="filter.alert_type" class="px-3 py-1.5 text-sm border border-gray-300 rounded bg-white">
        <option value="">全部</option>
        <option v-for="(label, type) in ALERT_TYPE_LABELS" :key="type" :value="type">{{ label }}</option>
      </select>
    </div>

    <div v-if="loading && alerts.length === 0" class="text-center py-12 text-gray-500">加载中...</div>
    <div v-else-if="alerts.length === 0" class="text-center py-12 text-gray-500">
      <div class="text-4xl mb-2">🔔</div>
      <div>暂无告警记录</div>
    </div>

    <div v-else class="space-y-2">
      <AlertItem v-for="a in alerts" :key="a.id" :alert="a" />

      <div class="flex items-center justify-center gap-2 mt-4">
        <button
          @click="page--"
          :disabled="page <= 1"
          class="px-3 py-1.5 text-sm rounded border border-gray-300 disabled:opacity-50 hover:bg-gray-50"
        >上一页</button>
        <span class="text-sm text-gray-600">第 {{ page }} 页</span>
        <button
          @click="page++"
          :disabled="alerts.length < pageSize"
          class="px-3 py-1.5 text-sm rounded border border-gray-300 disabled:opacity-50 hover:bg-gray-50"
        >下一页</button>
      </div>
    </div>
  </div>
</template>
