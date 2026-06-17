<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({
      search: '',
      stock_filter: 'all',
      discount_filter: 'all',
      sort_by: 'updated_at',
      sort_order: 'desc',
    }),
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

function emitNow() {
  clearTimeout(debounceTimer)
  emit('update:modelValue', { ...local.value })
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
      @change="emitNow"
      class="px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500 bg-white"
    >
      <option value="all">全部商品</option>
      <option value="in_stock">仅有货</option>
      <option value="out_of_stock">仅缺货</option>
    </select>

    <select
      v-model="local.discount_filter"
      @change="emitNow"
      class="px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500 bg-white"
      title="优惠筛选"
    >
      <option value="all">全部价格</option>
      <option value="discounted">仅优惠</option>
      <option value="not_discounted">未优惠</option>
    </select>

    <select
      v-model="local.sort_by"
      @change="emitNow"
      class="px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500 bg-white"
      title="排序方式"
    >
      <option value="updated_at">最近更新</option>
      <option value="discount_amount">优惠金额最大</option>
      <option value="discount_percent">优惠百分比最大</option>
      <option value="price">价格</option>
      <option value="stock">库存</option>
    </select>

    <select
      v-model="local.sort_order"
      @change="emitNow"
      class="px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:border-blue-500 bg-white"
      title="升序/降序"
    >
      <option value="desc">从高到低</option>
      <option value="asc">从低到高</option>
    </select>
  </div>
</template>
