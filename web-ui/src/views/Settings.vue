<template>
  <section class="space-y-6">
    <div class="rounded-[26px] border border-stone-200/60 bg-[rgba(255,253,248,0.56)] p-5 shadow-[0_8px_24px_rgba(71,52,31,0.035)] lg:p-6">
      <div class="text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-400">{{ t('navSettings') }}</div>
      <h2 class="mt-2 text-[2rem] font-semibold tracking-tight text-stone-900">{{ t('settingsTitle') }}</h2>
      <p class="mt-3 max-w-2xl text-sm leading-7 text-stone-600">
        {{ t('settingsDescription') }}
      </p>
    </div>

    <div class="grid gap-4 xl:grid-cols-3">
      <div class="memory-panel rounded-[24px] p-5 xl:col-span-2">
        <div class="flex items-center justify-between gap-4">
          <div>
            <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('backend') }}</div>
            <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('settingsTitle') }}</h3>
          </div>
          <button
            @click="checkConnection"
            :disabled="checkingConnection"
            class="rounded-full bg-white px-4 py-2 text-sm font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50 disabled:opacity-50"
          >
            {{ checkingConnection ? t('checking') : t('refresh') }}
          </button>
        </div>
        <div class="mt-5 flex items-center gap-3 rounded-2xl bg-white/70 px-4 py-4 ring-1 ring-stone-200/70">
          <span :class="connected ? 'bg-emerald-500' : 'bg-rose-500'" class="inline-flex h-3 w-3 rounded-full"></span>
          <span :class="connected ? 'text-emerald-700' : 'text-rose-700'" class="text-sm font-medium">
            {{ connected ? t('connectedToApi') : t('notConnectedToApi') }}
          </span>
        </div>
      </div>

      <div class="memory-panel rounded-[24px] p-5">
        <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('aiMode') }}</div>
        <div class="mt-2 text-xl font-semibold text-stone-900">{{ aiAvailable ? aiProvider : t('fallbackExtraction') }}</div>
        <p class="mt-3 text-sm leading-6 text-stone-500">
          {{ aiAvailable ? t('activeProvider') : t('fallbackProvider') }}
        </p>
        <button
          @click="reloadAI"
          :disabled="reloadingAI || !connected"
          class="mt-4 rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
        >
          {{ reloadingAI ? t('reloading') : t('reloadAI') }}
        </button>
      </div>
    </div>

    <div class="memory-panel rounded-[26px] p-5 lg:p-6">
      <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('providers') }}</div>
      <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('environmentVariables') }}</h3>
      <p class="mt-3 text-sm leading-6 text-stone-500">
        {{ t('envConfigDescription') }}
      </p>
      <p v-if="aiMessage" class="mt-3 text-xs text-stone-500">{{ aiMessage }}</p>
      <div class="mt-5 grid gap-3">
        <div
          v-for="provider in providers"
          :key="provider.name"
          class="flex flex-col gap-2 rounded-2xl bg-white/70 px-4 py-4 ring-1 ring-stone-200/70 sm:flex-row sm:items-center sm:justify-between"
        >
          <div class="text-sm font-medium text-stone-800">{{ provider.name }}</div>
          <div class="text-xs font-mono text-stone-500">{{ provider.envVar }}</div>
          <span class="memory-badge bg-stone-100 text-stone-600">{{ t('envOnly') }}</span>
        </div>
      </div>
    </div>

    <div class="memory-panel rounded-[26px] p-5 lg:p-6">
      <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('localImport') }}</div>
      <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('localImportTitle') }}</h3>
      <p class="mt-3 text-sm leading-6 text-stone-500">
        {{ t('localImportDescription') }}
      </p>
      <p class="mt-3 text-xs leading-6 text-stone-500">
        {{ t('importHint') }}
      </p>

      <div class="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_180px_auto]">
        <label class="space-y-2">
          <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('importSource') }}</span>
          <select
            v-model="importForm.source"
            class="w-full rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
          >
            <option v-for="option in importSourceOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="space-y-2">
          <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('importLimit') }}</span>
          <input
            v-model.number="importForm.limit"
            type="number"
            min="1"
            max="200"
            class="w-full rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
          />
        </label>

        <div class="flex flex-col justify-end gap-3">
          <label class="flex items-center gap-2 text-sm text-stone-600">
            <input v-model="importForm.dryRun" type="checkbox" class="h-4 w-4 rounded border-stone-300 text-stone-900 focus:ring-stone-400" />
            <span>{{ t('dryRun') }}</span>
          </label>
          <button
            @click="runLocalImport"
            :disabled="importingLocal || !connected"
            class="rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
          >
            {{ importingLocal ? t('importing') : t('importNow') }}
          </button>
        </div>
      </div>

      <p v-if="importMessage" class="mt-4 text-sm text-stone-600">{{ importMessage }}</p>

      <div class="mt-5 rounded-[20px] bg-stone-950 p-4 text-xs leading-6 text-stone-100">
        <pre v-if="importResult" class="overflow-x-auto whitespace-pre-wrap">{{ importResult }}</pre>
        <div v-else class="text-stone-400">{{ t('noImportResult') }}</div>
      </div>
    </div>

    <div class="memory-panel rounded-[26px] p-5 lg:p-6">
      <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('backupExport') }}</div>
      <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('backupExportTitle') }}</h3>
      <p class="mt-3 text-sm leading-6 text-stone-500">
        {{ t('backupExportDescription') }}
      </p>
      <div class="mt-5 flex items-center gap-3">
        <button
          @click="runBackup"
          :disabled="backingUp || !connected"
          class="rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
        >
          {{ backingUp ? t('backingUp') : t('backupNow') }}
        </button>
      </div>

      <p v-if="backupMessage" class="mt-4 text-sm text-stone-600">{{ backupMessage }}</p>

      <div class="mt-5 rounded-[20px] bg-stone-950 p-4 text-xs leading-6 text-stone-100">
        <pre v-if="backupResult" class="overflow-x-auto whitespace-pre-wrap">{{ backupResult }}</pre>
        <div v-else class="text-stone-400">{{ t('noBackupResult') }}</div>
      </div>
    </div>

    <div class="memory-panel rounded-[26px] p-5 lg:p-6">
      <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('autoBackup') }}</div>
      <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('autoBackup') }}</h3>
      <p class="mt-3 text-sm leading-6 text-stone-500">
        {{ t('autoBackupDescription') }}
      </p>

      <div class="mt-5 grid gap-4 lg:grid-cols-[auto_180px_180px_auto]">
        <label class="flex items-center gap-2 text-sm text-stone-600">
          <input v-model="backupSettings.enabled" type="checkbox" class="h-4 w-4 rounded border-stone-300 text-stone-900 focus:ring-stone-400" />
          <span>{{ t('autoBackupEnabled') }}</span>
        </label>

        <label class="space-y-2">
          <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('backupIntervalHours') }}</span>
          <input
            v-model.number="backupSettings.interval_hours"
            type="number"
            min="1"
            max="720"
            class="w-full rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
          />
        </label>

        <label class="space-y-2">
          <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('backupRetentionCount') }}</span>
          <input
            v-model.number="backupSettings.retention_count"
            type="number"
            min="1"
            max="200"
            class="w-full rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
          />
        </label>

        <label class="space-y-2 lg:col-span-2">
          <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('backupRoot') }}</span>
          <input
            v-model="backupSettings.backup_root"
            type="text"
            :placeholder="t('backupRootPlaceholder')"
            class="w-full rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
          />
        </label>

        <div class="flex items-end">
          <button
            @click="saveBackupSettings"
            :disabled="savingBackupSettings || !connected"
            class="rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
          >
            {{ savingBackupSettings ? t('saving') : t('saveBackupSettings') }}
          </button>
        </div>
      </div>

      <p v-if="backupSettingsMessage" class="mt-4 text-sm text-stone-600">{{ backupSettingsMessage }}</p>

      <div class="mt-5 grid gap-4 lg:grid-cols-3">
        <div class="rounded-2xl bg-white/70 px-4 py-4 ring-1 ring-stone-200/70">
          <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('lastRunAt') }}</div>
          <div class="mt-2 text-sm text-stone-800">{{ formatBackupValue(backupSettings.last_run_at) }}</div>
        </div>
        <div class="rounded-2xl bg-white/70 px-4 py-4 ring-1 ring-stone-200/70">
          <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('lastBackupDir') }}</div>
          <div class="mt-2 break-all text-sm text-stone-800">{{ formatBackupValue(backupSettings.last_backup_dir) }}</div>
        </div>
        <div class="rounded-2xl bg-white/70 px-4 py-4 ring-1 ring-stone-200/70">
          <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('lastBackupZip') }}</div>
          <div class="mt-2 break-all text-sm text-stone-800">{{ formatBackupValue(backupSettings.last_backup_zip) }}</div>
        </div>
        <div class="rounded-2xl bg-white/70 px-4 py-4 ring-1 ring-stone-200/70 lg:col-span-3">
          <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('lastError') }}</div>
          <div class="mt-2 break-all text-sm text-stone-800">{{ formatBackupValue(backupSettings.last_error) }}</div>
        </div>
      </div>

      <div class="mt-5 rounded-[20px] bg-stone-950 p-4 text-xs leading-6 text-stone-100">
        <div class="mb-3 text-stone-300">{{ t('backupHistory') }}</div>
        <pre v-if="backupHistory.length" class="overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(backupHistory, null, 2) }}</pre>
        <div v-else class="text-stone-400">{{ t('noBackupsYet') }}</div>
      </div>
    </div>

    <div class="memory-panel rounded-[26px] p-5 lg:p-6">
      <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('restoreBackup') }}</div>
      <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('restoreBackup') }}</h3>
      <p class="mt-3 text-sm leading-6 text-stone-500">
        {{ t('restoreBackupDescription') }}
      </p>

      <div class="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
        <label class="space-y-2">
          <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('restoreSource') }}</span>
          <select
            v-model="selectedRestoreSource"
            class="w-full rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
          >
            <option value=""></option>
            <option v-for="item in restoreSourceOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </label>

        <div class="flex items-end">
          <button
            @click="runRestore"
            :disabled="restoringBackup || !connected || !selectedRestoreSource"
            class="rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
          >
            {{ restoringBackup ? t('restoring') : t('restoreNow') }}
          </button>
        </div>
      </div>

      <p v-if="restoreMessage" class="mt-4 text-sm text-stone-600">{{ restoreMessage }}</p>

      <div class="mt-5 rounded-[20px] bg-stone-950 p-4 text-xs leading-6 text-stone-100">
        <div class="mb-3 text-stone-300">{{ t('backupPreview') }}</div>
        <pre v-if="backupPreview" class="overflow-x-auto whitespace-pre-wrap">{{ backupPreview }}</pre>
        <div v-else class="text-stone-400">{{ previewMessage || t('noPreviewAvailable') }}</div>
      </div>

      <div class="mt-5 rounded-[20px] bg-stone-950 p-4 text-xs leading-6 text-stone-100">
        <div class="mb-3 text-stone-300">{{ t('backupValidation') }}</div>
        <pre v-if="backupValidation" class="overflow-x-auto whitespace-pre-wrap">{{ backupValidation }}</pre>
        <div v-else class="text-stone-400">{{ validationMessage || t('noValidationAvailable') }}</div>
      </div>

      <div class="mt-5 rounded-[20px] bg-stone-950 p-4 text-xs leading-6 text-stone-100">
        <pre v-if="restoreResult" class="overflow-x-auto whitespace-pre-wrap">{{ restoreResult }}</pre>
        <div v-else class="text-stone-400">{{ t('noRestoreResult') }}</div>
      </div>
    </div>

    <div class="memory-panel rounded-[26px] p-5 lg:p-6">
      <div class="flex items-center justify-between gap-4">
        <div>
          <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('data') }}</div>
          <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('rawStatistics') }}</h3>
        </div>
        <button
          @click="viewStats"
          :disabled="loadingStats"
          class="rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
        >
          {{ loadingStats ? t('loading') : t('viewStatistics') }}
        </button>
      </div>

      <div v-if="rawJson" class="mt-5">
        <pre class="max-h-96 overflow-y-auto rounded-[20px] bg-stone-950 p-4 text-xs leading-6 text-stone-100">{{ rawJson }}</pre>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import api from '../api/memory-hub.js'
