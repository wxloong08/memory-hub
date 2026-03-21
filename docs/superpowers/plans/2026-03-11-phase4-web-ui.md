# Phase 4.2: Web UI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
> **评审状态:** 已合并 Gemini/Codex/Claude 三方评审修订 (2026-03-12)

**Goal:** Build a Vue 3 Web UI for viewing, searching, and managing synced conversations from all platforms.

**Architecture:** Vue 3 SPA with Vue Router, connecting to existing Memory Hub FastAPI backend at localhost:8765. Tailwind CSS for styling.

**Tech Stack:** Vue 3, Vite, Tailwind CSS, Vue Router, Axios

**前置依赖:** Phase 0 数据契约已完成（提供 `/api/conversations/list`, `/api/conversations/{id}`, 转换后的 `/api/search` 和 `/api/related` 端点）

---

## Chunk 1: Project Setup + API Layer

### Task 1: Scaffold Vue 3 project

**Files:**
- Create: `web-ui/package.json`
- Create: `web-ui/vite.config.js`
- Create: `web-ui/index.html`
- Create: `web-ui/src/main.js`
- Create: `web-ui/src/App.vue`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "claude-memory-ui",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "axios": "^1.7.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.4.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

- [ ] **Step 2: Create vite.config.js**

```javascript
// web-ui/vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8765',
        changeOrigin: true
      },
      '/health': {
        target: 'http://localhost:8765',
        changeOrigin: true
      }
    }
  }
})
```

- [ ] **Step 3: Create Tailwind config files**

```javascript
// web-ui/tailwind.config.js
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        primary: { 50: '#eef2ff', 100: '#e0e7ff', 500: '#6366f1', 600: '#4f46e5', 700: '#4338ca' },
      }
    }
  },
  plugins: []
}
```

```javascript
// web-ui/postcss.config.js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {}
  }
}
```

- [ ] **Step 4: Create index.html**

```html
<!-- web-ui/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Claude Memory System</title>
</head>
<body class="bg-gray-50 min-h-screen">
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 5: Create src/style.css**

```css
/* web-ui/src/style.css */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 6: Create src/main.js**

```javascript
// web-ui/src/main.js
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router/index.js'
import './style.css'

const app = createApp(App)
app.use(router)
app.mount('#app')
```

- [ ] **Step 7: Create src/App.vue (shell with nav)**

```vue
<!-- web-ui/src/App.vue -->
<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Sidebar Navigation -->
    <nav class="fixed left-0 top-0 h-full w-56 bg-white border-r border-gray-200 flex flex-col">
      <div class="p-4 border-b border-gray-100">
        <div class="flex items-center gap-2">
          <span class="text-2xl">🧠</span>
          <div>
            <div class="font-semibold text-gray-800">Memory Hub</div>
            <div class="text-xs text-gray-400">v2.0</div>
          </div>
        </div>
      </div>
      <div class="flex-1 p-3 space-y-1">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors"
          :class="$route.path === item.path ? 'bg-primary-50 text-primary-700 font-medium' : 'text-gray-600 hover:bg-gray-50'"
        >
          <span>{{ item.icon }}</span>
          <span>{{ item.name }}</span>
        </router-link>
      </div>
      <div class="p-3 border-t border-gray-100">
        <div class="flex items-center gap-2 px-3 py-2 text-xs">
          <span class="w-2 h-2 rounded-full" :class="connected ? 'bg-green-500' : 'bg-red-500'"></span>
          <span class="text-gray-500">{{ connected ? 'Connected' : 'Disconnected' }}</span>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="ml-56 p-6">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from './api/memory-hub.js'

const route = useRoute()
const connected = ref(false)

const navItems = [
  { path: '/', name: 'Dashboard', icon: '📊' },
  { path: '/conversations', name: 'Conversations', icon: '💬' },
  { path: '/search', name: 'Search', icon: '🔍' },
  { path: '/settings', name: 'Settings', icon: '⚙️' },
]

onMounted(async () => {
  connected.value = await api.checkHealth()
  setInterval(async () => {
    connected.value = await api.checkHealth()
  }, 30000)
})
</script>
```

- [ ] **Step 8: Create router**

