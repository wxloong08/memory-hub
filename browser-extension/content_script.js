if (!globalThis.__memoryCollectorContentScriptLoaded) {
  globalThis.__memoryCollectorContentScriptLoaded = true;

/**
 * Claude Memory Collector - Unified Content Script
 * Detects which platform extractor is loaded and coordinates syncing.
 */

const MEMORY_HUB_URL = 'http://127.0.0.1:8765';
const DEDUP_WINDOW_MS = 5 * 60 * 1000; // 5 minutes

// Dedup map: key = platform + url + messageCount hash, value = timestamp
const recentSyncs = new Map();

setInterval(() => {
  const now = Date.now();
  for (const [k, ts] of recentSyncs) {
    if (now - ts > DEDUP_WINDOW_MS) recentSyncs.delete(k);
  }
}, 10 * 60 * 1000);

/**
 * Detect which extractor class is available in the global scope.
 * The manifest loads exactly one platform extractor per content_scripts entry.
 * @returns {PlatformExtractor|null}
 */
function detectExtractor() {
  if (typeof ClaudeExtractor !== 'undefined') return new ClaudeExtractor();
  if (typeof ChatGPTExtractor !== 'undefined') return new ChatGPTExtractor();
  if (typeof GeminiExtractor !== 'undefined') return new GeminiExtractor();
  if (typeof GrokExtractor !== 'undefined') return new GrokExtractor();
  if (typeof DeepSeekExtractor !== 'undefined') return new DeepSeekExtractor();
  return null;
}

const extractor = detectExtractor();

if (extractor) {
  console.log(`[MemoryCollector] Loaded extractor: ${extractor.getPlatformName()}`);
} else {
  console.warn('[MemoryCollector] No platform extractor found for this page.');
}

/**
 * Build a dedup key from the current conversation state.
 */
function buildDedupKey(platform, url, messageCount, conversationId) {
  if (conversationId) {
    return `${platform}|${conversationId}`;
  }
  return `${platform}|${url}|${messageCount}`;
}

/**
 * Check whether this conversation state was recently synced.
 * Also prunes expired entries.
 */
function isDuplicate(platform, url, messageCount, conversationId) {
  const now = Date.now();
  const key = buildDedupKey(platform, url, messageCount, conversationId);

  // Prune expired entries
  for (const [k, ts] of recentSyncs) {
    if (now - ts > DEDUP_WINDOW_MS) {
      recentSyncs.delete(k);
    }
  }

  if (recentSyncs.has(key)) {
    return true;
  }

  return false;
}

/**
 * Record a successful sync in the dedup map.
 */
function recordSync(platform, url, messageCount, conversationId) {
  const key = buildDedupKey(platform, url, messageCount, conversationId);
  recentSyncs.set(key, Date.now());
}

/**
 * Normalize extractor output so the coordinator supports both array-only and
 * object-based extractors.
 */
async function getConversationData() {
  if (!extractor) {
    return null;
  }

  const extracted = await Promise.resolve(extractor.extractConversation());
  if (Array.isArray(extracted)) {
    return {
      title: document.title || 'Untitled Conversation',
      url: window.location.href,
      conversationId: null,
      messages: extracted
    };
  }

  if (extracted && Array.isArray(extracted.messages)) {
    return {
      title: extracted.title || document.title || 'Untitled Conversation',
      summary: extracted.summary || null,
      url: extracted.url || window.location.href,
      conversationId: extracted.conversationId || null,
      messages: extracted.messages
    };
  }

  return null;
}

async function getConversationStatus() {
  const conversation = await getConversationData();
  const platform = extractor ? extractor.getPlatformName() : null;
  const title = conversation?.title || document.title || 'Untitled Conversation';
  const messageCount = conversation?.messages?.length || 0;

  return {
    ready: Boolean(conversation && messageCount > 0),
    platform,
    title,
    messageCount,
    url: conversation?.url || window.location.href,
    conversationId: conversation?.conversationId || null
  };
}

/**
 * Send conversation data to Memory Hub.
 */
async function syncConversation(conversation, force) {
  if (!extractor) return { success: false, error: 'No extractor' };

  const platform = extractor.getPlatformName();
  const url = conversation.url || window.location.href;
  const messages = conversation.messages || [];
  const conversationId = conversation.conversationId || null;
  const assistantMetadata = typeof extractor.getAssistantMetadata === 'function'
    ? extractor.getAssistantMetadata(conversation)
    : {};

  if (!force && isDuplicate(platform, url, messages.length, conversationId)) {
    console.log('[MemoryCollector] Skipping duplicate sync');
    return { success: false, error: 'duplicate' };
  }

  const payload = {
    platform: platform,
    timestamp: new Date().toISOString(),
    messages: messages,
    project: conversation.title || document.title || null,
    summary: conversation.summary || null,
    provider: assistantMetadata?.provider || null,
    model: assistantMetadata?.model || null,
    assistant_label: assistantMetadata?.assistantLabel || null,
    working_dir: null
  };

  const payloadStr = JSON.stringify(payload);
  if (payloadStr.length > 10 * 1024 * 1024) {
    return { success: false, error: `Conversation too large (${(payloadStr.length / 1024 / 1024).toFixed(1)}MB)` };
  }

  try {
    const response = await fetch(`${MEMORY_HUB_URL}/api/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payloadStr,
      signal: AbortSignal.timeout(30000)
    });

    if (response.ok) {
      const result = await response.json();
      recordSync(platform, url, messages.length, conversationId);

      // Notify background
      chrome.runtime.sendMessage({
        type: 'SYNC_SUCCESS',
        conversationId: result.conversation_id,
        messageCount: messages.length,
        platform: platform,
        title: document.title || 'Untitled Conversation'
      });

      console.log(`[MemoryCollector] Synced ${messages.length} messages (${platform})`);
      return {
        success: true,
        conversationId: result.conversation_id,
        platform,
        title: conversation.title || document.title || 'Untitled Conversation',
        messageCount: messages.length
      };
    } else {
      console.error(`[MemoryCollector] Sync failed: ${response.status}`);
      return { success: false, error: `HTTP ${response.status}` };
    }
  } catch (error) {
    console.error('[MemoryCollector] Sync error:', error.message);
    return { success: false, error: error.message };
  }
}

/**
 * Listen for messages from popup.
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (!extractor) {
    sendResponse({ error: 'No extractor available' });
    return;
  }

  if (request.type === 'GET_STATUS') {
    getConversationStatus().then(status => {
      sendResponse(status);
    }).catch(error => {
      sendResponse({ error: error.message });
    });
    return true;
  } else if (request.type === 'SYNC_NOW') {
    getConversationData().then(conversation => {
      if (!conversation || conversation.messages.length === 0) {
        sendResponse({ success: false, error: 'No messages found' });
        return;
      }

      const platform = extractor.getPlatformName();
      const url = conversation.url || window.location.href;
      const conversationId = conversation.conversationId || null;

      if (isDuplicate(platform, url, conversation.messages.length, conversationId)) {
        sendResponse({ success: false, error: 'duplicate' });
        return;
      }

      syncConversation(conversation, false).then(result => {
        sendResponse(result);
      });
    }).catch(error => {
      sendResponse({ success: false, error: error.message });
    });
    return true; // Keep channel open for async response
  }
});
}
