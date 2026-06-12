<script setup>
import { computed } from 'vue'
import { imageUrl, ALERT_TYPE_LABELS } from '../api/client'

const props = defineProps({
  alert: { type: Object, required: true },
})

const imgSrc = computed(() => imageUrl(props.alert.extra?.pic1))
const productUrl = computed(() => {
  const link = props.alert.extra?.link
  return link ? `https://www.hobbylandeshop.com${link}` : null
})

const typeStyle = computed(() => {
  const map = {
    back_in_stock: 'bg-green-100 text-green-700 border-green-300',
    discount: 'bg-yellow-100 text-yellow-700 border-yellow-300',
    lower_price: 'bg-red-100 text-red-700 border-red-300',
    price_change: 'bg-blue-100 text-blue-700 border-blue-300',
    good_deal: 'bg-purple-100 text-purple-700 border-purple-300',
  }
  return map[props.alert.alert_type] || 'bg-gray-100 text-gray-700 border-gray-300'
})

const icon = computed(() => {
  const map = {
    back_in_stock: '🟢',
    discount: '🏷️',
    lower_price: '🔥',
    price_change: '💰',
    good_deal: '✨',
  }
  return map[props.alert.alert_type] || '📢'
})

function formatTime(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}
</script>

<template>
  <div class="bg-white rounded-lg border border-gray-200 p-3 flex gap-3 items-center">
    <a v-if="imgSrc" :href="productUrl" target="_blank" class="w-16 h-16 flex-shrink-0 bg-gray-50 rounded overflow-hidden">
      <img :src="imgSrc" :alt="alert.title" loading="lazy" class="w-full h-full object-contain" />
    </a>
    <div v-else class="w-16 h-16 flex-shrink-0 bg-gray-50 rounded flex items-center justify-center text-2xl text-gray-300">🤖</div>

    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 mb-1">
        <span class="text-xs px-2 py-0.5 rounded border" :class="typeStyle">
          {{ icon }} {{ ALERT_TYPE_LABELS[alert.alert_type] || alert.alert_type }}
        </span>
        <span class="text-xs text-gray-400">{{ formatTime(alert.created_at) }}</span>
      </div>
      <a :href="productUrl" target="_blank" class="text-sm font-medium text-gray-800 hover:text-blue-600 line-clamp-1">
        {{ alert.title }}
      </a>
      <div class="text-xs text-gray-500 mt-0.5">
        <template v-if="alert.alert_type === 'back_in_stock'">
          库存: <span class="font-medium">{{ alert.old_value }}</span> → <span class="font-medium text-green-700">{{ alert.new_value }}</span>
        </template>
        <template v-else>
          价格: <span class="line-through">${{ alert.old_value }}</span> → <span class="font-medium text-red-600">${{ alert.new_value }}</span>
          <span v-if="alert.extra?.regular_price" class="text-gray-400 ml-2">原价 ${{ alert.extra.regular_price }}</span>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
