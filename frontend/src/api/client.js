import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// Products
export function getProducts(params = {}) {
  return api.get('/products', { params }).then(r => r.data)
}

export function getProduct(sku) {
  return api.get(`/products/${sku}`).then(r => r.data)
}

// Watchlist
export function getWatchlist(watchType = '') {
  const params = watchType ? { watch_type: watchType } : {}
  return api.get('/watchlist', { params }).then(r => r.data)
}

export function addWatch(sku, watchType) {
  return api.post('/watchlist', { sku, watch_type: watchType }).then(r => r.data)
}

export function removeWatch(sku, watchType) {
  return api.delete(`/watchlist/${sku}/${watchType}`).then(r => r.data)
}

export function getSuggestedType(sku) {
  return api.get(`/watchlist/suggested-type/${sku}`).then(r => r.data)
}

// Alerts
export function getAlerts(params = {}) {
  return api.get('/alerts', { params }).then(r => r.data)
}

// Scan (read-only status only — scans run automatically on startup and daily at noon)
export function getScanStatus() {
  return api.get('/scan/status').then(r => r.data)
}

// Helper: build image URL through the proxy
export function imageUrl(pic1) {
  if (!pic1) return null
  // Strip leading slash if any
  const path = pic1.replace(/^\/+/, '')
  // The proxy returns the image directly
  return `/api/images/${path}`
}

export const WATCH_TYPE_LABELS = {
  back_in_stock: '到货关注',
  discount: '打折关注',
  lower_price: '更低价关注',
}

export const WATCH_TYPE_COLORS = {
  back_in_stock: 'bg-green-100 text-green-800 border-green-300',
  discount: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  lower_price: 'bg-red-100 text-red-800 border-red-300',
}

export const WATCH_TYPE_ICONS = {
  back_in_stock: '🟢',
  discount: '🏷️',
  lower_price: '🔥',
}

export const ALERT_TYPE_LABELS = {
  back_in_stock: '到货提醒',
  discount: '打折提醒',
  lower_price: '更低价提醒',
  price_change: '价格变动',
  good_deal: '好价提醒',
}
