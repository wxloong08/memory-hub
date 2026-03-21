<template>
  <section class="space-y-6">
    <div class="rounded-[26px] border border-stone-200/60 bg-[rgba(255,253,248,0.56)] p-5 shadow-[0_8px_24px_rgba(71,52,31,0.035)] lg:p-6">
      <div class="text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-400">{{ t('searchTitle') }}</div>
      <h2 class="mt-2 text-[2rem] font-semibold tracking-tight text-stone-900">{{ t('searchSubtitle') }}</h2>
      <p class="mt-3 max-w-2xl text-sm leading-7 text-stone-600">
        {{ t('searchDescription') }}
      </p>

      <div class="mt-5 flex flex-col gap-3 sm:flex-row">
        <input
          v-model="query"
          @keyup.enter="doSearch"
          type="text"
          :placeholder="t('searchPlaceholder')"
          class="flex-1 rounded-2xl border border-stone-200 bg-white/85 px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-[var(--brand)]/40 focus:ring-2 focus:ring-[var(--brand)]/10"
        />
        <button
          @click="doSearch"
          :disabled="!query.trim() || searching"
          class="rounded-2xl bg-stone-900 px-5 py-3 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {{ searching ? t('searching') : t('search') }}
        </button>
      </div>
    </div>

    <div v-if="error" class="rounded-[24px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
      {{ error }}
    </div>

    <div v-if="searched" class="space-y-4">
      <div class="text-sm text-stone-500">{{ t('searchResultsFor', { count: results.length, query: lastQuery }) }}</div>

      <div v-if="results.length === 0 && memoryResults.length === 0" class="memory-panel rounded-[24px] p-8 text-center text-sm text-stone-500">
        {{ t('noSearchResults') }}
      </div>

      <div v-if="memoryResults.length" class="memory-panel rounded-[24px] p-5">
        <div class="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400">{{ t('memoryCenter') }}</div>
        <h3 class="mt-2 text-lg font-semibold text-stone-900">{{ t('memorySearchResults') }}</h3>
        <div class="mt-4 grid gap-3">
          <div
            v-for="memory in memoryResults"
            :key="memory.id"
            class="rounded-2xl bg-white/80 px-4 py-4 ring-1 ring-stone-200/70"
          >
            <div class="flex flex-wrap items-center gap-2">
              <span class="memory-badge bg-stone-100 text-stone-700">{{ memory.category }}</span>
              <span class="memory-badge bg-sky-50 text-sky-800">{{ memory.key }}</span>
              <span class="text-xs text-stone-400">{{ t('memoryConfidence') }} {{ Number(memory.confidence || 0).toFixed(1) }}</span>
            </div>
            <p class="mt-3 text-sm leading-6 text-stone-700">{{ memory.value }}</p>
          </div>
        </div>
      </div>

      <div v-if="results.length" class="grid gap-4">
        <router-link
          v-for="r in results"
          :key="r.id"
          :to="`/conversations/${r.id}`"
          class="memory-panel rounded-[24px] p-4 transition-transform duration-200 hover:-translate-y-0.5"
        >
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex items-center gap-2 text-sm text-stone-700">
              <span>{{ platformEmoji(r.platform) }}</span>
              <span class="memory-badge bg-white text-stone-700">{{ r.platform }}</span>
              <span class="text-xs text-stone-400">{{ formatTime(r.timestamp) }}</span>
            </div>
            <span v-if="r.similarity != null" class="memory-badge bg-teal-50 text-teal-800">
              {{ (r.similarity * 100).toFixed(0) }}% match
            </span>
          </div>
          <p class="mt-3 text-sm leading-6 text-stone-700">{{ r.summary || t('noSummaryYet') }}</p>
        </router-link>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api/memory-hub.js'
import { platformEmoji } from '../constants/platforms.js'
import { useI18n } from '../composables/useI18n.js'

const query = ref('')
const results = ref([])
const memoryResults = ref([])
const searching = ref(false)
const searched = ref(false)
const error = ref(null)
const lastQuery = ref('')
const { t, formatDateTime } = useI18n()

function formatTime(ts) {
  return formatDateTime(ts)
}

async function doSearch() {
  if (!query.value.trim()) return
  searching.value = true
  error.value = null
  lastQuery.value = query.value.trim()

  try {
    const result = await api.search(lastQuery.value)
    results.value = result.results || result || []
    memoryResults.value = result.memory_results || []
  } catch (e) {
    error.value = `Search failed: ${e.message}`
    results.value = []
    memoryResults.value = []
  } finally {
    searching.value = false
    searched.value = true
  }
}
</script>
