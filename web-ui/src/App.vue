<template>
  <div class="memory-shell lg:flex">
    <aside class="hidden lg:flex lg:w-[17.5rem] xl:w-[18.5rem] p-4 xl:p-5">
      <div class="memory-nav-panel flex min-h-[calc(100vh-2rem)] w-full flex-col rounded-[28px] px-4 py-5">
        <div class="mb-6">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-stone-900 text-xs font-semibold tracking-[0.24em] text-stone-50">
              CM
            </div>
            <div class="min-w-0">
              <div class="text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">{{ t('appName') }}</div>
              <h1 class="mt-1 text-[1.2rem] font-semibold tracking-tight text-stone-900">{{ t('appTitle') }}</h1>
            </div>
          </div>
          <p class="mt-4 text-sm leading-6 text-stone-600">
            {{ t('appDescription') }}
          </p>
        </div>

        <div class="mb-3 text-[10px] font-semibold uppercase tracking-[0.24em] text-stone-400">{{ t('browse') }}</div>
        <nav class="space-y-1.5">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            :class="[
              'group flex items-center justify-between rounded-2xl px-3.5 py-3 transition-all duration-200',
              isActive(item.path)
                ? 'bg-stone-900 text-stone-50 shadow-lg shadow-stone-900/8'
                : 'text-stone-600 hover:bg-white/78 hover:text-stone-900'
            ]"
          >
            <div class="flex items-center gap-3">
              <span class="text-sm font-semibold tracking-[0.2em]">{{ item.icon }}</span>
              <span class="text-sm font-medium">{{ item.label }}</span>
            </div>
            <span
              class="h-2 w-2 rounded-full transition-colors"
              :class="isActive(item.path) ? 'bg-amber-300' : 'bg-stone-300 group-hover:bg-stone-400'"
            ></span>
          </router-link>
        </nav>

        <div class="mt-6 rounded-[24px] bg-white/78 px-4 py-4 text-stone-900 ring-1 ring-stone-200/70">
          <div class="text-[10px] uppercase tracking-[0.2em] text-stone-400">{{ t('language') }}</div>
          <div class="mt-3 grid grid-cols-2 gap-2">
            <button
              v-for="option in localeOptions"
              :key="option.value"
              type="button"
              class="rounded-full px-3 py-2 text-sm font-medium transition-colors"
              :class="locale === option.value ? 'bg-stone-900 text-stone-50' : 'bg-stone-100 text-stone-700 hover:bg-stone-200'"
              @click="setLocale(option.value)"
            >
              {{ option.label }}
            </button>
          </div>
        </div>

        <div class="mt-auto rounded-[24px] bg-white/78 px-4 py-4 text-stone-900 ring-1 ring-stone-200/70">
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
              <div class="text-[10px] uppercase tracking-[0.2em] text-stone-400">{{ t('backend') }}</div>
              <div class="mt-1 text-sm font-medium">{{ connected ? t('connected') : t('offline') }}</div>
            </div>
            <span
              :class="connected ? 'bg-emerald-500 shadow-emerald-500/30' : 'bg-rose-500 shadow-rose-500/30'"
              class="inline-flex h-2.5 w-2.5 rounded-full shadow-md"
            ></span>
          </div>
          <p class="mt-3 text-xs leading-5 text-stone-500">
            {{ t('statusRefreshHint') }}
          </p>
        </div>
      </div>
    </aside>

    <div class="flex-1">
      <header class="px-4 pt-4 lg:hidden">
        <div class="memory-nav-panel rounded-[22px] px-4 py-4">
          <div class="flex items-start justify-between gap-4">
            <div>
              <div class="text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-500">{{ t('appName') }}</div>
              <div class="mt-2 text-2xl font-semibold tracking-tight text-stone-900">{{ t('appTitle') }}</div>
            </div>
            <span
              class="memory-badge"
              :class="connected ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'"
            >
              <span class="inline-block h-2 w-2 rounded-full" :class="connected ? 'bg-emerald-500' : 'bg-rose-500'"></span>
              {{ connected ? t('connected') : t('offline') }}
            </span>
          </div>
          <div class="mt-4 flex gap-2">
            <button
              v-for="option in localeOptions"
              :key="option.value"
              type="button"
              class="rounded-full px-3 py-1.5 text-xs font-medium transition-colors"
              :class="locale === option.value ? 'bg-stone-900 text-stone-50' : 'bg-white/75 text-stone-700'"
              @click="setLocale(option.value)"
            >
              {{ option.label }}
            </button>
          </div>
          <nav class="mt-4 flex gap-2 overflow-x-auto pb-1">
            <router-link
              v-for="item in navItems"
              :key="item.path"
              :to="item.path"
              :class="[
                'whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium transition-colors',
                isActive(item.path)
                  ? 'bg-stone-900 text-stone-50'
                  : 'bg-white/75 text-stone-700'
              ]"
            >
              {{ item.label }}
            </router-link>
          </nav>
        </div>
      </header>

      <main class="px-4 pb-8 pt-4 lg:px-6 lg:pb-10 lg:pt-5 xl:px-8">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import api from './api/memory-hub.js'
import { useI18n } from './composables/useI18n.js'

const route = useRoute()
const connected = ref(false)
let healthInterval = null
const { locale, setLocale, t } = useI18n()

const navItems = computed(() => ([
  { path: '/', icon: '◎', label: t('navOverview') },
  { path: '/conversations', icon: '☰', label: t('navThreads') },
  { path: '/search', icon: '⌕', label: t('navSearch') },
  { path: '/memories', icon: '◆', label: t('navMemories') },
  { path: '/switch', icon: '⇄', label: t('navSwitch') },
  { path: '/settings', icon: '⚙', label: t('navSettings') },
]))

const localeOptions = computed(() => ([
  { value: 'zh-CN', label: t('languageZh') },
  { value: 'en', label: t('languageEn') },
]))

function isActive(path) {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

async function checkConnection() {
  connected.value = await api.checkHealth()
}

onMounted(() => {
  checkConnection()
  healthInterval = setInterval(checkConnection, 30000)
})

onUnmounted(() => {
  if (healthInterval) clearInterval(healthInterval)
})
</script>
