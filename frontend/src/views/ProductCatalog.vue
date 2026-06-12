<script setup>
import { ref, onMounted, watch } from 'vue'
import SearchBar from '../components/SearchBar.vue'
import ProductCard from '../components/ProductCard.vue'
import { getProducts } from '../api/client'

const filters = ref({ search: '', stock_filter: 'all' })
const page = ref(1)
const pageSize = ref(24)
const products = ref([])
const total = ref(0)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await getProducts({
      page: page.value,
      page_size: pageSize.value,
      search: filters.value.search,
      stock_filter: filters.value.stock_filter,
    })
    products.value = data.items
    total.value = data.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

watch(filters, () => {
  page.value = 1
  load()
}, { deep: true })

watch(page, load)

function totalPages() {
  return Math.max(1, Math.ceil(total.value / pageSize.value))
}
</script>

<template>
  <div>
    <SearchBar v-model="filters" />

    <div v-if="loading && products.length === 0" class="text-center py-12 text-gray-500">
      加载中...
    </div>
    <div v-else-if="products.length === 0" class="text-center py-12 text-gray-500">
      <div class="text-4xl mb-2">📦</div>
      <div>没有找到商品。数据库可能还在初始化扫描中，请稍后刷新。</div>
    </div>
    <div v-else>
      <div class="text-sm text-gray-500 mb-3">共 {{ total }} 个商品</div>
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        <ProductCard
          v-for="p in products"
          :key="p.sku"
          :product="p"
          @updated="load"
        />
      </div>

      <!-- Pagination -->
      <div class="flex items-center justify-center gap-2 mt-6">
        <button
          @click="page--"
          :disabled="page <= 1"
          class="px-3 py-1.5 text-sm rounded border border-gray-300 disabled:opacity-50 hover:bg-gray-50"
        >上一页</button>
        <span class="text-sm text-gray-600">第 {{ page }} / {{ totalPages() }} 页</span>
        <button
          @click="page++"
          :disabled="page >= totalPages()"
          class="px-3 py-1.5 text-sm rounded border border-gray-300 disabled:opacity-50 hover:bg-gray-50"
        >下一页</button>
      </div>
    </div>
  </div>
</template>
