<template>
  <section class="space-y-6">
    <div class="rounded-[26px] border border-stone-200/60 bg-[rgba(255,253,248,0.56)] p-5 shadow-[0_8px_24px_rgba(71,52,31,0.035)] lg:p-6">
      <div class="text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-400">Overview</div>
      <h2 class="mt-2 text-[2rem] font-semibold tracking-tight text-stone-900">System snapshot</h2>
      <p class="mt-3 max-w-2xl text-sm leading-7 text-stone-600">
        A lightweight summary of stored conversations, vector documents, and platform distribution.
      </p>
    </div>

    <div v-if="loading" class="memory-panel rounded-[24px] p-6 text-sm text-stone-500">Loading dashboard...</div>

    <div v-else-if="error" class="rounded-[24px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
      {{ error }}
    </div>

    <template v-else>
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div class="memory-panel rounded-[24px] p-5">
          <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">Total Conversations</div>
          <div class="mt-3 text-3xl font-semibold text-stone-900">{{ totalConversations }}</div>
        </div>
        <div class="memory-panel rounded-[24px] p-5">
          <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">Platforms</div>
          <div class="mt-3 text-3xl font-semibold text-stone-900">{{ platformCount }}</div>
        </div>
        <div class="memory-panel rounded-[24px] p-5">
          <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">Vector Documents</div>
          <div class="mt-3 text-3xl font-semibold text-stone-900">{{ vectorDocs }}</div>
        </div>
        <div class="memory-panel rounded-[24px] p-5">
          <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">Average Importance</div>
          <div class="mt-3 text-3xl font-semibold text-stone-900">{{ avgImportance }}</div>
        </div>
      </div>

      <div class="memory-panel rounded-[26px] p-5 lg:p-6">
        <div class="text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-400">Breakdown</div>
        <h3 class="mt-2 text-xl font-semibold text-stone-900">Platform activity</h3>
        <div class="mt-5 space-y-4">
          <div v-for="p in byPlatform" :key="p.platform" class="grid gap-2 sm:grid-cols-[9rem_1fr_auto] sm:items-center">
            <div class="flex items-center gap-2 text-sm text-stone-700">
              <span>{{ platformEmoji(p.platform) }}</span>
              <span>{{ p.platform }}</span>
            </div>
            <div class="h-2.5 overflow-hidden rounded-full bg-stone-200/80">
              <div
                class="h-full rounded-full bg-[var(--brand)]/85 transition-all"
                :style="{ width: barWidth(p.count) }"
              ></div>
            </div>
            <div class="text-sm text-stone-500">{{ p.count }}</div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api/memory-hub.js'
import { platformEmoji } from '../constants/platforms.js'

const loading = ref(true)
const error = ref(null)
const rawStats = ref(null)

const byPlatform = computed(() => rawStats.value?.database?.by_platform || [])
const totalConversations = computed(() => rawStats.value?.database?.total_conversations || 0)
const platformCount = computed(() => byPlatform.value.length)
const vectorDocs = computed(() => rawStats.value?.vector_store?.total_documents || 0)

const avgImportance = computed(() => {
  const platforms = byPlatform.value
  if (!platforms.length) return '0.0'
  const sum = platforms.reduce((acc, p) => acc + (p.avg_importance || 0), 0)
  return (sum / platforms.length).toFixed(1)
})

const maxCount = computed(() => Math.max(...byPlatform.value.map(p => p.count), 1))

function barWidth(count) {
  return Math.round((count / maxCount.value) * 100) + '%'
}

onMounted(async () => {
  try {
    rawStats.value = await api.getStats()
  } catch (e) {
    error.value = 'Failed to load stats: ' + e.message
  } finally {
    loading.value = false
  }
})
</script>
