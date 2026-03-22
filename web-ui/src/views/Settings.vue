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
      <div class="text-[11px] uppercase tracking-[0.18em] text-stone-400">{{ t('memoryCenter') }}</div>
      <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('memoryCenterTitle') }}</h3>
      <p class="mt-3 text-sm leading-6 text-stone-500">
        {{ t('memoryCenterDescription') }}
      </p>

      <div class="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div
          v-for="item in memoryHealthItems"
          :key="item.key"
          class="cursor-pointer rounded-2xl px-4 py-4 ring-1 transition-colors"
          :class="memoryViewFilter === item.key
            ? 'bg-stone-900 text-stone-50 ring-stone-900'
            : 'bg-white/75 ring-stone-200/70 hover:bg-white'"
          @click="toggleMemoryViewFilter(item.key)"
        >
          <div
            class="text-[11px] uppercase tracking-[0.16em]"
            :class="memoryViewFilter === item.key ? 'text-stone-300' : 'text-stone-400'"
          >
            {{ t('memoryHealth') }}
          </div>
          <div class="mt-2 flex items-end justify-between gap-3">
            <div>
              <div class="text-sm font-medium" :class="memoryViewFilter === item.key ? 'text-stone-50' : 'text-stone-800'">{{ item.label }}</div>
              <div class="mt-1 text-xs leading-5" :class="memoryViewFilter === item.key ? 'text-stone-300' : 'text-stone-500'">{{ item.description }}</div>
            </div>
            <span
              class="rounded-full px-3 py-1 text-sm font-semibold"
              :class="memoryViewFilter === item.key ? 'bg-stone-700 text-stone-50' : 'bg-stone-100 text-stone-800'"
            >
              {{ item.count }}
            </span>
          </div>
        </div>
      </div>

      <div class="mt-4 flex flex-wrap items-center gap-2">
        <span class="text-xs uppercase tracking-[0.16em] text-stone-400">{{ t('memoryViewFilter') }}</span>
        <span
          class="memory-badge"
          :class="memoryViewFilter ? 'bg-stone-900 text-stone-50' : 'bg-white text-stone-500 ring-1 ring-stone-200/70'"
        >
          {{ memoryViewFilter ? activeMemoryFilterLabel : t('memoryViewFilterAll') }}
        </span>
        <button
          v-if="memoryViewFilter"
          @click="memoryViewFilter = ''"
          class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50"
        >
          {{ t('clearMemoryViewFilter') }}
        </button>
      </div>

      <div class="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
        <label class="space-y-2">
          <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('memorySearch') }}</span>
          <input
            v-model="memorySearchQuery"
            type="text"
            :placeholder="t('memorySearchPlaceholder')"
            class="w-full rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
          />
        </label>
        <div class="flex items-end">
          <button
            v-if="memorySearchQuery"
            @click="memorySearchQuery = ''"
            class="rounded-full bg-white px-4 py-2 text-sm font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50"
          >
            {{ t('clearMemorySearch') }}
          </button>
        </div>
      </div>

      <div class="mt-5 grid gap-4 lg:grid-cols-[180px_180px_minmax(0,1fr)_140px_auto]">
        <label class="space-y-2">
          <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('memoryCategory') }}</span>
          <input
            v-model="memoryForm.category"
            type="text"
            class="w-full rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
          />
        </label>
        <label class="space-y-2">
          <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('memoryKey') }}</span>
          <input
            v-model="memoryForm.key"
            type="text"
            class="w-full rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
          />
        </label>
        <label class="space-y-2">
          <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('memoryValue') }}</span>
          <input
            v-model="memoryForm.value"
            type="text"
            class="w-full rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
          />
        </label>
        <label class="space-y-2">
          <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('memoryConfidence') }}</span>
          <input
            v-model.number="memoryForm.confidence"
            type="number"
            min="0"
            max="1"
            step="0.1"
            class="w-full rounded-2xl border border-stone-200 bg-white/80 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
          />
        </label>
        <div class="flex items-end">
          <button
            @click="addMemoryRecord"
            :disabled="addingMemory || !connected"
            class="rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
          >
            {{ addingMemory ? t('addingMemory') : t('addMemory') }}
          </button>
        </div>
      </div>

      <p v-if="memoryMessage" class="mt-4 text-sm text-stone-600">{{ memoryMessage }}</p>

      <div class="mt-5 space-y-5">
        <div
          v-for="section in groupedMemorySections"
          :key="section.status"
          class="rounded-[24px] bg-stone-50/70 px-4 py-4 ring-1 ring-stone-200/70"
        >
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryCenter') }}</div>
              <div class="mt-1 text-sm font-medium text-stone-800">{{ section.label }}</div>
            </div>
            <span class="memory-badge bg-white text-stone-700 ring-1 ring-stone-200/70">{{ section.count }}</span>
          </div>

          <div v-if="!section.groups.length" class="mt-4 rounded-2xl bg-white/70 px-4 py-4 text-sm text-stone-500 ring-1 ring-stone-200/70">
            {{ t('noMemoriesInSection') }}
          </div>

          <div v-else class="mt-4 space-y-4">
            <div
              v-for="group in section.groups"
              :key="`${section.status}-${group.category}`"
              class="rounded-2xl bg-white/70 px-4 py-4 ring-1 ring-stone-200/70"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ group.category }}</div>
                <span class="text-xs text-stone-400">{{ t('memoryGroupCount', { count: group.items.length }) }}</span>
              </div>

              <div class="mt-3 space-y-3">
                <div
                  v-for="memory in group.items"
                  :key="memory.id"
                  class="rounded-2xl bg-white/80 px-4 py-4 ring-1 ring-stone-200/70"
                >
                  <div class="flex flex-wrap items-center justify-between gap-3">
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="memory-badge bg-stone-100 text-stone-700">{{ editingMemoryId === memory.id ? memoryEditForm.category : memory.category }}</span>
                      <span class="memory-badge bg-sky-50 text-sky-800">{{ editingMemoryId === memory.id ? memoryEditForm.key : memory.key }}</span>
                      <span
                        v-if="Number(memory.priority || 0) > 0"
                        class="memory-badge bg-amber-100 text-amber-900"
                      >
                        {{ t('memoryPinned') }}
                      </span>
                      <span
                        class="memory-badge"
                        :class="memory.status === 'archived' ? 'bg-stone-200 text-stone-700' : 'bg-emerald-50 text-emerald-800'"
                      >
                        {{ memory.status === 'archived' ? t('memoryStatusArchived') : t('memoryStatusActive') }}
                      </span>
                      <span class="text-xs text-stone-400">{{ t('memoryConfidence') }} {{ Number(memory.effective_confidence ?? memory.confidence ?? 0).toFixed(1) }}</span>
                    </div>
                    <div class="flex flex-wrap gap-2">
                      <button
                        v-if="editingMemoryId !== memory.id"
                        @click="setMemoryPriority(memory.id, Number(memory.priority || 0) > 0 ? 0 : 100)"
                        :disabled="updatingMemoryPriorityId === memory.id"
                        class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50 disabled:opacity-50"
                      >
                        {{
                          updatingMemoryPriorityId === memory.id
                            ? t('updatingMemoryPriority')
                            : (Number(memory.priority || 0) > 0 ? t('unpinMemory') : t('pinMemory'))
                        }}
                      </button>
                      <button
                        v-if="editingMemoryId !== memory.id"
                        @click="startEditingMemory(memory)"
                        class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50"
                      >
                        {{ t('editMemory') }}
                      </button>
                      <button
                        v-if="editingMemoryId !== memory.id"
                        @click="setMemoryStatus(memory.id, memory.status === 'archived' ? 'active' : 'archived')"
                        :disabled="updatingMemoryStatusId === memory.id"
                        class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50 disabled:opacity-50"
                      >
                        {{
                          updatingMemoryStatusId === memory.id
                            ? t('updatingMemoryStatus')
                            : (memory.status === 'archived' ? t('restoreMemory') : t('archiveMemory'))
                        }}
                      </button>
                      <button
                        v-if="editingMemoryId !== memory.id"
                        @click="removeMemoryRecord(memory.id)"
                        :disabled="deletingMemoryId === memory.id"
                        class="rounded-full bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-700 ring-1 ring-rose-200 transition-colors hover:bg-rose-100 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {{ deletingMemoryId === memory.id ? t('deletingMemory') : t('deleteMemory') }}
                      </button>
                      <template v-else>
                        <button
                          @click="saveMemoryRecord(memory.id)"
                          :disabled="savingMemoryId === memory.id"
                          class="rounded-full bg-stone-900 px-3 py-1.5 text-xs font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
                        >
                          {{ savingMemoryId === memory.id ? t('savingMemory') : t('saveMemory') }}
                        </button>
                        <button
                          @click="cancelEditingMemory"
                          :disabled="savingMemoryId === memory.id"
                          class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50 disabled:opacity-50"
                        >
                          {{ t('cancelEdit') }}
                        </button>
                      </template>
                    </div>
                  </div>
                  <div v-if="editingMemoryId === memory.id" class="mt-3 grid gap-3 lg:grid-cols-2">
                    <label class="space-y-2">
                      <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('memoryCategory') }}</span>
                      <input
                        v-model="memoryEditForm.category"
                        type="text"
                        class="w-full rounded-2xl border border-stone-200 bg-white/90 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
                      />
                    </label>
                    <label class="space-y-2">
                      <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('memoryKey') }}</span>
                      <input
                        v-model="memoryEditForm.key"
                        type="text"
                        class="w-full rounded-2xl border border-stone-200 bg-white/90 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
                      />
                    </label>
                    <label class="space-y-2 lg:col-span-2">
                      <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('memoryValue') }}</span>
                      <textarea
                        v-model="memoryEditForm.value"
                        rows="3"
                        class="w-full rounded-2xl border border-stone-200 bg-white/90 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
                      ></textarea>
                    </label>
                    <label class="space-y-2">
                      <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('memoryConfidence') }}</span>
                      <input
                        v-model.number="memoryEditForm.confidence"
                        type="number"
                        min="0"
                        max="1"
                        step="0.1"
                        class="w-full rounded-2xl border border-stone-200 bg-white/90 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
                      />
                    </label>
                  </div>
                  <div v-else class="mt-3 text-sm leading-6 text-stone-700">{{ memory.value }}</div>
                  <div v-if="memory.usage_count || memory.last_used_at || memory.client_usage?.length" class="mt-3 border-t border-stone-200/70 pt-3">
                    <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryUsage') }}</div>
                    <div class="mt-2 flex flex-wrap items-center gap-2 text-xs text-stone-500">
                      <span class="memory-badge bg-white text-stone-700 ring-1 ring-stone-200/70">
                        {{ t('memoryUsageCount', { count: Number(memory.usage_count || 0) }) }}
                      </span>
                      <span v-if="memory.last_used_at" class="memory-badge bg-white text-stone-700 ring-1 ring-stone-200/70">
                        {{ t('memoryLastUsedAt', { time: formatDateTime(memory.last_used_at) || memory.last_used_at }) }}
                      </span>
                    </div>
                    <div v-if="memory.client_usage?.length" class="mt-2 flex flex-wrap gap-2">
                      <span
                        v-for="item in memory.client_usage"
                        :key="`${memory.id}-usage-${item.client_id}`"
                        class="memory-badge bg-stone-100 text-stone-700"
                      >
                        {{ item.client_id }} x{{ item.count }}
                      </span>
                    </div>
                  </div>
                  <div class="mt-3 border-t border-stone-200/70 pt-3">
                    <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryClientRules') }}</div>
                    <div class="mt-3 grid gap-3 lg:grid-cols-3">
                      <label
                        v-for="clientOption in exportRuleClients"
                        :key="`${memory.id}-rule-${clientOption.value}`"
                        class="space-y-2"
                      >
                        <span class="text-xs font-medium text-stone-500">{{ clientOption.label }}</span>
                        <select
                          :value="(memory.client_rules || {})[clientOption.value] || 'default'"
                          class="w-full rounded-2xl border border-stone-200 bg-white/90 px-3 py-2 text-sm text-stone-800 outline-none transition focus:border-stone-400"
                          @change="updateMemoryClientRule(memory, clientOption.value, $event.target.value)"
                        >
                          <option value="default">{{ t('memoryClientRuleDefault') }}</option>
                          <option value="include">{{ t('memoryClientRuleInclude') }}</option>
                          <option value="exclude">{{ t('memoryClientRuleExclude') }}</option>
                        </select>
                      </label>
                    </div>
                  </div>
                  <div v-if="memory.parent_memories?.length" class="mt-3 border-t border-stone-200/70 pt-3">
                    <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryLineage') }}</div>
                    <div class="mt-2 flex flex-wrap gap-2">
                      <span
                        v-for="parent in memory.parent_memories"
                        :key="`${memory.id}-parent-${parent.memory_id}`"
                        class="memory-badge bg-amber-50 text-amber-900 ring-1 ring-amber-200/70"
                      >
                        {{ parent.category || t('memoryMergedFrom') }} / {{ parent.key || parent.memory_id }}
                      </span>
                    </div>
                  </div>
                  <div v-if="memory.sources?.length" class="mt-3 border-t border-stone-200/70 pt-3">
                    <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memorySources') }}</div>
                    <div class="mt-2 flex flex-wrap gap-2">
                      <router-link
                        v-for="source in memory.sources"
                        :key="`${memory.id}-${source.conversation_id}`"
                        :to="`/conversations/${source.conversation_id}`"
                        class="memory-badge bg-white text-stone-700 ring-1 ring-stone-200/70 transition-colors hover:bg-stone-50"
                      >
                        {{ source.project || source.summary || source.conversation_id }}
                      </router-link>
                    </div>
                  </div>
                  <div v-if="memory.timeline?.length" class="mt-3 border-t border-stone-200/70 pt-3">
                    <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryTimeline') }}</div>
                    <div class="mt-3 space-y-2">
                      <div
                        v-for="(entry, timelineIndex) in memory.timeline"
                        :key="`${memory.id}-timeline-${timelineIndex}`"
                        class="rounded-2xl bg-stone-50/80 px-3 py-3 text-sm text-stone-700"
                      >
                        <div class="flex flex-wrap items-center justify-between gap-2">
                          <span class="memory-badge bg-white text-stone-700 ring-1 ring-stone-200/70">
                            {{ t(entry.label) }}
                          </span>
                          <span class="text-xs text-stone-400">{{ formatDateTime(entry.timestamp) || entry.timestamp || t('none') }}</span>
                        </div>
                        <div class="mt-2 leading-6 text-stone-600">{{ entry.description || t('none') }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="!memories.length" class="rounded-2xl bg-white/70 px-4 py-4 text-sm text-stone-500 ring-1 ring-stone-200/70">
          {{ t('noMemoriesYet') }}
        </div>
      </div>

      <div class="mt-6 rounded-[22px] bg-stone-50/80 px-4 py-4 ring-1 ring-stone-200/70">
        <div class="flex items-center justify-between gap-3">
          <div>
            <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryCenter') }}</div>
            <div class="mt-1 text-sm font-medium text-stone-800">{{ t('memorySuggestionsTitle') }}</div>
          </div>
          <button
            @click="loadMemorySuggestions"
            :disabled="!connected"
            class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50 disabled:opacity-50"
          >
            {{ t('refresh') }}
          </button>
        </div>
        <p class="mt-2 text-sm leading-6 text-stone-500">{{ t('memorySuggestionsDescription') }}</p>

        <div class="mt-4 space-y-3">
          <div
            v-for="(item, index) in memorySuggestions"
            :key="`${item.left.id}-${item.right.id}-${index}`"
            class="rounded-2xl bg-white/85 px-4 py-4 ring-1 ring-stone-200/70"
          >
            <div class="flex flex-wrap items-center gap-2">
              <span class="memory-badge bg-amber-100 text-amber-900">{{ t('mergeSuggestion') }}</span>
              <span class="text-xs text-stone-400">{{ t('suggestionScore', { score: item.score }) }}</span>
            </div>
            <div class="mt-3 grid gap-3 lg:grid-cols-2">
              <div class="rounded-2xl bg-stone-50 px-3 py-3">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="memory-badge bg-stone-100 text-stone-700">{{ item.left.category }}</span>
                  <span class="memory-badge bg-sky-50 text-sky-800">{{ item.left.key }}</span>
                </div>
                <div class="mt-2 text-sm leading-6 text-stone-700">{{ item.left.value }}</div>
              </div>
              <div class="rounded-2xl bg-stone-50 px-3 py-3">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="memory-badge bg-stone-100 text-stone-700">{{ item.right.category }}</span>
                  <span class="memory-badge bg-sky-50 text-sky-800">{{ item.right.key }}</span>
                </div>
                <div class="mt-2 text-sm leading-6 text-stone-700">{{ item.right.value }}</div>
              </div>
            </div>
            <div class="mt-3 flex justify-end">
              <div class="flex flex-wrap gap-2">
                <button
                  @click="mergeMemorySuggestion(item, index, false)"
                  :disabled="mergingMemorySuggestionKey === `${item.left.id}-${item.right.id}-${index}`"
                  class="rounded-full bg-stone-900 px-3 py-1.5 text-xs font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
                >
                  {{ mergingMemorySuggestionKey === `${item.left.id}-${item.right.id}-${index}` ? t('mergingMemory') : t('mergeAsNewMemory') }}
                </button>
                <button
                  @click="mergeMemorySuggestion(item, index, true)"
                  :disabled="mergingMemorySuggestionKey === `${item.left.id}-${item.right.id}-${index}`"
                  class="rounded-full bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-900 transition-colors hover:bg-amber-200 disabled:opacity-50"
                >
                  {{ mergingMemorySuggestionKey === `${item.left.id}-${item.right.id}-${index}` ? t('mergingMemory') : t('mergeAndDeleteSources') }}
                </button>
              </div>
            </div>
          </div>
          <div v-if="!memorySuggestions.length" class="rounded-2xl bg-white/70 px-4 py-4 text-sm text-stone-500 ring-1 ring-stone-200/70">
            {{ t('noMemorySuggestions') }}
          </div>
        </div>

        <div class="mt-6 rounded-[22px] bg-rose-50/70 px-4 py-4 ring-1 ring-rose-100/80">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[11px] uppercase tracking-[0.16em] text-rose-400">{{ t('memoryCenter') }}</div>
              <div class="mt-1 text-sm font-medium text-stone-800">{{ t('memoryConflictsTitle') }}</div>
            </div>
            <button
              @click="loadMemoryConflicts"
              :disabled="!connected"
              class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50 disabled:opacity-50"
            >
              {{ t('refresh') }}
            </button>
          </div>
          <p class="mt-2 text-sm leading-6 text-stone-500">{{ t('memoryConflictsDescription') }}</p>

          <div class="mt-4 space-y-3">
            <div
              v-for="(item, index) in memoryConflicts"
              :key="`${item.left.id}-${item.right.id}-${index}`"
              class="rounded-2xl bg-white/90 px-4 py-4 ring-1 ring-rose-100/80"
            >
              <div class="flex flex-wrap items-center gap-2">
                <span class="memory-badge bg-rose-100 text-rose-800">{{ t('conflictSuggestion') }}</span>
                <span class="text-xs text-stone-400">{{ t('suggestionScore', { score: item.score }) }}</span>
              </div>
              <div class="mt-3 grid gap-3 lg:grid-cols-2">
                <div class="rounded-2xl bg-rose-50/70 px-3 py-3">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="memory-badge bg-stone-100 text-stone-700">{{ item.left.category }}</span>
                    <span class="memory-badge bg-sky-50 text-sky-800">{{ item.left.key }}</span>
                  </div>
                  <div class="mt-2 text-sm leading-6 text-stone-700">{{ item.left.value }}</div>
                </div>
                <div class="rounded-2xl bg-rose-50/70 px-3 py-3">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="memory-badge bg-stone-100 text-stone-700">{{ item.right.category }}</span>
                    <span class="memory-badge bg-sky-50 text-sky-800">{{ item.right.key }}</span>
                  </div>
                  <div class="mt-2 text-sm leading-6 text-stone-700">{{ item.right.value }}</div>
                </div>
              </div>
              <div class="mt-3 flex justify-end">
                <div class="flex flex-wrap gap-2">
                  <button
                    @click="resolveMemoryConflict(item, index, 'keep_left')"
                    :disabled="resolvingMemoryConflictKey.startsWith(`${item.left.id}-${item.right.id}-${index}-`)"
                    class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50 disabled:opacity-50"
                  >
                    {{ resolvingMemoryConflictKey === `${item.left.id}-${item.right.id}-${index}-keep_left` ? t('resolvingConflict') : t('keepLeftMemory') }}
                  </button>
                  <button
                    @click="resolveMemoryConflict(item, index, 'keep_right')"
                    :disabled="resolvingMemoryConflictKey.startsWith(`${item.left.id}-${item.right.id}-${index}-`)"
                    class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50 disabled:opacity-50"
                  >
                    {{ resolvingMemoryConflictKey === `${item.left.id}-${item.right.id}-${index}-keep_right` ? t('resolvingConflict') : t('keepRightMemory') }}
                  </button>
                  <button
                    @click="resolveMemoryConflict(item, index, 'merge_new')"
                    :disabled="resolvingMemoryConflictKey.startsWith(`${item.left.id}-${item.right.id}-${index}-`)"
                    class="rounded-full bg-rose-100 px-3 py-1.5 text-xs font-medium text-rose-900 transition-colors hover:bg-rose-200 disabled:opacity-50"
                  >
                    {{ resolvingMemoryConflictKey === `${item.left.id}-${item.right.id}-${index}-merge_new` ? t('resolvingConflict') : t('mergeConflictAsNew') }}
                  </button>
                </div>
              </div>
            </div>
            <div v-if="!memoryConflicts.length" class="rounded-2xl bg-white/70 px-4 py-4 text-sm text-stone-500 ring-1 ring-rose-100/80">
              {{ t('noMemoryConflicts') }}
            </div>
          </div>
        </div>

      <div class="mt-6 rounded-[22px] bg-amber-50/70 px-4 py-4 ring-1 ring-amber-100/80">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[11px] uppercase tracking-[0.16em] text-amber-500">{{ t('memoryCenter') }}</div>
              <div class="mt-1 text-sm font-medium text-stone-800">{{ t('memoryCleanupSuggestionsTitle') }}</div>
            </div>
            <div class="flex flex-wrap gap-2">
              <button
                @click="archiveSelectedCleanupSuggestions"
                :disabled="!connected || !selectedCleanupMemoryIds.length || archivingCleanupBatch"
                class="rounded-full bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-900 transition-colors hover:bg-amber-200 disabled:opacity-50"
              >
                {{ archivingCleanupBatch ? t('archivingSuggestedMemories') : t('archiveSelectedSuggestedMemories', { count: selectedCleanupMemoryIds.length }) }}
              </button>
              <button
                @click="loadMemoryCleanupSuggestions"
                :disabled="!connected"
                class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50 disabled:opacity-50"
              >
                {{ t('refresh') }}
              </button>
            </div>
          </div>
          <p class="mt-2 text-sm leading-6 text-stone-500">{{ t('memoryCleanupSuggestionsDescription') }}</p>

          <div class="mt-4 space-y-3">
            <div
              v-for="(item, index) in memoryCleanupSuggestions"
              :key="`${item.memory.id}-${index}`"
              class="rounded-2xl bg-white/90 px-4 py-4 ring-1 ring-amber-100/80"
            >
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div class="flex flex-wrap items-center gap-2">
                  <input
                    :id="`cleanup-memory-${item.memory.id}`"
                    v-model="selectedCleanupMemoryIds"
                    :value="item.memory.id"
                    type="checkbox"
                    class="h-4 w-4 rounded border-stone-300 text-amber-600 focus:ring-amber-500"
                  />
                  <label :for="`cleanup-memory-${item.memory.id}`" class="text-xs text-stone-500">
                    {{ t('selectCleanupSuggestion') }}
                  </label>
                  <span class="memory-badge bg-amber-100 text-amber-900">{{ t('memoryCleanupSuggestion') }}</span>
                  <span class="text-xs text-stone-400">{{ t('suggestionScore', { score: item.score }) }}</span>
                </div>
              </div>
              <div class="mt-3 rounded-2xl bg-amber-50/60 px-3 py-3">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="memory-badge bg-stone-100 text-stone-700">{{ item.memory.category }}</span>
                  <span class="memory-badge bg-sky-50 text-sky-800">{{ item.memory.key }}</span>
                  <span v-if="Number(item.memory.usage_count || 0) === 0" class="memory-badge bg-white text-stone-700 ring-1 ring-stone-200/70">
                    {{ t('memoryUsageCount', { count: 0 }) }}
                  </span>
                </div>
                <div class="mt-2 text-sm leading-6 text-stone-700">{{ item.memory.value }}</div>
              </div>
              <div v-if="item.reasons?.length" class="mt-3 flex flex-wrap gap-2">
                <span
                  v-for="reason in item.reasons"
                  :key="`${item.memory.id}-${reason}`"
                  class="memory-badge bg-white text-stone-700 ring-1 ring-stone-200/70"
                >
                  {{ t(reason) }}
                </span>
              </div>
              <div class="mt-3 flex justify-end">
                <button
                  @click="setMemoryStatus(item.memory.id, 'archived')"
                  :disabled="updatingMemoryStatusId === item.memory.id"
                  class="rounded-full bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-900 transition-colors hover:bg-amber-200 disabled:opacity-50"
                >
                  {{ updatingMemoryStatusId === item.memory.id ? t('updatingMemoryStatus') : t('archiveSuggestedMemory') }}
                </button>
              </div>
            </div>
            <div v-if="!memoryCleanupSuggestions.length" class="rounded-2xl bg-white/70 px-4 py-4 text-sm text-stone-500 ring-1 ring-amber-100/80">
              {{ t('noMemoryCleanupSuggestions') }}
            </div>
          </div>
        </div>
      </div>

      <div class="mt-6 rounded-[22px] bg-sky-50/70 px-4 py-4 ring-1 ring-sky-100/80">
        <div class="flex items-center justify-between gap-3">
          <div>
            <div class="text-[11px] uppercase tracking-[0.16em] text-sky-500">{{ t('memoryCenter') }}</div>
            <div class="mt-1 text-sm font-medium text-stone-800">{{ t('memoryExportSimulatorTitle') }}</div>
          </div>
          <button
            @click="runMemoryExportSimulation"
            :disabled="simulatingMemoryExport || !connected"
            class="rounded-full bg-stone-900 px-3 py-1.5 text-xs font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
          >
            {{ simulatingMemoryExport ? t('simulatingMemoryExport') : t('runMemoryExportSimulation') }}
          </button>
        </div>
        <p class="mt-2 text-sm leading-6 text-stone-500">{{ t('memoryExportSimulatorDescription') }}</p>

        <div class="mt-4 grid gap-4 lg:grid-cols-2">
          <label class="space-y-2">
            <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('exportTarget') }}</span>
            <select
              v-model="memoryExportSimulationForm.client"
              class="w-full rounded-2xl border border-stone-200 bg-white/90 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
            >
              <option v-for="clientOption in exportRuleClients" :key="`sim-${clientOption.value}`" :value="clientOption.value">
                {{ clientOption.label }}
              </option>
            </select>
          </label>
          <label class="space-y-2">
            <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('project') }}</span>
            <input
              v-model="memoryExportSimulationForm.project"
              type="text"
              class="w-full rounded-2xl border border-stone-200 bg-white/90 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
            />
          </label>
          <label class="space-y-2 lg:col-span-2">
            <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('memoryExportSimulationPrompt') }}</span>
            <textarea
              v-model="memoryExportSimulationForm.prompt"
              rows="4"
              :placeholder="t('memoryExportSimulationPromptPlaceholder')"
              class="w-full rounded-2xl border border-stone-200 bg-white/90 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
            ></textarea>
          </label>
        </div>

        <p v-if="memoryExportSimulationMessage" class="mt-4 text-sm text-stone-600">{{ memoryExportSimulationMessage }}</p>

        <div class="mt-4 rounded-2xl bg-white/85 px-4 py-4 ring-1 ring-sky-100/80">
          <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryExportSimulationResult') }}</div>
          <div v-if="memoryExportSimulationResult" class="mt-3 space-y-3">
            <div class="text-sm leading-6 text-stone-600">
              {{ t('exportStrategySummary', { summary: memoryExportSimulationResult.strategy_summary }) }}
            </div>
            <div class="text-sm leading-6 text-stone-600">
              {{ t('exportMemoryCountDetailed', { selected: memoryExportSimulationResult.memory_count, total: memoryExportSimulationResult.total_memory_count }) }}
            </div>
            <div v-if="memoryExportSimulationResult.selected_memories?.length" class="space-y-2">
              <div
                v-for="memory in memoryExportSimulationResult.selected_memories"
                :key="`sim-memory-${memory.id}`"
                class="rounded-2xl bg-sky-50/70 px-3 py-3"
              >
                <div class="flex flex-wrap items-center gap-2">
                  <span class="memory-badge bg-stone-100 text-stone-700">{{ memory.category }}</span>
                  <span class="memory-badge bg-sky-100 text-sky-800">{{ memory.key }}</span>
                </div>
                <div class="mt-2 text-sm leading-6 text-stone-700">{{ memory.value }}</div>
                <div v-if="memory.reasons?.length" class="mt-2 flex flex-wrap gap-2">
                  <span
                    v-for="reason in memory.reasons"
                    :key="`sim-memory-${memory.id}-${reason}`"
                    class="memory-badge bg-white text-stone-700 ring-1 ring-stone-200/70"
                  >
                    {{ t(reason) }}
                  </span>
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-stone-500">{{ t('noMemoryExportSimulationResult') }}</div>
          </div>
          <div v-else class="mt-3 text-sm text-stone-500">{{ t('noMemoryExportSimulationResult') }}</div>
        </div>

        <div class="mt-4 rounded-2xl bg-white/85 px-4 py-4 ring-1 ring-sky-100/80">
          <div class="flex items-center justify-between gap-3">
            <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryExportComparisonTitle') }}</div>
            <button
              @click="runMemoryExportComparison"
              :disabled="comparingMemoryExport || !connected || !selectedComparisonConversationId || !memoryExportSimulationResult"
              class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50 disabled:opacity-50"
            >
              {{ comparingMemoryExport ? t('comparingMemoryExport') : t('runMemoryExportComparison') }}
            </button>
          </div>
          <p class="mt-2 text-sm leading-6 text-stone-500">{{ t('memoryExportComparisonDescription') }}</p>

          <label class="mt-4 block space-y-2">
            <span class="text-xs font-medium uppercase tracking-[0.16em] text-stone-500">{{ t('comparisonConversation') }}</span>
            <select
              v-model="selectedComparisonConversationId"
              class="w-full rounded-2xl border border-stone-200 bg-white/90 px-4 py-3 text-sm text-stone-800 outline-none transition focus:border-stone-400"
            >
              <option value=""></option>
              <option v-for="conversation in comparisonConversations" :key="conversation.id" :value="conversation.id">
                {{ conversation.summary || conversation.project || conversation.id }}
              </option>
            </select>
          </label>

          <p v-if="memoryExportComparisonMessage" class="mt-4 text-sm text-stone-600">{{ memoryExportComparisonMessage }}</p>

          <div v-if="memoryExportComparisonResult" class="mt-4 space-y-3">
            <div class="text-sm leading-6 text-stone-600">
              {{ t('memoryExportComparisonTarget', { client: memoryExportSimulationForm.client, conversation: comparisonConversationLabel }) }}
            </div>
            <div v-if="memoryExportComparisonDiff.added.length || memoryExportComparisonDiff.removed.length" class="space-y-3">
              <div v-if="memoryExportComparisonDiff.added.length">
                <div class="text-sm font-medium text-stone-800">{{ t('memoryExportComparisonOnlyInSimulation') }}</div>
                <div class="mt-2 flex flex-wrap gap-2">
                  <span
                    v-for="memory in memoryExportComparisonDiff.added"
                    :key="`sim-added-${memory.id}`"
                    class="memory-badge bg-sky-100 text-sky-900"
                  >
                    {{ memory.key || memory.id }}
                  </span>
                </div>
              </div>
              <div v-if="memoryExportComparisonDiff.removed.length">
                <div class="text-sm font-medium text-stone-800">{{ t('memoryExportComparisonOnlyInConversation') }}</div>
                <div class="mt-2 flex flex-wrap gap-2">
                  <span
                    v-for="memory in memoryExportComparisonDiff.removed"
                    :key="`sim-removed-${memory.id}`"
                    class="memory-badge bg-amber-100 text-amber-900"
                  >
                    {{ memory.key || memory.id }}
                  </span>
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-stone-500">{{ t('memoryExportComparisonNoDiff') }}</div>
          </div>
          <div v-else class="mt-4 text-sm text-stone-500">{{ t('noMemoryExportComparisonResult') }}</div>
        </div>

        <div class="mt-4 rounded-2xl bg-white/85 px-4 py-4 ring-1 ring-sky-100/80">
          <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryExportTuningSuggestionsTitle') }}</div>
          <p class="mt-2 text-sm leading-6 text-stone-500">{{ t('memoryExportTuningSuggestionsDescription') }}</p>

          <div v-if="memoryExportTuningSuggestions.length" class="mt-4 space-y-3">
            <div
              v-for="item in memoryExportTuningSuggestions"
              :key="`tuning-${item.memory.id}-${item.kind}`"
              class="rounded-2xl bg-sky-50/60 px-4 py-4"
            >
              <div class="flex flex-wrap items-center gap-2">
                <span class="memory-badge bg-stone-100 text-stone-700">{{ item.memory.category }}</span>
                <span class="memory-badge bg-sky-100 text-sky-800">{{ item.memory.key }}</span>
                <span class="text-xs text-stone-500">{{ item.label }}</span>
              </div>
              <div class="mt-2 text-sm leading-6 text-stone-700">{{ item.description }}</div>
              <div class="mt-3 flex justify-end">
                <button
                  @click="applyMemoryTuningSuggestion(item)"
                  :disabled="applyingMemoryTuningKey === `${item.memory.id}-${item.kind}`"
                  class="rounded-full bg-stone-900 px-3 py-1.5 text-xs font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
                >
                  {{
                    applyingMemoryTuningKey === `${item.memory.id}-${item.kind}`
                      ? t('applyingMemoryTuningSuggestion')
                      : item.actionLabel
                  }}
                </button>
              </div>
            </div>
          </div>
          <div v-else class="mt-4 text-sm text-stone-500">{{ t('noMemoryExportTuningSuggestions') }}</div>
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
const memories = ref([])
const memorySuggestions = ref([])
const memoryConflicts = ref([])
const memoryCleanupSuggestions = ref([])
const selectedCleanupMemoryIds = ref([])
const memoryViewFilter = ref('')
const memorySearchQuery = ref('')
const simulatingMemoryExport = ref(false)
const memoryExportSimulationMessage = ref('')
const memoryExportSimulationResult = ref(null)
const comparingMemoryExport = ref(false)
const memoryExportComparisonMessage = ref('')
const memoryExportComparisonResult = ref(null)
const applyingMemoryTuningKey = ref('')
const comparisonConversations = ref([])
const selectedComparisonConversationId = ref('')
const addingMemory = ref(false)
const editingMemoryId = ref(null)
const savingMemoryId = ref(null)
const updatingMemoryStatusId = ref(null)
const updatingMemoryPriorityId = ref(null)
const archivingCleanupBatch = ref(false)
const mergingMemorySuggestionKey = ref('')
const resolvingMemoryConflictKey = ref('')
const memoryMessage = ref('')
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
const memoryForm = ref({
  category: 'general',
  key: '',
  value: '',
  confidence: 0.8,
})
const memoryEditForm = ref({
  category: 'general',
  key: '',
  value: '',
  confidence: 0.8,
})
const memoryExportSimulationForm = ref({
  client: 'codex',
  project: '',
  prompt: '',
})

