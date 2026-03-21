# Phase 4.1: Browser Extension Multi-Platform + Manual Sync Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
> **评审状态:** 已合并 Gemini/Codex/Claude 三方评审修订 (2026-03-12)

**Goal:** Refactor the browser extension to support manual sync across 5 AI platforms (Claude, ChatGPT, Gemini, Grok, DeepSeek) with a unified architecture.

**Architecture:** Each platform gets its own extractor implementing a shared `PlatformExtractor` interface. Content scripts are injected per-platform via manifest URL matching. Popup communicates with content scripts via Chrome messaging.

**Tech Stack:** Chrome Extension Manifest V3, vanilla JavaScript

**前置依赖:** Phase 0 数据契约已完成

---

## Chunk 1: Core Architecture + Claude Platform

### Task 1: Create core extractor interface

**Files:**
- Create: `browser-extension/core/extractor.js`

> **[FIX P0-1 + P1-9]** 删除原计划中的 `core/sync-manager.js`。它与 `popup.js` 存在 `const MEMORY_HUB_URL` 重复声明（会导致 `SyntaxError` 使 popup 完全无法运行），且其功能已在 content_script.js 和 popup.js 中直接实现，是死代码。

> **[FIX P1-10]** PlatformExtractor 基类添加 `_determineRole()` 和 `_extractTextContent()` 默认实现，各平台只需重写特殊逻辑，消除 5 个 extractor 中 90% 的重复代码。

- [ ] **Step 1: Create extractor base class with common methods**

```javascript
// browser-extension/core/extractor.js

/**
 * Base class for platform-specific conversation extractors.
 * Each platform (Claude, ChatGPT, etc.) extends this class.
 * [FIX P1-10] Common methods (_determineRole, _extractTextContent) implemented here.
 */
class PlatformExtractor {
  /**
   * @returns {string} Platform identifier (e.g., 'claude_web', 'chatgpt')
   */
  getPlatformName() {
    throw new Error('getPlatformName() must be implemented');
  }

  /**
   * @returns {boolean} Whether the current page belongs to this platform
   */
  isOnPlatform() {
    throw new Error('isOnPlatform() must be implemented');
  }

  /**
   * Extract the current conversation from the page DOM.
   * @returns {Promise<{title: string, messages: Array<{role: string, content: string}>, url: string, conversationId: string|null}>}
   */
  async extractConversation() {
    throw new Error('extractConversation() must be implemented');
  }

  /**
   * Get a short preview of the current conversation (for popup display).
   * @returns {Promise<{title: string, messageCount: number, platform: string}>}
   */
  async getPreview() {
    const conv = await this.extractConversation();
    return {
      title: conv.title || 'Untitled Conversation',
      messageCount: conv.messages.length,
      platform: this.getPlatformName()
    };
  }

  /**
   * [FIX P1-10] Default role determination based on common CSS class patterns.
   * Subclasses can override for platform-specific logic.
   * @param {Element} element
   * @returns {string} 'user' or 'assistant'
   */
  _determineRole(element) {
    const className = (element.className || '').toLowerCase();
    const parentClassName = (element.parentElement?.className || '').toLowerCase();
    const combined = className + ' ' + parentClassName;

    if (combined.includes('human') || combined.includes('user') ||
        combined.includes('self') || combined.includes('query')) {
      return 'user';
    }
    return 'assistant';
  }

  /**
   * [FIX P1-10] Default text content extraction with code block handling.
   * Subclasses can override for platform-specific DOM structure.
   * @param {Element} element
   * @returns {string}
   */
  _extractTextContent(element) {
    const paragraphs = element.querySelectorAll('p, li, h1, h2, h3, h4');

    if (paragraphs.length > 0) {
      let content = '';
      element.childNodes.forEach(node => {
        if (node.nodeType === Node.TEXT_NODE) {
          content += node.textContent;
        } else if (node.tagName === 'PRE' || node.classList?.contains('code-block')) {
          content += '\n```\n' + node.textContent + '\n```\n';
        } else {
          content += node.textContent + '\n';
        }
      });
      return content.trim();
    }

    return element.textContent || '';
  }
}

// Export for use in content scripts
if (typeof module !== 'undefined') {
  module.exports = { PlatformExtractor };
}
```

- [ ] **Step 2: Verify file created**

Run: `ls -la "D:/python project/claude-memory-system/browser-extension/core/"`
Expected: extractor.js listed (no sync-manager.js)

- [ ] **Step 3: Commit**

```bash
cd "D:/python project/claude-memory-system"
git add browser-extension/core/extractor.js
git commit -m "feat: add PlatformExtractor base class with common methods"
```

---

### Task 2: Create Claude platform extractor

**Files:**
- Create: `browser-extension/platforms/claude.js`
- Reference: `browser-extension/content_script.js` (existing code to migrate)

> **[FIX P1-8]** Strategy 2 修复消息顺序混乱问题：原代码先推所有 assistant 消息再推所有 user 消息，导致 `[asst,asst,asst,user,user,user]`。修复后按 DOM 顺序收集并判断角色。