```javascript
// web-ui/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', component: () => import('../views/Dashboard.vue') },
  { path: '/conversations', component: () => import('../views/Conversations.vue') },
  { path: '/conversations/:id', component: () => import('../views/ConversationDetail.vue') },
  { path: '/search', component: () => import('../views/Search.vue') },
  { path: '/settings', component: () => import('../views/Settings.vue') },
]

export const router = createRouter({
  history: createWebHistory(),
  routes
})
```

- [ ] **Step 9: Install dependencies and verify dev server starts**

Run: `cd "D:/python project/claude-memory-system/web-ui" && npm install && npm run dev`
Expected: Vite dev server running on http://localhost:5173

- [ ] **Step 10: Commit**

```bash
cd "D:/python project/claude-memory-system"
git add web-ui/
git commit -m "feat: scaffold Vue 3 web UI project"
```

---

### Task 2: Create API layer

**Files:**
- Create: `web-ui/src/api/memory-hub.js`
- Create: `web-ui/src/constants/platforms.js`

> **[FIX P2-15]** PLATFORM_EMOJIS 和 PLATFORM_CLASSES 提取到 `src/constants/platforms.js`，所有 Vue 组件统一 import。

- [ ] **Step 1: Create shared platform constants**

```javascript
// web-ui/src/constants/platforms.js
// [FIX P2-15] Shared platform constants used across all views

export const PLATFORM_EMOJIS = {
  claude_web: '🟣',
  chatgpt: '🟢',
  gemini: '🔵',
  grok: '🟡',
  deepseek: '🔷',
  claude_code: '⚫',
  test: '🔧',
  test_manual: '🔧'
}

export const PLATFORM_CLASSES = {
  claude_web: 'bg-purple-50 text-purple-700',
  chatgpt: 'bg-green-50 text-green-700',
  gemini: 'bg-blue-50 text-blue-700',
  grok: 'bg-yellow-50 text-yellow-700',
  deepseek: 'bg-sky-50 text-sky-700',
}

export function platformEmoji(name) {
  return PLATFORM_EMOJIS[name] || '⚪'
}

export function platformClass(name) {
  return PLATFORM_CLASSES[name] || 'bg-gray-50 text-gray-700'
}
```

- [ ] **Step 2: Create API client**

> 使用 Phase 0 数据契约中定义的新端点（`/api/conversations/list`, `/api/conversations/{id}`, 转换后的 `/api/search` 和 `/api/related`）。

```javascript
// web-ui/src/api/memory-hub.js
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 10000
})

export default {
  async checkHealth() {
    try {
      const { data } = await axios.get('/health')
      return data.status === 'healthy'
    } catch {
      return false
    }
  },

  async getStats() {
    const { data } = await client.get('/stats')
    return data
  },

  // Phase 0 structured endpoints
  async listConversations(params = {}) {
    const { data } = await client.get('/conversations/list', { params })
    return data
  },

  async getConversation(id) {
    const { data } = await client.get(`/conversations/${id}`)
    return data
  },

  async search(query, limit = 10) {
    const { data } = await client.get('/search', {
      params: { query, limit }
    })
    return data
  },

  async getRelated(conversationId, limit = 5) {
    const { data } = await client.get(`/related/${conversationId}`, {
      params: { limit }
    })
    return data
  },

  // AI analysis endpoints (Phase 4.3)
  async getAIStatus() {
    const { data } = await client.get('/ai/status')
    return data
  },

  async analyzeConversation(conversationId) {
    const { data } = await client.post(`/analyze/${conversationId}`)
    return data
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/api/memory-hub.js web-ui/src/constants/platforms.js
git commit -m "feat: add API client and shared platform constants"
```

---

## Chunk 2: Views

### Task 3: Create Dashboard view

**Files:**
- Create: `web-ui/src/views/Dashboard.vue`

> **[FIX P0-4]** Dashboard 使用后端返回的 `database.by_platform`（数组格式 `[{platform, count, avg_importance}]`），而非错误的 `database.platforms`（对象格式）。
> **[FIX P2-16]** Stats 网格从 `grid-cols-4` 改为 `grid-cols-2 md:grid-cols-4` 以支持响应式。

- [ ] **Step 1: Create Dashboard.vue**

