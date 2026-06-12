import { createRouter, createWebHistory } from 'vue-router'
import ProductCatalog from '../views/ProductCatalog.vue'
import WatchlistView from '../views/WatchlistView.vue'
import AlertHistory from '../views/AlertHistory.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'catalog', component: ProductCatalog },
    { path: '/watchlist', name: 'watchlist', component: WatchlistView },
    { path: '/alerts', name: 'alerts', component: AlertHistory },
  ],
})

export default router