- [ ] **Step 1: Create Claude extractor**

```javascript
// browser-extension/platforms/claude.js

class ClaudeExtractor extends PlatformExtractor {
  getPlatformName() {
    return 'claude_web';
  }

  isOnPlatform() {
    return window.location.hostname === 'claude.ai';
  }

  async extractConversation() {
    const messages = this._extractMessages();
    const context = this._extractContext();

    return {
      title: context.title,
      messages: messages,
      url: window.location.href,
      conversationId: context.conversationId
    };
  }

  _extractMessages() {
    const messages = [];

    // Strategy 1: data-test-render-count elements (most reliable)
    const renderElements = document.querySelectorAll('[data-test-render-count]');
    if (renderElements.length > 0) {
      renderElements.forEach(el => {
        const role = this._determineRole(el);
        const content = this._extractTextContent(el);
        if (content.trim()) {
          messages.push({ role, content: content.trim() });
        }
      });
      if (messages.length > 0) return messages;
    }

    // Strategy 2: font-claude-message + user elements
    // [FIX P1-8] Collect ALL message elements and sort by DOM order
    const claudeMessages = document.querySelectorAll('.font-claude-message');
    if (claudeMessages.length > 0) {
      const allElements = document.querySelectorAll(
        '.font-claude-message, [class*="human"], [class*="user"]'
      );
      const sorted = Array.from(allElements).sort((a, b) => {
        const pos = a.compareDocumentPosition(b);
        return pos & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
      });
      sorted.forEach(el => {
        const role = this._determineRole(el);
        const content = this._extractTextContent(el);
        if (content.trim()) {
          messages.push({ role, content: content.trim() });
        }
      });
      if (messages.length > 0) return messages;
    }

    // Strategy 3: Generic message elements
    const genericMessages = document.querySelectorAll('[class*="message"], [role="article"]');
    genericMessages.forEach(el => {
      const role = this._determineRole(el);
      const content = this._extractTextContent(el);
      if (content.trim()) {
        messages.push({ role, content: content.trim() });
      }
    });

    return messages;
  }

  // Override base _determineRole for Claude-specific classes
  _determineRole(element) {
    const className = element.className || '';
    const parentHTML = element.parentElement ? element.parentElement.innerHTML.substring(0, 200) : '';

    if (className.includes('human') || className.includes('user') ||
        parentHTML.includes('human') || parentHTML.includes('user-message')) {
      return 'user';
    }
    if (className.includes('assistant') || className.includes('claude') ||
        className.includes('font-claude')) {
      return 'assistant';
    }
    return 'assistant';
  }

  _extractContext() {
    const url = window.location.href;
    const pathParts = url.split('/');
    const conversationId = pathParts[pathParts.length - 1] || null;
    const title = document.title.replace(' - Claude', '').trim() || 'Claude Conversation';

    return { conversationId, title };
  }
}

if (typeof module !== 'undefined') {
  module.exports = { ClaudeExtractor };
}
```

- [ ] **Step 2: Commit**

```bash
git add browser-extension/platforms/claude.js
git commit -m "feat: add Claude platform extractor with DOM-ordered message fix"
```

---

### Task 3: Create ChatGPT platform extractor

**Files:**
- Create: `browser-extension/platforms/chatgpt.js`

- [ ] **Step 1: Create ChatGPT extractor**

```javascript
// browser-extension/platforms/chatgpt.js

class ChatGPTExtractor extends PlatformExtractor {
  getPlatformName() {
    return 'chatgpt';
  }

  isOnPlatform() {
    return window.location.hostname === 'chatgpt.com' ||
           window.location.hostname === 'chat.openai.com';
  }

  async extractConversation() {
    const messages = this._extractMessages();
    const context = this._extractContext();

    return {
      title: context.title,
      messages: messages,
      url: window.location.href,
      conversationId: context.conversationId
    };
  }

  _extractMessages() {
    const messages = [];

    // ChatGPT uses article elements with data-message-author-role
    const articleElements = document.querySelectorAll('article[data-testid^="conversation-turn"]');
    if (articleElements.length > 0) {
      articleElements.forEach(el => {
        const roleAttr = el.querySelector('[data-message-author-role]');
        const role = roleAttr?.getAttribute('data-message-author-role') === 'user' ? 'user' : 'assistant';
        const contentEl = el.querySelector('.markdown, .whitespace-pre-wrap, [class*="text-message"]');
        const content = contentEl ? contentEl.textContent.trim() : el.textContent.trim();
        if (content) {
          messages.push({ role, content });
        }
      });
      if (messages.length > 0) return messages;
    }

    // Fallback: look for message groups
    const groups = document.querySelectorAll('[data-message-author-role]');
    groups.forEach(el => {
      const role = el.getAttribute('data-message-author-role') === 'user' ? 'user' : 'assistant';
      const parent = el.closest('[class*="group"]') || el.parentElement;
      const contentEl = parent?.querySelector('.markdown, .whitespace-pre-wrap');
      const content = contentEl ? contentEl.textContent.trim() : el.textContent.trim();
      if (content) {
        messages.push({ role, content });
      }
    });

    return messages;
  }

  _extractContext() {
    const url = window.location.href;
    const match = url.match(/\/c\/([a-zA-Z0-9-]+)/);
    const conversationId = match ? match[1] : null;
    const title = document.title.replace(' | ChatGPT', '').trim() || 'ChatGPT Conversation';

    return { conversationId, title };
  }
}

if (typeof module !== 'undefined') {
  module.exports = { ChatGPTExtractor };
}
```