```vue
<!-- web-ui/src/views/Dashboard.vue -->
<template>
  <div>
    <h1 class="text-2xl font-bold text-gray-800 mb-6">Dashboard</h1>

    <!-- Stats Cards -->
    <!-- [FIX P2-16] Responsive grid -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <div v-for="stat in stats" :key="stat.label"
           class="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <div class="text-3xl mb-1">{{ stat.icon }}</div>
        <div class="text-2xl font-bold text-gray-800">{{ stat.value }}</div>
        <div class="text-sm text-gray-500">{{ stat.label }}</div>
      </div>
    </div>

    <!-- Platform Breakdown -->
    <div class="bg-white rounded-xl p-6 border border-gray-100 shadow-sm mb-8" v-if="platforms.length">
      <h2 class="text-lg font-semibold text-gray-700 mb-4">Platforms</h2>
      <div class="space-y-3">
        <div v-for="p in platforms" :key="p.name" class="flex items-center gap-3">
          <span class="text-lg">{{ getPlatformEmoji(p.name) }}</span>
          <span class="text-sm font-medium text-gray-700 w-24">{{ p.name }}</span>
          <div class="flex-1 bg-gray-100 rounded-full h-3">
            <div class="bg-primary-500 rounded-full h-3 transition-all"
                 :style="{ width: (p.count / totalConversations * 100) + '%' }"></div>
          </div>
          <span class="text-sm text-gray-500 w-12 text-right">{{ p.count }}</span>
        </div>
      </div>
    </div>

    <!-- Loading / Error states -->
    <div v-if="loading" class="text-center py-12 text-gray-400">Loading...</div>
    <div v-if="error" class="text-center py-12 text-red-400">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../api/memory-hub.js'
import { platformEmoji as getPlatformEmoji } from '../constants/platforms.js'

const loading = ref(true)
const error = ref(null)
const rawStats = ref(null)

const totalConversations = computed(() => rawStats.value?.database?.total_conversations || 0)

// [FIX P0-4] Use by_platform array, not platforms object
const stats = computed(() => {
  if (!rawStats.value) return []
  const db = rawStats.value.database || {}
  const vs = rawStats.value.vector_store || {}
  return [
    { icon: '💬', value: db.total_conversations || 0, label: 'Total Conversations' },
    { icon: '🌐', value: (db.by_platform || []).length, label: 'Platforms' },
    { icon: '📐', value: vs.total_documents || 0, label: 'Vector Documents' },
    { icon: '⭐', value: avgImportance.value, label: 'Avg Importance' },
  ]
})

// [FIX P0-4] Compute from by_platform array
const avgImportance = computed(() => {
  const byPlatform = rawStats.value?.database?.by_platform
  if (!byPlatform || byPlatform.length === 0) return '—'
  const total = byPlatform.reduce((sum, p) => sum + (p.avg_importance || 0) * (p.count || 0), 0)
  const count = byPlatform.reduce((sum, p) => sum + (p.count || 0), 0)
  return count > 0 ? (total / count).toFixed(1) : '—'
})

// [FIX P0-4] Map from by_platform array [{platform, count, avg_importance}]
const platforms = computed(() => {
  if (!rawStats.value?.database?.by_platform) return []
  return rawStats.value.database.by_platform
    .map(p => ({ name: p.platform, count: p.count || 0, avgImportance: p.avg_importance || 0 }))
    .sort((a, b) => b.count - a.count)
})

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
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/views/Dashboard.vue
git commit -m "feat: add Dashboard view with correct by_platform data mapping"
```

---

### Task 4: Create Conversations list view

**Files:**
- Create: `web-ui/src/views/Conversations.vue`

> **[FIX P0-6]** 直接使用 Phase 0 的 `/api/conversations/list` JSON API，不需要解析 markdown context。原计划中的 `parseContextToConversations()` 函数已删除。

- [ ] **Step 1: Create Conversations.vue**

