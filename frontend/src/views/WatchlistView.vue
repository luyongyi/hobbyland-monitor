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

// 已达成的关注项
const satisfied = computed(() => items.value.filter(i => i.is_satisfied))

// 未达成的，按类型分组
const grouped = computed(() => {
  const groups = { back_in_stock: [], discount: [], lower_price: [] }
  for (const item of items.value) {
    if (item.is_satisfied) continue   // 已达成的不在这里再显示
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
    msrp_jpy: item.msrp_jpy,
    msrp_source: item.msrp_source,
    msrp_confidence: item.msrp_confidence,
    msrp_hkd_estimate: item.msrp_hkd_estimate,
    official_url: item.official_url,
    sell_type: '',
    link: null,
    watch_types: [item.watch_type],
  }
}

function satisfiedReason(item) {
  if (item.watch_type === 'back_in_stock') {
    return `🟢 已到货（库存 ${item.stock}）`
  }
  if (item.watch_type === 'discount') {
    const pct = item.regular_price ? Math.round((1 - item.price / item.regular_price) * 100) : 0
    return `🏷️ 已打折 (-${pct}%)`
  }
  if (item.watch_type === 'lower_price') {
    return `🔥 价格更低 ($${item.baseline_price?.toFixed(0)} → $${item.price.toFixed(0)})`
  }
  return ''
}

const sectionMeta = {
  back_in_stock: {
    color: 'border-l-green-500 bg-green-50',
    desc: '缺货商品 — 有货时立即提醒',
  },
  discount: {
    color: 'border-l-yellow-500 bg-yellow-50',
    desc: '原价商品 — 开始打折时提醒',
  },
  lower_price: {
    color: 'border-l-red-500 bg-red-50',
    desc: '已打折商品 — 价格进一步下降时提醒',
  },
}
</script>

<template>
  <div>
    <div class="mb-4 flex items-center justify-between flex-wrap gap-2">
      <div>
        <h1 class="text-xl font-bold text-gray-800">⭐ 我的关注</h1>
        <p class="text-sm text-gray-500 mt-1">
          {{ items.length === 0 ? '还没有关注任何商品' : `共 ${items.length} 个关注项 · ${satisfied.length} 个已达成` }}
        </p>
      </div>
      <router-link
        to="/catalog"
        class="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700"
      >
        + 新增关注
      </router-link>
    </div>

    <div v-if="loading && items.length === 0" class="text-center py-12 text-gray-500">加载中...</div>

    <!-- 空状态 -->
    <div v-else-if="items.length === 0" class="bg-white rounded-lg border border-dashed border-gray-300 p-12 text-center">
      <div class="text-5xl mb-3">⭐</div>
      <h2 class="text-lg font-medium text-gray-700 mb-1">还没有关注任何商品</h2>
      <p class="text-sm text-gray-500 mb-4">前往商品目录，挑选你想监控的高达模型</p>
      <router-link
        to="/catalog"
        class="inline-block px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
      >
        去商品目录浏览
      </router-link>
    </div>

    <div v-else class="space-y-6">
      <!-- 已达成栏框（始终显示，空也显示） -->
      <section>
        <div class="border-l-4 border-l-purple-500 pl-3 mb-3 bg-purple-50 py-2 pr-3 rounded">
          <h2 class="font-bold text-purple-900">
            🎉 已达成 ({{ satisfied.length }})
          </h2>
          <p class="text-xs text-purple-700">关注目标已经达成的商品 — 可以下单啦</p>
        </div>
        <div v-if="satisfied.length === 0" class="bg-white rounded-lg border border-dashed border-gray-200 p-6 text-center text-sm text-gray-400">
          暂无已达成项 — 关注的商品状态变化时会出现在这里
        </div>
        <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          <div
            v-for="item in satisfied"
            :key="`satisfied-${item.sku}-${item.watch_type}`"
            class="relative"
          >
            <!-- 角标显示达成原因 -->
            <span class="absolute top-1 left-1 z-10 px-2 py-0.5 text-xs rounded bg-purple-600 text-white shadow font-medium">
              {{ satisfiedReason(item) }}
            </span>
            <ProductCard :product="itemAsProduct(item)" @updated="load" />
          </div>
        </div>
      </section>

      <!-- 未达成的，按类型分组 -->
      <section v-for="(group, type) in grouped" :key="type" v-show="group.length > 0">
        <div class="border-l-4 pl-3 mb-3 py-2 pr-3 rounded" :class="sectionMeta[type].color">
          <h2 class="font-bold text-gray-800">
            {{ WATCH_TYPE_ICONS[type] }} {{ WATCH_TYPE_LABELS[type] }} ({{ group.length }})
          </h2>
          <p class="text-xs text-gray-600">{{ sectionMeta[type].desc }}</p>
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