- [ ] **Step 2: Commit**

```bash
git add browser-extension/platforms/chatgpt.js
git commit -m "feat: add ChatGPT platform extractor"
```

---

### Task 4: Create Gemini platform extractor (experimental)

**Files:**
- Create: `browser-extension/platforms/gemini.js`

> Gemini, Grok, DeepSeek 标记为 experimental，DOM 选择器可能随平台更新而变化。

- [ ] **Step 1: Create Gemini extractor**

```javascript
// browser-extension/platforms/gemini.js

/**
 * Gemini platform extractor (experimental).
 * Uses base class _determineRole() - no override needed.
 */
class GeminiExtractor extends PlatformExtractor {
  getPlatformName() {
    return 'gemini';
  }

  isOnPlatform() {
    return window.location.hostname === 'gemini.google.com';
  }

  async extractConversation() {
    const messages = this._extractMessages();
    const context = this._extractContext();

    return {
      title: context.title,
      messages: messages,
      url: window.location.href,
      conversationId: context.conversationId
    };
  }

  _extractMessages() {
    const messages = [];

    // Gemini uses specific message containers
    const turns = document.querySelectorAll('message-content, .conversation-turn, [class*="turn"]');
    if (turns.length > 0) {
      turns.forEach(el => {
        const role = this._determineRole(el);
        const content = el.textContent.trim();
        if (content) {
          messages.push({ role, content });
        }
      });
      if (messages.length > 0) return messages;
    }

    // Fallback: look for user query and model response patterns
    const userQueries = document.querySelectorAll('.query-text, [class*="query"], [class*="user-message"]');
    const modelResponses = document.querySelectorAll('.model-response-text, [class*="response"], [class*="model-message"]');

    userQueries.forEach(el => {
      const content = el.textContent.trim();
      if (content) messages.push({ role: 'user', content });
    });

    modelResponses.forEach(el => {
      const content = el.textContent.trim();
      if (content) messages.push({ role: 'assistant', content });
    });

    // If still empty, try broader selectors
    if (messages.length === 0) {
      const allTurns = document.querySelectorAll('[data-turn-id], [class*="chat-turn"]');
      allTurns.forEach(el => {
        const role = this._determineRole(el);
        const content = el.textContent.trim();
        if (content) messages.push({ role, content });
      });
    }

    return messages;
  }

  _extractContext() {
    const url = window.location.href;
    const match = url.match(/\/app\/([a-zA-Z0-9-]+)/);
    const conversationId = match ? match[1] : null;
    const title = document.title.replace(' - Google Gemini', '').trim() || 'Gemini Conversation';

    return { conversationId, title };
  }
}

if (typeof module !== 'undefined') {
  module.exports = { GeminiExtractor };
}
```

- [ ] **Step 2: Commit**

```bash
git add browser-extension/platforms/gemini.js
git commit -m "feat: add Gemini platform extractor (experimental)"
```

---

### Task 5: Create Grok platform extractor (experimental)

**Files:**
- Create: `browser-extension/platforms/grok.js`

- [ ] **Step 1: Create Grok extractor**

```javascript
// browser-extension/platforms/grok.js

/**
 * Grok platform extractor (experimental).
 * Uses base class _determineRole() - no override needed.
 */
class GrokExtractor extends PlatformExtractor {
  getPlatformName() {
    return 'grok';
  }

  isOnPlatform() {
    return window.location.hostname === 'grok.com' ||
           window.location.hostname === 'x.com' && window.location.pathname.startsWith('/i/grok');
  }

  async extractConversation() {
    const messages = this._extractMessages();
    const context = this._extractContext();

    return {
      title: context.title,
      messages: messages,
      url: window.location.href,
      conversationId: context.conversationId
    };
  }

  _extractMessages() {
    const messages = [];

    // Grok message containers
    const turns = document.querySelectorAll('[class*="message"], [class*="turn"], [class*="chat-item"]');
    turns.forEach(el => {
      const role = this._determineRole(el);
      const content = el.textContent.trim();
      if (content && content.length > 1) {
        messages.push({ role, content });
      }
    });

    if (messages.length > 0) return messages;

    // Fallback: look for specific Grok selectors
    const userMsgs = document.querySelectorAll('[class*="user"], [class*="human"]');
    const botMsgs = document.querySelectorAll('[class*="bot"], [class*="grok"], [class*="assistant"]');

    userMsgs.forEach(el => {
      const content = el.textContent.trim();
      if (content) messages.push({ role: 'user', content });
    });

    botMsgs.forEach(el => {
      const content = el.textContent.trim();
      if (content) messages.push({ role: 'assistant', content });
    });

    return messages;
  }

  _extractContext() {
    const url = window.location.href;
    const conversationId = url.split('/').pop() || null;
    const title = document.title.replace(' - Grok', '').trim() || 'Grok Conversation';

    return { conversationId, title };
  }
}

if (typeof module !== 'undefined') {
  module.exports = { GrokExtractor };
}
```

