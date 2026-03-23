<template>
  <section class="space-y-5">
    <router-link
      to="/conversations"
      class="inline-flex items-center gap-2 rounded-full bg-white/82 px-4 py-2 text-sm font-medium text-stone-700 shadow-sm ring-1 ring-stone-200/70 transition-colors hover:text-stone-900"
    >
      <span>&larr;</span>
      {{ t('backToThreads') }}
    </router-link>

    <div v-if="loading" class="memory-panel rounded-[28px] p-8 text-sm text-stone-500">{{ t('loadingConversation') }}</div>

    <div v-else-if="error" class="rounded-[28px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
      {{ error }}
    </div>

    <template v-else-if="conversation">
      <div v-if="actionError" class="rounded-[22px] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
        {{ actionError }}
      </div>

      <div class="rounded-[26px] border border-stone-200/60 bg-[rgba(255,253,248,0.52)] p-5 shadow-[0_8px_22px_rgba(71,52,31,0.03)] lg:p-6">
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <span>{{ platformEmoji(conversation.platform) }}</span>
            <span :class="['memory-badge', platformClass(conversation.platform)]">{{ conversation.platform }}</span>
            <span v-if="conversation.project" class="memory-badge bg-white/85 text-stone-700">{{ conversation.project }}</span>
            <span class="memory-badge bg-white/85 text-stone-700">{{ t('messages', { count: parsedMessages.length }) }}</span>
            <span class="memory-badge bg-white/85 text-stone-700">{{ t('importance') }} {{ conversation.importance ?? '-' }}</span>
          </div>
          <h1 class="mt-4 max-w-4xl text-[1.8rem] font-semibold leading-tight tracking-tight text-stone-900 lg:text-[2.15rem]">
            {{ heroTitle }}
          </h1>
          <p v-if="heroDescription" class="mt-3 max-w-3xl text-sm leading-7 text-stone-600">
            {{ heroDescription }}
          </p>
          <div class="mt-4 text-[11px] uppercase tracking-[0.18em] text-stone-400">
            {{ formatTime(conversation.timestamp) }}
          </div>
          <div class="mt-4">
            <div class="flex flex-wrap gap-3">
              <label class="inline-flex items-center gap-3 rounded-full bg-white/85 px-4 py-2 text-sm text-stone-700 ring-1 ring-stone-200/80">
                <span class="text-stone-500">{{ t('memoryTier') }}</span>
                <select
                  v-model="selectedMemoryTier"
                  class="border-0 bg-transparent pr-5 text-sm font-medium text-stone-900 focus:outline-none focus:ring-0"
                  @change="updateMemoryTier"
                >
                  <option value="temporary">{{ t('memoryTierTemporary') }}</option>
                  <option value="saved">{{ t('memoryTierSaved') }}</option>
                  <option value="pinned">{{ t('memoryTierPinned') }}</option>
                </select>
              </label>
              <button
                type="button"
                class="rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white ring-1 ring-[var(--brand)] transition-colors hover:bg-[var(--brand-deep)] disabled:opacity-50"
                :disabled="analyzing"
                @click="runAnalysis"
              >
                {{ analyzing ? t('analyzing') : t('analyze') }}
              </button>
              <button
                type="button"
                class="rounded-full bg-white/85 px-4 py-2 text-sm font-medium text-stone-700 ring-1 ring-stone-200/80 transition-colors hover:bg-stone-50 disabled:opacity-50"
                :disabled="extractingMemories"
                @click="extractMemories"
              >
                {{ extractingMemories ? t('extractingMemories') : t('extractMemories') }}
              </button>
              <button
                type="button"
                class="rounded-full bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700 ring-1 ring-rose-200 transition-colors hover:bg-rose-100 disabled:opacity-50"
                :disabled="deleting"
                @click="deleteCurrentConversation"
              >
                {{ deleting ? t('deletingConversation') : t('deleteConversation') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="space-y-6">
        <div class="rounded-[24px] border border-stone-200/45 bg-[rgba(255,253,248,0.32)] p-5 shadow-[0_6px_18px_rgba(71,52,31,0.02)] lg:p-6">
          <div class="flex items-end justify-between gap-4">
            <div>
              <div class="text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-400">{{ t('transcript') }}</div>
              <h2 class="mt-1 text-base font-medium tracking-tight text-stone-500">{{ t('transcriptSubtitle') }}</h2>
            </div>
            <div class="memory-badge bg-white/90 text-stone-700">
              {{ t('messages', { count: parsedMessages.length }) }}
              <span v-if="parsedMessages.length > renderedMessages.length">
                · {{ t('loadedCount', { loaded: renderedMessages.length, total: parsedMessages.length }) }}
              </span>
            </div>
          </div>

          <div v-if="parsedMessages.length === 0" class="mt-5 rounded-3xl bg-stone-100 px-5 py-6 text-sm text-stone-500">
            {{ t('noParsedMessages') }}
          </div>

          <div v-else class="memory-transcript-shell mt-8">
            <div class="memory-transcript-column">
              <div class="memory-transcript">
                <article
                  v-for="(message, index) in renderedMessages"
                  :key="`${message.role}-${index}`"
                  class="memory-transcript-row"
                  :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
                >
                  <div
                    class="memory-transcript-bubble"
                    :class="message.role === 'user' ? 'memory-transcript-user' : 'memory-transcript-assistant'"
                  >
                    <div
                      class="memory-message-header"
                      :class="message.role === 'user' ? 'memory-message-header-user' : ''"
                    >
                      <div class="memory-message-meta" :class="message.role === 'user' ? 'justify-end' : ''">
                        <span class="memory-message-dot" :class="message.role === 'user' ? 'bg-amber-500/70' : 'bg-stone-300'"></span>
                        <span>{{ message.role === 'user' ? t('you') : assistantLabel }}</span>
                      </div>
                      <button
                        type="button"
                        class="memory-message-copy"
                        :class="message.role === 'user' ? 'memory-message-copy-user' : ''"
                        @click.stop="copyMessage(message.content, index)"
                      >
                        {{ copiedMessageIndex === index ? t('copied') : t('copy') }}
                      </button>
                    </div>

                    <div
                      class="rounded-[24px]"
                      :class="message.role === 'user'
                        ? 'rounded-[22px] bg-stone-900 px-4 py-3 text-stone-50 shadow-[0_8px_18px_rgba(28,23,19,0.12)]'
                        : 'memory-assistant-surface px-2 py-1 text-stone-800'"
                    >
                      <div
                        class="memory-markdown"
                        :class="message.role === 'user' ? 'memory-markdown-user' : 'memory-markdown-assistant'"
                        v-html="message.html"
                      ></div>
                    </div>
                  </div>
                </article>
              </div>

              <div
                v-if="renderedMessages.length < parsedMessages.length"
                ref="transcriptSentinel"
                class="mt-5 flex justify-center"
              >
                <div class="rounded-full bg-white px-5 py-2.5 text-sm text-stone-500 ring-1 ring-stone-200/80">
                  {{ autoLoadingTranscript ? t('loadingMoreMessages') : t('loadMoreMessagesHint', { count: Math.min(messagePageSize, parsedMessages.length - renderedMessages.length) }) }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="memory-panel rounded-[24px] p-4 lg:p-5">
          <button
            class="flex w-full items-center justify-between gap-4 text-left"
            @click="showDetails = !showDetails"
          >
            <div>
              <div class="text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-400">{{ t('conversationTools') }}</div>
              <h3 class="mt-1 text-base font-medium tracking-tight text-stone-600">{{ t('conversationToolsDescription') }}</h3>
            </div>
            <span class="memory-badge bg-white text-stone-700">{{ showDetails ? t('hide') : t('show') }}</span>
          </button>
        </div>

        <div v-if="showDetails" class="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          <div class="memory-panel rounded-[28px] p-5 lg:p-6 xl:col-span-2">
            <div class="flex items-center justify-between gap-4">
              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">{{ t('aiAnalysis') }}</div>
                <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('conversationDistillation') }}</h3>
              </div>
              <button
                @click="runAnalysis"
                :disabled="analyzing"
                class="rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--brand-deep)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {{ analyzing ? t('analyzing') : t('analyze') }}
              </button>
            </div>

            <div v-if="analysisError" class="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {{ analysisError }}
            </div>

            <div v-if="analysis" class="mt-5 space-y-4">
              <div class="memory-surface rounded-3xl px-4 py-4">
                <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('analysisMode') }}</div>
                <div class="mt-2 text-sm font-medium text-stone-900">{{ analysisAIAvailable ? t('aiProvider') : t('fallbackExtraction') }}</div>
              </div>

              <div v-if="analysis.summary" class="memory-surface rounded-3xl px-4 py-4">
                <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('summary') }}</div>
                <div class="mt-2 text-sm leading-6 text-stone-700">{{ analysis.summary }}</div>
              </div>

              <div v-if="analysis.key_points?.length" class="memory-surface rounded-3xl px-4 py-4">
                <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('keyPoints') }}</div>
                <ul class="mt-3 space-y-2 text-sm leading-6 text-stone-700">
                  <li v-for="item in analysis.key_points" :key="item">{{ item }}</li>
                </ul>
              </div>

              <div v-if="analysis.topics?.length" class="memory-surface rounded-3xl px-4 py-4">
                <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('topics') }}</div>
                <div class="mt-3 flex flex-wrap gap-2">
                  <span v-for="topic in analysis.topics" :key="topic" class="memory-badge bg-teal-50 text-teal-800">
                    {{ topic }}
                  </span>
                </div>
              </div>

              <div v-if="analysis.key_decisions?.length" class="memory-surface rounded-3xl px-4 py-4">
                <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('keyDecisions') }}</div>
                <ul class="mt-3 space-y-2 text-sm leading-6 text-stone-700">
                  <li v-for="item in analysis.key_decisions" :key="item">{{ item }}</li>
                </ul>
              </div>

              <div v-if="analysis.todos?.length" class="memory-surface rounded-3xl px-4 py-4">
                <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('todos') }}</div>
                <ul class="mt-3 space-y-2 text-sm leading-6 text-stone-700">
                  <li v-for="item in analysis.todos" :key="item">{{ item }}</li>
                </ul>
              </div>
            </div>

            <div v-else class="mt-5 rounded-3xl bg-stone-100 px-4 py-5 text-sm leading-6 text-stone-500">
              {{ t('runAnalysisHint') }}
            </div>
          </div>

          <div class="memory-panel rounded-[28px] p-5 lg:p-6">
            <div class="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">{{ t('metadata') }}</div>
            <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('recordDetails') }}</h3>
            <dl class="mt-5 space-y-4 text-sm">
              <div class="memory-surface rounded-3xl px-4 py-4">
                <dt class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('conversationId') }}</dt>
                <dd class="mt-2 break-all font-mono text-xs text-stone-700">{{ conversation.id }}</dd>
              </div>
              <div class="memory-surface rounded-3xl px-4 py-4">
                <dt class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('project') }}</dt>
                <dd class="mt-2 text-sm text-stone-700">{{ conversation.project || t('none') }}</dd>
              </div>
              <div class="memory-surface rounded-3xl px-4 py-4">
                <dt class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('provider') }}</dt>
                <dd class="mt-2 text-sm text-stone-700">{{ conversation.provider || t('none') }}</dd>
              </div>
              <div class="memory-surface rounded-3xl px-4 py-4">
                <dt class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('model') }}</dt>
                <dd class="mt-2 text-sm text-stone-700">{{ conversation.model || t('none') }}</dd>
              </div>
              <div class="memory-surface rounded-3xl px-4 py-4">
                <dt class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('assistant') }}</dt>
                <dd class="mt-2 text-sm text-stone-700">{{ assistantLabel }}</dd>
              </div>
              <div class="memory-surface rounded-3xl px-4 py-4">
                <dt class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('summarySource') }}</dt>
                <dd class="mt-2 text-sm text-stone-700">{{ summarySourceLabel }}</dd>
              </div>
              <div class="memory-surface rounded-3xl px-4 py-4">
                <dt class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryTier') }}</dt>
                <dd class="mt-2 text-sm text-stone-700">{{ memoryTierLabel }}</dd>
              </div>
              <div class="memory-surface rounded-3xl px-4 py-4">
                <dt class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('recoveryMode') }}</dt>
                <dd class="mt-2 text-sm text-stone-700">{{ recoveryModeLabel }}</dd>
              </div>
              <div class="memory-surface rounded-3xl px-4 py-4">
                <dt class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('status') }}</dt>
                <dd class="mt-2 text-sm text-stone-700">{{ conversation.status || t('completed') }}</dd>
              </div>
            </dl>
          </div>

          <div class="memory-panel rounded-[28px] p-5 lg:p-6">
            <div class="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">{{ t('related') }}</div>
            <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('nearbyConversations') }}</h3>

            <div v-if="loadingRelated" class="mt-4 text-sm text-stone-500">{{ t('loadingRelated') }}</div>

            <div v-else-if="related.length === 0" class="mt-4 rounded-3xl bg-stone-100 px-4 py-5 text-sm text-stone-500">
              {{ t('noRelated') }}
            </div>

            <div v-else class="mt-5 space-y-3">
              <router-link
                v-for="r in related"
                :key="r.id"
                :to="`/conversations/${r.id}`"
                class="memory-surface block rounded-[24px] px-4 py-4 transition-transform duration-200 hover:-translate-y-0.5"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="flex items-center gap-2">
                    <span>{{ platformEmoji(r.platform) }}</span>
                    <span class="text-sm font-medium text-stone-900">{{ r.platform }}</span>
                  </div>
                  <span class="memory-badge bg-teal-50 text-teal-800">{{ (r.similarity * 100).toFixed(0) }}%</span>
                </div>
                <p class="mt-3 text-sm leading-6 text-stone-600">{{ compactSummary(r.summary) }}</p>
              </router-link>
            </div>
          </div>

          <div class="memory-panel rounded-[28px] p-5 lg:p-6">
            <div class="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">{{ t('memoryCenter') }}</div>
            <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('conversationMemoriesTitle') }}</h3>

            <div v-if="conversationMemories.length === 0" class="mt-4 rounded-3xl bg-stone-100 px-4 py-5 text-sm text-stone-500">
              {{ t('noConversationMemories') }}
            </div>

            <div v-else class="mt-5 space-y-3">
              <div
                v-for="memory in conversationMemories"
                :key="memory.id"
                class="memory-surface rounded-[24px] px-4 py-4"
              >
                <div class="flex flex-wrap items-center gap-2">
                  <span class="memory-badge bg-stone-100 text-stone-700">{{ memory.category }}</span>
                  <span class="memory-badge bg-sky-50 text-sky-800">{{ memory.key }}</span>
                  <span class="text-xs text-stone-400">{{ t('memoryConfidence') }} {{ Number(memory.effective_confidence ?? memory.confidence ?? 0).toFixed(1) }}</span>
                </div>
                <div class="mt-3 text-sm leading-6 text-stone-700">{{ memory.value }}</div>
                <div v-if="memory.parent_memories?.length" class="mt-3 border-t border-stone-200/70 pt-3">
                  <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryLineage') }}</div>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <span
                      v-for="parent in memory.parent_memories"
                      :key="`${memory.id}-parent-${parent.memory_id}`"
                      class="memory-badge bg-amber-50 text-amber-900"
                    >
                      {{ parent.category || t('memoryMergedFrom') }} / {{ parent.key || parent.memory_id }}
                    </span>
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
                        <span class="memory-badge bg-white text-stone-700">{{ t(entry.label) }}</span>
                        <span class="text-xs text-stone-400">{{ formatDateTime(entry.timestamp) || entry.timestamp || t('none') }}</span>
                      </div>
                      <div class="mt-2 leading-6 text-stone-600">{{ entry.description || t('none') }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="memory-panel rounded-[28px] p-5 lg:p-6 xl:col-span-2">
            <div class="flex items-center justify-between gap-4">
              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">{{ t('resumeWorkspace') }}</div>
                <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('resumeWorkspaceTitle') }}</h3>
              </div>
              <button
                type="button"
                class="rounded-full bg-white px-4 py-2 text-sm font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50"
                @click="copyExportPreview"
              >
                {{ t('copyPreview') }}
              </button>
            </div>
            <p class="mt-3 text-sm leading-6 text-stone-500">{{ t('resumeWorkspaceDescription') }}</p>

            <div v-if="exportError" class="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {{ exportError }}
            </div>

            <div v-if="memoryActionMessage" class="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              {{ memoryActionMessage }}
            </div>

            <div v-if="exportMessage" class="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              {{ exportMessage }}
            </div>

            <div class="mt-5 grid gap-4 lg:grid-cols-[minmax(0,15rem)_minmax(0,1fr)]">
              <label class="grid gap-2">
                <span class="text-[11px] font-semibold uppercase tracking-[0.16em] text-stone-500">{{ t('exportTarget') }}</span>
                <select
                  v-model="selectedExportClient"
                  class="rounded-2xl border border-stone-200 bg-white/85 px-4 py-3 text-sm text-stone-900 outline-none focus:border-[var(--brand)]/40 focus:ring-2 focus:ring-[var(--brand)]/10"
                >
                  <option value="" disabled>{{ t('all') }}</option>
                  <option v-for="client in exportClients" :key="client.client" :value="client.client">
                    {{ client.display_name }}
                  </option>
                </select>
              </label>

              <label class="grid gap-2">
                <span class="text-[11px] font-semibold uppercase tracking-[0.16em] text-stone-500">{{ t('workspacePath') }}</span>
                <input
                  v-model="workspacePath"
                  type="text"
                  class="rounded-2xl border border-stone-200 bg-white/85 px-4 py-3 text-sm text-stone-900 outline-none focus:border-[var(--brand)]/40 focus:ring-2 focus:ring-[var(--brand)]/10"
                  :placeholder="t('workspacePathPlaceholder')"
                />
              </label>
            </div>

            <div class="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                class="rounded-full bg-stone-900 px-4 py-2 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:opacity-50"
                :disabled="!selectedExportClient || exportingPreview"
                @click="generateExportPreview"
              >
                {{ exportingPreview ? t('loading') : t('exportPreview') }}
              </button>
              <button
                type="button"
                class="rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--brand-deep)] disabled:opacity-50"
                :disabled="!selectedExportClient || !workspacePath.trim() || applyingExport"
                @click="applyExport"
              >
                {{ applyingExport ? t('applying') : t('exportApply') }}
              </button>
            </div>

            <div v-if="exportPreview" class="mt-5 space-y-4">
              <div class="grid gap-3 sm:grid-cols-2">
                <div class="memory-surface rounded-3xl px-4 py-4">
                  <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('targetPath') }}</div>
                  <div class="mt-2 break-all text-sm text-stone-700">{{ exportTargetPath || exportPreview.target_relpath }}</div>
                </div>
                <div class="memory-surface rounded-3xl px-4 py-4">
                  <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('backupPath') }}</div>
                  <div class="mt-2 break-all text-sm text-stone-700">{{ exportBackupPath || t('none') }}</div>
                </div>
              </div>

              <div class="memory-surface rounded-3xl px-4 py-4">
                <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryCenter') }}</div>
                <div class="mt-2 text-sm text-stone-700">{{ t('exportMemoryCountDetailed', { selected: exportPreview.memory_count || 0, total: exportPreview.total_memory_count || exportPreview.memory_count || 0 }) }}</div>
                <div v-if="exportPreview.strategy_summary" class="mt-2 text-sm leading-6 text-stone-500">{{ t('exportStrategySummary', { summary: exportPreview.strategy_summary }) }}</div>
              </div>

              <div v-if="exportMemoryOptions.length" class="memory-surface rounded-3xl px-4 py-4">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryCenter') }}</div>
                    <div class="mt-2 text-sm text-stone-700">{{ t('exportMemorySelection') }}</div>
                  </div>
                  <button
                    type="button"
                    class="rounded-full bg-white px-3 py-1.5 text-xs font-medium text-stone-700 ring-1 ring-stone-200 transition-colors hover:bg-stone-50"
                    @click="useRecommendedExportMemories"
                  >
                    {{ t('useRecommendedMemories') }}
                  </button>
                </div>
                <div class="mt-3 grid gap-2">
                  <label
                    v-for="memory in exportMemoryOptions"
                    :key="`export-memory-${memory.id}`"
                    class="flex items-start gap-3 rounded-2xl bg-white/80 px-3 py-3 text-sm text-stone-700 ring-1 ring-stone-200/70"
                  >
                    <input
                      :checked="selectedExportMemoryIds.includes(Number(memory.id))"
                      type="checkbox"
                      class="mt-1 h-4 w-4 rounded border-stone-300 text-stone-900 focus:ring-stone-400"
                      @change="toggleExportMemory(memory.id)"
                    />
                    <div class="min-w-0">
                      <div class="flex flex-wrap items-center gap-2">
                        <span class="memory-badge bg-stone-100 text-stone-700">{{ memory.category }}</span>
                        <span class="memory-badge bg-sky-50 text-sky-800">{{ memory.key }}</span>
                        <span v-if="Number(memory.priority || 0) > 0" class="memory-badge bg-amber-100 text-amber-900">{{ t('memoryPinned') }}</span>
                      </div>
                      <div class="mt-2 line-clamp-2 leading-6 text-stone-600">{{ memory.value }}</div>
                    </div>
                  </label>
                </div>
              </div>

              <div v-if="exportPreview.selected_memories?.length" class="memory-surface rounded-3xl px-4 py-4">
                <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryCenter') }}</div>
                <div class="mt-2 text-sm text-stone-700">{{ t('exportMemoryReasons') }}</div>
                <div class="mt-3 space-y-3">
                  <div
                    v-for="memory in exportPreview.selected_memories"
                    :key="`selected-memory-${memory.id}`"
                    class="rounded-2xl bg-white/80 px-3 py-3 ring-1 ring-stone-200/70"
                  >
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="memory-badge bg-stone-100 text-stone-700">{{ memory.category }}</span>
                      <span class="memory-badge bg-sky-50 text-sky-800">{{ memory.key }}</span>
                      <span v-if="Number(memory.priority || 0) > 0" class="memory-badge bg-amber-100 text-amber-900">{{ t('memoryPinned') }}</span>
                    </div>
                    <div class="mt-2 line-clamp-2 text-sm leading-6 text-stone-600">{{ memory.value }}</div>
                    <div class="mt-3 flex flex-wrap gap-2">
                      <span
                        v-for="reason in memory.reasons || []"
                        :key="`memory-reason-${memory.id}-${reason}`"
                        class="memory-badge bg-white text-stone-700 ring-1 ring-stone-200/70"
                      >
                        {{ t(reason) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div
                v-if="exportMemoryDiff.added.length || exportMemoryDiff.removed.length"
                class="memory-surface rounded-3xl px-4 py-4"
              >
                <div class="text-[11px] uppercase tracking-[0.16em] text-stone-500">{{ t('memoryCenter') }}</div>
                <div class="mt-2 text-sm text-stone-700">{{ t('exportMemoryDiffTitle') }}</div>

                <div v-if="exportMemoryDiff.added.length" class="mt-3">
                  <div class="text-xs font-medium text-emerald-700">{{ t('exportMemoryAdded') }}</div>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <span
                      v-for="memory in exportMemoryDiff.added"
                      :key="`added-memory-${memory.id}`"
                      class="memory-badge bg-emerald-50 text-emerald-800"
                    >
                      {{ memory.category }} / {{ memory.key }}
                    </span>
                  </div>
                </div>

                <div v-if="exportMemoryDiff.removed.length" class="mt-3">
                  <div class="text-xs font-medium text-rose-700">{{ t('exportMemoryRemoved') }}</div>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <span
                      v-for="memory in exportMemoryDiff.removed"
                      :key="`removed-memory-${memory.id}`"
                      class="memory-badge bg-rose-50 text-rose-800"
                    >
                      {{ memory.category }} / {{ memory.key }}
                    </span>
                  </div>
                </div>
              </div>

              <pre class="max-h-[28rem] overflow-auto rounded-[24px] bg-stone-950 p-5 text-sm leading-7 text-stone-100">{{ exportPreview.content }}</pre>
            </div>
          </div>

          <div class="memory-panel rounded-[28px] p-5 lg:p-6 lg:col-span-2 xl:col-span-3">
            <button
              class="flex w-full items-center justify-between gap-4 text-left"
              @click="showContent = !showContent"
            >
              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">{{ t('fallback') }}</div>
                <h3 class="mt-2 text-xl font-semibold text-stone-900">{{ t('rawStoredContent') }}</h3>
              </div>
              <span class="memory-badge bg-white text-stone-700">{{ showContent ? t('hide') : t('show') }}</span>
            </button>

            <div v-if="showContent" class="mt-5">
              <pre class="max-h-[28rem] overflow-auto rounded-[24px] bg-stone-950 p-5 text-sm leading-7 text-stone-100">{{ conversation.full_content || t('noContentAvailable') }}</pre>
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/memory-hub.js'
import { platformEmoji, platformClass } from '../constants/platforms.js'
import { useI18n } from '../composables/useI18n.js'

const route = useRoute()
const router = useRouter()
const messagePageSize = 24
const conversation = ref(null)
const related = ref([])
const conversationMemories = ref([])
const loading = ref(true)
const loadingRelated = ref(true)
const error = ref(null)
const actionError = ref(null)
const showContent = ref(false)
const showDetails = ref(true)
const analyzing = ref(false)
const analysis = ref(null)
const analysisError = ref(null)
const analysisAIAvailable = ref(false)
const copiedMessageIndex = ref(null)
const exportClients = ref([])
const selectedExportClient = ref('')
const workspacePath = ref('')
const exportPreview = ref(null)
const previousExportPreview = ref(null)
const exportError = ref(null)
const exportMessage = ref('')
const exportingPreview = ref(false)
const applyingExport = ref(false)
const exportTargetPath = ref('')
const exportBackupPath = ref('')
const exportMemoryOptions = ref([])
const selectedExportMemoryIds = ref([])
const visibleMessageLimit = ref(messagePageSize)
const transcriptSentinel = ref(null)
const autoLoadingTranscript = ref(false)
const deleting = ref(false)
const selectedMemoryTier = ref('temporary')
const extractingMemories = ref(false)
const memoryActionMessage = ref('')
let transcriptObserver = null
let loadRequestId = 0
const { t, formatDateTime } = useI18n()

const parsedMessages = computed(() => parseMessages(conversation.value?.full_content || ''))
const renderedMessages = computed(() => parsedMessages.value.slice(0, visibleMessageLimit.value))
const assistantLabel = computed(() => getAssistantLabel(conversation.value))
const summarySourceLabel = computed(() => {
  const source = String(conversation.value?.summary_source || '').trim().toLowerCase()
  if (source === 'ai') return t('summarySourceAi')
  if (source === 'imported') return t('summarySourceImported')
  if (!source) return t('summarySourceUnknown')
  return t('summarySourceFallback')
})
const memoryTierLabel = computed(() => {
  const tier = String(conversation.value?.memory_tier || '').trim().toLowerCase()
  if (tier === 'saved') return t('memoryTierSaved')
  if (tier === 'pinned') return t('memoryTierPinned')
  return t('memoryTierTemporary')
})
const recoveryModeLabel = computed(() => {
  const mode = String(conversation.value?.recovery_mode || '').trim().toLowerCase()
  if (!mode) return t('recoveryModeUnknown')
  if (mode === 'live-rpc') return t('recoveryModeLiveRpc')
  if (mode === 'live-rpc-summary-fallback') return t('recoveryModeLiveRpcSummaryFallback')
  if (mode === 'pb-undecoded') return t('recoveryModePbUndecoded')
  return mode
})
const heroTitle = computed(() => {
  const summary = String(conversation.value?.summary || '').trim()
  const project = String(conversation.value?.project || '').trim()
  return summary.split('\n')[0] || project || t('conversationDetailFallbackTitle')
})
const heroDescription = computed(() => {
  const summary = String(conversation.value?.summary || '').trim()
  if (!summary) return ''
  const normalized = summary.replace(/\s+/g, ' ').trim()
  return normalized === heroTitle.value ? '' : normalized
})
const exportMemoryDiff = computed(() => {
  const current = Array.isArray(exportPreview.value?.selected_memories) ? exportPreview.value.selected_memories : []
  const previous = Array.isArray(previousExportPreview.value?.selected_memories) ? previousExportPreview.value.selected_memories : []
  if (!current.length && !previous.length) {
    return { added: [], removed: [] }
  }

  const currentMap = new Map(current.map(memory => [Number(memory.id), memory]))
  const previousMap = new Map(previous.map(memory => [Number(memory.id), memory]))

  return {
    added: current.filter(memory => !previousMap.has(Number(memory.id))),
    removed: previous.filter(memory => !currentMap.has(Number(memory.id))),
  }
})

function formatTime(ts) {
  return formatDateTime(ts)
}

function compactSummary(text) {
  return String(text || '').replace(/\s+/g, ' ').trim() || t('noSummaryYet')
}

function loadMoreMessages() {
  visibleMessageLimit.value += messagePageSize
}

function setupTranscriptObserver() {
  if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') {
    return
  }

  transcriptObserver?.disconnect()
  transcriptObserver = new IntersectionObserver((entries) => {
    const entry = entries[0]
    if (!entry?.isIntersecting) {
      return
    }
    if (loading.value || renderedMessages.value.length >= parsedMessages.value.length) {
      return
    }
    autoLoadingTranscript.value = true
    loadMoreMessages()
    window.setTimeout(() => {
      autoLoadingTranscript.value = false
    }, 120)
  }, {
    rootMargin: '240px 0px',
  })

  if (transcriptSentinel.value) {
    transcriptObserver.observe(transcriptSentinel.value)
  }
}

function getAssistantLabel(record) {
  const explicitLabel = String(record?.assistant_label || '').trim()
  if (explicitLabel) return explicitLabel
  const model = String(record?.model || '').trim()
  if (model) return model
  const provider = String(record?.provider || '').trim().toLowerCase()
  const providerLabels = { anthropic: 'Claude', openai: 'ChatGPT', google: 'Gemini', xai: 'Grok', deepseek: 'DeepSeek' }
  if (providerLabels[provider]) return providerLabels[provider]
  const platform = String(record?.platform || '').trim().toLowerCase()
  const platformLabels = {
    claude_web: 'Claude',
    claude_code: 'Claude Code',
    chatgpt: 'ChatGPT',
    gemini: 'Gemini',
    gemini_cli: 'Gemini CLI',
    grok: 'Grok',
    deepseek: 'DeepSeek',
    codex: 'Codex',
    antigravity: 'Antigravity',
  }
  return platformLabels[platform] || t('assistant')
}

function parseMessages(fullContent) {
  const lines = String(fullContent || '').split('\n')
  const messages = []
  let current = null
  for (const rawLine of lines) {
    const line = rawLine.replace(/\r/g, '')
    const match = line.match(/^(user|assistant):\s?(.*)$/)
    if (match) {
      if (current) {
        current.content = current.content.trim()
        if (current.content) {
          current.html = renderMessageHtml(current.content, current.role)
          messages.push(current)
        }
      }
      current = { role: match[1], content: match[2] || '', html: '' }
      continue
    }
    if (!current) continue
    current.content += `${current.content ? '\n' : ''}${line}`
  }
  if (current) {
    current.content = current.content.trim()
    if (current.content) {
      current.html = renderMessageHtml(current.content, current.role)
      messages.push(current)
    }
  }
  return messages
}

function normalizeMessageContent(content) {
  return String(content || '')
    .replace(/\r/g, '')
    .replace(/<details>/gi, '')
    .replace(/<\/details>/gi, '')
    .replace(/<summary>(.*?)<\/summary>/gi, (_, text) => `\nThinking: ${text}\n`)
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function sanitizeHtml(html) {
  const div = document.createElement('div')
  div.innerHTML = html
  div.querySelectorAll('script,iframe,object,embed,form,style,link').forEach(el => el.remove())
  div.querySelectorAll('*').forEach(el => {
    for (const attr of [...el.attributes]) {
      if (attr.name.startsWith('on') || attr.name === 'srcdoc' || (attr.name === 'href' && attr.value.trim().toLowerCase().startsWith('javascript:'))) {
        el.removeAttribute(attr.name)
      }
    }
  })
  return div.innerHTML
}

function renderMessageHtml(content, role = 'assistant') {
  const normalized = preprocessMarkdownSource(normalizeMessageContent(content))
  const blocks = finalizeMarkdownBlocks(parseMarkdownBlocks(normalized))
  return sanitizeHtml(blocks.map(renderMarkdownBlock).join(''))
}

function preprocessMarkdownSource(content) {
  return String(content || '')
}

function parseMarkdownBlocks(content) {
  const lines = String(content || '').split('\n')
  const blocks = []
  let paragraph = []
  let listItems = []
  let codeLines = []
  let codeLanguage = ''
  let inCode = false

  function flushParagraph() {
    if (!paragraph.length) return
    blocks.push({ type: 'paragraph', lines: [...paragraph] })
    paragraph = []
  }

  function flushList() {
    if (!listItems.length) return
    blocks.push({ type: 'list', items: [...listItems] })
    listItems = []
  }

  function flushCode() {
    if (!codeLines.length && !codeLanguage) return
    blocks.push({ type: 'code', language: codeLanguage, lines: [...codeLines] })
    codeLines = []
    codeLanguage = ''
  }

  for (const rawLine of lines) {
    const line = rawLine.replace(/\r/g, '')
    const trimmed = line.trim()

    if (trimmed.startsWith('```')) {
      if (inCode) {
        flushCode()
        inCode = false
      } else {
        flushParagraph()
        flushList()
        inCode = true
        codeLanguage = trimmed.slice(3).trim()
      }
      continue
    }

    if (inCode) {
      codeLines.push(line)
      continue
    }

    if (!trimmed) {
      flushParagraph()
      flushList()
      continue
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/)
    if (headingMatch) {
      flushParagraph()
      flushList()
      blocks.push({ type: 'heading', level: headingMatch[1].length, text: headingMatch[2] })
      continue
    }

    const listMatch = trimmed.match(/^[-*]\s+(.*)$/)
    if (listMatch) {
      flushParagraph()
      listItems.push(listMatch[1])
      continue
    }

    flushList()
    paragraph.push(line)
  }

  if (inCode) {
    flushCode()
  }
  flushParagraph()
  flushList()
  return blocks
}

function finalizeMarkdownBlocks(blocks) {
  return blocks
}

function renderMarkdownBlock(block) {
  if (block.type === 'heading') {
    const level = Math.min(Math.max(block.level || 1, 1), 6)
    return `<h${level} class="memory-md-heading memory-md-heading-${level}">${renderInline(block.text)}</h${level}>`
  }
  if (block.type === 'list') {
    const items = block.items.map(item => `<li>${renderInline(item)}</li>`).join('')
    return `<ul class="memory-md-list">${items}</ul>`
  }
  if (block.type === 'code') {
    const language = block.language ? `<div class="memory-md-code-label">${escapeHtml(block.language)}</div>` : ''
    return `${language}<pre class="memory-md-code"><code>${escapeHtml(block.lines.join('\n'))}</code></pre>`
  }
  if (block.type === 'paragraph') {
    return `<p class="memory-md-paragraph">${renderInline(block.lines.join('\n'))}</p>`
  }
  return ''
}

function renderInline(text) {
  let html = escapeHtml(String(text || ''))
  html = html.replace(/`([^`]+)`/g, '<code class="memory-md-inline-code">$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  return html.replace(/\n/g, '<br />')
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

async function handleContentClick(event) {
  const button = event.target instanceof HTMLElement ? event.target.closest('[data-copy-code]') : null
  if (!button) return
}

async function copyMessage(content, index) {
  const text = normalizeMessageContent(content)
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copiedMessageIndex.value = index
    window.setTimeout(() => {
      if (copiedMessageIndex.value === index) copiedMessageIndex.value = null
    }, 1400)
  } catch {
    copiedMessageIndex.value = null
  }
}

async function copyExportPreview() {
  if (!exportPreview.value?.content) {
    exportError.value = t('previewEmpty')
    return
  }
  try {
    await navigator.clipboard.writeText(exportPreview.value.content)
    exportMessage.value = t('previewReady')
  } catch {
    exportError.value = t('copyFailed')
  }
}

async function loadExportClients() {
  try {
    const result = await api.listExportClients()
    exportClients.value = result.clients || []
    if (!selectedExportClient.value && exportClients.value.length > 0) {
      selectedExportClient.value = exportClients.value[0].client
    }
  } catch (e) {
    exportError.value = t('loadTargetsFailed', { message: e.message })
  }
}

async function loadExportMemories() {
  try {
    const result = await api.listMemories()
    exportMemoryOptions.value = (result.memories || []).filter(memory => String(memory.status || 'active') === 'active')
  } catch {
    exportMemoryOptions.value = []
  }
}

function toggleExportMemory(memoryId) {
  const normalizedId = Number(memoryId)
  if (!normalizedId) return
  if (selectedExportMemoryIds.value.includes(normalizedId)) {
    selectedExportMemoryIds.value = selectedExportMemoryIds.value.filter(id => id !== normalizedId)
    return
  }
  selectedExportMemoryIds.value = [...selectedExportMemoryIds.value, normalizedId]
}

function useRecommendedExportMemories() {
  selectedExportMemoryIds.value = Array.isArray(exportPreview.value?.selected_memory_ids)
    ? exportPreview.value.selected_memory_ids.map(id => Number(id)).filter(Boolean)
    : []
}

async function generateExportPreview() {
  if (!route.params.id || !selectedExportClient.value) return
  exportingPreview.value = true
  exportError.value = null
  exportMessage.value = ''
  try {
    previousExportPreview.value = exportPreview.value
    const result = await api.previewConversationExport(
      route.params.id,
      selectedExportClient.value,
      selectedExportMemoryIds.value,
    )
    exportPreview.value = result
    if (!selectedExportMemoryIds.value.length && Array.isArray(result.selected_memory_ids)) {
      selectedExportMemoryIds.value = result.selected_memory_ids.map(id => Number(id)).filter(Boolean)
    }
    exportTargetPath.value = workspacePath.value.trim()
      ? `${workspacePath.value.trim()}\\${String(result.target_relpath || '').replace(/\//g, '\\')}`
      : result.target_relpath || ''
    exportBackupPath.value = ''
    exportMessage.value = t('previewReady')
  } catch (e) {
    exportError.value = t('exportPreviewFailed', { message: e.message })
  } finally {
    exportingPreview.value = false
  }
}

async function applyExport() {
  if (!route.params.id || !selectedExportClient.value || !workspacePath.value.trim()) return
  applyingExport.value = true
  exportError.value = null
  exportMessage.value = ''
  try {
    previousExportPreview.value = exportPreview.value
    const result = await api.applyConversationExport(route.params.id, {
      client: selectedExportClient.value,
      workspace_path: workspacePath.value.trim(),
      selected_memory_ids: selectedExportMemoryIds.value,
    })
    exportPreview.value = result
    exportTargetPath.value = result.target_path || ''
    exportBackupPath.value = result.backup_path || ''
    exportMessage.value = t('exportSuccess', { target: result.target_path || result.target_relpath || result.client_display_name })
  } catch (e) {
    exportError.value = t('exportApplyFailed', { message: e.message })
  } finally {
    applyingExport.value = false
  }
}

async function loadData(id) {
  const thisRequest = ++loadRequestId
  loading.value = true
  loadingRelated.value = true
  error.value = null
  analysis.value = null
  analysisError.value = null
  analysisAIAvailable.value = false
  copiedMessageIndex.value = null
  showContent.value = false
  exportPreview.value = null
  previousExportPreview.value = null
  exportError.value = null
  exportMessage.value = ''
  memoryActionMessage.value = ''
  exportTargetPath.value = ''
  exportBackupPath.value = ''
  exportMemoryOptions.value = []
  selectedExportMemoryIds.value = []
  visibleMessageLimit.value = messagePageSize
  try {
    const conv = await api.getConversation(id)
    if (thisRequest !== loadRequestId) return
    conversation.value = conv
    selectedMemoryTier.value = String(conv?.memory_tier || 'temporary')
  } catch (e) {
    if (thisRequest !== loadRequestId) return
    error.value = t('failedToLoadConversation', { message: e.message })
  } finally {
    if (thisRequest === loadRequestId) loading.value = false
  }
  if (thisRequest !== loadRequestId) return
  try {
    const result = await api.getRelated(id)
    if (thisRequest !== loadRequestId) return
    related.value = result.related || result || []
  } catch {
    if (thisRequest !== loadRequestId) return
    related.value = []
  } finally {
    if (thisRequest === loadRequestId) loadingRelated.value = false
  }
  if (thisRequest !== loadRequestId) return
  try {
    const memoryResult = await api.getConversationMemories(id)
    if (thisRequest !== loadRequestId) return
    conversationMemories.value = memoryResult.memories || []
  } catch {
    if (thisRequest !== loadRequestId) return
    conversationMemories.value = []
  }
}

async function updateMemoryTier() {
  if (!route.params.id) return
  const previousTier = conversation.value?.memory_tier || 'temporary'
  actionError.value = null
  try {
    const result = await api.updateConversationMemoryTier(route.params.id, selectedMemoryTier.value)
    conversation.value = {
      ...conversation.value,
      memory_tier: result.memory_tier,
    }
  } catch (e) {
    selectedMemoryTier.value = previousTier
    actionError.value = t('updateMemoryTierFailed', { message: e.message })
  }
}

async function extractMemories() {
  if (!route.params.id || extractingMemories.value) return
  extractingMemories.value = true
  actionError.value = null
  memoryActionMessage.value = ''
  try {
    const result = await api.extractMemoriesFromConversation(route.params.id)
    const count = Number(result.inserted_count || 0)
    memoryActionMessage.value = count > 0
      ? t('extractMemoriesDone', { count })
      : t('extractMemoriesEmpty')
    const memoryResult = await api.getConversationMemories(route.params.id)
    conversationMemories.value = memoryResult.memories || []
  } catch (e) {
    actionError.value = t('extractMemoriesFailed', { message: e.message })
  } finally {
    extractingMemories.value = false
  }
}

async function runAnalysis() {
  if (!route.params.id || analyzing.value) return
  analyzing.value = true
  analysisError.value = null
  try {
    const result = await api.analyzeConversation(route.params.id)
    analysis.value = result.analysis || null
    analysisAIAvailable.value = Boolean(result.ai_available)
    if (analysis.value?.summary) {
      conversation.value = { ...conversation.value, summary: analysis.value.summary }
    }
  } catch (e) {
    analysisError.value = t('analyzeConversationFailed', { message: e.message })
  } finally {
    analyzing.value = false
  }
}

async function deleteCurrentConversation() {
  if (!route.params.id || deleting.value) return

  const confirmed = window.confirm(t('deleteConversationConfirm'))
  if (!confirmed) return

  deleting.value = true
  actionError.value = null
  try {
    await api.deleteConversation(route.params.id)
    await router.push('/conversations')
  } catch (e) {
    actionError.value = t('deleteConversationFailed', { message: e.message })
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  await Promise.allSettled([loadExportClients(), loadExportMemories()])
  await loadData(route.params.id)
  setupTranscriptObserver()
})

watch(() => route.params.id, (newId) => {
  if (newId) loadData(newId)
})

watch([parsedMessages, renderedMessages, transcriptSentinel], () => {
  setupTranscriptObserver()
})

onBeforeUnmount(() => {
  transcriptObserver?.disconnect()
})
</script>