import { useI18n } from '../composables/useI18n.js'

const connected = ref(false)
const checkingConnection = ref(false)
const loadingStats = ref(false)
const rawJson = ref(null)
const aiAvailable = ref(false)
const aiProvider = ref('Unknown')
const aiMessage = ref('')
const reloadingAI = ref(false)
const importingLocal = ref(false)
const importResult = ref('')
const importMessage = ref('')
const backingUp = ref(false)
const backupResult = ref('')
const backupMessage = ref('')
const savingBackupSettings = ref(false)
const backupSettingsMessage = ref('')
const backupHistory = ref([])
const selectedRestoreSource = ref('')
const restoringBackup = ref(false)
const restoreMessage = ref('')
const restoreResult = ref('')
const backupPreview = ref('')
const previewMessage = ref('')
const backupValidation = ref('')
const validationMessage = ref('')
const backupSettings = ref({
  enabled: false,
  interval_hours: 24,
  retention_count: 10,
  backup_root: '',
  last_run_at: null,
  last_backup_dir: null,
  last_backup_zip: null,
  last_error: '',
})
const { t, formatDateTime } = useI18n()

const importForm = ref({
  source: 'all',
  limit: 20,
  dryRun: false,
})

const importSourceOptions = computed(() => ([
  { value: 'all', label: t('importSourceAll') },
  { value: 'codex', label: t('importSourceCodex') },
  { value: 'claude_code', label: t('importSourceClaudeCode') },
  { value: 'gemini_cli', label: t('importSourceGeminiCli') },
  { value: 'antigravity', label: t('importSourceAntigravity') },
]))

