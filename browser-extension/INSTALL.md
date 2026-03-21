# Browser Extension Install

## Prerequisite

Start the Memory Hub backend first:

```powershell
cd "D:\python project\claude-memory-system\backend"
python main.py
```

Expected backend health check:

```powershell
curl http://localhost:8765/health
```

Expected response:

```json
{"status":"healthy"}
```

## Load In Chrome

1. Open `chrome://extensions/`
2. Enable `Developer mode`
3. Click `Load unpacked`
4. Choose:

```text
D:\python project\claude-memory-system\browser-extension
```

## Smoke Test

1. Open one supported platform:
   - `https://claude.ai`
   - `https://chatgpt.com`
   - `https://gemini.google.com`
   - `https://grok.com`
   - `https://chat.deepseek.com`
2. Open or create a conversation with at least one user message and one assistant reply
3. Click the extension icon
4. Verify:
   - popup shows `Connected`
   - popup shows platform name
   - popup shows non-zero message count
   - `Sync Now` is enabled
5. Click `Sync Now`
6. Verify popup shows `Synced!`

## Verify Backend Storage

```powershell
@'
import sqlite3
conn = sqlite3.connect("D:/python project/claude-memory-system/backend/data/memory.db")
cur = conn.cursor()
cur.execute("select id, platform, summary from conversations order by created_at desc limit 5")
for row in cur.fetchall():
    print(row)
conn.close()
'@ | python -
```

## Duplicate Protection Check

1. Stay on the same conversation
2. Click `Sync Now` again immediately
3. Expected popup message: `Already synced`

## If It Fails

- `Disconnected`
  Backend is not reachable on `http://localhost:8765`
- `No conversation detected`
  Active tab is not on a supported platform
- `No messages found`
  Extractor matched the site but failed to read the current DOM
- `Sync failed`
  Open DevTools on the chat page and inspect console logs from `MemoryCollector`
