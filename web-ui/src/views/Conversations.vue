<template>
  <section class="space-y-5">
    <div class="rounded-[26px] border border-stone-200/60 bg-[rgba(255,253,248,0.56)] p-5 shadow-[0_8px_22px_rgba(71,52,31,0.035)] lg:p-6">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div class="text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400">{{ t('navThreads') }}</div>
          <h2 class="mt-2 text-[2rem] font-semibold tracking-tight text-stone-900">{{ t('conversationListTitle') }}</h2>
          <p class="mt-3 max-w-2xl text-sm leading-7 text-stone-600">
            {{ t('conversationListDescription') }}
          </p>
          <div class="mt-3 inline-flex rounded-full bg-white/80 px-4 py-2 text-sm text-stone-600 ring-1 ring-stone-200/70">
            {{ t('summaryModeStatus', { mode: summaryModeLabel }) }}
          </div>
        </div>

        <div class="flex flex-col gap-3">
          <!-- Row 1: Essential filters (always visible) -->
          <div class="flex flex-wrap items-center gap-3">
            <label class="inline-flex items-center gap-3 rounded-full bg-white/80 px-4 py-2 ring-1 ring-stone-200/70">
              <span class="text-sm text-stone-500">{{ t('quickFilter') }}</span>
              <input
                v-model="quickFilter"
                type="text"
                :placeholder="t('quickFilterPlaceholder')"
                class="min-w-[220px] border-0 bg-transparent text-sm font-medium text-stone-900 placeholder:text-stone-400 focus:outline-none focus:ring-0"
              />
            </label>
            <label class="inline-flex items-center gap-3 rounded-full bg-white/80 px-4 py-2 ring-1 ring-stone-200/70">
              <span class="text-sm text-stone-500">{{ t('platform') }}</span>
              <select
                v-model="selectedPlatform"
                class="border-0 bg-transparent pr-6 text-sm font-medium text-stone-900 focus:outline-none focus:ring-0"
              >
                <option value="">{{ t('all') }}</option>
                <option v-for="p in platforms" :key="p" :value="p">{{ platformEmoji(p) }} {{ p }}</option>
              </select>
            </label>
            <label class="inline-flex items-center gap-3 rounded-full bg-white/80 px-4 py-2 ring-1 ring-stone-200/70">
              <span class="text-sm text-stone-500">{{ t('timeRange') }}</span>
              <select
                v-model="selectedTimeRange"
                class="border-0 bg-transparent pr-6 text-sm font-medium text-stone-900 focus:outline-none focus:ring-0"
              >
                <option value="all">{{ t('timeRangeAll') }}</option>
                <option value="24h">{{ t('timeRange24h') }}</option>
                <option value="7d">{{ t('timeRange7d') }}</option>
                <option value="30d">{{ t('timeRange30d') }}</option>
              </select>
            </label>
            <label class="inline-flex items-center gap-3 rounded-full bg-white/80 px-4 py-2 ring-1 ring-stone-200/70">
              <span class="text-sm text-stone-500">{{ t('sortBy') }}</span>
              <select
                v-model="selectedSort"
                class="border-0 bg-transparent pr-6 text-sm font-medium text-stone-900 focus:outline-none focus:ring-0"
              >
                <option value="newest">{{ t('sortNewest') }}</option>
                <option value="oldest">{{ t('sortOldest') }}</option>
                <option value="importance">{{ t('sortImportance') }}</option>
                <option value="ai_summary">{{ t('sortAiSummary') }}</option>
              </select>
            </label>
            <button
              @click="showAdvancedFilters = !showAdvancedFilters"
              class="rounded-full bg-white/80 px-4 py-2 text-sm font-medium text-stone-600 ring-1 ring-stone-200/70 transition-colors hover:bg-white"
            >
              {{ showAdvancedFilters ? '\u25B2 ' + t('hideAdvancedFilters') : '\u25BC ' + t('showAdvancedFilters') }}
            </button>
          </div>

          <!-- Row 2: Advanced filters (toggleable) -->
          <div v-if="showAdvancedFilters" class="flex flex-wrap items-center gap-3">
            <label class="inline-flex items-center gap-3 rounded-full bg-white/80 px-4 py-2 ring-1 ring-stone-200/70">
              <span class="text-sm text-stone-500">{{ t('modelFilter') }}</span>
              <select
                v-model="selectedModel"
                class="border-0 bg-transparent pr-6 text-sm font-medium text-stone-900 focus:outline-none focus:ring-0"
              >
                <option value="">{{ t('all') }}</option>
                <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
              </select>
            </label>
            <label class="inline-flex items-center gap-3 rounded-full bg-white/80 px-4 py-2 ring-1 ring-stone-200/70">
              <span class="text-sm text-stone-500">{{ t('summarySource') }}</span>
              <select
                v-model="selectedSummarySource"
                class="border-0 bg-transparent pr-6 text-sm font-medium text-stone-900 focus:outline-none focus:ring-0"
              >
                <option value="">{{ t('all') }}</option>
                <option v-for="source in summarySources" :key="source" :value="source">
                  {{ summarySourceLabel(source) }}
                </option>
              </select>
            </label>
            <label class="inline-flex items-center gap-3 rounded-full bg-white/80 px-4 py-2 ring-1 ring-stone-200/70">
              <span class="text-sm text-stone-500">{{ t('recoveryMode') }}</span>
              <select
                v-model="selectedRecoveryMode"
                class="border-0 bg-transparent pr-6 text-sm font-medium text-stone-900 focus:outline-none focus:ring-0"
              >
                <option value="">{{ t('all') }}</option>
                <option v-for="mode in recoveryModes" :key="mode" :value="mode">
                  {{ recoveryModeLabel(mode) }}
                </option>
              </select>
            </label>
            <label class="inline-flex items-center gap-3 rounded-full bg-white/80 px-4 py-2 ring-1 ring-stone-200/70">
              <span class="text-sm text-stone-500">{{ t('memoryTier') }}</span>
              <select
                v-model="selectedMemoryTier"
                class="border-0 bg-transparent pr-6 text-sm font-medium text-stone-900 focus:outline-none focus:ring-0"
              >
                <option value="">{{ t('all') }}</option>
                <option v-for="tier in memoryTiers" :key="tier" :value="tier">{{ memoryTierLabel(tier) }}</option>
              </select>
            </label>
            <label class="inline-flex items-center gap-3 rounded-full bg-white/80 px-4 py-2 ring-1 ring-stone-200/70">
              <span class="text-sm text-stone-500">{{ t('density') }}</span>
              <select
                v-model="selectedDensity"
                class="border-0 bg-transparent pr-6 text-sm font-medium text-stone-900 focus:outline-none focus:ring-0"
              >
                <option value="comfortable">{{ t('densityComfortable') }}</option>
                <option value="compact">{{ t('densityCompact') }}</option>
              </select>
            </label>
          </div>

          <!-- Row 3: Status + Actions (always visible, but less prominent) -->
          <div class="flex flex-wrap items-center gap-3">
            <div class="rounded-full bg-white/80 px-4 py-2 text-sm text-stone-600 ring-1 ring-stone-200/70">
              {{ t('visibleCount', { count: filteredConversations.length }) }}
              <span v-if="conversations.length > 0">
                · {{ t('loadedCount', { loaded: conversations.length, total: totalAvailable || conversations.length }) }}
              </span>
            </div>
            <button
              @click="summarizeVisibleConversations"
              :disabled="loading || summarizing || filteredConversations.length === 0"
              class="rounded-full bg-stone-900 px-3 py-1.5 text-xs font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
            >
              {{ summarizing ? t('summarizingVisible') : t('summarizeVisible') }}
            </button>
            <button
              @click="summarizeUnreadableConversations"
              :disabled="loading || summarizing || filteredConversations.length === 0"
              class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50 disabled:opacity-50"
            >
              {{ summarizing ? t('summarizingVisible') : t('summarizeUnreadable') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="memory-panel rounded-[28px] p-8 text-sm text-stone-500">{{ t('loadingConversations') }}</div>

    <div v-if="!loading && statusMessage" class="rounded-[28px] border border-emerald-200 bg-emerald-50 p-5 text-sm text-emerald-700">
      {{ statusMessage }}
    </div>

    <div v-else-if="error" class="rounded-[28px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
      {{ error }}
    </div>

    <div v-else-if="filteredConversations.length === 0" class="memory-panel rounded-[28px] p-10 text-center">
      <div class="text-sm uppercase tracking-[0.22em] text-stone-400">{{ t('emptyState') }}</div>
      <div class="mt-3 text-2xl font-semibold text-stone-900">{{ t('noConversationsFound') }}</div>
      <p class="mx-auto mt-3 max-w-md text-sm leading-6 text-stone-500">
        {{ t('syncHint') }}
      </p>
    </div>

    <div v-else class="memory-thread-list-wrap">
      <div class="memory-thread-list">
        <router-link
          v-for="conv in renderedConversations"
          :key="conv.id"
          :to="`/conversations/${conv.id}`"
          :class="[
            'memory-thread-row group',
            selectedDensity === 'compact' ? 'py-4' : '',
          ]"
        >
          <div class="memory-thread-main">
            <div class="flex flex-wrap items-center gap-2">
              <span>{{ platformEmoji(conv.platform) }}</span>
              <span :class="['memory-badge', platformClass(conv.platform)]">{{ conv.platform }}</span>
              <span class="memory-badge bg-stone-100 text-stone-600">
                {{ assistantLabel(conv) }}
              </span>
              <span :class="['memory-badge', summarySourceClass(conv.summary_source)]">
                {{ summarySourceLabel(conv.summary_source) }}
              </span>
              <span :class="['memory-badge', memoryTierClass(conv.memory_tier)]">
                {{ memoryTierLabel(conv.memory_tier) }}
              </span>
              <span
                v-if="conv.platform === 'antigravity'"
                :class="['memory-badge', recoveryModeClass(conv.recovery_mode)]"
              >
                {{ recoveryModeLabel(conv.recovery_mode) }}
              </span>
            </div>

            <h3 class="memory-thread-title">
              {{ displayTitle(conv) }}
            </h3>

            <p
              class="memory-thread-preview"
              :class="selectedDensity === 'compact' ? 'max-h-[3.2rem] overflow-hidden text-[13px] leading-6' : ''"
            >
              {{ displayPreview(conv) }}
            </p>

            <div :class="['flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-400', selectedDensity === 'compact' ? 'mt-1.5' : 'mt-2']">
              <span v-if="conv.project">
                {{ t('originalProject') }}: {{ conv.project }}
              </span>
              <span>
              {{ t('sourceModel') }}: {{ modelLabel(conv) }}
              </span>
            </div>
          </div>

          <div class="memory-thread-side">
            <div class="rounded-full bg-stone-100 px-3 py-1.5 text-xs font-medium text-stone-600">
              {{ formatTime(conv.timestamp) }}
            </div>
            <div class="rounded-full bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-900">
              {{ t('importance') }} {{ conv.importance ?? '-' }}
            </div>
          </div>
        </router-link>
      </div>

      <div
        v-if="renderedConversations.length < filteredConversations.length || hasMoreFromApi"
        ref="loadMoreSentinel"
        class="mt-5 flex justify-center"
      >
        <div class="rounded-full bg-white px-5 py-2.5 text-sm text-stone-500 ring-1 ring-stone-200/80">
          {{
            autoLoadingMore || loadingMoreFromApi
              ? t('loadingMoreConversations')
              : t('loadMoreHint', {
                  count: Math.max(
                    1,
                    Math.min(
                      pageSize,
                      renderedConversations.length < filteredConversations.length
                        ? filteredConversations.length - renderedConversations.length
                        : totalAvailable - conversations.length
                    )
                  ),
                })
          }}
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/memory-hub.js'
import { platformEmoji, platformClass } from '../constants/platforms.js'
import { useI18n } from '../composables/useI18n.js'

const pageSize = 40
const summaryBatchSize = 8
const backendPageSize = 50
const route = useRoute()
const router = useRouter()
const conversations = ref([])
const platforms = ref([])
const models = ref([])
const summarySources = ref([])
const recoveryModes = ref([])
const memoryTiers = ref(['temporary', 'saved', 'pinned'])
const selectedPlatform = ref('')
const selectedModel = ref('')
const selectedSummarySource = ref('')
const selectedRecoveryMode = ref('')
const selectedMemoryTier = ref('')
const selectedTimeRange = ref('all')
const selectedSort = ref('newest')
const selectedDensity = ref('comfortable')
const quickFilter = ref('')
const showAdvancedFilters = ref(false)
const loading = ref(true)
const error = ref(null)
const summarizing = ref(false)
const statusMessage = ref('')
const aiAvailable = ref(false)
const aiProvider = ref('')
const visibleLimit = ref(pageSize)
const loadMoreSentinel = ref(null)
const autoLoadingMore = ref(false)
const totalAvailable = ref(0)
const loadingMoreFromApi = ref(false)
const hasMoreFromApi = ref(false)
let loadMoreObserver = null
let filterReloadTimer = null
let suppressQuerySync = false
let suppressRouteReload = false
const { t, formatDateTime } = useI18n()

const summaryModeLabel = computed(() => (
  aiAvailable.value
    ? t('aiSummaryMode', { provider: aiProvider.value || 'AI' })
    : t('fallbackSummaryMode')
))

const filteredConversations = computed(() => {
  return conversations.value
})

const renderedConversations = computed(() => (
  filteredConversations.value.slice(0, visibleLimit.value)
))

function formatTime(ts) {
  return formatDateTime(ts)
}

function firstLine(summary) {
  return String(summary || '').split('\n')[0].trim()
}

function secondarySummary(summary) {
  return String(summary || '').replace(/\s+/g, ' ').trim()
}

function compactSentence(text, maxLength = 72) {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim()
  if (!normalized) return ''

  const sentence = normalized.split(/(?<=[。！？!?\.])\s+/)[0]?.trim() || normalized
  if (sentence.length <= maxLength) {
    return sentence
  }
  return `${sentence.slice(0, maxLength - 1).trim()}…`
}

function assistantLabel(conv) {
  return conv.assistant_label || conv.model || conv.provider || t('assistant')
}

function summarySourceLabel(source) {
  if (source === 'ai') return t('summarySourceAi')
  if (source === 'imported') return t('summarySourceImported')
  if (!source) return t('summarySourceUnknown')
  return t('summarySourceFallback')
}

function summarySourceClass(source) {
  if (source === 'ai') {
    return 'bg-emerald-100 text-emerald-800'
  }
  if (source === 'imported') {
    return 'bg-sky-100 text-sky-800'
  }
  if (!source) {
    return 'bg-stone-100 text-stone-500'
  }
  return 'bg-stone-100 text-stone-600'
}

function recoveryModeLabel(mode) {
  const normalized = String(mode || '').trim().toLowerCase()
  if (!normalized) return t('recoveryModeUnknown')
  if (normalized === 'live-rpc') return t('recoveryModeLiveRpc')
  if (normalized === 'live-rpc-summary-fallback') return t('recoveryModeLiveRpcSummaryFallback')
  if (normalized === 'pb-undecoded') return t('recoveryModePbUndecoded')
  return normalized
}

function recoveryModeClass(mode) {
  const normalized = String(mode || '').trim().toLowerCase()
  if (normalized === 'live-rpc') {
    return 'bg-emerald-100 text-emerald-800'
  }
  if (normalized === 'live-rpc-summary-fallback') {
    return 'bg-amber-100 text-amber-900'
  }
  if (normalized === 'pb-undecoded') {
    return 'bg-rose-100 text-rose-800'
  }
  return 'bg-stone-100 text-stone-600'
}

function memoryTierLabel(tier) {
  const normalized = String(tier || '').trim().toLowerCase()
  if (normalized === 'saved') return t('memoryTierSaved')
  if (normalized === 'pinned') return t('memoryTierPinned')
  return t('memoryTierTemporary')
}

function memoryTierClass(tier) {
  const normalized = String(tier || '').trim().toLowerCase()
  if (normalized === 'saved') {
    return 'bg-sky-100 text-sky-800'
  }
  if (normalized === 'pinned') {
    return 'bg-amber-100 text-amber-900'
  }
  return 'bg-stone-100 text-stone-600'
}

function modelLabel(conv) {
  return conv.model || conv.provider || t('noModelInfo')
}

function displayTitle(conv) {
  const titleCandidate = firstLine(conv.summary) || conv.project || ''
  return compactSentence(titleCandidate, 64) || t('noSummaryYet')
}

function displayPreview(conv) {
  const normalized = secondarySummary(conv.summary)
  const title = displayTitle(conv)
  if (!normalized) {
    return t('noOverviewYet')
  }
  if (normalized === title) {
    return conv.project && conv.project !== title ? conv.project : t('noOverviewYet')
  }
  return normalized
}

function normalizeRouteValue(value) {
  return Array.isArray(value) ? String(value[0] || '') : String(value || '')
}

function applyQueryState(query) {
  suppressQuerySync = true
  selectedPlatform.value = normalizeRouteValue(query.platform)
  selectedModel.value = normalizeRouteValue(query.model)
  selectedSummarySource.value = normalizeRouteValue(query.summary_source)
  selectedRecoveryMode.value = normalizeRouteValue(query.recovery_mode)
  selectedMemoryTier.value = normalizeRouteValue(query.memory_tier)
  selectedTimeRange.value = normalizeRouteValue(query.time_range) || 'all'
  selectedSort.value = normalizeRouteValue(query.sort) || 'newest'
  selectedDensity.value = normalizeRouteValue(query.density) || 'comfortable'
  quickFilter.value = normalizeRouteValue(query.q)
  suppressQuerySync = false
}

async function syncQueryState() {
  if (suppressQuerySync) {
    return
  }

  const nextQuery = {
    ...route.query,
    platform: selectedPlatform.value || undefined,
    model: selectedModel.value || undefined,
    summary_source: selectedSummarySource.value || undefined,
    recovery_mode: selectedRecoveryMode.value || undefined,
    memory_tier: selectedMemoryTier.value || undefined,
    time_range: selectedTimeRange.value !== 'all' ? selectedTimeRange.value : undefined,
    sort: selectedSort.value !== 'newest' ? selectedSort.value : undefined,
    density: selectedDensity.value !== 'comfortable' ? selectedDensity.value : undefined,
    q: quickFilter.value.trim() || undefined,
  }

  suppressRouteReload = true
  await router.replace({ path: route.path, query: nextQuery })
  suppressRouteReload = false
}

function looksUnreadable(conv) {
  const summary = String(conv.summary || '').trim()
  const project = String(conv.project || '').trim()
  if (!summary) {
    return true
  }

  const first = firstLine(summary)
  const normalized = first.toLowerCase()
  const projectNormalized = project.toLowerCase()

  if (projectNormalized && normalized === projectNormalized) {
    return true
  }
  if (/^(rollout|agent)-[\w-]{6,}$/i.test(first)) {
    return true
  }
  if (/^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(first)) {
    return true
  }
  return first.length < 8 && !/\s/.test(first)
}

function chunkArray(items, size) {
  const chunks = []
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size))
  }
  return chunks
}

