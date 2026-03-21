"""
Memory Hub V2 -- API endpoints for the three-layer memory architecture.

All V2 endpoints are under /api/v2/ prefix.
V1 endpoints in main.py remain unchanged for backward compatibility.
"""

from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query

from database_v2 import DatabaseV2
from message_compressor import compress_messages, estimate_tokens
from models_v2 import (
    ConversationV2Input,
    ConversationV2Response,
    LocalImportV2Input,
    WorkingMemoryInput,
)
from vector_store import VectorStore

router = APIRouter(prefix="/api/v2", tags=["v2"])

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Initialize V2 database — can be replaced via set_db_v2() to share
# a single instance with main.py.
db_v2 = DatabaseV2(str(DATA_DIR / "memory.db"))


def set_db_v2(instance: DatabaseV2):
    """Allow main.py to inject a shared DatabaseV2 instance."""
    global db_v2
    if db_v2 is not None and hasattr(db_v2, 'close'):
        db_v2.close()
    db_v2 = instance


# Vector store instance — injected by main.py via set_vector_store_v2()
_vector_store: VectorStore | None = None


def set_vector_store_v2(instance: VectorStore):
    """Allow main.py to inject a shared VectorStore instance."""
    global _vector_store
    _vector_store = instance


def _index_conversation_in_vector_store(
    conv_id: str,
    messages_dicts: list[dict],
    *,
    platform: str = "unknown",
    started_at: str = "",
    project: str = "",
    provider: str = "",
    model: str = "",
    assistant_label: str = "",
    importance: int = 5,
    summary: str = "",
):
    """Index a V2 conversation into the shared vector store (if available)."""
    if _vector_store is None:
        return
    full_content = "\n\n".join(
        f"{m.get('role', '')}: {m.get('content', '')}" for m in messages_dicts
    )
    _vector_store.add_conversation(
        conv_id=conv_id,
        content=full_content,
        metadata={
            "platform": platform,
            "timestamp": started_at,
            "project": project,
            "provider": provider or "",
            "model": model or "",
            "assistant_label": assistant_label or "",
            "importance": importance,
            "summary": summary,
        },
    )


# ---------------------------------------------------------------------------
# Helper: derive summary from messages (reused from V1 logic)
# ---------------------------------------------------------------------------

def _derive_summary_v2(messages: list[dict], project: str | None = None, provided_summary: str | None = None) -> str:
    """Derive a summary from conversation messages."""
    if provided_summary and provided_summary.strip():
        return provided_summary.strip()[:2000]

    user_messages = [
        m.get("content", "").strip()
        for m in messages
        if m.get("role") == "user" and m.get("content", "").strip()
    ]

    if user_messages:
        first_user = user_messages[0][:200]
        if project and project.strip():
            return f"{project.strip()}: {first_user}"
        return first_user

    if project and project.strip():
        return project.strip()[:200]

    return "No summary"


# ---------------------------------------------------------------------------
# Archive Layer: Conversations
# ---------------------------------------------------------------------------

