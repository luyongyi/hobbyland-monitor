<script setup>
defineProps({
  price: { type: Number, required: true },
  regularPrice: { type: Number, default: null },
  size: { type: String, default: 'normal' },  // 'normal' | 'large' | 'small'
})

function pct(price, regularPrice) {
  if (!regularPrice || regularPrice <= price) return null
  return Math.round((1 - price / regularPrice) * 100)
}
</script>

<template>
  <div class="flex items-baseline gap-2 flex-wrap">
    <span
      class="font-bold"
      :class="{
        'text-2xl': size === 'large',
        'text-lg': size === 'normal',
        'text-base': size === 'small',
        'text-red-600': regularPrice && regularPrice > price,
        'text-gray-900': !regularPrice || regularPrice <= price,
      }"
    >
      ${{ price.toFixed(0) }}
    </span>
    <template v-if="regularPrice && regularPrice > price">
      <span class="text-sm text-gray-400 line-through">${{ regularPrice.toFixed(0) }}</span>
      <span class="text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-medium">
        -{{ pct(price, regularPrice) }}%
      </span>
    </template>
  </div>
</template>
