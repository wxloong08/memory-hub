<template>
  <section class="space-y-5">
    <!-- Page header -->
    <div class="rounded-[26px] border border-stone-200/60 bg-[rgba(255,253,248,0.56)] p-5 shadow-[0_8px_24px_rgba(71,52,31,0.035)] lg:p-6">
      <div class="text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-400">{{ t('navSwitch') }}</div>
      <h2 class="mt-2 text-[2rem] font-semibold tracking-tight text-stone-900">{{ t('switchTitle') }}</h2>
      <p class="mt-3 max-w-2xl text-sm leading-7 text-stone-600">
        {{ t('switchDescription') }}
      </p>
    </div>

    <!-- Three-panel layout -->
    <div class="grid gap-5 xl:grid-cols-3">

      <!-- ==================== Left Panel: Context Selection ==================== -->
      <div class="space-y-4">
        <!-- Recent conversations -->
        <div class="memory-panel rounded-[24px] p-5">
          <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('switchContextSelection') }}</div>
          <h3 class="mt-2 text-lg font-semibold text-stone-900">{{ t('switchRecentConversations') }}</h3>
          <p class="mt-2 text-sm text-stone-500">{{ t('switchSelectConversations') }}</p>

          <div v-if="loadingConversations" class="mt-4 text-sm text-stone-400">{{ t('loading') }}</div>
          <div v-else-if="conversations.length === 0" class="mt-4 text-sm text-stone-400">{{ t('noConversationsFound') }}</div>
          <div v-else class="mt-4 max-h-[320px] space-y-2 overflow-y-auto pr-1">
            <label
              v-for="conv in conversations"
              :key="conv.id"
              class="flex cursor-pointer items-start gap-3 rounded-2xl px-3 py-3 transition-colors hover:bg-white/70"
              :class="selectedConversationIds.has(conv.id) ? 'bg-white/80 ring-1 ring-stone-200/70' : ''"
            >
              <input
                type="checkbox"
                :checked="selectedConversationIds.has(conv.id)"
                @change="toggleConversation(conv.id)"
                class="mt-1 h-4 w-4 rounded border-stone-300 text-stone-900 focus:ring-stone-500"
              />
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-base">{{ platformEmoji(conv.platform) }}</span>
                  <span class="truncate text-sm font-medium text-stone-800">
                    {{ conv.summary || conv.ai_summary || t('noSummaryYet') }}
                  </span>
                </div>
                <div class="mt-1 text-xs text-stone-400">
                  {{ conv.platform }} · {{ formatDateTime(conv.timestamp || conv.started_at) }}
                </div>
              </div>
            </label>
          </div>
        </div>

        <!-- Quick Notes -->
        <div class="memory-panel rounded-[24px] p-5">
          <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('switchQuickNotes') }}</div>
          <h3 class="mt-2 text-lg font-semibold text-stone-900">{{ t('switchCustomContext') }}</h3>
          <textarea
            v-model="customContext"
            :placeholder="t('switchCustomContextPlaceholder')"
            class="mt-3 w-full rounded-2xl border-0 bg-white/70 px-4 py-3 text-sm text-stone-800 ring-1 ring-stone-200/70 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-400"
            rows="4"
          ></textarea>
        </div>

        <!-- Workspace Path -->
        <div class="memory-panel rounded-[24px] p-5">
          <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('workspacePath') }}</div>
          <input
            v-model="workspacePath"
            type="text"
            :placeholder="t('workspacePathPlaceholder')"
            class="mt-3 w-full rounded-2xl border-0 bg-white/70 px-4 py-3 text-sm text-stone-800 ring-1 ring-stone-200/70 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-400"
          />
        </div>
      </div>

      <!-- ==================== Middle Panel: Context Preview ==================== -->
      <div class="space-y-4">
        <div class="memory-panel rounded-[24px] p-5">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('switchPreview') }}</div>
              <h3 class="mt-2 text-lg font-semibold text-stone-900">{{ t('switchContextPreview') }}</h3>
            </div>
            <button
              @click="refreshPreview"
              :disabled="previewLoading || !targetCli || !workspacePath.trim()"
              class="rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
            >
              {{ previewLoading ? t('loading') : t('switchRefreshPreview') }}
            </button>
          </div>

          <!-- Token counter -->
          <div v-if="previewContent" class="mt-4 flex items-center gap-3">
            <div class="rounded-full bg-white/80 px-4 py-2 text-sm text-stone-600 ring-1 ring-stone-200/70">
              {{ t('switchTokenCount', { tokens: previewTokens, budget: tokenBudgetDisplay }) }}
            </div>
            <div
              v-if="previewTokens > 0 && tokenBudgetDisplay > 0"
              class="h-2 flex-1 overflow-hidden rounded-full bg-stone-200"
            >
              <div
                class="h-full rounded-full transition-all"
                :class="tokenRatio > 0.9 ? 'bg-rose-500' : tokenRatio > 0.7 ? 'bg-amber-500' : 'bg-emerald-500'"
                :style="{ width: Math.min(tokenRatio * 100, 100) + '%' }"
              ></div>
            </div>
          </div>

          <!-- Preview textarea -->
          <textarea
            v-model="previewContent"
            :placeholder="t('switchPreviewPlaceholder')"
            class="mt-4 w-full rounded-2xl border-0 bg-white/70 px-4 py-3 font-mono text-xs leading-5 text-stone-700 ring-1 ring-stone-200/70 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-400"
            rows="22"
          ></textarea>

          <p v-if="previewError" class="mt-3 text-sm text-rose-600">{{ previewError }}</p>
        </div>
      </div>

      <!-- ==================== Right Panel: Target & Execute ==================== -->
      <div class="space-y-4">
        <!-- CLI selectors -->
        <div class="memory-panel rounded-[24px] p-5">
          <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('switchCliConfig') }}</div>
          <h3 class="mt-2 text-lg font-semibold text-stone-900">{{ t('switchTargetExecute') }}</h3>

          <!-- Source CLI -->
          <div class="mt-4">
            <label class="text-xs font-medium text-stone-500">{{ t('switchSourceCli') }}</label>
            <select
              v-model="sourceCli"
              class="mt-1.5 w-full rounded-2xl border-0 bg-white/70 px-4 py-3 text-sm text-stone-800 ring-1 ring-stone-200/70 focus:outline-none focus:ring-2 focus:ring-stone-400"
            >
              <option value="">{{ t('none') }}</option>
              <option v-for="cli in cliOptions" :key="cli.value" :value="cli.value">
                {{ cli.emoji }} {{ cli.label }}
              </option>
            </select>
          </div>

          <!-- Target CLI -->
          <div class="mt-4">
            <label class="text-xs font-medium text-stone-500">{{ t('switchTargetCli') }}</label>
            <select
              v-model="targetCli"
              class="mt-1.5 w-full rounded-2xl border-0 bg-white/70 px-4 py-3 text-sm text-stone-800 ring-1 ring-stone-200/70 focus:outline-none focus:ring-2 focus:ring-stone-400"
            >
              <option value="">{{ t('switchSelectTarget') }}</option>
              <option v-for="cli in cliOptions" :key="cli.value" :value="cli.value">
                {{ cli.emoji }} {{ cli.label }}
              </option>
            </select>
          </div>

          <!-- Token budget -->
          <div class="mt-4 rounded-2xl bg-white/70 px-4 py-3 ring-1 ring-stone-200/70">
            <div class="text-xs text-stone-400">{{ t('switchTokenBudget') }}</div>
            <div class="mt-1 text-lg font-semibold text-stone-800">
              {{ tokenBudgetDisplay > 0 ? tokenBudgetDisplay.toLocaleString() : '--' }}
            </div>
          </div>

          <!-- Execute button -->
          <button
            @click="executeSwitch"
            :disabled="executing || !targetCli || !workspacePath.trim()"
            class="mt-5 w-full rounded-2xl bg-stone-900 px-5 py-3.5 text-sm font-semibold text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
          >
            {{ executing ? t('switchExecuting') : t('switchGenerateContext') }}
          </button>

          <!-- Success message -->
          <div v-if="switchResult" class="mt-4 rounded-2xl bg-emerald-50 px-4 py-4 ring-1 ring-emerald-200/70">
            <div class="text-sm font-medium text-emerald-800">{{ t('switchSuccess') }}</div>
            <div class="mt-2 break-all font-mono text-xs text-emerald-700">{{ switchResult.target_file }}</div>
            <div v-if="switchResult.warning" class="mt-2 text-xs text-amber-700">{{ switchResult.warning }}</div>
            <div class="mt-2 text-xs text-emerald-600">
              {{ t('switchResultStats', {
                tokens: switchResult.context_assembled?.total_tokens || 0,
                core: switchResult.core_memories_injected || 0,
                archive: switchResult.archive_turns_injected || 0,
              }) }}
            </div>
          </div>

          <!-- Error message -->
          <p v-if="switchError" class="mt-3 text-sm text-rose-600">{{ switchError }}</p>
        </div>

        <!-- Switch History -->
        <div class="memory-panel rounded-[24px] p-5">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('switchHistory') }}</div>
              <h3 class="mt-2 text-lg font-semibold text-stone-900">{{ t('switchRecentSwitches') }}</h3>
            </div>
            <button
              @click="loadHistory"
              class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-600 ring-1 ring-stone-200 transition-colors hover:bg-stone-50"
            >
              {{ t('refresh') }}
            </button>
          </div>

          <div v-if="historyLoading" class="mt-4 text-sm text-stone-400">{{ t('loading') }}</div>
          <div v-else-if="history.length === 0" class="mt-4 text-sm text-stone-400">{{ t('switchNoHistory') }}</div>
          <div v-else class="mt-4 max-h-[260px] space-y-2 overflow-y-auto pr-1">
            <div
              v-for="event in history"
              :key="event.id"
              class="rounded-2xl bg-white/70 px-4 py-3 ring-1 ring-stone-200/70"
            >
              <div class="flex items-center gap-2 text-sm font-medium text-stone-800">
                <span v-if="event.from_cli">{{ platformEmoji(event.from_cli) }} {{ event.from_cli }}</span>
                <span v-if="event.from_cli" class="text-stone-400">&rarr;</span>
                <span>{{ platformEmoji(event.to_cli) }} {{ event.to_cli }}</span>
              </div>
              <div class="mt-1.5 text-xs text-stone-400">
                {{ formatDateTime(event.switched_at) }}
                · {{ event.tokens_injected?.toLocaleString() || 0 }} tokens
                · {{ event.core_memories_count || 0 }} {{ t('switchCoreMemories') }}
              </div>
              <div class="mt-1 truncate text-xs text-stone-400">{{ event.workspace_path }}</div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '../api/memory-hub.js'