```vue
<!-- web-ui/src/views/Conversations.vue -->
<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">Conversations</h1>
      <div class="flex gap-2">
        <select v-model="platformFilter"
                class="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white">
          <option value="">All Platforms</option>
          <option v-for="p in availablePlatforms" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="text-center py-12 text-gray-400">Loading...</div>

    <div v-else-if="conversations.length === 0" class="text-center py-12 text-gray-400">
      No conversations found
    </div>

    <div v-else class="space-y-3">
      <router-link
        v-for="conv in filteredConversations"
        :key="conv.id"
        :to="`/conversations/${conv.id}`"
        class="block bg-white rounded-xl p-5 border border-gray-100 shadow-sm hover:border-primary-200 hover:shadow-md transition-all"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span class="text-sm">{{ getPlatformEmoji(conv.platform) }}</span>
              <span class="text-xs font-medium px-2 py-0.5 rounded"
                    :class="getPlatformClass(conv.platform)">{{ conv.platform }}</span>
              <span class="text-xs text-gray-400">{{ formatTime(conv.timestamp) }}</span>
            </div>
            <div class="text-sm text-gray-700 line-clamp-2">{{ conv.summary }}</div>
          </div>
          <div class="ml-4 flex items-center gap-1 text-xs text-gray-400">
            <span>⭐</span>
            <span>{{ conv.importance }}/10</span>
          </div>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api/memory-hub.js'
import { platformEmoji as getPlatformEmoji, platformClass as getPlatformClass } from '../constants/platforms.js'

const loading = ref(true)
const conversations = ref([])
const platformFilter = ref('')

const availablePlatforms = computed(() =>
  [...new Set(conversations.value.map(c => c.platform))].sort()
)

const filteredConversations = computed(() => {
  if (!platformFilter.value) return conversations.value
  return conversations.value.filter(c => c.platform === platformFilter.value)
})

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// [FIX P0-6] Use structured JSON API directly, no markdown parsing needed
onMounted(async () => {
  try {
    const data = await api.listConversations({
      hours: 8760,
      min_importance: 1,
      limit: 100
    })
    conversations.value = data.conversations || []
  } catch (e) {
    console.error('Failed to load conversations:', e)
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/views/Conversations.vue
git commit -m "feat: add Conversations list view using structured JSON API"
```

---

### Task 5: Create ConversationDetail view

**Files:**
- Create: `web-ui/src/views/ConversationDetail.vue`

- [ ] **Step 1: Create ConversationDetail.vue**

```vue
<!-- web-ui/src/views/ConversationDetail.vue -->
<template>
  <div>
    <router-link to="/conversations" class="text-primary-600 text-sm hover:underline mb-4 inline-block">
      ← Back to list
    </router-link>

    <div v-if="loading" class="text-center py-12 text-gray-400">Loading...</div>

    <div v-else-if="conversation">
      <!-- Header -->
      <div class="bg-white rounded-xl p-6 border border-gray-100 shadow-sm mb-4">
        <div class="flex items-center gap-3 mb-3">
          <span class="text-2xl">{{ getPlatformEmoji(conversation.platform) }}</span>
          <div>
            <div class="text-lg font-semibold text-gray-800">{{ conversation.platform }}</div>
            <div class="text-sm text-gray-500">{{ conversation.timestamp }}</div>
          </div>
          <span class="ml-auto px-3 py-1 rounded-full text-sm font-medium bg-yellow-50 text-yellow-700">
            ⭐ {{ conversation.importance }}/10
          </span>
        </div>
        <div v-if="conversation.summary" class="text-sm text-gray-600 bg-gray-50 rounded-lg p-4">
          <strong>Summary:</strong> {{ conversation.summary }}
        </div>
      </div>

      <!-- Full Content -->
      <div class="bg-white rounded-xl p-6 border border-gray-100 shadow-sm mb-4">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-gray-700">Full Content</h2>
          <button @click="expanded = !expanded"
                  class="text-sm text-primary-600 hover:underline">
            {{ expanded ? 'Collapse' : 'Expand' }}
          </button>
        </div>
        <div v-if="expanded" class="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
          {{ conversation.full_content }}
        </div>
        <div v-else class="text-sm text-gray-400">Click "Expand" to view full conversation</div>
      </div>

      <!-- Related Conversations -->
      <div v-if="related.length" class="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
        <h2 class="text-lg font-semibold text-gray-700 mb-4">Related Conversations</h2>
        <div class="space-y-2">
          <div v-for="r in related" :key="r.id"
               class="p-3 rounded-lg bg-gray-50 text-sm">
            <span>{{ getPlatformEmoji(r.platform) }}</span>
            <span class="text-gray-700">{{ r.summary }}</span>
            <span class="text-gray-400 text-xs ml-2">Similarity: {{ (r.similarity * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/memory-hub.js'
import { platformEmoji as getPlatformEmoji } from '../constants/platforms.js'

const route = useRoute()
const loading = ref(true)
const conversation = ref(null)
const related = ref([])
const expanded = ref(false)

// Use structured API endpoint directly
onMounted(async () => {
  try {
    const id = route.params.id
    conversation.value = await api.getConversation(id)

    try {
      const relData = await api.getRelated(id)
      related.value = relData.related || []
    } catch (e) {
      // Related may not be available
    }
  } catch (e) {
    console.error('Failed to load conversation:', e)
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/views/ConversationDetail.vue
git commit -m "feat: add ConversationDetail view"
```

