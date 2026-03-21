# Memory Sync Browser Extension

Chrome extension for manually syncing AI chat conversations into the local Memory Hub.

## Current Scope

- Manual sync from the popup
- Supported platforms:
  - Claude (`claude.ai`)
  - ChatGPT (`chatgpt.com`, `chat.openai.com`)
  - Gemini (`gemini.google.com`)
  - Grok (`grok.com`, `x.com/i/grok`) experimental
  - DeepSeek (`chat.deepseek.com`) experimental
- Local-only sync target: `http://localhost:8765`
- Recent sync history stored in Chrome local storage
- 5-minute duplicate protection per conversation

## Not Implemented

- No automatic background sync
- No offline queue
- No settings page inside the extension
- No guaranteed extractor stability for Gemini, Grok, or DeepSeek

## Install

1. Start the backend:

```powershell
cd "D:\python project\claude-memory-system\backend"
python main.py
```

2. Open `chrome://extensions/`
3. Enable `Developer mode`
4. Click `Load unpacked`
5. Select:

```text
D:\python project\claude-memory-system\browser-extension
```

## Use

1. Open a supported AI chat page
2. Wait for the conversation to fully render
3. Click the extension popup
4. Confirm the popup shows the detected platform and message count
5. Click `Sync Now`

If the same conversation is synced again within 5 minutes, the popup will show `Already synced`.

## Popup Behavior

- `Connected` means the backend responded to `/health`
- `Disconnected` means Memory Hub is not reachable
- `No conversation detected` means the active tab is not a supported AI chat page
- `No messages found` means the page matched a supported platform but the extractor found no usable messages

## Architecture

- [manifest.json](/D:/python%20project/claude-memory-system/browser-extension/manifest.json)
  Loads one platform extractor plus the shared content coordinator per supported site
- [core/extractor.js](/D:/python%20project/claude-memory-system/browser-extension/core/extractor.js)
  Base extractor helpers
- [content_script.js](/D:/python%20project/claude-memory-system/browser-extension/content_script.js)
  Normalizes extractor output, deduplicates, posts to Memory Hub
- [popup.js](/D:/python%20project/claude-memory-system/browser-extension/popup.js)
  Popup status, manual sync, local history
- [background.js](/D:/python%20project/claude-memory-system/browser-extension/background.js)
  Backend health logging and sync event logging

## Debug

1. Open the target AI page
2. Open DevTools on that page
3. Check console messages from `MemoryCollector`
4. Open the popup and verify connection state

Useful checks:

```powershell
curl http://localhost:8765/health
python -m pytest backend/tests/test_api_contracts.py
```

## Known Risks

- Extractors depend on each site DOM structure
- Experimental platforms may break without code changes
- Chat pages with partial rendering or virtualization may produce incomplete message lists
