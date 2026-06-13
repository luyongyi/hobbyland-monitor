import { createRouter, createWebHistory } from 'vue-router'
import WatchlistView from '../views/WatchlistView.vue'
import ProductCatalog from '../views/ProductCatalog.vue'
import AlertHistory from '../views/AlertHistory.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'watchlist', component: WatchlistView },
    { path: '/catalog', name: 'catalog', component: ProductCatalog },
    { path: '/alerts', name: 'alerts', component: AlertHistory },
  ],
})

export default router
