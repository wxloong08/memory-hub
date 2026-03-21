# V2 Code Review Report

**Date**: 2026-03-19
**Reviewer**: code-reviewer (automated)
**Scope**: All V2 modules -- code quality, security, correctness, integration

---

## Critical Issues (Fixed)

### 1. [CRITICAL] switch_engine.py:382 -- `compress_message()` called with wrong argument count

**File**: `backend/switch_engine.py`, function `_parse_v1_content_to_messages`

**Problem**: `compress_message(current["content"], current.get("content_type", "text"))` passes two arguments, but `compress_message()` in `message_compressor.py` only accepts one parameter (`text: str`). This causes a `TypeError` at runtime when parsing V1 content that ends with a trailing message.

**Severity**: CRITICAL -- crashes the V1 fallback path in switch_engine during CLI switches.

**Fix Applied**: Changed to `compress_message(current["content"])` (removed the extra argument).

---

## Warning Issues

### 2. [WARNING] database_v2.py:29 -- SQLite `check_same_thread=False` without connection locking

**File**: `backend/database_v2.py:29`

The `sqlite3.connect(..., check_same_thread=False)` call allows multi-threaded access to the connection, but there is no mutex/lock around `self.conn` operations. With FastAPI's async workers, concurrent requests could cause `sqlite3.OperationalError: database is locked` or corrupt state.

**Recommendation**: Add a `threading.Lock` around all write operations (INSERT/UPDATE/DELETE + commit), or use a connection pool (e.g., `aiosqlite` or a per-request connection pattern).

### 3. [WARNING] database_v2.py:397 -- `LIMIT`/`OFFSET` injected via f-string

**File**: `backend/database_v2.py:397`

```python
if limit:
    query += f" LIMIT {limit} OFFSET {offset}"
```

While `limit` and `offset` come from typed Python parameters (not raw user input), the f-string injection pattern is fragile. If the call chain ever changes to pass unsanitized input, this becomes SQL injection.

**Recommendation**: Use parameterized queries: `query += " LIMIT ? OFFSET ?"` with params.

### 4. [WARNING] database_v2.py:666 -- Migration swallows exceptions silently

**File**: `backend/database_v2.py:666`

```python
except Exception:
    errors += 1
```

Migration errors are counted but not logged. If a conversation fails to migrate, there is no way to diagnose the cause.

**Recommendation**: Log the exception (at minimum `logger.warning("Migration error for %s: %s", conv_id, exc)`).

### 5. [WARNING] sync_scheduler.py:172 -- `sync_all_sources` called in async loop but is synchronous

**File**: `backend/sync_scheduler.py:172`

`periodic_sync_loop` is an `async def` but calls `sync_all_sources()` which is a blocking synchronous function doing file I/O. This blocks the asyncio event loop during sync.

**Recommendation**: Run the sync in a thread executor: `await asyncio.get_event_loop().run_in_executor(None, sync_all_sources, ...)`.

### 6. [WARNING] sync_scheduler.py:289-296 -- File watcher process_pending loop uses `time.sleep(1)` in thread

**File**: `backend/sync_scheduler.py:289`

The `_process_loop` thread does `load_state()` and `save_state()` per file, which reads/writes the state file repeatedly without batching. Under high file creation rates, this causes I/O contention.

**Recommendation**: Batch pending files and do a single state save per cycle.

### 7. [WARNING] switch_engine.py:68-94 -- `upsert_working_memory` uses `COALESCE` which prevents explicit NULL updates

**File**: `backend/switch_engine.py:68`

The UPDATE uses `coalesce(?, active_task)` which means you can never clear a field to NULL -- a NULL parameter is treated as "keep the old value". This differs from `database_v2.py`'s `upsert_working_memory` which uses explicit `is not None` checks.

**Recommendation**: Use the same pattern as `database_v2.py` -- build dynamic SET clauses for provided fields only.

### 8. [WARNING] context_assembler.py:246 -- Truncation message counts incorrectly

**File**: `backend/context_assembler.py:246`

```python
lines.append(f"[...{len(messages) - total_turns} more messages truncated]")
```

`total_turns` is a running count across all sessions, but `len(messages)` is the count for the current session. When processing multiple sessions, this produces incorrect counts.

**Recommendation**: Track per-session message index separately.

### 9. [WARNING] api_v2.py:35-36 -- Module-level DB initialization creates a connection before `set_db_v2()` is called

**File**: `backend/api_v2.py:35`

