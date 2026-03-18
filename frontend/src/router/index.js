import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
  },
  {
    path: '/simulation/:id',
    name: 'simulation',
    component: () => import('../views/SimulationView.vue'),
    meta: { hideShell: true },
  },
  {
    path: '/report/:id',
    name: 'report',
    component: () => import('../views/ReportView.vue'),
  },
  {
    path: '/gallery',
    name: 'gallery',
    component: () => import('../views/GalleryView.vue'),
  },
  {
    path: '/compare/:id/:forkId',
    name: 'compare',
    component: () => import('../views/CompareView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