- [ ] **Step 2: Commit**

```bash
git add browser-extension/platforms/grok.js
git commit -m "feat: add Grok platform extractor (experimental)"
```

---

### Task 6: Create DeepSeek platform extractor (experimental)

**Files:**
- Create: `browser-extension/platforms/deepseek.js`

- [ ] **Step 1: Create DeepSeek extractor**

```javascript
// browser-extension/platforms/deepseek.js

/**
 * DeepSeek platform extractor (experimental).
 * Uses base class _determineRole() - no override needed.
 */
class DeepSeekExtractor extends PlatformExtractor {
  getPlatformName() {
    return 'deepseek';
  }

  isOnPlatform() {
    return window.location.hostname === 'chat.deepseek.com';
  }

  async extractConversation() {
    const messages = this._extractMessages();
    const context = this._extractContext();

    return {
      title: context.title,
      messages: messages,
      url: window.location.href,
      conversationId: context.conversationId
    };
  }

  _extractMessages() {
    const messages = [];

    // DeepSeek uses markdown rendered messages
    const turns = document.querySelectorAll('[class*="message"], [class*="chat-message"]');
    turns.forEach(el => {
      const role = this._determineRole(el);
      const contentEl = el.querySelector('.markdown-body, [class*="content"], .ds-markdown');
      const content = contentEl ? contentEl.textContent.trim() : el.textContent.trim();
      if (content && content.length > 1) {
        messages.push({ role, content });
      }
    });

    if (messages.length > 0) return messages;

    // Fallback: broader selectors
    const allItems = document.querySelectorAll('[class*="chat-item"], [class*="turn"]');
    allItems.forEach(el => {
      const role = this._determineRole(el);
      const content = el.textContent.trim();
      if (content) messages.push({ role, content });
    });

    return messages;
  }

  _extractContext() {
    const url = window.location.href;
    const match = url.match(/\/chat\/([a-zA-Z0-9-]+)/);
    const conversationId = match ? match[1] : null;
    const title = document.title.replace(' - DeepSeek', '').trim() || 'DeepSeek Conversation';

    return { conversationId, title };
  }
}

if (typeof module !== 'undefined') {
  module.exports = { DeepSeekExtractor };
}
```

- [ ] **Step 2: Commit**

```bash
git add browser-extension/platforms/deepseek.js
git commit -m "feat: add DeepSeek platform extractor (experimental)"
```

---

## Chunk 2: Manifest + Content Script + Popup Refactor

### Task 7: Rewrite manifest.json for multi-platform support

**Files:**
- Modify: `browser-extension/manifest.json`

- [ ] **Step 1: Rewrite manifest.json**

```json
{
  "manifest_version": 3,
  "name": "Claude Memory Sync",
  "version": "2.0.0",
  "description": "Sync AI conversations from multiple platforms to Memory Hub",
  "permissions": [
    "storage",
    "activeTab"
  ],
  "host_permissions": [
    "https://claude.ai/*",
    "https://chatgpt.com/*",
    "https://chat.openai.com/*",
    "https://gemini.google.com/*",
    "https://grok.com/*",
    "https://x.com/i/grok/*",
    "https://chat.deepseek.com/*",
    "http://localhost:8765/*"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": ["https://claude.ai/*"],
      "js": ["core/extractor.js", "platforms/claude.js", "content_script.js"],
      "run_at": "document_idle"
    },
    {
      "matches": ["https://chatgpt.com/*", "https://chat.openai.com/*"],
      "js": ["core/extractor.js", "platforms/chatgpt.js", "content_script.js"],
      "run_at": "document_idle"
    },
    {
      "matches": ["https://gemini.google.com/*"],
      "js": ["core/extractor.js", "platforms/gemini.js", "content_script.js"],
      "run_at": "document_idle"
    },
    {
      "matches": ["https://grok.com/*", "https://x.com/i/grok/*"],
      "js": ["core/extractor.js", "platforms/grok.js", "content_script.js"],
      "run_at": "document_idle"
    },
    {
      "matches": ["https://chat.deepseek.com/*"],
      "js": ["core/extractor.js", "platforms/deepseek.js", "content_script.js"],
      "run_at": "document_idle"
    }
  ],
  "action": {
    "default_popup": "popup.html",
    "default_title": "Claude Memory Sync"
  },
  "icons": {
    "16": "icon16.png",
    "48": "icon48.png",
    "128": "icon128.png"
  }
}
```

> **注意:** content_scripts 不再包含 `core/sync-manager.js`（已删除，见 P0-1/P1-9）。