import { useI18n } from '../composables/useI18n.js'
import { platformEmoji } from '../constants/platforms.js'

const { t, formatDateTime } = useI18n()

// ── CLI options ──
const cliOptions = [
  { value: 'claude_code', label: 'Claude Code', emoji: '\u26AB' },
  { value: 'codex', label: 'Codex', emoji: '\uD83D\uDFE0' },
  { value: 'gemini_cli', label: 'Gemini CLI', emoji: '\uD83D\uDD39' },
  { value: 'antigravity', label: 'Antigravity', emoji: '\uD83E\uDE90' },
]

// Token budgets by CLI (approximate defaults)
const CLI_TOKEN_BUDGETS = {
  claude_code: 8000,
  codex: 6000,
  gemini_cli: 8000,
  antigravity: 6000,
}

// ── State: Left panel ──
const conversations = ref([])
const loadingConversations = ref(false)
const selectedConversationIds = ref(new Set())
const customContext = ref('')
const workspacePath = ref('')

// ── State: Middle panel ──
const previewContent = ref('')
const previewTokens = ref(0)
const previewLoading = ref(false)
const previewError = ref('')

// ── State: Right panel ──
const sourceCli = ref('')
const targetCli = ref('')
const executing = ref(false)
const switchResult = ref(null)
const switchError = ref('')
const history = ref([])
const historyLoading = ref(false)

