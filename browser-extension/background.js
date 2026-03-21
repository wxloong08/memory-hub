/**
 * Claude Memory Collector - Background Service Worker
 * Simple health checking and sync event logging.
 */

let isMemoryHubHealthy = false;

/**
 * Check Memory Hub health with a 3-second timeout.
 */
async function checkMemoryHubHealth() {
  try {
    const response = await fetch('http://127.0.0.1:8765/health', {
      method: 'GET',
      signal: AbortSignal.timeout(3000)
    });

    if (response.ok) {
      isMemoryHubHealthy = true;
      console.log('[MemoryCollector] Memory Hub is healthy');
    } else {
      isMemoryHubHealthy = false;
      console.warn('[MemoryCollector] Memory Hub returned non-OK status');
    }
  } catch (error) {
    isMemoryHubHealthy = false;
    console.warn('[MemoryCollector] Memory Hub not accessible:', error.message);
  }
}

/**
 * Listen for SYNC_SUCCESS messages from content scripts and log stats.
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'SYNC_SUCCESS') {
    const platform = request.platform || 'unknown';
    const count = request.messageCount || 0;
    const convId = request.conversationId || 'n/a';

    console.log(
      `[MemoryCollector] Sync success: platform=${platform}, messages=${count}, id=${convId}`
    );
  }
});

// Initial health check
checkMemoryHubHealth();

// Periodic health check every 30 seconds
setInterval(checkMemoryHubHealth, 30000);