const restoreSourceOptions = computed(() => backupHistory.value.flatMap((item) => {
  const options = [{
    value: item.path,
    label: `${t('restoreSourceDirectory')}: ${item.name}`,
  }]
  if (item.zip_path) {
    options.push({
      value: item.zip_path,
      label: `${t('restoreSourceZip')}: ${item.name}.zip`,
    })
  }
  return options
}))

const providers = [
  { name: 'Claude', envVar: 'AI_CLAUDE_API_KEY' },
  { name: 'DeepSeek', envVar: 'AI_DEEPSEEK_API_KEY' },
  { name: 'OpenAI', envVar: 'AI_OPENAI_API_KEY' },
  { name: 'Qwen', envVar: 'AI_QWEN_API_KEY' },
  { name: 'Kimi', envVar: 'AI_KIMI_API_KEY' },
  { name: 'MiniMax', envVar: 'AI_MINIMAX_API_KEY' },
  { name: 'GLM', envVar: 'AI_GLM_API_KEY' },
]

async function checkConnection() {
  checkingConnection.value = true
  try {
    connected.value = await api.checkHealth()
    if (connected.value) {
      await Promise.allSettled([
        loadAIStatus(),
        loadBackupSettings(),
      ])
    }
  } finally {
    checkingConnection.value = false
  }
}