- [ ] **Step 2: Commit**

```bash
git add browser-extension/manifest.json
git commit -m "feat: update manifest for multi-platform support"
```

---

### Task 8: Rewrite content_script.js as unified entry point

**Files:**
- Modify: `browser-extension/content_script.js`

> **[FIX P1-11]** 添加去重逻辑：SYNC_NOW 处理时检查 5 分钟内是否已同步同一 conversationId，避免重复同步。

- [ ] **Step 1: Rewrite content_script.js**

```javascript
// browser-extension/content_script.js
// Unified content script - works with whichever platform extractor is loaded

(function() {
  'use strict';

  const MEMORY_HUB_URL = 'http://localhost:8765';
  let currentExtractor = null;
  let isConnected = false;

  // [FIX P1-11] Dedup: track recent syncs to avoid duplicates
  const recentSyncs = new Map(); // conversationId -> timestamp
  const DEDUP_WINDOW_MS = 5 * 60 * 1000; // 5 minutes

  function isDuplicate(conversationId) {
    if (!conversationId) return false;
    const lastSync = recentSyncs.get(conversationId);
    if (lastSync && (Date.now() - lastSync) < DEDUP_WINDOW_MS) {
      return true;
    }
    return false;
  }

  function recordSync(conversationId) {
    if (conversationId) {
      recentSyncs.set(conversationId, Date.now());
      // Clean old entries
      for (const [id, ts] of recentSyncs) {
        if (Date.now() - ts > DEDUP_WINDOW_MS) {
          recentSyncs.delete(id);
        }
      }
    }
  }

  // Detect which platform extractor is available
  function detectExtractor() {
    if (typeof ClaudeExtractor !== 'undefined') return new ClaudeExtractor();
    if (typeof ChatGPTExtractor !== 'undefined') return new ChatGPTExtractor();
    if (typeof GeminiExtractor !== 'undefined') return new GeminiExtractor();
    if (typeof GrokExtractor !== 'undefined') return new GrokExtractor();
    if (typeof DeepSeekExtractor !== 'undefined') return new DeepSeekExtractor();
    return null;
  }

  async function checkConnection() {
    try {
      const response = await fetch(`${MEMORY_HUB_URL}/health`, {
        signal: AbortSignal.timeout(3000)
      });
      const data = await response.json();
      isConnected = data.status === 'healthy';
    } catch (e) {
      isConnected = false;
    }
    return isConnected;
  }

  // Listen for messages from popup and background
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'GET_STATUS') {
      const extractor = currentExtractor;
      if (!extractor) {
        sendResponse({ platform: null, connected: isConnected, ready: false });
        return true;
      }
      extractor.getPreview().then(preview => {
        sendResponse({
          platform: preview.platform,
          title: preview.title,
          messageCount: preview.messageCount,
          connected: isConnected,
          ready: true
        });
      }).catch(() => {
        sendResponse({ platform: extractor.getPlatformName(), connected: isConnected, ready: false, messageCount: 0 });
      });
      return true; // async response
    }

    if (message.type === 'SYNC_NOW') {
      const extractor = currentExtractor;
      if (!extractor) {
        sendResponse({ success: false, error: 'No extractor available' });
        return true;
      }
      extractor.extractConversation().then(async (conversation) => {
        if (!conversation.messages || conversation.messages.length === 0) {
          sendResponse({ success: false, error: 'No messages found on this page' });
          return;
        }

        // [FIX P1-11] Check dedup
        if (isDuplicate(conversation.conversationId)) {
          sendResponse({
            success: false,
            error: 'This conversation was synced less than 5 minutes ago'
          });
          return;
        }

        try {
          const payload = {
            platform: extractor.getPlatformName(),
            timestamp: new Date().toISOString(),
            messages: conversation.messages,
            project: conversation.title || null,
            working_dir: null
          };

          const response = await fetch(`${MEMORY_HUB_URL}/api/conversations`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });

          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }

          const data = await response.json();

          // Record successful sync for dedup
          recordSync(conversation.conversationId);

          // Notify background of successful sync
          chrome.runtime.sendMessage({
            type: 'SYNC_SUCCESS',
            platform: extractor.getPlatformName(),
            title: conversation.title,
            messageCount: conversation.messages.length
          });

          sendResponse({ success: true, conversationId: data.conversation_id });
        } catch (e) {
          sendResponse({ success: false, error: e.message });
        }
      }).catch(e => {
        sendResponse({ success: false, error: e.message });
      });
      return true; // async response
    }
  });

  // Initialize
  async function init() {
    currentExtractor = detectExtractor();
    if (!currentExtractor) {
      console.log('[Memory Sync] No platform extractor found for this page');
      return;
    }

    console.log(`[Memory Sync] Detected platform: ${currentExtractor.getPlatformName()}`);
    await checkConnection();

    // Periodic health check
    setInterval(checkConnection, 60000);
  }

  init();
})();
```

- [ ] **Step 2: Commit**

```bash
git add browser-extension/content_script.js
git commit -m "refactor: rewrite content_script with dedup logic and unified platform coordination"
```

