<script setup>
import { ref, onMounted, computed } from 'vue'
import ProductCard from '../components/ProductCard.vue'
import {
  getWatchlist, WATCH_TYPE_LABELS, WATCH_TYPE_ICONS,
} from '../api/client'

const items = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    items.value = await getWatchlist()
  } finally {
    loading.value = false
  }
}

onMounted(load)

const grouped = computed(() => {
  const groups = { back_in_stock: [], discount: [], lower_price: [] }
  for (const item of items.value) {
    if (groups[item.watch_type]) {
      groups[item.watch_type].push(item)
    }
  }
  return groups
})

function itemAsProduct(item) {
  return {
    sku: item.sku,
    title: item.title,
    price: item.price,
    regular_price: item.regular_price,
    stock: item.stock,
    pic1: item.pic1,
    sell_type: '',
    link: null,
    watch_types: [item.watch_type],
  }
}

const sectionMeta = {
  back_in_stock: {
    color: 'border-l-green-500 bg-green-50',
    desc: '缺货商品 — 有货时立即提醒你',
  },
  discount: {
    color: 'border-l-yellow-500 bg-yellow-50',
    desc: '有货原价商品 — 开始打折时提醒你',
  },
  lower_price: {
    color: 'border-l-red-500 bg-red-50',
    desc: '已打折商品 — 价格进一步下降时提醒你',
  },
}
</script>

<template>
  <div>
    <div class="mb-4">
      <h1 class="text-xl font-bold text-gray-800">⭐ 我的关注</h1>
      <p class="text-sm text-gray-500 mt-1">
        共 {{ items.length }} 个关注项 · 商品状态变化时会触发对应类型的告警
      </p>
    </div>

    <div v-if="loading" class="text-center py-12 text-gray-500">加载中...</div>
    <div v-else-if="items.length === 0" class="text-center py-12 text-gray-500">
      <div class="text-4xl mb-2">⭐</div>
      <div>还没有关注任何商品</div>
      <router-link to="/" class="inline-block mt-3 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm">
        去商品目录关注商品
      </router-link>
    </div>

    <div v-else class="space-y-6">
      <section v-for="(group, type) in grouped" :key="type" v-show="group.length > 0">
        <div class="border-l-4 pl-3 mb-3" :class="sectionMeta[type].color">
          <h2 class="font-bold text-gray-800">
            {{ WATCH_TYPE_ICONS[type] }} {{ WATCH_TYPE_LABELS[type] }} ({{ group.length }})
          </h2>
          <p class="text-xs text-gray-500">{{ sectionMeta[type].desc }}</p>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          <ProductCard
            v-for="item in group"
            :key="`${item.sku}-${item.watch_type}`"
            :product="itemAsProduct(item)"
            @updated="load"
          />
        </div>
      </section>
    </div>
  </div>
</template>