async function loadAIStatus() {
  try {
    const status = await api.getAIStatus()
    aiAvailable.value = Boolean(status.available)
    aiProvider.value = status.provider || 'Configured'
    aiMessage.value = status.config_path ? t('configPath', { path: status.config_path }) : ''
  } catch (_) {
    aiAvailable.value = false
    aiProvider.value = 'Unknown'
    aiMessage.value = ''
  }
}

async function reloadAI() {
  reloadingAI.value = true
  try {
    const result = await api.reloadAIConfig()
    aiAvailable.value = Boolean(result.available)
    aiProvider.value = result.provider || 'Unknown'
    aiMessage.value = result.available
      ? t('reloadSuccess', { provider: aiProvider.value })
      : t('reloadFallback')
  } catch (e) {
    aiMessage.value = t('reloadFailed', { message: e.message })
  } finally {
    reloadingAI.value = false
  }
}

async function viewStats() {
  loadingStats.value = true
  try {
    const stats = await api.getStats()
    rawJson.value = JSON.stringify(stats, null, 2)
  } catch (e) {
    rawJson.value = t('statsLoadFailed', { message: e.message })
  } finally {
    loadingStats.value = false
  }
}

async function runLocalImport() {
  importingLocal.value = true
  importMessage.value = ''

  try {
    const payload = {
      source: importForm.value.source,
      limit: Math.min(200, Math.max(1, Number(importForm.value.limit) || 20)),
      dry_run: Boolean(importForm.value.dryRun),
    }
    const result = await api.importLocalSessions(payload)
    importResult.value = JSON.stringify(result, null, 2)
    const autoSummary = result.auto_summarize
    if (autoSummary && typeof autoSummary.updated_count === 'number') {
      importMessage.value = autoSummary.ai_available
        ? t('importAutoSummaryDone', { count: autoSummary.updated_count })
        : t('importAutoSummaryFallback')
    } else {
      importMessage.value = t('importCompleted')
    }
  } catch (e) {
    importMessage.value = t('importFailedMessage', { message: e.message })
    importResult.value = ''
  } finally {
    importingLocal.value = false
  }
}