---

### Task 9: Rewrite popup.html with manual sync UI

**Files:**
- Modify: `browser-extension/popup.html`

> **[FIX P0-1]** popup.html 不再加载 `core/sync-manager.js`，避免 `const MEMORY_HUB_URL` 重复声明导致 SyntaxError。

- [ ] **Step 1: Rewrite popup.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Memory Sync</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      width: 360px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f8f9fa;
      color: #333;
    }

    .header {
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      color: white;
      padding: 16px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .header .logo { font-size: 24px; }
    .header .title { font-size: 16px; font-weight: 600; }
    .header .version { font-size: 11px; opacity: 0.7; }

    .status-bar {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 16px;
      background: white;
      border-bottom: 1px solid #e5e7eb;
      font-size: 13px;
    }
    .status-dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .status-dot.connected { background: #22c55e; }
    .status-dot.disconnected { background: #ef4444; }
    .status-dot.checking { background: #f59e0b; animation: pulse 1s infinite; }

    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

    .current-conversation {
      padding: 16px;
      background: white;
      margin: 8px;
      border-radius: 8px;
      border: 1px solid #e5e7eb;
    }
    .conv-label {
      font-size: 11px;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 6px;
    }
    .conv-platform {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 500;
      margin-bottom: 6px;
    }
    .platform-claude_web { background: #f3e8ff; color: #7c3aed; }
    .platform-chatgpt { background: #ecfdf5; color: #059669; }
    .platform-gemini { background: #eff6ff; color: #2563eb; }
    .platform-grok { background: #fef3c7; color: #d97706; }
    .platform-deepseek { background: #e0f2fe; color: #0284c7; }
    .platform-unknown { background: #f3f4f6; color: #6b7280; }

    .conv-title {
      font-size: 14px;
      font-weight: 500;
      margin-bottom: 4px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .conv-meta {
      font-size: 12px;
      color: #9ca3af;
    }

    .sync-btn {
      display: block;
      width: calc(100% - 32px);
      margin: 0 16px 8px;
      padding: 12px;
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      color: white;
      border: none;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.2s;
    }
    .sync-btn:hover { opacity: 0.9; }
    .sync-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .sync-btn.success { background: #22c55e; }
    .sync-btn.error { background: #ef4444; }

    .history-section {
      padding: 0 16px 16px;
    }
    .history-title {
      font-size: 12px;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
    }
    .history-list {
      max-height: 200px;
      overflow-y: auto;
    }
    .history-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px;
      border-radius: 6px;
      margin-bottom: 4px;
      font-size: 12px;
      background: white;
      border: 1px solid #f3f4f6;
    }
    .history-icon { font-size: 14px; }
    .history-info { flex: 1; min-width: 0; }
    .history-info .name {
      font-weight: 500;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .history-info .meta { color: #9ca3af; font-size: 11px; }

    .empty-state {
      text-align: center;
      padding: 20px;
      color: #9ca3af;
      font-size: 13px;
    }

    .no-conversation {
      text-align: center;
      padding: 24px 16px;
      color: #9ca3af;
    }
    .no-conversation .icon { font-size: 32px; margin-bottom: 8px; }
    .no-conversation .text { font-size: 13px; }
  </style>
</head>
<body>
  <div class="header">
    <span class="logo">🧠</span>
    <div>
      <div class="title">Memory Sync</div>
      <div class="version">v2.0 - Multi-Platform</div>
    </div>
  </div>

  <div class="status-bar">
    <div class="status-dot checking" id="statusDot"></div>
    <span id="statusText">Checking connection...</span>
  </div>

  <div id="conversationArea">
    <div class="no-conversation">
      <div class="icon">💬</div>
      <div class="text">Detecting conversation...</div>
    </div>
  </div>

  <button class="sync-btn" id="syncBtn" disabled>Sync This Conversation</button>

  <div class="history-section">
    <div class="history-title">Recent Syncs</div>
    <div class="history-list" id="historyList">
      <div class="empty-state">No syncs yet</div>
    </div>
  </div>

  <!-- [FIX P0-1] 不加载 sync-manager.js，避免 const 重复声明 -->
  <script src="popup.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add browser-extension/popup.html
git commit -m "refactor: redesign popup UI, remove sync-manager.js reference"
```

---

### Task 10: Rewrite popup.js for manual sync flow

**Files:**
- Modify: `browser-extension/popup.js`

> **[FIX P0-2]** 所有 DOM 渲染改用 `textContent` + `createElement` 组装，不再使用 `innerHTML` 插入用户数据，防止 XSS 攻击。

- [ ] **Step 1: Rewrite popup.js**

```javascript
// browser-extension/popup.js
// [FIX P0-2] All DOM rendering uses textContent + createElement (no innerHTML with user data)

(function() {
  'use strict';

  const MEMORY_HUB_URL = 'http://localhost:8765';
  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');
  const conversationArea = document.getElementById('conversationArea');
  const syncBtn = document.getElementById('syncBtn');
  const historyList = document.getElementById('historyList');

  let currentStatus = null;
  let isConnected = false;

  // Platform display names and colors
  const PLATFORMS = {
    claude_web: { name: 'Claude', emoji: '🟣' },
    chatgpt:    { name: 'ChatGPT', emoji: '🟢' },
    gemini:     { name: 'Gemini', emoji: '🔵' },
    grok:       { name: 'Grok', emoji: '🟡' },
    deepseek:   { name: 'DeepSeek', emoji: '🔷' }
  };

  async function checkConnection() {
    statusDot.className = 'status-dot checking';
    statusText.textContent = 'Checking...';
    try {
      const response = await fetch(`${MEMORY_HUB_URL}/health`, {
        signal: AbortSignal.timeout(3000)
      });
      const data = await response.json();
      isConnected = data.status === 'healthy';
    } catch (e) {
      isConnected = false;
    }

    statusDot.className = `status-dot ${isConnected ? 'connected' : 'disconnected'}`;
    statusText.textContent = isConnected ? 'Memory Hub Connected' : 'Memory Hub Offline';
  }

  async function getConversationStatus() {
    return new Promise((resolve) => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs[0]) {
          resolve(null);
          return;
        }
        chrome.tabs.sendMessage(tabs[0].id, { type: 'GET_STATUS' }, (response) => {
          if (chrome.runtime.lastError || !response) {
            resolve(null);
            return;
          }
          resolve(response);
        });
      });
    });
  }

  // [FIX P0-2] Safe DOM rendering - no innerHTML with user data
  function renderConversation(status) {
    conversationArea.innerHTML = ''; // Clear (safe - no user data)

    if (!status || !status.ready || status.messageCount === 0) {
      const div = document.createElement('div');
      div.className = 'no-conversation';

      const iconDiv = document.createElement('div');
      iconDiv.className = 'icon';
      iconDiv.textContent = '💬';
      div.appendChild(iconDiv);

      const textDiv = document.createElement('div');
      textDiv.className = 'text';
      textDiv.textContent = !status ? 'Not on a supported AI platform' :
                            !status.ready ? 'Waiting for conversation...' :
                            'No messages found';
      div.appendChild(textDiv);

      conversationArea.appendChild(div);
      syncBtn.disabled = true;
      return;
    }

    const platform = PLATFORMS[status.platform] || { name: status.platform, emoji: '⚪' };
    const platformClass = `platform-${status.platform || 'unknown'}`;

    const card = document.createElement('div');
    card.className = 'current-conversation';

    const label = document.createElement('div');
    label.className = 'conv-label';
    label.textContent = 'Current Conversation';
    card.appendChild(label);

    const platformEl = document.createElement('span');
    platformEl.className = `conv-platform ${platformClass}`;
    platformEl.textContent = `${platform.emoji} ${platform.name}`;
    card.appendChild(platformEl);

    const titleEl = document.createElement('div');
    titleEl.className = 'conv-title';
    titleEl.textContent = status.title || 'Untitled'; // Safe: textContent
    card.appendChild(titleEl);

    const metaEl = document.createElement('div');
    metaEl.className = 'conv-meta';
    metaEl.textContent = `${status.messageCount} messages`;
    card.appendChild(metaEl);

    conversationArea.appendChild(card);

    syncBtn.disabled = !isConnected;
    currentStatus = status;
  }

  async function handleSync() {
    if (!currentStatus || !isConnected) return;

    syncBtn.disabled = true;
    syncBtn.textContent = 'Syncing...';
    syncBtn.className = 'sync-btn';

    return new Promise((resolve) => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs[0]) {
          syncBtn.textContent = 'Error: No active tab';
          syncBtn.className = 'sync-btn error';
          setTimeout(() => resetSyncBtn(), 2000);
          resolve();
          return;
        }

        chrome.tabs.sendMessage(tabs[0].id, { type: 'SYNC_NOW' }, (response) => {
          if (chrome.runtime.lastError || !response) {
            syncBtn.textContent = 'Error: No response';
            syncBtn.className = 'sync-btn error';
          } else if (response.success) {
            syncBtn.textContent = 'Synced!';
            syncBtn.className = 'sync-btn success';
            loadHistory(); // Refresh history
          } else {
            syncBtn.textContent = `Error: ${response.error}`;
            syncBtn.className = 'sync-btn error';
          }

          setTimeout(() => resetSyncBtn(), 2000);
          resolve();
        });
      });
    });
  }

  function resetSyncBtn() {
    syncBtn.textContent = 'Sync This Conversation';
    syncBtn.className = 'sync-btn';
    syncBtn.disabled = !isConnected || !currentStatus?.ready;
  }

  // [FIX P0-2] Safe history rendering
  async function loadHistory() {
    return new Promise((resolve) => {
      chrome.storage.local.get(['syncHistory'], (result) => {
        const history = result.syncHistory || [];

        historyList.innerHTML = ''; // Clear (safe)

        if (history.length === 0) {
          const empty = document.createElement('div');
          empty.className = 'empty-state';
          empty.textContent = 'No syncs yet';
          historyList.appendChild(empty);
          resolve();
          return;
        }

        history.slice(0, 10).forEach(item => {
          const platform = PLATFORMS[item.platform] || { name: item.platform, emoji: '⚪' };
          const icon = item.success ? '✅' : '❌';
          const time = formatTime(item.timestamp);

          const div = document.createElement('div');
          div.className = 'history-item';

          const iconSpan = document.createElement('span');
          iconSpan.className = 'history-icon';
          iconSpan.textContent = icon;
          div.appendChild(iconSpan);

          const infoDiv = document.createElement('div');
          infoDiv.className = 'history-info';

          const nameDiv = document.createElement('div');
          nameDiv.className = 'name';
          nameDiv.textContent = `${platform.emoji} ${item.title || 'Untitled'}`; // Safe
          infoDiv.appendChild(nameDiv);

          const metaDiv = document.createElement('div');
          metaDiv.className = 'meta';
          metaDiv.textContent = `${item.messageCount || 0} msgs · ${time}`;
          infoDiv.appendChild(metaDiv);

          div.appendChild(infoDiv);
          historyList.appendChild(div);
        });

        resolve();
      });
    });
  }

  function formatTime(timestamp) {
    if (!timestamp) return '';
    const diff = Date.now() - new Date(timestamp).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  // Event listeners
  syncBtn.addEventListener('click', handleSync);

  // Initialize
  async function init() {
    await checkConnection();
    const status = await getConversationStatus();
    renderConversation(status);
    await loadHistory();

    // Auto-refresh every 5s
    setInterval(async () => {
      await checkConnection();
      const status = await getConversationStatus();
      renderConversation(status);
    }, 5000);
  }

  init();
})();
```

- [ ] **Step 2: Commit**

```bash
git add browser-extension/popup.js
git commit -m "refactor: rewrite popup.js with safe DOM rendering (XSS fix) and manual sync"
```

---

### Task 11: Update background.js for multi-platform

**Files:**
- Modify: `browser-extension/background.js`

- [ ] **Step 1: Rewrite background.js**

```javascript
// browser-extension/background.js

const MEMORY_HUB_URL = 'http://localhost:8765';

let syncStats = {
  totalSyncs: 0,
  lastSyncTime: null,
  isMemoryHubRunning: false,
  syncHistory: []
};

// Check Memory Hub health
async function checkMemoryHubHealth() {
  try {
    const response = await fetch(`${MEMORY_HUB_URL}/health`, {
      signal: AbortSignal.timeout(3000)
    });
    const data = await response.json();
    syncStats.isMemoryHubRunning = data.status === 'healthy';
  } catch (e) {
    syncStats.isMemoryHubRunning = false;
  }
}

// Listen for sync success notifications from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'SYNC_SUCCESS') {
    syncStats.totalSyncs++;
    syncStats.lastSyncTime = new Date().toISOString();
    console.log(`[Memory Sync] Synced: ${message.platform} - ${message.title} (${message.messageCount} msgs)`);
  }
});

// Initial health check and periodic updates
checkMemoryHubHealth();
setInterval(checkMemoryHubHealth, 30000);
```

- [ ] **Step 2: Commit**

```bash
git add browser-extension/background.js
git commit -m "refactor: simplify background.js for multi-platform support"
```

---

### ~~Task 12: Delete sync-manager.js~~ CLEANUP

> **[FIX P0-1 + P1-9]** 删除死代码文件 `browser-extension/core/sync-manager.js`（如果已存在）。

- [ ] **Step 1: Delete dead code**

```bash
rm -f "D:/python project/claude-memory-system/browser-extension/core/sync-manager.js"
git add -u browser-extension/core/sync-manager.js
git commit -m "chore: remove dead SyncManager code (fixes const redeclaration crash)"
```

---

### Task 13: End-to-end test

- [ ] **Step 1: Verify file structure**

```bash
ls -la "D:/python project/claude-memory-system/browser-extension/core/"
ls -la "D:/python project/claude-memory-system/browser-extension/platforms/"
```

Expected:
- `core/extractor.js` (no sync-manager.js)
- `platforms/claude.js`, `chatgpt.js`, `gemini.js`, `grok.js`, `deepseek.js`

- [ ] **Step 2: Load extension in Chrome**

1. Open `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked" → select `browser-extension/` folder
4. Verify no errors in extension error log

- [ ] **Step 3: Test on Claude.ai**

1. Open https://claude.ai and start a conversation
2. Click extension popup → should show "Claude" platform detected
3. Click "Sync This Conversation" → should succeed

- [ ] **Step 4: Test on ChatGPT**

1. Open https://chatgpt.com and start a conversation
2. Click extension popup → should show "ChatGPT" platform detected
3. Click "Sync This Conversation" → should succeed

- [ ] **Step 5: Test dedup**

1. Click "Sync This Conversation" again immediately
2. Should show error "This conversation was synced less than 5 minutes ago"

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: complete Phase 4.1 browser extension multi-platform support"
```
