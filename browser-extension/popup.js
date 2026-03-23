/**
 * Claude Memory Collector - Popup Script
 * All DOM rendering uses textContent + createElement (no innerHTML with user data).
 */

const MEMORY_HUB_URL = 'http://127.0.0.1:8765';

const PLATFORMS = {
  claude_web: { emoji: 'C', name: 'Claude' },
  chatgpt:    { emoji: 'G', name: 'ChatGPT' },
  gemini:     { emoji: 'G', name: 'Gemini' },
  grok:       { emoji: 'X', name: 'Grok' },
  deepseek:   { emoji: 'D', name: 'DeepSeek' }
};

const CONTENT_SCRIPT_TARGETS = [
  {
    match: url => url.hostname.includes('claude.ai'),
    files: ['browser-extension/core/extractor.js', 'browser-extension/platforms/claude.js', 'browser-extension/content_script.js']
  },
  {
    match: url => url.hostname.includes('chatgpt.com') || url.hostname.includes('chat.openai.com'),
    files: ['browser-extension/core/extractor.js', 'browser-extension/platforms/chatgpt.js', 'browser-extension/content_script.js']
  },
  {
    match: url => url.hostname.includes('gemini.google.com'),
    files: ['browser-extension/core/extractor.js', 'browser-extension/platforms/gemini.js', 'browser-extension/content_script.js']
  },
  {
    match: url => url.hostname.includes('grok.com') || (url.hostname.includes('x.com') && url.pathname.startsWith('/i/grok')),
    files: ['browser-extension/core/extractor.js', 'browser-extension/platforms/grok.js', 'browser-extension/content_script.js']
  },
  {
    match: url => url.hostname.includes('chat.deepseek.com'),
    files: ['browser-extension/core/extractor.js', 'browser-extension/platforms/deepseek.js', 'browser-extension/content_script.js']
  }
];

// DOM refs
let connectionStatusEl, convInfoEl, syncBtnEl, historyListEl;
let isConnected = false;
let currentConversation = null;

document.addEventListener('DOMContentLoaded', async () => {
  connectionStatusEl = document.getElementById('connectionStatus');
  convInfoEl = document.getElementById('conv-info');
  syncBtnEl = document.getElementById('sync-btn');
  historyListEl = document.getElementById('history-list');

  syncBtnEl.addEventListener('click', handleSync);

  await checkConnection();
  await getConversationStatus();
  loadHistory();

  // Refresh periodically
  setInterval(async () => {
    await checkConnection();
    await getConversationStatus();
  }, 15000);
});

/**
 * Check Memory Hub connectivity.
 */