async function resummarizeInBatches(ids, force = false) {
  let updatedCount = 0
  for (const chunk of chunkArray(ids, summaryBatchSize)) {
    const result = await api.resummarizeConversations({
      conversation_ids: chunk,
      force,
    })
    updatedCount += result.updated_count ?? 0
  }
  return updatedCount
}

function loadMore() {
  visibleLimit.value += pageSize
}

async function fetchConversationPage({ reset = false } = {}) {
  if (loadingMoreFromApi.value) {
    return
  }

  if (reset) {
    loading.value = true
    conversations.value = []
    totalAvailable.value = 0
    hasMoreFromApi.value = false
    visibleLimit.value = pageSize
  } else {
    loadingMoreFromApi.value = true
  }

  error.value = null

  try {
    const result = await api.listConversations({
      hours: {
        all: 24 * 365 * 20,
        '24h': 24,
        '7d': 24 * 7,
        '30d': 24 * 30,
      }[selectedTimeRange.value] ?? 24 * 365 * 20,
      platform: selectedPlatform.value || undefined,
      model: selectedModel.value || undefined,
      summary_source: selectedSummarySource.value || undefined,
      recovery_mode: selectedRecoveryMode.value || undefined,
      memory_tier: selectedMemoryTier.value || undefined,
      q: quickFilter.value.trim() || undefined,
      sort: selectedSort.value,
      limit: backendPageSize,
      offset: reset ? 0 : conversations.value.length,
    })
    const nextItems = result.conversations || result || []
    conversations.value = reset ? nextItems : [...conversations.value, ...nextItems]
    totalAvailable.value = Number(result.total ?? conversations.value.length)
    hasMoreFromApi.value = Boolean(result.has_more)
  } catch (e) {
    error.value = t('failedToLoadConversations', { message: e.message })
  } finally {
    loading.value = false
    loadingMoreFromApi.value = false
  }
}