// ── Computed ──
const tokenBudgetDisplay = computed(() => {
  return targetCli.value ? (CLI_TOKEN_BUDGETS[targetCli.value] || 6000) : 0
})

const tokenRatio = computed(() => {
  if (tokenBudgetDisplay.value <= 0) return 0
  return previewTokens.value / tokenBudgetDisplay.value
})

// ── Lifecycle ──
onMounted(() => {
  loadConversations()
  loadHistory()
})

// Auto-refresh preview when target CLI changes
watch(targetCli, (val) => {
  if (val && workspacePath.value) {
    refreshPreview()
  }
})

// ── Methods ──
async function loadConversations() {
  loadingConversations.value = true
  try {
    const data = await api.listConversations({ limit: 20 })
    const list = data.conversations || data || []
    conversations.value = list
    // Pre-select the most recent conversation
    if (list.length > 0) {
      selectedConversationIds.value = new Set([list[0].id])
    }
  } catch {
    conversations.value = []
  } finally {
    loadingConversations.value = false
  }
}

function toggleConversation(id) {
  const next = new Set(selectedConversationIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  selectedConversationIds.value = next
}

async function refreshPreview() {
  if (!targetCli.value || !workspacePath.value.trim()) return
  previewLoading.value = true
  previewError.value = ''
  try {
    const data = await api.switchPreview({
      to_cli: targetCli.value,
      workspace_path: workspacePath.value.trim(),
      token_budget: tokenBudgetDisplay.value || undefined,
      conversation_ids: [...selectedConversationIds.value],
      custom_context: customContext.value.trim() || undefined,
    })
    previewContent.value = data.content || data.content_preview || ''
    previewTokens.value = data.context_assembled?.total_tokens || 0
  } catch (err) {
    previewError.value = t('switchPreviewFailed', { message: err.response?.data?.detail || err.message })
    previewContent.value = ''
    previewTokens.value = 0
  } finally {
    previewLoading.value = false
  }
}

async function executeSwitch() {
  if (!targetCli.value || !workspacePath.value.trim()) return
  executing.value = true
  switchError.value = ''
  switchResult.value = null
  try {
    const data = await api.executeSwitch({
      to_cli: targetCli.value,
      workspace_path: workspacePath.value.trim(),
      from_cli: sourceCli.value || undefined,
      token_budget: tokenBudgetDisplay.value || undefined,
      conversation_ids: [...selectedConversationIds.value],
      custom_context: customContext.value.trim() || undefined,
    })
    switchResult.value = data
    // Refresh history after a successful switch
    loadHistory()
  } catch (err) {
    switchError.value = t('switchExecuteFailed', { message: err.response?.data?.detail || err.message })
  } finally {
    executing.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const data = await api.switchHistory()
    history.value = data.history || []
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}
</script>
