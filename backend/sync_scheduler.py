"""
Memory Hub V2 -- Sync Scheduler for automatic conversation capture.

Implements two sync strategies:
1. **Polling sync**: Periodically scans CLI session directories for new/updated files
2. **File watching**: Uses watchdog to detect file changes in real-time (optional)

Both strategies feed discovered sessions through the V2 ingest pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from local_importer import (
    SOURCE_DIRS,
    build_payload,
    iter_source_items,
    load_state,
    mark_imported,
    save_state,
    should_skip,
)

logger = logging.getLogger("sync_scheduler")


# ---------------------------------------------------------------------------
# Sync state tracking
# ---------------------------------------------------------------------------

class SyncState:
    """Tracks sync statistics and last-run timestamps."""

    def __init__(self):
        self.last_sync: dict[str, str] = {}  # source -> ISO timestamp
        self.total_synced: dict[str, int] = {}  # source -> count
        self.errors: list[dict] = []
        self.running = False

    def record_sync(self, source: str, count: int):
        self.last_sync[source] = datetime.now().isoformat()
        self.total_synced[source] = self.total_synced.get(source, 0) + count

    def record_error(self, source: str, error: str):
        self.errors.append({
            "source": source,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep only last 50 errors
        if len(self.errors) > 50:
            self.errors = self.errors[-50:]

    def to_dict(self) -> dict:
        return {
            "running": self.running,
            "last_sync": self.last_sync,
            "total_synced": self.total_synced,
            "recent_errors": self.errors[-10:],
        }


sync_state = SyncState()


# ---------------------------------------------------------------------------
# Polling-based sync
# ---------------------------------------------------------------------------

def sync_source_incremental(
    source: str,
    persist_callback: Callable[[dict], str],
    limit: int = 50,
) -> dict:
    """
    Incrementally sync a single source, importing only new/changed files.

    Uses the same fingerprint-based dedup as the V1 importer but routes
    through the provided persist_callback (which should store in V2 tables).

    Returns: {"source": str, "scanned": int, "imported": int, "items": list[str]}
    """
    state = load_state()
    scanned = 0
    imported = 0
    imported_items: list[str] = []
    imported_ids: list[str] = []

    for path in iter_source_items(source):
        if scanned >= limit:
            break
        scanned += 1

        if should_skip(path, state):
            continue

        payload = build_payload(path, source)
        if not payload:
            continue

        try:
            conv_id = persist_callback(payload)
            mark_imported(path, state)
            imported += 1
            imported_items.append(str(path))
            if conv_id:
                imported_ids.append(str(conv_id))
        except Exception as exc:
            logger.warning("Failed to import %s: %s", path, exc)
            sync_state.record_error(source, f"{path}: {exc}")

    save_state(state)
    sync_state.record_sync(source, imported)

    return {
        "source": source,
        "scanned": scanned,
        "imported": imported,
        "items": imported_items[:20],
        "conversation_ids": imported_ids[:50],
    }


def sync_all_sources(
    persist_callback: Callable[[dict], str],
    limit_per_source: int = 50,
) -> dict:
    """
    Sync all configured sources incrementally.

    Returns: {"sources": list[dict], "total_imported": int}
    """
    sources = ["codex", "claude_code", "gemini_cli", "antigravity"]
    results = []
    total = 0

    for source in sources:
        if source not in SOURCE_DIRS:
            continue
        result = sync_source_incremental(source, persist_callback, limit_per_source)
        results.append(result)
        total += result["imported"]

    return {"sources": results, "total_imported": total}


# ---------------------------------------------------------------------------
# Async periodic sync loop
# ---------------------------------------------------------------------------

async def periodic_sync_loop(
    persist_callback: Callable[[dict], str],
    interval_seconds: int = 300,
    limit_per_source: int = 30,
):
    """
    Run incremental sync on all sources every `interval_seconds`.
    Designed to be launched as an asyncio background task.
    """
    sync_state.running = True
    logger.info("Periodic sync started (interval=%ds)", interval_seconds)

    while sync_state.running:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: sync_all_sources(persist_callback, limit_per_source)
            )
            total = result.get("total_imported", 0)
            if total > 0:
                logger.info("Periodic sync imported %d conversations", total)
        except Exception as exc:
            logger.error("Periodic sync error: %s", exc)
            sync_state.record_error("all", str(exc))

        await asyncio.sleep(interval_seconds)

    logger.info("Periodic sync stopped")


def stop_periodic_sync():
    """Signal the periodic sync loop to stop."""
    sync_state.running = False


# ---------------------------------------------------------------------------
# File watcher (optional, requires watchdog)
# ---------------------------------------------------------------------------

_watcher_active = False


def start_file_watcher(
    persist_callback: Callable[[dict], str],
    debounce_seconds: float = 5.0,
) -> bool:
    """
    Start a watchdog-based file watcher on all CLI session directories.

    Returns True if successfully started, False if watchdog is not available.
    """
    global _watcher_active

    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        logger.warning("watchdog not installed -- file watcher unavailable")
        return False

    class SessionFileHandler(FileSystemEventHandler):
        """Handles new/modified session files."""

        def __init__(self):
            self._pending: dict[str, float] = {}

        def on_created(self, event):
            if not event.is_directory:
                self._schedule(event.src_path)

        def on_modified(self, event):
            if not event.is_directory:
                self._schedule(event.src_path)

        def _schedule(self, path_str: str):
            """Debounce: wait before processing to let the file finish writing."""
            self._pending[path_str] = time.time()

        def process_pending(self):
            """Process files that have been stable for debounce_seconds."""
            now = time.time()
            to_process = [
                p for p, t in self._pending.items()
                if now - t >= debounce_seconds
            ]

            if not to_process:
                return

            state = load_state()

            for path_str in to_process:
                del self._pending[path_str]
                path = Path(path_str)

                # Determine source from path
                source = _infer_source_from_path(path)
                if not source:
                    continue

                payload = build_payload(path, source)
                if not payload:
                    continue

                if should_skip(path, state):
                    continue

                try:
                    conv_id = persist_callback(payload)
                    mark_imported(path, state)
                    sync_state.record_sync(source, 1)
                    logger.info("File watcher imported: %s -> %s", path.name, conv_id[:8] if conv_id else "?")
                except Exception as exc:
                    logger.warning("File watcher import failed for %s: %s", path, exc)
                    sync_state.record_error(source, f"{path}: {exc}")

            save_state(state)

    handler = SessionFileHandler()
    observer = Observer()

    watched = 0
    for source, base_dir in SOURCE_DIRS.items():
        if base_dir.exists():
            observer.schedule(handler, str(base_dir), recursive=True)
            watched += 1
            logger.info("Watching %s: %s", source, base_dir)

    if watched == 0:
        logger.warning("No CLI session directories found to watch")
        return False

    observer.start()
    _watcher_active = True
    _observer = observer
    logger.info("File watcher started, monitoring %d directories", watched)

    # Start a background thread to process pending files
    import threading

    def _process_loop():
        while _watcher_active:
            handler.process_pending()
            time.sleep(1)

    thread = threading.Thread(target=_process_loop, daemon=True)
    thread.start()

    return True


_observer = None


def stop_file_watcher():
    """Stop the file watcher."""
    global _watcher_active, _observer
    _watcher_active = False
    if _observer is not None:
        _observer.stop()
        _observer.join(timeout=5)
        _observer = None


def _infer_source_from_path(path: Path) -> str | None:
    """Infer the source type from a file path."""
    path_str = str(path).lower()
    if ".codex" in path_str and path.suffix == ".jsonl":
        return "codex"
    if ".claude" in path_str and path.suffix == ".jsonl":
        return "claude_code"
    if "antigravity" in path_str and path.suffix == ".pb":
        return "antigravity"
    if ".gemini" in path_str and path.name.startswith("session-") and path.suffix == ".json":
        return "gemini_cli"
    return None


# ---------------------------------------------------------------------------
# Public API for sync status
# ---------------------------------------------------------------------------

def get_sync_status() -> dict:
    """Get current sync status including last run times and stats."""
    return {
        **sync_state.to_dict(),
        "file_watcher_active": _watcher_active,
        "monitored_directories": {
            source: str(base_dir)
            for source, base_dir in SOURCE_DIRS.items()
            if base_dir.exists()
        },
    }