async function loadFilterOptions() {
  try {
    const result = await api.getConversationFilters()
    platforms.value = result.platforms || []
    models.value = result.models || []
    summarySources.value = result.summary_sources || []
    recoveryModes.value = result.recovery_modes || []
    memoryTiers.value = result.memory_tiers || ['temporary', 'saved', 'pinned']
  } catch (_) {
    // Keep current options if the metadata endpoint is temporarily unavailable.
  }
}

function setupLoadMoreObserver() {
  if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') {
    return
  }

  loadMoreObserver?.disconnect()
  loadMoreObserver = new IntersectionObserver((entries) => {
    const entry = entries[0]
    if (!entry?.isIntersecting) {
      return
    }
    if (loading.value || loadingMoreFromApi.value || summarizing.value) {
      return
    }
    autoLoadingMore.value = true
    if (renderedConversations.value.length < filteredConversations.value.length) {
      loadMore()
    } else if (hasMoreFromApi.value) {
      fetchConversationPage()
    }
    window.setTimeout(() => {
      autoLoadingMore.value = false
    }, 120)
  }, {
    rootMargin: '200px 0px',
  })

  if (loadMoreSentinel.value) {
    loadMoreObserver.observe(loadMoreSentinel.value)
  }
}

async function loadConversations() {
  await fetchConversationPage({ reset: true })
}