async function checkConnection() {
  try {
    const response = await fetch(`${MEMORY_HUB_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(3000)
    });
    if (response.ok) {
      setConnectionStatus(true);
      return true;
    }
  } catch (_) {
    // ignore
  }
  setConnectionStatus(false);
  return false;
}

/**
 * Update the connection status indicator using DOM methods (no innerHTML).
 */
function setConnectionStatus(connected) {
  isConnected = connected;

  // Clear existing children
  while (connectionStatusEl.firstChild) {
    connectionStatusEl.removeChild(connectionStatusEl.firstChild);
  }

  const dot = document.createElement('span');
  dot.className = 'dot';

  const label = document.createTextNode(connected ? ' Connected' : ' Disconnected');

  connectionStatusEl.appendChild(dot);
  connectionStatusEl.appendChild(label);
  connectionStatusEl.className = 'status-indicator ' + (connected ? 'connected' : 'disconnected');
  updateSyncButtonState();
}

/**
 * Get conversation status from the active tab's content script.
 */
async function getConversationStatus() {
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs[0]) {
      renderConversation(null);
      return;
    }

    let response = await sendMessageToTab(tabs[0].id, { type: 'GET_STATUS' });
    if (!response) {
      const injected = await ensureContentScriptInjected(tabs[0]);
      if (injected) {
        await delay(300);
        response = await sendMessageToTab(tabs[0].id, { type: 'GET_STATUS' });
      }
    }

    renderConversation(response || null);
  } catch (_) {
    renderConversation(null);
  }
}

/**
 * Render conversation info using createElement (XSS-safe).
 */
function renderConversation(info) {
  currentConversation = info && info.platform ? info : null;

  // Clear
  while (convInfoEl.firstChild) {
    convInfoEl.removeChild(convInfoEl.firstChild);
  }

  if (!info || !info.platform || !info.ready) {
    convInfoEl.className = 'empty-state';
    convInfoEl.textContent = info && info.platform ? 'No messages found' : 'No conversation detected';
    updateSyncButtonState();
    return;
  }

  convInfoEl.className = '';

  const platformInfo = PLATFORMS[info.platform] || { emoji: '?', name: info.platform };

  const titleDiv = document.createElement('div');
  titleDiv.className = 'conv-title';
  titleDiv.textContent = info.title || 'Untitled';

  const metaDiv = document.createElement('div');
  metaDiv.className = 'conv-meta';
  metaDiv.textContent = `${platformInfo.emoji} ${platformInfo.name} - ${info.messageCount || 0} messages`;

  convInfoEl.appendChild(titleDiv);
  convInfoEl.appendChild(metaDiv);
  updateSyncButtonState();
}

/**
 * Handle sync button press.
 */
async function handleSync() {
  syncBtnEl.disabled = true;
  syncBtnEl.textContent = 'Syncing...';

  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs[0]) {
      resetSyncBtn('No active tab');
      return;
    }

    let response = await sendMessageToTab(tabs[0].id, { type: 'SYNC_NOW' });
    if (!response) {
      const injected = await ensureContentScriptInjected(tabs[0]);
      if (injected) {
        await delay(300);
        response = await sendMessageToTab(tabs[0].id, { type: 'SYNC_NOW' });
      }
    }

    if (!response) {
      resetSyncBtn('Not on supported platform');
      return;
    }

    if (response.success) {
      currentConversation = {
        ready: true,
        platform: response.platform || currentConversation?.platform || null,
        title: response.title || currentConversation?.title || 'Untitled',
        messageCount: response.messageCount || currentConversation?.messageCount || 0
      };
      syncBtnEl.textContent = 'Synced!';
      saveHistoryEntry(response.conversationId);
      setTimeout(() => { resetSyncBtn(); loadHistory(); }, 2000);
    } else if (response.error === 'duplicate') {
      resetSyncBtn('Already synced');
    } else {
      resetSyncBtn(response?.error || 'Sync failed');
    }
  } catch (error) {
    resetSyncBtn(error.message || 'Error');
  }
}

async function sendMessageToTab(tabId, message) {
  try {
    return await chrome.tabs.sendMessage(tabId, message);
  } catch (_) {
    return null;
  }
}

async function ensureContentScriptInjected(tab) {
  if (!tab?.id || !tab?.url) {
    return false;
  }

  let parsedUrl;
  try {
    parsedUrl = new URL(tab.url);
  } catch (_) {
    return false;
  }

  const target = CONTENT_SCRIPT_TARGETS.find(item => item.match(parsedUrl));
  if (!target) {
    return false;
  }

  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: target.files
    });
    return true;
  } catch (_) {
    return false;
  }
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Reset sync button to default state.
 */
function resetSyncBtn(tempLabel) {
  if (tempLabel) {
    syncBtnEl.textContent = tempLabel;
    setTimeout(() => {
      syncBtnEl.textContent = 'Sync Now';
      updateSyncButtonState();
    }, 5000);
  } else {
    syncBtnEl.textContent = 'Sync Now';
    updateSyncButtonState();
  }
}

/**
 * Save a sync to local history.
 */
function saveHistoryEntry(conversationId) {
  chrome.storage.local.get(['syncHistory'], (result) => {
    const history = result.syncHistory || [];
    history.unshift({
      id: conversationId,
      platform: currentConversation?.platform || currentPlatform(),
      title: currentConversation?.title || currentTitle(),
      messageCount: currentConversation?.messageCount || currentMessageCount(),
      time: new Date().toISOString(),
      url: ''
    });
    // Keep last 20
    chrome.storage.local.set({ syncHistory: history.slice(0, 20) });
  });
}

/**
 * Load and render sync history using createElement (XSS-safe).
 */
function loadHistory() {
  chrome.storage.local.get(['syncHistory'], (result) => {
    const history = result.syncHistory || [];

    // Clear
    while (historyListEl.firstChild) {
      historyListEl.removeChild(historyListEl.firstChild);
    }

    if (history.length === 0) {
      historyListEl.className = 'empty-state';
      historyListEl.textContent = 'No syncs yet';
      return;
    }

    historyListEl.className = '';

    history.forEach(entry => {
      const item = document.createElement('div');
      item.className = 'history-item';

      const idSpan = document.createElement('span');
      idSpan.className = 'history-platform';
      const platformInfo = PLATFORMS[entry.platform] || { emoji: '?', name: 'Unknown' };
      const title = entry.title || (entry.id ? entry.id.substring(0, 8) + '...' : 'Unknown');
      idSpan.textContent = `${platformInfo.emoji} ${title}`;

      const timeSpan = document.createElement('span');
      timeSpan.className = 'history-time';
      timeSpan.textContent = formatTime(entry.time);

      item.appendChild(idSpan);
      item.appendChild(timeSpan);
      historyListEl.appendChild(item);
    });
  });
}

function currentPlatform() {
  const meta = convInfoEl?.querySelector('.conv-meta')?.textContent || '';
  const matched = Object.entries(PLATFORMS).find(([, value]) => meta.includes(value.name));
  return matched ? matched[0] : null;
}

function currentTitle() {
  return convInfoEl?.querySelector('.conv-title')?.textContent || 'Untitled';
}

function currentMessageCount() {
  const meta = convInfoEl?.querySelector('.conv-meta')?.textContent || '';
  const match = meta.match(/(\d+)\s+messages/i);
  return match ? Number(match[1]) : 0;
}

function updateSyncButtonState() {
  const ready = Boolean(currentConversation && currentConversation.ready !== false && (currentConversation.messageCount || 0) > 0);
  syncBtnEl.disabled = !isConnected || !ready;
}

/**
 * Format an ISO timestamp into a human-readable relative string.
 */
function formatTime(isoString) {
  if (!isoString) return 'Unknown';

  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return diffMins + 'm ago';

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return diffHours + 'h ago';

  const diffDays = Math.floor(diffHours / 24);
  return diffDays + 'd ago';
}