`db_v2 = DatabaseV2(...)` runs at import time, creating a database connection. Then `main.py:2014` calls `set_db_v2()` to replace it with a shared instance. The original connection is never closed, leaking a SQLite connection.

**Recommendation**: Initialize `db_v2 = None` and lazily create it on first use, or close the old connection in `set_db_v2()`.

### 10. [WARNING] main.py:2009 + api_v2.py:35 -- Two DatabaseV2 instances created for same DB file

**File**: `backend/main.py:2009`, `backend/api_v2.py:35`

Both files independently create a `DatabaseV2` instance for the same `memory.db`. While `set_db_v2()` replaces the api_v2 instance, the router endpoints captured in the closure still use the module-global `db_v2` which is correctly replaced. However, the original api_v2 connection is leaked (see #9).

---

## Info Issues

### 11. [INFO] models_v2.py -- No field-level validation constraints

**File**: `backend/models_v2.py`

The Pydantic models lack constraints such as:
- `platform` has no enum or regex validation (accepts any string)
- `started_at` is a plain `str` instead of a validated datetime format
- `importance` has no min/max bounds (should be 1-10)
- `MessageInput.role` has no enum constraint

These are acceptable for an internal API but should be tightened if the API is exposed publicly.

### 12. [INFO] message_compressor.py -- Regex patterns are compiled at module level (good)

The module correctly compiles regex patterns at module level for performance. No issues.

### 13. [INFO] compression.py -- Thin compatibility layer is clean

Just re-exports and one utility function. No issues.

### 14. [INFO] cli/memory_hub.py:48-52 -- Error handling catches `URLError` before `HTTPError`

**File**: `cli/memory_hub.py:48`

`HTTPError` is a subclass of `URLError`. The `except urllib.error.URLError` on line 48 will catch HTTP errors before the `except urllib.error.HTTPError` on line 53 can run. The `HTTPError` handler is dead code.

**Recommendation**: Swap the order -- catch `HTTPError` first.

### 15. [INFO] switch_engine.py -- Duplicated working memory functions

`switch_engine.py` duplicates `get_working_memory`, `upsert_working_memory`, `delete_working_memory`, and `list_working_memories` from `database_v2.py`. The switch_engine versions operate on raw `sqlite3.Connection` while database_v2 uses `self.conn`. This creates maintenance burden.

**Recommendation**: Long-term, refactor switch_engine to accept a `DatabaseV2` instance instead of raw connections.

---

## Integration Verification

### V1/V2 Endpoint Conflicts
- **No conflicts found**. V2 endpoints use `/api/v2/` prefix consistently. V1 endpoints in main.py use `/api/` without the v2 prefix.
- Working memory endpoints are defined in `main.py` (not in `api_v2.py` router), which avoids duplication.

### `set_db_v2()` Shared Instance Mechanism
- **Works correctly**. `main.py:2013-2014` calls `set_db_v2(db_v2)` after creating the shared instance. The api_v2 module-level `db_v2` global is replaced. All router endpoints reference the global, so they pick up the shared instance.
- **Caveat**: The original connection created at import time in `api_v2.py:35` is leaked (see Warning #9).

### Import Paths
- All imports are correct assuming `backend/` is on `sys.path` (which it is, via the FastAPI startup).
- `cli/memory_hub.py` correctly adds `BACKEND_DIR` to `sys.path`.

### Circular Dependencies
- **No circular dependencies found**. The dependency graph is:
  - `main.py` -> `api_v2`, `database_v2`, `models_v2`, `switch_engine`, `sync_scheduler`
  - `api_v2` -> `database_v2`, `message_compressor`, `models_v2`, `sync_scheduler`
  - `switch_engine` -> `message_compressor`, `context_assembler`
  - `context_assembler` -> `client_exports`, `message_compressor`, `compression`
  - `compression` -> `message_compressor`
  - All edges are acyclic.

---

## Overall Code Quality Assessment

**Rating**: 7/10

**Strengths**:
- Clean separation of concerns across modules
- Good deduplication logic (content_hash + source_fingerprint)
- Token budgeting system is well-designed
- V1/V2 backward compatibility is handled gracefully
- Schema migration path is solid

**Areas for Improvement**:
- Thread safety for SQLite connections (Warning #2)
- Leaked database connection at import time (Warning #9)
- Blocking sync in async event loop (Warning #5)
- Duplicated working memory code between switch_engine and database_v2 (Info #15)
- Dead exception handler in CLI tool (Info #14)

**Critical issues fixed**: 1 (switch_engine.py `compress_message` call signature)