async function runBackup() {
  backingUp.value = true
  backupMessage.value = ''

  try {
    const result = await api.exportBackupBundle()
    backupResult.value = JSON.stringify(result, null, 2)
    backupMessage.value = t('backupCompleted')
    await loadBackupSettings()
  } catch (e) {
    backupMessage.value = t('backupFailedMessage', { message: e.message })
    backupResult.value = ''
  } finally {
    backingUp.value = false
  }
}

async function loadBackupSettings() {
  try {
    const result = await api.getBackupSettings()
    backupSettings.value = {
      ...backupSettings.value,
      ...(result.settings || {}),
    }
    backupHistory.value = result.backups || []
    if (!selectedRestoreSource.value && restoreSourceOptions.value.length) {
      selectedRestoreSource.value = restoreSourceOptions.value[0].value
    }
  } catch (_) {
    backupHistory.value = []
  }
}

async function saveBackupSettings() {
  savingBackupSettings.value = true
  backupSettingsMessage.value = ''

  try {
    const payload = {
      enabled: Boolean(backupSettings.value.enabled),
      interval_hours: Math.min(720, Math.max(1, Number(backupSettings.value.interval_hours) || 24)),
      retention_count: Math.min(200, Math.max(1, Number(backupSettings.value.retention_count) || 10)),
      backup_root: String(backupSettings.value.backup_root || '').trim() || null,
    }
    const result = await api.updateBackupSettings(payload)
    backupSettings.value = {
      ...backupSettings.value,
      ...(result.settings || {}),
    }
    backupHistory.value = result.backups || []
    backupSettingsMessage.value = t('backupSettingsSaved')
  } catch (e) {
    backupSettingsMessage.value = t('backupSettingsFailed', { message: e.message })
  } finally {
    savingBackupSettings.value = false
  }
}

function formatBackupValue(value) {
  if (!value) {
    return '-'
  }
  if (String(value).includes('T') && !Number.isNaN(Date.parse(value))) {
    return formatDateTime(value)
  }
  return String(value)
}

async function runRestore() {
  restoringBackup.value = true
  restoreMessage.value = ''

  try {
    const result = await api.restoreBackupBundle({ source_path: selectedRestoreSource.value })
    restoreResult.value = JSON.stringify(result, null, 2)
    restoreMessage.value = t('restoreCompleted')
    await loadBackupSettings()
    await viewStats()
  } catch (e) {
    restoreMessage.value = t('restoreFailedMessage', { message: e.message })
    restoreResult.value = ''
  } finally {
    restoringBackup.value = false
  }
}

async function loadBackupPreview() {
  backupPreview.value = ''
  previewMessage.value = ''
  backupValidation.value = ''
  validationMessage.value = ''

  if (!selectedRestoreSource.value) {
    return
  }

  previewMessage.value = t('loadingPreview')
  validationMessage.value = t('loadingValidation')
  try {
    const result = await api.previewBackupSource(selectedRestoreSource.value)
    backupPreview.value = JSON.stringify(result, null, 2)
    previewMessage.value = ''
  } catch (e) {
    previewMessage.value = t('previewFailedMessage', { message: e.message })
  }

  try {
    const result = await api.validateBackupSource(selectedRestoreSource.value)
    backupValidation.value = JSON.stringify(result, null, 2)
    validationMessage.value = ''
  } catch (e) {
    validationMessage.value = t('validationFailedMessage', { message: e.message })
  }
}

watch(selectedRestoreSource, () => {
  loadBackupPreview()
})

checkConnection()
</script>