@router.post("/conversations", response_model=ConversationV2Response)
async def ingest_conversation(payload: ConversationV2Input):
    """
    Ingest a full conversation with structured messages.
    This is the primary V2 ingest endpoint.
    """
    messages_dicts = [m.model_dump() for m in payload.messages]
    if not messages_dicts:
        raise HTTPException(status_code=400, detail="At least one message is required")

    # Derive summary
    summary = _derive_summary_v2(
        messages_dicts,
        project=payload.project,
        provided_summary=payload.summary,
    )
    summary_source = "imported" if payload.summary and payload.summary.strip() else "fallback"

    # Calculate importance
    importance = min(10, 5 + len(messages_dicts) // 4)

    # Compute content hash
    hash_source = "\n\n".join(
        f"{m.get('role', '')}: {m.get('content', '')}" for m in messages_dicts
    )
    content_hash = sha256(hash_source.encode("utf-8")).hexdigest()

    # Store conversation
    conv_id, msg_count, total_tokens = db_v2.add_conversation(
        platform=payload.platform,
        started_at=payload.started_at,
        messages=messages_dicts,
        session_id=payload.session_id,
        workspace_path=payload.workspace_path,
        ended_at=payload.ended_at,
        summary=summary,
        summary_source=summary_source,
        importance=importance,
        provider=payload.provider,
        model=payload.model,
        assistant_label=payload.assistant_label,
        source_path=payload.source_path,
        source_fingerprint=payload.source_fingerprint,
        content_hash=content_hash,
        metadata=payload.metadata,
    )

    # Index into vector store for semantic search
    _index_conversation_in_vector_store(
        conv_id=conv_id,
        messages_dicts=messages_dicts,
        platform=payload.platform,
        started_at=payload.started_at,
        project=payload.metadata.get("project", "") if payload.metadata else "",
        provider=payload.provider or "",
        model=payload.model or "",
        assistant_label=payload.assistant_label or "",
        importance=importance,
        summary=summary,
    )

    # Update working memory if working_state is provided
    working_memory_updated = False
    if payload.working_state and payload.workspace_path:
        ws = payload.working_state
        db_v2.upsert_working_memory(
            workspace_path=payload.workspace_path,
            active_task=ws.active_task,
            current_plan=ws.plan,
            progress=ws.progress,
            open_issues=ws.open_issues,
            recent_changes=ws.recent_changes,
            last_cli=payload.platform,
            last_session_id=conv_id,
        )
        working_memory_updated = True

    return ConversationV2Response(
        conversation_id=conv_id,
        message_count=msg_count,
        token_estimate=total_tokens,
        summary=summary,
        working_memory_updated=working_memory_updated,
    )


@router.get("/conversations")
async def list_conversations(
    workspace_path: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = "newest",
):
    """List conversations with filtering and pagination."""
    conversations, total = db_v2.get_conversations(
        workspace_path=workspace_path,
        platform=platform,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    return {
        "conversations": conversations,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a conversation with its messages."""
    conv = db_v2.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = db_v2.get_messages(conversation_id)
    conv["messages"] = messages
    return conv


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    role: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Get messages for a conversation, optionally filtered by role."""
    conv = db_v2.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    roles = [role] if role else None
    messages = db_v2.get_messages(
        conversation_id,
        roles=roles,
        limit=limit,
        offset=offset,
    )
    total = db_v2.count_messages(conversation_id, roles=roles)
    return {"messages": messages, "total": total}


@router.get("/conversations/{conversation_id}/compressed")
async def get_compressed_conversation(conversation_id: str):
    """Get the compressed version of a conversation's messages."""
    conv = db_v2.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = db_v2.get_compressed_messages(conversation_id)
    total_original = sum(m.get("token_estimate", 0) for m in db_v2.get_messages(conversation_id))
    total_compressed = sum(estimate_tokens(m.get("content", "")) for m in messages)

    return {
        "conversation_id": conversation_id,
        "messages": messages,
        "original_tokens": total_original,
        "compressed_tokens": total_compressed,
        "compression_ratio": round(total_compressed / max(total_original, 1), 3),
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and its messages."""
    if not db_v2.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "ok", "deleted": conversation_id}


# ---------------------------------------------------------------------------
# Working Memory -- routes defined in main.py by switch engine
# (see main.py /api/v2/working-memory/* endpoints)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Import (V2 enhanced)
# ---------------------------------------------------------------------------

@router.post("/import/local")
async def import_local_v2(payload: LocalImportV2Input):
    """
    Import local CLI sessions with V2 structured message storage.
    This wraps the existing local_importer but stores results in V2 tables.
    """
    from local_importer import import_sources as v1_import_sources

    sources_map = {
        "all": ["codex", "claude_code", "gemini_cli", "antigravity"],
    }
    sources = sources_map.get(payload.source, [payload.source])

    def persist_v2(v1_payload: dict) -> str:
        """Persist callback that stores in V2 archive tables."""
        messages = v1_payload.get("messages", [])
        msg_dicts = [
            {"role": m.get("role", "user"), "content": m.get("content", ""), "content_type": "text"}
            for m in messages
        ]

        summary = _derive_summary_v2(
            msg_dicts,
            project=v1_payload.get("project"),
            provided_summary=v1_payload.get("summary"),
        )

        importance = min(10, 5 + len(msg_dicts) // 4)
        conv_id, _, _ = db_v2.add_conversation(
            platform=v1_payload.get("platform", "unknown"),
            started_at=v1_payload.get("timestamp", datetime.now().isoformat()),
            messages=msg_dicts,
            workspace_path=v1_payload.get("working_dir"),
            summary=summary,
            summary_source="imported" if v1_payload.get("summary") else "fallback",
            importance=importance,
            provider=v1_payload.get("provider"),
            model=v1_payload.get("model"),
            assistant_label=v1_payload.get("assistant_label"),
            source_path=v1_payload.get("source_path"),
            source_fingerprint=v1_payload.get("source_fingerprint"),
            content_hash=v1_payload.get("content_hash"),
            metadata={
                "recovery_mode": v1_payload.get("recovery_mode"),
                "project": v1_payload.get("project"),
            },
        )
        _index_conversation_in_vector_store(
            conv_id=conv_id,
            messages_dicts=msg_dicts,
            platform=v1_payload.get("platform", "unknown"),
            started_at=v1_payload.get("timestamp", ""),
            project=v1_payload.get("project", ""),
            provider=v1_payload.get("provider", ""),
            model=v1_payload.get("model", ""),
            assistant_label=v1_payload.get("assistant_label", ""),
            importance=importance,
            summary=summary,
        )
        return conv_id

    try:
        result = v1_import_sources(
            sources, payload.limit, payload.dry_run, persist_v2,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported source: {payload.source}") from exc

    result["dry_run"] = payload.dry_run
    result["requested_source"] = payload.source
    result["storage"] = "v2_archive"
    return result


# ---------------------------------------------------------------------------
# Sync management
# ---------------------------------------------------------------------------

@router.get("/sync/status")
async def get_sync_status():
    """Get current sync status including file watcher and polling info."""
    from sync_scheduler import get_sync_status as _get_sync_status
    return _get_sync_status()


@router.post("/sync/trigger")
async def trigger_sync(source: str = "all", limit: int = 30):
    """Manually trigger an incremental sync of local CLI sessions."""
    from sync_scheduler import sync_all_sources, sync_source_incremental

    VALID_SOURCES = ["codex", "claude_code", "gemini_cli", "antigravity", "all"]
    if source not in VALID_SOURCES:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}. Valid: {VALID_SOURCES}")

    if source == "all":
        result = sync_all_sources(_persist_v2_callback, limit_per_source=limit)
    else:
        result = sync_source_incremental(source, _persist_v2_callback, limit=limit)
    return result


def _persist_v2_callback(v1_payload: dict) -> str:
    """Shared persist callback for V2 sync (used by scheduler and manual trigger)."""
    messages = v1_payload.get("messages", [])
    msg_dicts = [
        {"role": m.get("role", "user"), "content": m.get("content", ""), "content_type": "text"}
        for m in messages
    ]

    summary = _derive_summary_v2(
        msg_dicts,
        project=v1_payload.get("project"),
        provided_summary=v1_payload.get("summary"),
    )

    importance = min(10, 5 + len(msg_dicts) // 4)
    conv_id, _, _ = db_v2.add_conversation(
        platform=v1_payload.get("platform", "unknown"),
        started_at=v1_payload.get("timestamp", datetime.now().isoformat()),
        messages=msg_dicts,
        workspace_path=v1_payload.get("working_dir"),
        summary=summary,
        summary_source="imported" if v1_payload.get("summary") else "fallback",
        importance=importance,
        provider=v1_payload.get("provider"),
        model=v1_payload.get("model"),
        assistant_label=v1_payload.get("assistant_label"),
        source_path=v1_payload.get("source_path"),
        source_fingerprint=v1_payload.get("source_fingerprint"),
        content_hash=v1_payload.get("content_hash"),
        metadata={
            "recovery_mode": v1_payload.get("recovery_mode"),
            "project": v1_payload.get("project"),
        },
    )
    _index_conversation_in_vector_store(
        conv_id=conv_id,
        messages_dicts=msg_dicts,
        platform=v1_payload.get("platform", "unknown"),
        started_at=v1_payload.get("timestamp", ""),
        project=v1_payload.get("project", ""),
        provider=v1_payload.get("provider", ""),
        model=v1_payload.get("model", ""),
        assistant_label=v1_payload.get("assistant_label", ""),
        importance=importance,
        summary=summary,
    )
    return conv_id


# ---------------------------------------------------------------------------
# V1 Data Migration
# ---------------------------------------------------------------------------

@router.post("/migrate/v1-to-v2")
async def migrate_v1_data():
    """Migrate V1 conversations table to V2 archive tables."""
    import sqlite3
    v1_db_path = str(DATA_DIR / "memory.db")

    # Open a separate read connection to the V1 tables
    v1_conn = sqlite3.connect(v1_db_path, check_same_thread=False)
    v1_conn.row_factory = sqlite3.Row

    # Check if V1 table exists
    cursor = v1_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
    )
    if not cursor.fetchone():
        v1_conn.close()
        return {"status": "skipped", "reason": "No V1 conversations table found"}

    result = db_v2.migrate_from_v1(v1_conn)
    v1_conn.close()

    return {"status": "ok", **result}


# ---------------------------------------------------------------------------
# Stats -- primary stats endpoint is in main.py (/api/v2/stats)
# Sync status available at /api/v2/sync/status
# ---------------------------------------------------------------------------