---

### Task 6: Create Search view

**Files:**
- Create: `web-ui/src/views/Search.vue`

> **[FIX P0-5]** Search 结果直接使用 Phase 0 转换后的格式 `{id, platform, summary, timestamp, similarity, content_preview}`，无需前端再做字段映射。

- [ ] **Step 1: Create Search.vue**

```vue
<!-- web-ui/src/views/Search.vue -->
<template>
  <div>
    <h1 class="text-2xl font-bold text-gray-800 mb-6">Semantic Search</h1>

    <!-- Search Bar -->
    <div class="flex gap-3 mb-6">
      <input
        v-model="query"
        @keydown.enter="doSearch"
        type="text"
        placeholder="Search conversations by meaning..."
        class="flex-1 px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
      >
      <button @click="doSearch"
              :disabled="!query.trim() || searching"
              class="px-6 py-3 bg-primary-600 text-white rounded-xl text-sm font-medium hover:bg-primary-700 disabled:opacity-50 transition-colors">
        {{ searching ? 'Searching...' : 'Search' }}
      </button>
    </div>

    <!-- Results -->
    <div v-if="results.length" class="space-y-3">
      <div class="text-sm text-gray-500 mb-2">{{ results.length }} results for "{{ lastQuery }}"</div>
      <div v-for="r in results" :key="r.id"
           class="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <div class="flex items-center gap-2 mb-2">
          <span>{{ getPlatformEmoji(r.platform) }}</span>
          <span class="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-600">{{ r.platform }}</span>
          <span class="text-xs text-gray-400">{{ r.timestamp }}</span>
          <span class="ml-auto text-xs text-primary-600 font-medium">
            {{ (r.similarity * 100).toFixed(0) }}% match
          </span>
        </div>
        <div class="text-sm text-gray-700">{{ r.summary }}</div>
      </div>
    </div>

    <div v-else-if="searched && !searching" class="text-center py-12 text-gray-400">
      No results found for "{{ lastQuery }}"
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api/memory-hub.js'
import { platformEmoji as getPlatformEmoji } from '../constants/platforms.js'

const query = ref('')
const results = ref([])
const searching = ref(false)
const searched = ref(false)
const lastQuery = ref('')

async function doSearch() {
  if (!query.value.trim() || searching.value) return
  searching.value = true
  searched.value = true
  lastQuery.value = query.value

  try {
    const data = await api.search(query.value)
    // Phase 0 backend already transforms to {id, platform, summary, timestamp, similarity}
    results.value = data.results || []
  } catch (e) {
    console.error('Search failed:', e)
    results.value = []
  } finally {
    searching.value = false
  }
}
</script>
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/views/Search.vue
git commit -m "feat: add Search view"
```

---

### Task 7: Create Settings view

**Files:**
- Create: `web-ui/src/views/Settings.vue`

- [ ] **Step 1: Create Settings.vue**

