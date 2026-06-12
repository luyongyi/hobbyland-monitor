<script setup>
import { computed } from 'vue'
import PriceTag from './PriceTag.vue'
import WatchButton from './WatchButton.vue'
import { imageUrl } from '../api/client'

const props = defineProps({
  product: { type: Object, required: true },
})
const emit = defineEmits(['updated'])

const imgSrc = computed(() => imageUrl(props.product.pic1))
const productUrl = computed(() => {
  return props.product.link
    ? `https://www.hobbylandeshop.com${props.product.link}`
    : null
})

const stockStatus = computed(() => {
  if (props.product.stock === 0) return { label: '缺货', color: 'bg-red-100 text-red-700' }
  if (props.product.stock <= 3) return { label: `仅剩 ${props.product.stock}`, color: 'bg-orange-100 text-orange-700' }
  return { label: `有货 (${props.product.stock})`, color: 'bg-green-100 text-green-700' }
})
</script>

<template>
  <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition flex flex-col">
    <!-- Image -->
    <a :href="productUrl" target="_blank" class="block aspect-square bg-gray-50 overflow-hidden relative">
      <img
        v-if="imgSrc"
        :src="imgSrc"
        :alt="product.title"
        loading="lazy"
        class="w-full h-full object-contain hover:scale-105 transition"
      />
      <div v-else class="w-full h-full flex items-center justify-center text-gray-300 text-4xl">
        🤖
      </div>
      <!-- Stock badge overlay -->
      <span
        class="absolute top-2 right-2 px-2 py-0.5 text-xs rounded font-medium"
        :class="stockStatus.color"
      >
        {{ stockStatus.label }}
      </span>
      <span
        v-if="product.sell_type"
        class="absolute top-2 left-2 px-2 py-0.5 text-xs rounded font-medium bg-white/90 text-gray-700"
      >
        {{ product.sell_type }}
      </span>
    </a>

    <!-- Content -->
    <div class="p-3 flex flex-col flex-1 gap-2">
      <a
        :href="productUrl"
        target="_blank"
        class="text-sm font-medium text-gray-800 line-clamp-2 min-h-[2.5rem] hover:text-blue-600"
        :title="product.title"
      >
        {{ product.title }}
      </a>

      <PriceTag :price="product.price" :regular-price="product.regular_price" />

      <div class="text-xs text-gray-400">SKU: {{ product.sku }}</div>

      <div class="mt-auto pt-2 flex justify-end">
        <WatchButton
          :sku="product.sku"
          :watch-types="product.watch_types || []"
          @updated="emit('updated')"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
