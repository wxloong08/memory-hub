import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', component: () => import('../views/Dashboard.vue') },
  { path: '/conversations', component: () => import('../views/Conversations.vue') },
  { path: '/conversations/:id', component: () => import('../views/ConversationDetail.vue') },
  { path: '/search', component: () => import('../views/Search.vue') },
  { path: '/settings', component: () => import('../views/Settings.vue') },
  { path: '/switch', component: () => import('../views/SwitchCenter.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({ history: createWebHistory(), routes })