```vue
<!-- web-ui/src/views/Settings.vue -->
<template>
  <div>
    <h1 class="text-2xl font-bold text-gray-800 mb-6">Settings</h1>

    <!-- Connection Status -->
    <div class="bg-white rounded-xl p-6 border border-gray-100 shadow-sm mb-4">
      <h2 class="text-lg font-semibold text-gray-700 mb-4">Connection</h2>
      <div class="flex items-center gap-3">
        <span class="w-3 h-3 rounded-full" :class="connected ? 'bg-green-500' : 'bg-red-500'"></span>
        <span class="text-sm text-gray-600">Memory Hub: {{ connected ? 'Connected' : 'Disconnected' }}</span>
        <span class="text-xs text-gray-400">(localhost:8765)</span>
        <button @click="checkConnection"
                class="ml-auto px-3 py-1 text-xs bg-gray-100 rounded hover:bg-gray-200 transition-colors">
          Refresh
        </button>
      </div>
    </div>

    <!-- AI Provider Config -->
    <div class="bg-white rounded-xl p-6 border border-gray-100 shadow-sm mb-4">
      <h2 class="text-lg font-semibold text-gray-700 mb-4">AI Provider</h2>
      <p class="text-sm text-gray-500 mb-4">
        Configure AI API for smart summaries and analysis. Set via environment variables (AI_PROVIDER_API_KEY) or backend/data/ai_config.json
      </p>
      <div class="space-y-3">
        <div v-for="provider in providers" :key="provider.key"
             class="flex items-center gap-3 p-3 rounded-lg bg-gray-50">
          <span class="text-sm font-medium text-gray-700 w-20">{{ provider.name }}</span>
          <input type="password"
                 :placeholder="provider.placeholder"
                 class="flex-1 px-3 py-1.5 border border-gray-200 rounded text-sm"
                 :value="provider.configured ? '••••••••' : ''"
                 disabled>
          <span class="text-xs" :class="provider.configured ? 'text-green-600' : 'text-gray-400'">
            {{ provider.configured ? 'Configured' : 'Not set' }}
          </span>
        </div>
      </div>
      <p class="text-xs text-gray-400 mt-3">
        Set environment variables (e.g. AI_DEEPSEEK_API_KEY) or edit backend/data/ai_config.json.
      </p>
    </div>

    <!-- Data Management -->
    <div class="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
      <h2 class="text-lg font-semibold text-gray-700 mb-4">Data</h2>
      <div class="flex gap-3">
        <button @click="showStats"
                class="px-4 py-2 text-sm bg-primary-50 text-primary-700 rounded-lg hover:bg-primary-100 transition-colors">
          View Statistics
        </button>
      </div>
      <div v-if="statsVisible" class="mt-4 p-4 bg-gray-50 rounded-lg text-sm font-mono whitespace-pre">{{ statsText }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/memory-hub.js'

const connected = ref(false)
const statsVisible = ref(false)
const statsText = ref('')

const providers = ref([
  { key: 'claude', name: 'Claude', placeholder: 'sk-ant-...', configured: false },
  { key: 'deepseek', name: 'DeepSeek', placeholder: 'sk-...', configured: false },
  { key: 'openai', name: 'OpenAI', placeholder: 'sk-...', configured: false },
  { key: 'qwen', name: 'Qwen', placeholder: 'sk-...', configured: false },
  { key: 'kimi', name: 'Kimi', placeholder: 'sk-...', configured: false },
  { key: 'minimax', name: 'MiniMax', placeholder: 'sk-...', configured: false },
  { key: 'glm', name: 'GLM', placeholder: 'sk-...', configured: false },
])

async function checkConnection() {
  connected.value = await api.checkHealth()
}

async function showStats() {
  try {
    const data = await api.getStats()
    statsText.value = JSON.stringify(data, null, 2)
    statsVisible.value = true
  } catch (e) {
    statsText.value = 'Error: ' + e.message
    statsVisible.value = true
  }
}

onMounted(checkConnection)
</script>
```

- [ ] **Step 2: Commit**

```bash
git add web-ui/src/views/Settings.vue
git commit -m "feat: add Settings view"
```

---

## Chunk 3: End-to-end Test

### Task 8: End-to-end test

- [ ] **Step 1: Start Memory Hub**

Run: `cd "D:/python project/claude-memory-system/backend" && python main.py`
Expected: Server running on port 8765

- [ ] **Step 2: Start Web UI dev server**

Run: `cd "D:/python project/claude-memory-system/web-ui" && npm run dev`
Expected: Vite dev server running on port 5173

- [ ] **Step 3: Verify Dashboard**

Open http://localhost:5173/ - should show stats cards (responsive grid) and platform breakdown using `by_platform` array

- [ ] **Step 4: Verify Conversations list**

Open http://localhost:5173/conversations - should show conversation list from `/api/conversations/list`

- [ ] **Step 5: Verify Search**

Open http://localhost:5173/search - type a query, should return results with platform, summary, similarity fields

- [ ] **Step 6: Verify Settings**

Open http://localhost:5173/settings - should show connection status

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat: complete Phase 4.2 Web UI"
```