const importSourceOptions = computed(() => ([
  { value: 'all', label: t('importSourceAll') },
  { value: 'codex', label: t('importSourceCodex') },
  { value: 'claude_code', label: t('importSourceClaudeCode') },
  { value: 'gemini_cli', label: t('importSourceGeminiCli') },
  { value: 'antigravity', label: t('importSourceAntigravity') },
]))
const exportRuleClients = computed(() => ([
  { value: 'codex', label: 'Codex' },
  { value: 'claude_code', label: 'Claude Code' },
  { value: 'gemini_cli', label: 'Gemini CLI' },
]))
const memoryHealthItems = computed(() => {
  const activeMemories = memories.value.filter((memory) => (memory.status || 'active') === 'active')
  const archivedMemories = memories.value.filter((memory) => (memory.status || 'active') === 'archived')
  const unusedActiveMemories = activeMemories.filter((memory) => Number(memory.usage_count || 0) === 0)
  const frequentlyUsedMemories = activeMemories.filter((memory) => Number(memory.usage_count || 0) >= 3)

  return [
    {
      key: 'active',
      label: t('memoryHealthActive'),
      description: t('memoryHealthActiveDescription'),
      count: activeMemories.length,
    },
    {
      key: 'archived',
      label: t('memoryHealthArchived'),
      description: t('memoryHealthArchivedDescription'),
      count: archivedMemories.length,
    },
    {
      key: 'unused',
      label: t('memoryHealthUnused'),
      description: t('memoryHealthUnusedDescription'),
      count: unusedActiveMemories.length,
    },
    {
      key: 'used',
      label: t('memoryHealthFrequentlyUsed'),
      description: t('memoryHealthFrequentlyUsedDescription'),
      count: frequentlyUsedMemories.length,
    },
    {
      key: 'conflicts',
      label: t('memoryHealthConflicts'),
      description: t('memoryHealthConflictsDescription'),
      count: memoryConflicts.value.length,
    },
    {
      key: 'merge',
      label: t('memoryHealthMergeCandidates'),
      description: t('memoryHealthMergeCandidatesDescription'),
      count: memorySuggestions.value.length,
    },
  ]
})
const activeMemoryFilterLabel = computed(() => {
  const current = memoryHealthItems.value.find((item) => item.key === memoryViewFilter.value)
  return current?.label || ''
})
const comparisonConversationLabel = computed(() => {
  const current = comparisonConversations.value.find((item) => item.id === selectedComparisonConversationId.value)
  return current?.summary || current?.project || current?.id || ''
})
const filteredMemories = computed(() => {
  const currentFilter = memoryViewFilter.value
  const searchNeedle = String(memorySearchQuery.value || '').trim().toLowerCase()
  const activeIdsWithConflicts = new Set(memoryConflicts.value.flatMap((item) => [item.left.id, item.right.id]))
  const activeIdsWithMergeCandidates = new Set(memorySuggestions.value.flatMap((item) => [item.left.id, item.right.id]))

  return memories.value.filter((memory) => {
    let passesFilter = true
    switch (currentFilter) {
      case 'active':
        passesFilter = (memory.status || 'active') === 'active'
        break
      case 'archived':
        passesFilter = (memory.status || 'active') === 'archived'
        break
      case 'unused':
        passesFilter = (memory.status || 'active') === 'active' && Number(memory.usage_count || 0) === 0
        break
      case 'used':
        passesFilter = (memory.status || 'active') === 'active' && Number(memory.usage_count || 0) >= 3
        break
      case 'conflicts':
        passesFilter = activeIdsWithConflicts.has(memory.id)
        break
      case 'merge':
        passesFilter = activeIdsWithMergeCandidates.has(memory.id)
        break
      default:
        passesFilter = true
    }

    if (!passesFilter) {
      return false
    }

    if (!searchNeedle) {
      return true
    }

    const haystack = [
      memory.category,
      memory.key,
      memory.value,
      memory.status,
      ...((memory.sources || []).map((source) => source.project || source.summary || '')),
    ]
      .join(' ')
      .toLowerCase()

    return haystack.includes(searchNeedle)
  })
})
const memoryExportComparisonDiff = computed(() => {
  const simulation = Array.isArray(memoryExportSimulationResult.value?.selected_memories) ? memoryExportSimulationResult.value.selected_memories : []
  const actual = Array.isArray(memoryExportComparisonResult.value?.selected_memories) ? memoryExportComparisonResult.value.selected_memories : []
  if (!simulation.length && !actual.length) {
    return { added: [], removed: [] }
  }
  const simulationMap = new Map(simulation.map((memory) => [Number(memory.id), memory]))
  const actualMap = new Map(actual.map((memory) => [Number(memory.id), memory]))
  return {
    added: simulation.filter((memory) => !actualMap.has(Number(memory.id))),
    removed: actual.filter((memory) => !simulationMap.has(Number(memory.id))),
  }
})
const memoryExportTuningSuggestions = computed(() => {
  const clientId = memoryExportSimulationForm.value.client
  const memoryMap = new Map(memories.value.map((memory) => [Number(memory.id), memory]))
  const suggestions = []

  for (const memory of memoryExportComparisonDiff.value.removed) {
    const fullMemory = memoryMap.get(Number(memory.id))
    if (!fullMemory) continue
    const clientRule = (fullMemory.client_rules || {})[clientId] || 'default'
    if (clientRule !== 'include') {
      suggestions.push({
        kind: 'include',
        memory: fullMemory,
        label: t('memoryTuningSuggestIncludeLabel'),
        description: t('memoryTuningSuggestIncludeDescription', { client: clientId }),
        actionLabel: t('memoryTuningApplyInclude'),
      })
      continue
    }
    if (Number(fullMemory.priority || 0) === 0) {
      suggestions.push({
        kind: 'pin',
        memory: fullMemory,
        label: t('memoryTuningSuggestPinLabel'),
        description: t('memoryTuningSuggestPinDescription'),
        actionLabel: t('memoryTuningApplyPin'),
      })
    }
  }

  for (const memory of memoryExportComparisonDiff.value.added) {
    const fullMemory = memoryMap.get(Number(memory.id))
    if (!fullMemory) continue
    const clientRule = (fullMemory.client_rules || {})[clientId] || 'default'
    if (clientRule !== 'exclude') {
      suggestions.push({
        kind: 'exclude',
        memory: fullMemory,
        label: t('memoryTuningSuggestExcludeLabel'),
        description: t('memoryTuningSuggestExcludeDescription', { client: clientId }),
        actionLabel: t('memoryTuningApplyExclude'),
      })
    }
  }

  const seen = new Set()
  return suggestions.filter((item) => {
    const key = `${item.memory.id}-${item.kind}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
})

const groupedMemorySections = computed(() => {
  const statusOrder = ['active', 'archived']
  return statusOrder
    .map((status) => {
      const items = filteredMemories.value.filter((memory) => (memory.status || 'active') === status)
      const categories = [...new Set(items.map((memory) => memory.category || 'general'))].sort((a, b) => a.localeCompare(b))
      return {
        status,
        label: status === 'archived' ? t('memoryStatusArchivedSection') : t('memoryStatusActiveSection'),
        count: items.length,
        groups: categories.map((category) => ({
          category,
          items: items.filter((memory) => (memory.category || 'general') === category),
        })),
      }
    })
    .filter((section) => section.count > 0)
})

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
        loadMemories(),
        loadComparisonConversations(),
        loadMemorySuggestions(),
        loadMemoryConflicts(),
        loadMemoryCleanupSuggestions(),
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

async function refreshAllMemoryData() {
  await Promise.allSettled([
    loadMemories(),
    loadMemorySuggestions(),
    loadMemoryConflicts(),
    loadMemoryCleanupSuggestions(),
  ])
}

async function loadMemories() {
  try {
    const result = await api.listMemories()
    memories.value = result.memories || []
  } catch (e) {
    memoryMessage.value = t('loadMemoriesFailed', { message: e.message })
  }
}

async function loadComparisonConversations() {
  try {
    const result = await api.listConversations({ limit: 50, offset: 0, hours: 24 * 365 * 20 })
    comparisonConversations.value = result.conversations || []
  } catch (_) {
    comparisonConversations.value = []
  }
}

async function loadMemorySuggestions() {
  try {
    const result = await api.listMemorySuggestions()
    memorySuggestions.value = result.suggestions || []
  } catch (e) {
    memoryMessage.value = t('loadMemorySuggestionsFailed', { message: e.message })
  }
}

async function loadMemoryConflicts() {
  try {
    const result = await api.listMemoryConflicts()
    memoryConflicts.value = result.conflicts || []
  } catch (e) {
    memoryMessage.value = t('loadMemoryConflictsFailed', { message: e.message })
  }
}

async function loadMemoryCleanupSuggestions() {
  try {
    const result = await api.listMemoryCleanupSuggestions()
    memoryCleanupSuggestions.value = result.suggestions || []
    const validIds = new Set(memoryCleanupSuggestions.value.map((item) => item.memory.id))
    selectedCleanupMemoryIds.value = selectedCleanupMemoryIds.value.filter((memoryId) => validIds.has(memoryId))
  } catch (e) {
    memoryMessage.value = t('loadMemoryCleanupSuggestionsFailed', { message: e.message })
  }
}

async function archiveSelectedCleanupSuggestions() {
  archivingCleanupBatch.value = true
  memoryMessage.value = ''
  try {
    for (const memoryId of selectedCleanupMemoryIds.value) {
      await api.updateMemoryStatus(memoryId, 'archived')
    }
    memoryMessage.value = t('archiveSelectedSuggestedMemoriesDone', { count: selectedCleanupMemoryIds.value.length })
    selectedCleanupMemoryIds.value = []
    await refreshAllMemoryData()
  } catch (e) {
    memoryMessage.value = t('archiveSelectedSuggestedMemoriesFailed', { message: e.message })
  } finally {
    archivingCleanupBatch.value = false
  }
}

function toggleMemoryViewFilter(filterKey) {
  memoryViewFilter.value = memoryViewFilter.value === filterKey ? '' : filterKey
}

async function runMemoryExportSimulation() {
  simulatingMemoryExport.value = true
  memoryExportSimulationMessage.value = ''
  try {
    const result = await api.simulateMemoryExport({
      client: memoryExportSimulationForm.value.client,
      project: String(memoryExportSimulationForm.value.project || '').trim() || null,
      prompt: String(memoryExportSimulationForm.value.prompt || '').trim(),
    })
    memoryExportSimulationResult.value = result
    memoryExportComparisonResult.value = null
    memoryExportComparisonMessage.value = ''
    memoryExportSimulationMessage.value = t('memoryExportSimulationDone')
  } catch (e) {
    memoryExportSimulationMessage.value = t('memoryExportSimulationFailed', { message: e.message })
    memoryExportSimulationResult.value = null
  } finally {
    simulatingMemoryExport.value = false
  }
}

async function runMemoryExportComparison() {
  comparingMemoryExport.value = true
  memoryExportComparisonMessage.value = ''
  try {
    const result = await api.previewConversationExport(
      selectedComparisonConversationId.value,
      memoryExportSimulationForm.value.client,
      []
    )
    memoryExportComparisonResult.value = result
    memoryExportComparisonMessage.value = t('memoryExportComparisonDone')
  } catch (e) {
    memoryExportComparisonResult.value = null
    memoryExportComparisonMessage.value = t('memoryExportComparisonFailed', { message: e.message })
  } finally {
    comparingMemoryExport.value = false
  }
}

async function applyMemoryTuningSuggestion(item) {
  const memoryId = Number(item?.memory?.id || 0)
  if (!memoryId || !item?.kind) {
    return
  }

  applyingMemoryTuningKey.value = `${memoryId}-${item.kind}`
  memoryExportComparisonMessage.value = ''
  try {
    if (item.kind === 'pin') {
      await api.updateMemoryPriority(memoryId, 100)
    } else {
      const nextRules = {
        ...(item.memory.client_rules || {}),
        [memoryExportSimulationForm.value.client]: item.kind === 'include' ? 'include' : 'exclude',
      }
      await api.updateMemoryClientRules(memoryId, nextRules)
    }
    await loadMemories()
    await runMemoryExportComparison()
    memoryExportComparisonMessage.value = t('memoryTuningApplyDone')
  } catch (e) {
    memoryExportComparisonMessage.value = t('memoryTuningApplyFailed', { message: e.message })
  } finally {
    applyingMemoryTuningKey.value = ''
  }
}

async function addMemoryRecord() {
  addingMemory.value = true
  memoryMessage.value = ''
  try {
    await api.createMemory({
      category: memoryForm.value.category,
      key: memoryForm.value.key,
      value: memoryForm.value.value,
      confidence: Number(memoryForm.value.confidence || 0.8),
    })
    memoryForm.value.key = ''
    memoryForm.value.value = ''
    await refreshAllMemoryData()
  } catch (e) {
    memoryMessage.value = t('addMemoryFailed', { message: e.message })
  } finally {
    addingMemory.value = false
  }
}

function startEditingMemory(memory) {
  editingMemoryId.value = memory.id
  memoryEditForm.value = {
    category: memory.category || 'general',
    key: memory.key || '',
    value: memory.value || '',
    confidence: Number(memory.confidence ?? 0.8),
  }
}

function cancelEditingMemory() {
  editingMemoryId.value = null
  savingMemoryId.value = null
}

async function saveMemoryRecord(memoryId) {
  savingMemoryId.value = memoryId
  memoryMessage.value = ''
  try {
    await api.updateMemory(memoryId, {
      category: memoryEditForm.value.category,
      key: memoryEditForm.value.key,
      value: memoryEditForm.value.value,
      confidence: Number(memoryEditForm.value.confidence || 0.8),
    })
    memoryMessage.value = t('updateMemoryDone')
    editingMemoryId.value = null
    await refreshAllMemoryData()
  } catch (e) {
    memoryMessage.value = t('updateMemoryFailed', { message: e.message })
  } finally {
    savingMemoryId.value = null
  }
}

async function setMemoryStatus(memoryId, status) {
  updatingMemoryStatusId.value = memoryId
  memoryMessage.value = ''
  try {
    await api.updateMemoryStatus(memoryId, status)
    memoryMessage.value = status === 'archived' ? t('archiveMemoryDone') : t('restoreMemoryDone')
    if (editingMemoryId.value === memoryId) {
      cancelEditingMemory()
    }
    await refreshAllMemoryData()
  } catch (e) {
    memoryMessage.value = t('updateMemoryStatusFailed', { message: e.message })
  } finally {
    updatingMemoryStatusId.value = null
  }
}

async function setMemoryPriority(memoryId, priority) {
  updatingMemoryPriorityId.value = memoryId
  memoryMessage.value = ''
  try {
    await api.updateMemoryPriority(memoryId, priority)
    memoryMessage.value = priority > 0 ? t('pinMemoryDone') : t('unpinMemoryDone')
    await refreshAllMemoryData()
  } catch (e) {
    memoryMessage.value = t('updateMemoryPriorityFailed', { message: e.message })
  } finally {
    updatingMemoryPriorityId.value = null
  }
}

async function updateMemoryClientRule(memory, clientId, value) {
  memoryMessage.value = ''
  try {
    const nextRules = {
      ...(memory.client_rules || {}),
      [clientId]: value,
    }
    if (value === 'default') {
      delete nextRules[clientId]
    }
    await api.updateMemoryClientRules(memory.id, nextRules)
    memoryMessage.value = t('updateMemoryClientRulesDone')
    await loadMemories()
  } catch (e) {
    memoryMessage.value = t('updateMemoryClientRulesFailed', { message: e.message })
  }
}

async function mergeMemorySuggestion(item, index, deleteSources = false) {
  const key = `${item.left.id}-${item.right.id}-${index}`
  mergingMemorySuggestionKey.value = key
  memoryMessage.value = ''
  try {
    await api.mergeMemories({
      left_id: item.left.id,
      right_id: item.right.id,
      delete_sources: Boolean(deleteSources),
    })
    memoryMessage.value = deleteSources ? t('mergeMemoryAndDeleteDone') : t('mergeMemoryDone')
    await refreshAllMemoryData()
  } catch (e) {
    memoryMessage.value = t('mergeMemoryFailed', { message: e.message })
  } finally {
    mergingMemorySuggestionKey.value = ''
  }
}

async function resolveMemoryConflict(item, index, action) {
  const key = `${item.left.id}-${item.right.id}-${index}-${action}`
  resolvingMemoryConflictKey.value = key
  memoryMessage.value = ''
  try {
    await api.resolveMemoryConflict({
      left_id: item.left.id,
      right_id: item.right.id,
      action,
    })
    if (action === 'keep_left') {
      memoryMessage.value = t('resolveConflictKeepLeftDone')
    } else if (action === 'keep_right') {
      memoryMessage.value = t('resolveConflictKeepRightDone')
    } else {
      memoryMessage.value = t('resolveConflictMergeDone')
    }
    await refreshAllMemoryData()
  } catch (e) {
    memoryMessage.value = t('resolveConflictFailed', { message: e.message })
  } finally {
    resolvingMemoryConflictKey.value = ''
  }
}

const deletingMemoryId = ref(null)

async function removeMemoryRecord(memoryId) {
  if (!window.confirm(t('deleteMemoryConfirm'))) {
    return
  }
  deletingMemoryId.value = memoryId
  try {
    await api.deleteMemory(memoryId)
    await refreshAllMemoryData()
  } catch (e) {
    memoryMessage.value = t('deleteMemoryFailed', { message: e.message })
  } finally {
    deletingMemoryId.value = null
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