async function loadAIStatus() {
  try {
    const status = await api.getAIStatus()
    aiAvailable.value = Boolean(status.available)
    aiProvider.value = status.provider || ''
  } catch (_) {
    aiAvailable.value = false
    aiProvider.value = ''
  }
}

async function summarizeVisibleConversations() {
  summarizing.value = true
  error.value = null
  statusMessage.value = ''
  try {
    const ids = filteredConversations.value.map((item) => item.id)
    const updatedCount = await resummarizeInBatches(ids, false)
    await loadConversations()
    statusMessage.value = t('summarizeVisibleDone', { count: updatedCount })
  } catch (e) {
    error.value = t('summarizeVisibleFailed', { message: e.message })
  } finally {
    summarizing.value = false
  }
}

async function summarizeUnreadableConversations() {
  summarizing.value = true
  error.value = null
  statusMessage.value = ''
  try {
    const ids = filteredConversations.value.filter(looksUnreadable).map((item) => item.id)
    const updatedCount = await resummarizeInBatches(ids, false)
    await loadConversations()
    statusMessage.value = t('summarizeUnreadableDone', { count: updatedCount })
  } catch (e) {
    error.value = t('summarizeVisibleFailed', { message: e.message })
  } finally {
    summarizing.value = false
  }
}

onMounted(async () => {
  applyQueryState(route.query)
  await Promise.all([loadConversations(), loadAIStatus(), loadFilterOptions()])
  setupLoadMoreObserver()
})

watch(
  [selectedPlatform, selectedModel, selectedSummarySource, selectedRecoveryMode, selectedMemoryTier, selectedTimeRange, selectedSort, quickFilter],
  () => {
    if (suppressQuerySync) {
      return
    }
    visibleLimit.value = pageSize
    syncQueryState()
    if (filterReloadTimer) {
      window.clearTimeout(filterReloadTimer)
    }
    filterReloadTimer = window.setTimeout(() => {
      loadConversations()
    }, 180)
  }
)

watch(selectedDensity, () => {
  syncQueryState()
})

watch([renderedConversations, filteredConversations, loadMoreSentinel, hasMoreFromApi], () => {
  setupLoadMoreObserver()
})

watch(() => route.query, (query) => {
  if (suppressRouteReload) return
  applyQueryState(query)
  if (filterReloadTimer) {
    window.clearTimeout(filterReloadTimer)
  }
  loadConversations()
}, { deep: true })

onBeforeUnmount(() => {
  loadMoreObserver?.disconnect()
  if (filterReloadTimer) {
    window.clearTimeout(filterReloadTimer)
  }
})
</script>
