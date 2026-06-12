<script setup>
import { ref, computed } from 'vue'
import {
  addWatch, removeWatch, getSuggestedType,
  WATCH_TYPE_LABELS, WATCH_TYPE_COLORS, WATCH_TYPE_ICONS,
} from '../api/client'

const props = defineProps({
  sku: { type: String, required: true },
  watchTypes: { type: Array, default: () => [] },
})
const emit = defineEmits(['updated'])

const showMenu = ref(false)
const loading = ref(false)
const suggested = ref(null)

const isWatched = computed(() => props.watchTypes.length > 0)
const allTypes = ['back_in_stock', 'discount', 'lower_price']

async function loadSuggested() {
  if (suggested.value) return
  try {
    const data = await getSuggestedType(props.sku)
    suggested.value = data
  } catch (e) {
    console.error(e)
  }
}

async function follow(type) {
  loading.value = true
  try {
    await addWatch(props.sku, type)
    emit('updated')
  } catch (e) {
    alert(e.response?.data?.detail || '添加失败')
  } finally {
    loading.value = false
    showMenu.value = false
  }
}

async function unfollow(type) {
  loading.value = true
  try {
    await removeWatch(props.sku, type)
    emit('updated')
  } catch (e) {
    alert('取消关注失败')
  } finally {
    loading.value = false
    showMenu.value = false
  }
}

async function quickFollow() {
  await loadSuggested()
  if (suggested.value) {
    await follow(suggested.value.suggested_type)
  }
}

function toggleMenu() {
  showMenu.value = !showMenu.value
  if (showMenu.value && !isWatched.value) loadSuggested()
}
</script>

<template>
  <div class="relative inline-block">
    <!-- Not watched: simple follow button -->
    <button
      v-if="!isWatched"
      @click="quickFollow"
      :disabled="loading"
      class="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-300 transition"
    >
      <span v-if="loading">...</span>
      <span v-else>⭐ 关注</span>
    </button>

    <!-- Already watched: show types + manage button -->
    <div v-else class="flex items-center gap-1 flex-wrap">
      <span
        v-for="t in watchTypes"
        :key="t"
        class="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border"
        :class="WATCH_TYPE_COLORS[t]"
      >
        {{ WATCH_TYPE_ICONS[t] }} {{ WATCH_TYPE_LABELS[t] }}
        <button
          @click="unfollow(t)"
          :disabled="loading"
          class="ml-1 hover:text-red-600 font-bold"
          title="取消关注"
        >×</button>
      </span>
      <button
        @click="toggleMenu"
        class="px-2 py-0.5 text-xs rounded border border-gray-300 text-gray-600 hover:bg-gray-100"
        title="添加其他关注类型"
      >+</button>
    </div>

    <!-- Manage menu -->
    <div
      v-if="showMenu"
      class="absolute right-0 mt-1 w-56 bg-white border border-gray-200 rounded-md shadow-lg z-20"
      @click.stop
    >
      <div class="p-2 text-xs text-gray-500 border-b">
        <div v-if="suggested && !isWatched">
          <div class="font-medium text-gray-700 mb-1">推荐: {{ WATCH_TYPE_LABELS[suggested.suggested_type] }}</div>
          <div>{{ suggested.reasoning }}</div>
        </div>
        <div v-else>选择关注类型</div>
      </div>
      <button
        v-for="t in allTypes"
        :key="t"
        @click="watchTypes.includes(t) ? unfollow(t) : follow(t)"
        :disabled="loading"
        class="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center justify-between"
      >
        <span>{{ WATCH_TYPE_ICONS[t] }} {{ WATCH_TYPE_LABELS[t] }}</span>
        <span v-if="watchTypes.includes(t)" class="text-xs text-red-600">取消</span>
        <span v-else-if="suggested?.suggested_type === t" class="text-xs text-blue-600">推荐</span>
      </button>
      <button
        @click="showMenu = false"
        class="w-full text-center py-1.5 text-xs text-gray-500 border-t hover:bg-gray-50"
      >关闭</button>
    </div>
  </div>
</template>
