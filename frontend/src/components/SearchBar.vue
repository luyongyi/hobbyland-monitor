<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({ search: '', stock_filter: 'all' }),
  },
})
const emit = defineEmits(['update:modelValue'])

const local = ref({ ...props.modelValue })

let debounceTimer = null
function emitChange() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emit('update:modelValue', { ...local.value })
  }, 300)
}

watch(() => props.modelValue, (v) => {
  local.value = { ...v }
})
</script>

<template>
  <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-3 mb-4 flex flex-wrap gap-3 items-center">
    <input
      v-model="local.search"
      @input="emitChange"
      type="text"
      placeholder="🔍 搜索商品名、SKU..."
      class="flex-1 min-w-[200px] px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500"
    />
    <select
      v-model="local.stock_filter"
      @change="emitChange"
      class="px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500 bg-white"
    >
      <option value="all">全部商品</option>
      <option value="in_stock">仅有货</option>
      <option value="out_of_stock">仅缺货</option>
    </select>
  </div>
</template>
