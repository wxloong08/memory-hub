import asyncio
from datetime import datetime
from pathlib import Path
import json
import re
from typing import Dict, List, Optional
from hashlib import sha256

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai_analyzer import analyzer
from backup_export import (
    create_backup_bundle,
    list_backups,
    load_backup_settings,
    read_backup_manifest,
    restore_backup_source,
    run_scheduled_backup_if_due,
    save_backup_settings,
    validate_backup_source,
)
from client_exports import CLIENT_EXPORT_PROFILES, apply_export_package, build_export_package
from database import Database
from local_importer import import_sources
from vector_store import VectorStore

app = FastAPI(title="Claude Memory Hub")

# Mount V2 API router
try:
    from api_v2 import router as v2_router
    app.include_router(v2_router)
except ImportError:
    pass

# CORS for browser extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:8765",   # Self
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8765",
    ],
    allow_origin_regex=r"^chrome-extension://.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
AI_CONFIG_PATH = DATA_DIR / "ai_config.json"

# Initialize database and vector store
db = Database(str(DATA_DIR / "memory.db"))
vector_store = VectorStore(str(DATA_DIR / "vectors"))
backup_task: asyncio.Task | None = None


def _sync_existing_conversations_to_vector_store():
    """Backfill persisted conversations into the active vector collection."""
    # Sync V1 conversations
    cursor = db.conn.execute(
        """
        SELECT id, platform, timestamp, project, provider, model, assistant_label, summary, full_content, importance, status
        FROM conversations
        """
    )
    vector_store.sync_from_records([dict(row) for row in cursor.fetchall()])

    # Sync V2 archive_conversations (if table exists)
    try:
        v2_cursor = db.conn.execute(
            """
            SELECT id, platform, started_at as timestamp, '' as project,
                   provider, model, assistant_label, summary, importance
            FROM archive_conversations
            """
        )
        v2_rows = [dict(row) for row in v2_cursor.fetchall()]
        if v2_rows:
            # Reconstruct full_content from archive_messages for each V2 conversation
            for row in v2_rows:
                msg_cursor = db.conn.execute(
                    "SELECT role, content FROM archive_messages WHERE conversation_id = ? ORDER BY ordinal",
                    (row["id"],),
                )
                row["full_content"] = "\n\n".join(
                    f"{m['role']}: {m['content']}" for m in [dict(r) for r in msg_cursor.fetchall()]
                )
            vector_store.sync_from_records(v2_rows)
    except Exception:
        # Table may not exist yet on first startup
        pass


def _reload_runtime_state():
    global db, vector_store, db_v2
    try:
        db.conn.close()
    except Exception:
        pass

    db = Database(str(DATA_DIR / "memory.db"))
    vector_store = VectorStore(str(DATA_DIR / "vectors"))
    vector_store.reset()
    _sync_existing_conversations_to_vector_store()

    # Rebuild V2 database connection so V2 endpoints use the restored data
    try:
        old_v2 = db_v2
        try:
            old_v2.conn.close()
        except Exception:
            pass
        db_v2 = DatabaseV2(str(DATA_DIR / "memory.db"))
        from api_v2 import set_db_v2, set_vector_store_v2
        set_db_v2(db_v2)
        set_vector_store_v2(vector_store)
    except Exception:
        pass


_sync_existing_conversations_to_vector_store()


sync_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup_event():
    global backup_task, sync_task
    if backup_task is None or backup_task.done():
        backup_task = asyncio.create_task(_backup_scheduler_loop())

    # Start V2 periodic sync (every 5 minutes)
    try:
        from sync_scheduler import periodic_sync_loop
        from api_v2 import _persist_v2_callback
        if sync_task is None or sync_task.done():
            sync_task = asyncio.create_task(
                periodic_sync_loop(_persist_v2_callback, interval_seconds=300, limit_per_source=30)
            )
    except ImportError:
        pass


@app.on_event("shutdown")
async def shutdown_event():
    global backup_task, sync_task
    if backup_task is not None:
        backup_task.cancel()
        try:
            await backup_task
        except asyncio.CancelledError:
            pass
        backup_task = None

    if sync_task is not None:
        try:
            from sync_scheduler import stop_periodic_sync
            stop_periodic_sync()
        except ImportError:
            pass
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
        sync_task = None


async def _backup_scheduler_loop():
    while True:
        try:
            run_scheduled_backup_if_due(db.conn, DATA_DIR)
        except Exception as e:
            print(f"[backup_scheduler] Error: {e}")
        await asyncio.sleep(300)

class ConversationInput(BaseModel):
    platform: str
    timestamp: str
    messages: List[dict]
    working_dir: Optional[str] = None
    project: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    assistant_label: Optional[str] = None
    summary: Optional[str] = None


class ExportApplyInput(BaseModel):
    client: str
    workspace_path: str
    selected_memory_ids: Optional[List[int]] = None


class MemoryExportSimulationInput(BaseModel):
    client: str
    prompt: str
    project: Optional[str] = None
    selected_memory_ids: Optional[List[int]] = None


class MemoryTierInput(BaseModel):
    memory_tier: str


class PreferenceInput(BaseModel):
    category: str
    key: str
    value: str
    confidence: float = 0.7


class MemoryUpdateInput(BaseModel):
    category: str
    key: str
    value: str
    confidence: float = 0.7


class MemoryStatusInput(BaseModel):
    status: str


class MemoryPriorityInput(BaseModel):
    priority: int


class MemoryClientRulesInput(BaseModel):
    client_rules: Dict[str, str]


class MemoryMergeInput(BaseModel):
    left_id: int
    right_id: int
    delete_sources: bool = False


class MemoryConflictResolutionInput(BaseModel):
    left_id: int
    right_id: int
    action: str


class LocalImportInput(BaseModel):
    source: str = "all"
    limit: int = 20
    dry_run: bool = False
    auto_summarize: bool = True


class BackupSettingsInput(BaseModel):
    enabled: bool
    interval_hours: int = 24
    retention_count: int = 10
    backup_root: Optional[str] = None


class BackupRestoreInput(BaseModel):
    source_path: str


class ResummarizeInput(BaseModel):
    conversation_ids: List[str]
    force: bool = False


class ResummarizeUglyInput(BaseModel):
    limit: int = 20
    force: bool = False


def _clean_project_title(project: Optional[str]) -> str:
    """Normalize browser-provided conversation titles."""
    if not project:
        return ""

    cleaned = project.strip()
    cleaned = re.sub(r"\s*-\s*Claude.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*-\s*ChatGPT.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _looks_like_placeholder(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True

    lowered = stripped.lower()
    if lowered in {"new chat", "untitled", "no summary"}:
        return True

    # Short, title-like fragments should not override a better conversation title.
    if len(stripped) <= 18:
        if _contains_chinese(stripped):
            return False
        word_count = len([part for part in re.split(r"[\s/_-]+", stripped) if part])
        if word_count <= 3 and not re.search(r"[。！？!?，,:：；;]", stripped):
            return True

    return False


def _clean_summary_text(text: Optional[str]) -> str:
    """Normalize extracted summary text while preserving paragraph breaks."""
    if not text:
        return ""

    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _clean_message_for_summary(text: str) -> str:
    """Strip markdown-like scaffolding so summary previews focus on content."""
    cleaned = _clean_summary_text(text)
    if not cleaned:
        return ""

    cleaned = re.sub(r"<details>[\s\S]*?</details>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<summary>[\s\S]*?</summary>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^>\s*.*$", " ", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    cleaned = re.sub(r"#+\s*", " ", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\n+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _derive_summary(messages: List[dict], project: Optional[str], provided_summary: Optional[str] = None) -> str:
    """Prefer provider/export summary, else derive a short conversation overview."""
    cleaned_summary = _clean_summary_text(provided_summary)
    if cleaned_summary and not _looks_like_placeholder(cleaned_summary):
        return cleaned_summary[:2000]

    project_title = _clean_project_title(project)
    normalized_project = re.sub(r"\s+", " ", project_title).strip().lower()

    user_messages = [
        _clean_message_for_summary(msg.get("content") or "")
        for msg in messages
        if msg.get("role") == "user" and (msg.get("content") or "").strip()
    ]
    assistant_messages = [
        _clean_message_for_summary(msg.get("content") or "")
        for msg in messages
        if msg.get("role") == "assistant" and (msg.get("content") or "").strip()
    ]

    best_candidate = ""
    for candidate in user_messages:
        normalized = re.sub(r"\s+", " ", candidate).strip().lower()
        if normalized_project and normalized == normalized_project:
            continue
        if _looks_like_placeholder(candidate):
            continue
        best_candidate = candidate
        break

    if best_candidate:
        first_assistant = next(
            (
                candidate for candidate in assistant_messages
                if candidate and not _looks_like_placeholder(candidate)
            ),
            "",
        )
        topic = project_title if project_title and not _looks_like_placeholder(project_title) else best_candidate

        if first_assistant:
            if _contains_chinese(topic + first_assistant):
                return (
                    f"这段对话主要围绕“{topic[:80]}”展开。"
                    f"用户首先提出：{best_candidate[:120]}。"
                    f"助手随后主要给出：{first_assistant[:180]}"
                )[:500]

            return (
                f"This conversation focused on {topic[:100]}. "
                f"The user first asked: {best_candidate[:160]}. "
                f"The assistant mainly responded with: {first_assistant[:220]}"
            )[:500]

        if project_title and not _looks_like_placeholder(project_title):
            return (
                f"{project_title}\n\n{best_candidate[:280]}"
            )[:400]

        return best_candidate[:200]

    if project_title:
        return project_title[:200]

    return "No summary"


def _load_conversation_map(conversation_ids: List[str]) -> dict[str, dict]:
    """Load conversation records for search/related response enrichment."""
    ids = [conversation_id for conversation_id in conversation_ids if conversation_id]
    if not ids:
        return {}

    placeholders = ",".join("?" for _ in ids)
    cursor = db.conn.execute(
        f"""
        SELECT id, platform, timestamp, summary, full_content, importance, project, provider, model, assistant_label, status
        FROM conversations
        WHERE id IN ({placeholders})
        """,
        ids,
    )
    return {row["id"]: dict(row) for row in cursor.fetchall()}


def _transform_vector_result(result: dict, conversation_map: dict[str, dict]) -> dict:
    """Convert raw vector search output to the frontend contract."""
    conversation_id = result.get("id", "")
    db_row = conversation_map.get(conversation_id, {})
    metadata = result.get("metadata") or {}
    content = result.get("content", "") or ""
    distance = result.get("distance")

    similarity = 0
    if distance is not None:
        similarity = round(max(0.0, min(1.0, 1 - float(distance))), 3)

    return {
        "id": conversation_id,
        "platform": db_row.get("platform") or metadata.get("platform", "unknown"),
        "provider": db_row.get("provider") or metadata.get("provider") or "",
        "model": db_row.get("model") or metadata.get("model") or "",
        "assistant_label": db_row.get("assistant_label") or metadata.get("assistant_label") or "",
        "summary": db_row.get("summary") or metadata.get("summary") or content[:200],
        "timestamp": str(db_row.get("timestamp") or metadata.get("timestamp") or ""),
        "similarity": similarity,
        "content_preview": (db_row.get("full_content") or content)[:300],
    }


def _get_conversation_record(conversation_id: str) -> dict:
    cursor = db.conn.execute(
        "SELECT * FROM conversations WHERE id = ?",
        (conversation_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return dict(row)


def _get_pinned_memories(limit: int = 50) -> list[dict]:
    cursor = db.conn.execute(
        """
        SELECT id, category, key, value, confidence, priority, client_rules, status, last_updated
        FROM preferences
        WHERE coalesce(status, 'active') = 'active'
        ORDER BY
            priority DESC,
            CASE category
                WHEN 'identity' THEN 0
                WHEN 'preference' THEN 1
                WHEN 'workflow' THEN 2
                WHEN 'avoid' THEN 3
                ELSE 4
            END ASC,
            confidence DESC,
            last_updated DESC,
            id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return _attach_sources_to_memories([dict(row) for row in cursor.fetchall()])


def _search_memories(query: str, limit: int = 5) -> list[dict]:
    needle = f"%{str(query or '').strip().lower()}%"
    if needle == "%%":
        return []
    cursor = db.conn.execute(
        """
        SELECT id, category, key, value, confidence, priority, client_rules, status, last_updated
        FROM preferences
        WHERE
            coalesce(status, 'active') = 'active'
            AND (
            lower(coalesce(category, '')) LIKE ?
            OR lower(coalesce(key, '')) LIKE ?
            OR lower(coalesce(value, '')) LIKE ?
            )
        ORDER BY priority DESC, confidence DESC, last_updated DESC, id DESC
        LIMIT ?
        """,
        (needle, needle, needle, limit),
    )
    return _attach_sources_to_memories([dict(row) for row in cursor.fetchall()])


def _memory_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"\w+|[\u4e00-\u9fff]", str(text or "").lower(), flags=re.UNICODE)
        if token
    }


def _memory_signature(memory: dict) -> str:
    return " ".join([
        str(memory.get("category") or ""),
        str(memory.get("key") or ""),
        str(memory.get("value") or ""),
    ]).strip().lower()


def _memory_merge_suggestions(limit: int = 20) -> list[dict]:
    memories = _get_pinned_memories(limit=200)
    suggestions: list[dict] = []

    for left_index in range(len(memories)):
        left = memories[left_index]
        left_sig = _memory_signature(left)
        left_tokens = _memory_tokens(left_sig)
        if not left_sig:
            continue

        for right_index in range(left_index + 1, len(memories)):
            right = memories[right_index]
            if str(left.get("category") or "").strip().lower() != str(right.get("category") or "").strip().lower():
                continue

            right_sig = _memory_signature(right)
            right_tokens = _memory_tokens(right_sig)
            if not right_sig:
                continue

            overlap = len(left_tokens & right_tokens)
            shorter = min(len(left_tokens), len(right_tokens)) or 1
            overlap_ratio = overlap / shorter
            contains_relation = left_sig in right_sig or right_sig in left_sig
            same_key = str(left.get("key") or "").strip().lower() == str(right.get("key") or "").strip().lower()

            if not (contains_relation or overlap_ratio >= 0.66 or (same_key and overlap_ratio >= 0.45)):
                continue

            score = round(max(overlap_ratio, 0.95 if contains_relation else overlap_ratio), 3)
            suggestions.append({
                "score": score,
                "reason": "contains" if contains_relation else "overlap",
                "left": left,
                "right": right,
            })

    suggestions.sort(
        key=lambda item: (
            item["score"],
            float(item["left"].get("confidence") or 0.0) + float(item["right"].get("confidence") or 0.0),
        ),
        reverse=True,
    )
    return suggestions[:limit]


def _memory_conflict_suggestions(limit: int = 20) -> list[dict]:
    memories = _get_pinned_memories(limit=200)
    conflicts: list[dict] = []
    negative_markers = ("不喜欢", "避免", "不要", "别", "don't", "do not", "avoid", "dislike", "never")
    positive_markers = ("喜欢", "偏好", "习惯", "通常", "prefer", "like", "usually", "tend to")

    def polarity(text: str) -> str:
        lowered = str(text or "").strip().lower()
        if any(marker in lowered for marker in negative_markers):
            return "negative"
        if any(marker in lowered for marker in positive_markers):
            return "positive"
        return "neutral"

    for left_index in range(len(memories)):
        left = memories[left_index]
        left_sig = _memory_signature(left)
        left_tokens = _memory_tokens(left_sig)
        left_polarity = polarity(left.get("value") or "")
        if not left_sig or left_polarity == "neutral":
            continue

        for right_index in range(left_index + 1, len(memories)):
            right = memories[right_index]
            if str(left.get("category") or "").strip().lower() != str(right.get("category") or "").strip().lower():
                continue

            right_sig = _memory_signature(right)
            right_tokens = _memory_tokens(right_sig)
            right_polarity = polarity(right.get("value") or "")
            if not right_sig or right_polarity == "neutral" or left_polarity == right_polarity:
                continue

            same_key = str(left.get("key") or "").strip().lower() == str(right.get("key") or "").strip().lower()
            overlap = len(left_tokens & right_tokens)
            shorter = min(len(left_tokens), len(right_tokens)) or 1
            overlap_ratio = overlap / shorter

            if not (same_key or overlap_ratio >= 0.35):
                continue

            score = round(max(overlap_ratio, 0.92 if same_key else overlap_ratio), 3)
            conflicts.append({
                "score": score,
                "reason": "polarity_conflict",
                "left": left,
                "right": right,
            })

    conflicts.sort(
        key=lambda item: (
            item["score"],
            float(item["left"].get("effective_confidence") or item["left"].get("confidence") or 0.0)
            + float(item["right"].get("effective_confidence") or item["right"].get("confidence") or 0.0),
        ),
        reverse=True,
    )
    return conflicts[:limit]


def _memory_cleanup_suggestions(limit: int = 20) -> list[dict]:
    memories = _get_pinned_memories(limit=300)
    suggestions: list[dict] = []

    for memory in memories:
        usage_count = int(memory.get("usage_count") or 0)
        if usage_count > 0:
            continue

        reasons: list[str] = ["unused_in_exports"]
        if int(memory.get("source_count") or 0) <= 1:
            reasons.append("single_source_memory")
        if float(memory.get("effective_confidence") or memory.get("confidence") or 0.0) < 0.75:
            reasons.append("low_confidence_memory")

        suggestions.append({
            "score": round(1.0 - min(0.99, float(memory.get("effective_confidence") or memory.get("confidence") or 0.0)), 3),
            "memory": memory,
            "reasons": reasons,
        })

    suggestions.sort(
        key=lambda item: (
            len(item["reasons"]),
            item["score"],
            -(float(item["memory"].get("effective_confidence") or item["memory"].get("confidence") or 0.0)),
        ),
        reverse=True,
    )
    return suggestions[:limit]


def _get_memory_record(memory_id: int) -> dict:
    cursor = db.conn.execute(
        """
        SELECT id, category, key, value, confidence, priority, client_rules, status, last_updated
        FROM preferences
        WHERE id = ?
        """,
        (memory_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    return dict(row)


def _merge_memory_values(left_value: str, right_value: str) -> str:
    left_text = str(left_value or "").strip()
    right_text = str(right_value or "").strip()
    if not left_text:
        return right_text
    if not right_text:
        return left_text
    if left_text == right_text:
        return left_text
    if left_text in right_text:
        return right_text
    if right_text in left_text:
        return left_text
    return f"{left_text}\n{right_text}"


def _format_memory_context(memories: list[dict]) -> str:
    if not memories:
        return ""

    lines = []
    for memory in memories:
        category = str(memory.get("category") or "general").strip() or "general"
        key = str(memory.get("key") or category).strip() or category
        value = str(memory.get("value") or "").strip()
        if value:
            lines.append(f"- [{category}] {key}: {value}")
    return "\n".join(lines)


def _get_memory_sources_map(memory_ids: list[int]) -> dict[int, list[dict]]:
    ids = [int(memory_id) for memory_id in memory_ids if memory_id]
    if not ids:
        return {}

    placeholders = ",".join("?" for _ in ids)
    cursor = db.conn.execute(
        f"""
        SELECT
            ps.memory_id,
            ps.conversation_id,
            c.platform,
            c.timestamp,
            c.summary,
            c.project
        FROM preference_sources ps
        LEFT JOIN conversations c ON c.id = ps.conversation_id
        WHERE ps.memory_id IN ({placeholders})
        ORDER BY c.timestamp DESC, ps.id DESC
        """,
        ids,
    )

    result: dict[int, list[dict]] = {}
    for row in cursor.fetchall():
        memory_id = int(row["memory_id"])
        result.setdefault(memory_id, []).append({
            "conversation_id": row["conversation_id"],
            "platform": row["platform"] or "",
            "timestamp": row["timestamp"] or "",
            "summary": row["summary"] or "",
            "project": row["project"] or "",
        })
    return result


def _get_memory_lineage_map(memory_ids: list[int]) -> dict[int, list[dict]]:
    ids = [int(memory_id) for memory_id in memory_ids if memory_id]
    if not ids:
        return {}

    placeholders = ",".join("?" for _ in ids)
    cursor = db.conn.execute(
        f"""
        SELECT
            pl.child_memory_id,
            pl.parent_memory_id,
            pl.relation_type,
            pl.created_at,
            p.category,
            p.key,
            p.value,
            p.confidence,
            p.status,
            p.last_updated
        FROM preference_lineage pl
        LEFT JOIN preferences p ON p.id = pl.parent_memory_id
        WHERE pl.child_memory_id IN ({placeholders})
        ORDER BY pl.id DESC
        """,
        ids,
    )

    result: dict[int, list[dict]] = {}
    for row in cursor.fetchall():
        child_memory_id = int(row["child_memory_id"])
        result.setdefault(child_memory_id, []).append({
            "memory_id": row["parent_memory_id"],
            "relation_type": row["relation_type"] or "merged",
            "created_at": row["created_at"] or "",
            "category": row["category"] or "",
            "key": row["key"] or "",
            "value": row["value"] or "",
            "confidence": row["confidence"] if row["confidence"] is not None else None,
            "status": row["status"] or "active",
            "last_updated": row["last_updated"] or "",
        })
    return result


def _get_memory_usage_map(memory_ids: list[int]) -> dict[int, dict]:
    ids = [int(memory_id) for memory_id in memory_ids if memory_id]
    if not ids:
        return {}

    placeholders = ",".join("?" for _ in ids)
    summary_cursor = db.conn.execute(
        f"""
        SELECT
            memory_id,
            COUNT(*) AS usage_count,
            MAX(used_at) AS last_used_at
        FROM preference_usage
        WHERE memory_id IN ({placeholders})
        GROUP BY memory_id
        """,
        ids,
    )
    client_cursor = db.conn.execute(
        f"""
        SELECT
            memory_id,
            client_id,
            COUNT(*) AS usage_count
        FROM preference_usage
        WHERE memory_id IN ({placeholders})
        GROUP BY memory_id, client_id
        ORDER BY usage_count DESC, client_id ASC
        """,
        ids,
    )

    result: dict[int, dict] = {}
    for row in summary_cursor.fetchall():
        result[int(row["memory_id"])] = {
            "usage_count": int(row["usage_count"] or 0),
            "last_used_at": row["last_used_at"] or "",
            "client_counts": [],
        }

    for row in client_cursor.fetchall():
        memory_id = int(row["memory_id"])
        result.setdefault(memory_id, {
            "usage_count": 0,
            "last_used_at": "",
            "client_counts": [],
        })
        result[memory_id]["client_counts"].append({
            "client_id": row["client_id"] or "",
            "count": int(row["usage_count"] or 0),
        })

    return result


def _compute_effective_confidence(confidence: float | int | None, source_count: int) -> float:
    base = max(0.0, min(1.0, float(confidence or 0.0)))
    support_bonus = min(0.24, max(0, source_count - 1) * 0.06)
    return round(min(0.99, base + support_bonus), 3)


def _normalize_client_rules(raw_rules) -> dict[str, str]:
    if isinstance(raw_rules, dict):
        candidate = raw_rules
    else:
        try:
            candidate = json.loads(str(raw_rules or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            candidate = {}

    normalized: dict[str, str] = {}
    for client_id, rule in dict(candidate or {}).items():
        client_key = str(client_id or "").strip().lower()
        rule_value = str(rule or "").strip().lower()
        if client_key and rule_value in {"default", "include", "exclude"}:
            normalized[client_key] = rule_value
    return normalized


def _serialize_client_rules(raw_rules) -> str:
    return json.dumps(_normalize_client_rules(raw_rules), ensure_ascii=False, sort_keys=True)


def _upsert_preference_exact(
    *,
    category: str,
    key: str,
    value: str,
    confidence: float,
    priority: int,
    client_rules_json: str,
    status: str,
) -> tuple[int, bool]:
    # Check for existing record with same semantic identity (category+key+value)
    row = db.conn.execute(
        """
        SELECT id
        FROM preferences
        WHERE
            COALESCE(category, '') = COALESCE(?, '')
            AND COALESCE(key, '') = COALESCE(?, '')
            AND COALESCE(value, '') = COALESCE(?, '')
        ORDER BY id ASC
        LIMIT 1
        """,
        (category, key, value),
    ).fetchone()

    if row:
        # Update mutable fields on existing record
        memory_id = int(row["id"])
        db.conn.execute(
            """
            UPDATE preferences
            SET confidence = MAX(confidence, ?),
                priority = MAX(priority, ?),
                client_rules = ?,
                last_updated = ?
            WHERE id = ?
            """,
            (confidence, priority, client_rules_json, datetime.now().isoformat(), memory_id),
        )
        return memory_id, False

    # Insert new record
    cursor = db.conn.execute(
        """
        INSERT INTO preferences (category, key, value, confidence, priority, client_rules, status, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (category, key, value, confidence, priority, client_rules_json, status, datetime.now().isoformat()),
    )
    return cursor.lastrowid, True


def _build_memory_timeline(memory: dict, sources: list[dict], parent_memories: list[dict]) -> list[dict]:
    timeline: list[dict] = []
    last_updated = str(memory.get("last_updated") or "").strip()
    if last_updated:
        timeline.append({
            "type": "memory_updated",
            "timestamp": last_updated,
            "label": "memoryUpdated",
            "description": str(memory.get("value") or "")[:180],
        })

    for source in sources:
        source_timestamp = str(source.get("timestamp") or "").strip()
        timeline.append({
            "type": "source_conversation",
            "timestamp": source_timestamp,
            "label": "sourceConversation",
            "conversation_id": source.get("conversation_id") or "",
            "description": source.get("project") or source.get("summary") or source.get("conversation_id") or "",
        })

    for parent in parent_memories:
        parent_timestamp = str(parent.get("created_at") or parent.get("last_updated") or "").strip()
        timeline.append({
            "type": "merged_from_memory",
            "timestamp": parent_timestamp,
            "label": "mergedFromMemory",
            "memory_id": parent.get("memory_id"),
            "description": parent.get("value") or parent.get("key") or "",
        })

    timeline.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return timeline


def _attach_sources_to_memories(memories: list[dict]) -> list[dict]:
    sources_map = _get_memory_sources_map([memory.get("id") for memory in memories])
    lineage_map = _get_memory_lineage_map([memory.get("id") for memory in memories])
    usage_map = _get_memory_usage_map([memory.get("id") for memory in memories])
    enriched = []
    for memory in memories:
        memory_id = int(memory.get("id"))
        sources = sources_map.get(memory_id, [])
        parent_memories = lineage_map.get(memory_id, [])
        source_count = len(sources)
        usage = usage_map.get(memory_id, {})
        enriched.append({
            **memory,
            "sources": sources,
            "parent_memories": parent_memories,
            "parent_memory_count": len(parent_memories),
            "source_count": source_count,
            "priority": int(memory.get("priority") or 0),
            "client_rules": _normalize_client_rules(memory.get("client_rules")),
            "usage_count": int(usage.get("usage_count") or 0),
            "last_used_at": usage.get("last_used_at") or "",
            "client_usage": usage.get("client_counts") or [],
            "effective_confidence": _compute_effective_confidence(memory.get("confidence"), source_count),
            "timeline": _build_memory_timeline(memory, sources, parent_memories),
        })
    return enriched


def _get_memories_for_conversation(conversation_id: str) -> list[dict]:
    cursor = db.conn.execute(
        """
        SELECT DISTINCT
            p.id,
            p.category,
            p.key,
            p.value,
            p.confidence,
            p.last_updated
        FROM preference_sources ps
        INNER JOIN preferences p ON p.id = ps.memory_id
        WHERE ps.conversation_id = ?
        ORDER BY p.confidence DESC, p.last_updated DESC, p.id DESC
        """,
        (conversation_id,),
    )
    memories = [dict(row) for row in cursor.fetchall()]
    return _attach_sources_to_memories(memories)


def _persist_conversation_payload(payload: dict) -> str:
    full_content = "\n\n".join([
        f"{msg['role']}: {msg['content']}"
        for msg in payload["messages"]
    ])
    content_hash = payload.get("content_hash") or sha256(full_content.encode("utf-8")).hexdigest()
    timestamp = datetime.fromisoformat(payload["timestamp"])

    existing_id = db.find_existing_conversation(
        platform=payload["platform"],
        timestamp=timestamp,
        content_hash=content_hash,
        source_path=payload.get("source_path"),
        source_fingerprint=payload.get("source_fingerprint"),
    )
    if existing_id:
        return existing_id

    provided_summary = payload.get("summary")
    summary = _derive_summary(payload["messages"], payload.get("project"), provided_summary)
    summary_source = "imported" if provided_summary and str(provided_summary).strip() and summary == _clean_summary_text(provided_summary)[:2000] else "fallback"
    importance = min(10, 5 + len(payload["messages"]) // 4)

    conv_id = db.add_conversation(
        platform=payload["platform"],
        timestamp=timestamp,
        full_content=full_content,
        project=payload.get("project"),
        working_dir=payload.get("working_dir"),
        provider=payload.get("provider"),
        model=payload.get("model"),
        assistant_label=payload.get("assistant_label"),
        source_path=payload.get("source_path"),
        source_fingerprint=payload.get("source_fingerprint"),
        content_hash=content_hash,
        recovery_mode=payload.get("recovery_mode"),
        memory_tier=payload.get("memory_tier"),
        summary_source=summary_source,
        summary=summary,
        importance=importance,
    )

    vector_store.add_conversation(
        conv_id=conv_id,
        content=full_content,
        metadata={
            "platform": payload["platform"],
            "timestamp": payload["timestamp"],
            "project": payload.get("project") or "",
            "provider": payload.get("provider") or "",
            "model": payload.get("model") or "",
            "assistant_label": payload.get("assistant_label") or "",
            "importance": importance,
            "summary": summary,
        },
    )

    return conv_id


def _summary_needs_upgrade(summary: Optional[str], project: Optional[str] = None) -> bool:
    text = str(summary or "").strip()
    project_text = str(project or "").strip()
    if not text:
        return True
    if _looks_like_placeholder(text):
        return True
    if project_text and text == project_text:
        return True
    if re.fullmatch(r"[0-9a-f]{8,}", text.lower()):
        return True
    if re.fullmatch(r"[0-9a-f-]{16,}", text.lower()):
        return True
    if re.match(r"^(rollout|agent)-[a-z0-9-]{12,}$", text.lower()):
        return True
    return False


def _update_conversation_summary(conversation_id: str, summary: str) -> None:
    db.conn.execute(
        "UPDATE conversations SET summary = ?, summary_source = ? WHERE id = ?",
        (summary, "ai", conversation_id),
    )
    db.conn.commit()
    _sync_existing_conversations_to_vector_store()

@app.post("/api/conversations")
async def add_conversation(conv: ConversationInput):
    """Receive and store a new conversation"""
    conv_id = _persist_conversation_payload(conv.model_dump())

    return {"status": "ok", "conversation_id": conv_id}

@app.get("/api/context")
async def get_context(
    hours: int = 24,
    working_dir: Optional[str] = None,
    min_importance: int = 7
):
    """Get context summary for recent conversations"""

    conversations = db.get_recent_conversations(
        hours=hours,
        min_importance=min_importance,
        working_dir=working_dir
    )

    pinned_memories = _get_pinned_memories(limit=20)

    if not conversations and not pinned_memories:
        return {"context": "No recent conversations found."}

    # Generate markdown context
    context_lines = ["# Auto-Generated Context", ""]
    context_lines.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    context_lines.append("")
    context_lines.append("## Recent Activity")
    context_lines.append("")

    for conv in conversations[:5]:  # Top 5 most important
        context_lines.append(f"### {conv['platform']} - {conv['timestamp']}")
        context_lines.append(f"**Summary**: {conv['summary']}")
        context_lines.append(f"**Importance**: {conv['importance']}/10")
        if conv['working_dir']:
            context_lines.append(f"**Location**: {conv['working_dir']}")
        context_lines.append("")

    if pinned_memories:
        context_lines.append("## Pinned Memory")
        context_lines.append("")
        for memory in pinned_memories[:12]:
            category = str(memory.get("category") or "general").strip() or "general"
            key = str(memory.get("key") or category).strip() or category
            value = str(memory.get("value") or "").strip()
            if value:
                context_lines.append(f"- [{category}] {key}: {value}")
        context_lines.append("")

    context = "\n".join(context_lines)

    if analyzer.is_ai_available() and conversations:
        try:
            ai_context = await analyzer.generate_context_injection([
                {
                    "platform": conv.get("platform"),
                    "timestamp": conv.get("timestamp"),
                    "summary": conv.get("summary"),
                    "importance": conv.get("importance"),
                }
                for conv in conversations[:10]
            ], pinned_memories=pinned_memories[:12])
            if ai_context:
                context = f"# AI-Synthesized Context\n\n{ai_context}\n\n---\n\n{context}"
        except Exception as e:
            print(f"[ai_context] Generation failed: {e}")

    return {"context": context}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/api/search")
async def search_conversations(query: str, limit: int = 5):
    """Semantic search for conversations - returns frontend-friendly format"""
    raw_results = vector_store.search(query, top_k=limit)
    conversation_map = _load_conversation_map([item.get("id", "") for item in raw_results])
    results = [_transform_vector_result(item, conversation_map) for item in raw_results]
    memory_results = _search_memories(query, limit=min(limit, 5))

    return {
        "query": query,
        "results": results,
        "memory_results": memory_results,
        "count": len(results),
        "memory_count": len(memory_results),
    }

@app.get("/api/related/{conversation_id}")
async def get_related_conversations(conversation_id: str, limit: int = 3):
    """Get related conversations - returns frontend-friendly format"""
    raw_related = vector_store.find_related_conversations(conversation_id, top_k=limit)
    conversation_map = _load_conversation_map([item.get("id", "") for item in raw_related])
    related = [_transform_vector_result(item, conversation_map) for item in raw_related]

    return {
        "conversation_id": conversation_id,
        "related": related,
        "count": len(related),
    }

@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    # Database stats
    import sqlite3
    conn = sqlite3.connect(str(DATA_DIR / "memory.db"))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM conversations")
    total_conversations = cursor.fetchone()[0]

    cursor.execute("""
        SELECT platform, COUNT(*) as count, AVG(importance) as avg_importance
        FROM conversations
        GROUP BY platform
    """)
    by_platform = [
        {"platform": row[0], "count": row[1], "avg_importance": round(row[2], 1)}
        for row in cursor.fetchall()
    ]

    conn.close()

    # Vector store stats
    vector_stats = vector_store.get_stats()

    return {
        "database": {
            "total_conversations": total_conversations,
            "by_platform": by_platform
        },
        "vector_store": vector_stats
    }


@app.get("/api/conversations/list")
async def list_conversations(
    hours: int = 24 * 365 * 20,
    min_importance: int = 1,
    platform: str = None,
    model: str = None,
    summary_source: str = None,
    recovery_mode: str = None,
    memory_tier: str = None,
    q: str = None,
    sort: str = "newest",
    limit: int = 50,
    offset: int = 0,
):
    """List conversations as structured JSON for Web UI."""
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")
    if sort not in {"newest", "oldest", "importance", "ai_summary"}:
        raise HTTPException(status_code=400, detail="invalid sort")

    conversations, total = db.get_recent_conversations_page(
        hours=hours,
        min_importance=min_importance,
        working_dir=None,
        platform=platform,
        model_or_provider=model,
        summary_source=summary_source,
        recovery_mode=recovery_mode,
        memory_tier=memory_tier,
        query_text=q,
        sort=sort,
        limit=limit,
        offset=offset,
    )

    results = []
    for conv in conversations:
        results.append({
            'id': conv.get('id', ''),
            'platform': conv.get('platform', 'unknown'),
            'provider': conv.get('provider', ''),
            'model': conv.get('model', ''),
            'assistant_label': conv.get('assistant_label', ''),
            'timestamp': conv.get('timestamp', ''),
            'summary': conv.get('summary', ''),
            'importance': conv.get('importance', 5),
            'project': conv.get('project', None),
            'status': conv.get('status', 'completed'),
            'summary_source': conv.get('summary_source', ''),
            'recovery_mode': conv.get('recovery_mode', ''),
            'memory_tier': conv.get('memory_tier', 'temporary'),
        })

    return {
        'conversations': results,
        'total': total,
        'limit': limit,
        'offset': offset,
        'has_more': offset + len(results) < total,
    }


@app.get("/api/conversations/filters")
async def list_conversation_filters():
    """Return stable filter options for the conversation list UI."""
    return db.get_conversation_filter_values()


@app.get("/api/memories")
async def list_memories():
    cursor = db.conn.execute(
        """
        SELECT id, category, key, value, confidence, priority, client_rules, status, last_updated
        FROM preferences
        ORDER BY
            CASE coalesce(status, 'active')
                WHEN 'active' THEN 0
                ELSE 1
            END ASC,
            priority DESC,
            confidence DESC, last_updated DESC, id DESC
        """
    )
    memories = [dict(row) for row in cursor.fetchall()]
    return {"memories": _attach_sources_to_memories(memories)}


@app.get("/api/memories/suggestions")
async def list_memory_merge_suggestions(limit: int = 20):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return {
        "suggestions": _memory_merge_suggestions(limit=limit),
        "count": len(_memory_merge_suggestions(limit=limit)),
    }


@app.get("/api/memories/conflicts")
async def list_memory_conflicts(limit: int = 20):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    conflicts = _memory_conflict_suggestions(limit=limit)
    return {
        "conflicts": conflicts,
        "count": len(conflicts),
    }


@app.get("/api/memories/cleanup-suggestions")
async def list_memory_cleanup_suggestions(limit: int = 20):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    suggestions = _memory_cleanup_suggestions(limit=limit)
    return {
        "suggestions": suggestions,
        "count": len(suggestions),
    }


@app.post("/api/memories/conflicts/resolve")
async def resolve_memory_conflict(payload: MemoryConflictResolutionInput):
    if payload.left_id == payload.right_id:
        raise HTTPException(status_code=400, detail="left_id and right_id must be different")

    action = str(payload.action or "").strip().lower()
    if action not in {"keep_left", "keep_right", "merge_new"}:
        raise HTTPException(status_code=400, detail="action must be keep_left, keep_right, or merge_new")

    left = _get_memory_record(payload.left_id)
    right = _get_memory_record(payload.right_id)

    if action == "merge_new":
        category = str(left.get("category") or right.get("category") or "general").strip() or "general"
        key = str(left.get("key") or right.get("key") or category).strip() or category
        merged_value = _merge_memory_values(left.get("value"), right.get("value"))
        merged_confidence = max(float(left.get("confidence") or 0.0), float(right.get("confidence") or 0.0))
        merged_rules = _normalize_client_rules(left.get("client_rules"))
        for client_id, rule in _normalize_client_rules(right.get("client_rules")).items():
            if merged_rules.get(client_id) == "include" or rule == "include":
                merged_rules[client_id] = "include"
            elif merged_rules.get(client_id) != "include":
                merged_rules[client_id] = rule

        merged_priority = max(int(left.get("priority") or 0), int(right.get("priority") or 0))
        merged_memory_id, _ = _upsert_preference_exact(
            category=category,
            key=key,
            value=merged_value[:1000],
            confidence=merged_confidence,
            priority=merged_priority,
            client_rules_json=_serialize_client_rules(merged_rules),
            status="active",
        )

        source_rows = db.conn.execute(
            """
            SELECT DISTINCT conversation_id
            FROM preference_sources
            WHERE memory_id IN (?, ?)
            """,
            (payload.left_id, payload.right_id),
        ).fetchall()

        for row in source_rows:
            if row["conversation_id"]:
                db.conn.execute(
                    """
                    INSERT OR IGNORE INTO preference_sources (memory_id, conversation_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (merged_memory_id, row["conversation_id"], datetime.now().isoformat()),
                )

        for parent_id in (payload.left_id, payload.right_id):
            if int(parent_id) == merged_memory_id:
                continue
            db.conn.execute(
                """
                INSERT OR IGNORE INTO preference_lineage (child_memory_id, parent_memory_id, relation_type, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (merged_memory_id, parent_id, "merged", datetime.now().isoformat()),
            )

        db.conn.commit()
        return {
            "status": "ok",
            "action": action,
            "kept_memory_id": None,
            "deleted_memory_id": None,
            "merged_memory_id": merged_memory_id,
        }

    kept_id = payload.left_id if action == "keep_left" else payload.right_id
    deleted_id = payload.right_id if action == "keep_left" else payload.left_id

    db.conn.execute("DELETE FROM preference_lineage WHERE child_memory_id = ? OR parent_memory_id = ?", (deleted_id, deleted_id))
    db.conn.execute("DELETE FROM preference_usage WHERE memory_id = ?", (deleted_id,))
    db.conn.execute("DELETE FROM preference_sources WHERE memory_id = ?", (deleted_id,))
    cursor = db.conn.execute("DELETE FROM preferences WHERE id = ?", (deleted_id,))
    db.conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {
        "status": "ok",
        "action": action,
        "kept_memory_id": kept_id,
        "deleted_memory_id": deleted_id,
        "merged_memory_id": None,
    }


@app.post("/api/memories")
async def create_memory(payload: PreferenceInput):
    category = str(payload.category or "").strip() or "general"
    key = str(payload.key or "").strip()
    value = str(payload.value or "").strip()
    confidence = max(0.0, min(1.0, float(payload.confidence)))

    if not key or not value:
        raise HTTPException(status_code=400, detail="key and value are required")
    if len(key) > 500:
        raise HTTPException(status_code=400, detail="key must be <= 500 characters")
    if len(value) > 5000:
        raise HTTPException(status_code=400, detail="value must be <= 5000 characters")

    memory_id, _ = _upsert_preference_exact(
        category=category,
        key=key,
        value=value,
        confidence=confidence,
        priority=0,
        client_rules_json=_serialize_client_rules({}),
        status="active",
    )
    db.conn.commit()
    return {"status": "ok", "memory_id": memory_id}


@app.post("/api/memories/{memory_id:int}")
async def update_memory(memory_id: int, payload: MemoryUpdateInput):
    _get_memory_record(memory_id)
    category = str(payload.category or "").strip() or "general"
    key = str(payload.key or "").strip()
    value = str(payload.value or "").strip()
    confidence = max(0.0, min(1.0, float(payload.confidence)))

    if not key or not value:
        raise HTTPException(status_code=400, detail="key and value are required")

    # Check if another record with the same semantic identity already exists
    existing = db.conn.execute(
        """
        SELECT id FROM preferences
        WHERE COALESCE(category, '') = ? AND COALESCE(key, '') = ?
          AND COALESCE(value, '') = ?
          AND id != ?
        LIMIT 1
        """,
        (category, key, value, memory_id),
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A memory with the same category/key/value already exists (id={existing['id']})",
        )

    cursor = db.conn.execute(
        """
        UPDATE preferences
        SET category = ?, key = ?, value = ?, confidence = ?, last_updated = ?
        WHERE id = ?
        """,
        (category, key, value, confidence, datetime.now().isoformat(), memory_id),
    )
    db.conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"status": "ok", "memory_id": memory_id, "updated": True}


@app.post("/api/memories/{memory_id:int}/status")
async def update_memory_status(memory_id: int, payload: MemoryStatusInput):
    _get_memory_record(memory_id)
    memory_status = str(payload.status or "").strip().lower()
    if memory_status not in {"active", "archived"}:
        raise HTTPException(status_code=400, detail="status must be active or archived")

    cursor = db.conn.execute(
        """
        UPDATE preferences
        SET status = ?, last_updated = ?
        WHERE id = ?
        """,
        (memory_status, datetime.now().isoformat(), memory_id),
    )
    db.conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"status": "ok", "memory_id": memory_id, "memory_status": memory_status}


@app.post("/api/memories/{memory_id:int}/priority")
async def update_memory_priority(memory_id: int, payload: MemoryPriorityInput):
    _get_memory_record(memory_id)
    priority = max(0, min(100, int(payload.priority)))

    cursor = db.conn.execute(
        """
        UPDATE preferences
        SET priority = ?, last_updated = ?
        WHERE id = ?
        """,
        (priority, datetime.now().isoformat(), memory_id),
    )
    db.conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"status": "ok", "memory_id": memory_id, "priority": priority}


@app.post("/api/memories/{memory_id:int}/client-rules")
async def update_memory_client_rules(memory_id: int, payload: MemoryClientRulesInput):
    _get_memory_record(memory_id)
    normalized_rules = _normalize_client_rules(payload.client_rules)

    cursor = db.conn.execute(
        """
        UPDATE preferences
        SET client_rules = ?, last_updated = ?
        WHERE id = ?
        """,
        (json.dumps(normalized_rules, ensure_ascii=False), datetime.now().isoformat(), memory_id),
    )
    db.conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"status": "ok", "memory_id": memory_id, "client_rules": normalized_rules}


@app.post("/api/memories/merge")
async def merge_memories(payload: MemoryMergeInput):
    if payload.left_id == payload.right_id:
        raise HTTPException(status_code=400, detail="left_id and right_id must be different")

    left = _get_memory_record(payload.left_id)
    right = _get_memory_record(payload.right_id)

    category = str(left.get("category") or right.get("category") or "general").strip() or "general"
    key = str(left.get("key") or right.get("key") or category).strip() or category
    merged_value = _merge_memory_values(left.get("value"), right.get("value"))
    merged_confidence = max(float(left.get("confidence") or 0.0), float(right.get("confidence") or 0.0))
    merged_priority = max(int(left.get("priority") or 0), int(right.get("priority") or 0))
    merged_rules = _normalize_client_rules(left.get("client_rules"))
    for client_id, rule in _normalize_client_rules(right.get("client_rules")).items():
        if merged_rules.get(client_id) == "include" or rule == "include":
            merged_rules[client_id] = "include"
        elif merged_rules.get(client_id) != "include":
            merged_rules[client_id] = rule

    merged_memory_id, _ = _upsert_preference_exact(
        category=category,
        key=key,
        value=merged_value[:1000],
        confidence=merged_confidence,
        priority=merged_priority,
        client_rules_json=_serialize_client_rules(merged_rules),
        status="active",
    )
    source_rows = db.conn.execute(
        """
        SELECT DISTINCT conversation_id
        FROM preference_sources
        WHERE memory_id IN (?, ?)
        """,
        (payload.left_id, payload.right_id),
    ).fetchall()

    for row in source_rows:
        if row["conversation_id"]:
            db.conn.execute(
                """
                INSERT OR IGNORE INTO preference_sources (memory_id, conversation_id, created_at)
                VALUES (?, ?, ?)
                """,
                (merged_memory_id, row["conversation_id"], datetime.now().isoformat()),
            )

    for parent_id in (payload.left_id, payload.right_id):
        if int(parent_id) == merged_memory_id:
            continue
        db.conn.execute(
            """
            INSERT OR IGNORE INTO preference_lineage (child_memory_id, parent_memory_id, relation_type, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (merged_memory_id, parent_id, "merged", datetime.now().isoformat()),
        )

    deleted_source_ids: list[int] = []
    if payload.delete_sources:
        candidates = [payload.left_id, payload.right_id]
        delete_ids = [memory_id for memory_id in candidates if int(memory_id) != merged_memory_id]
        if delete_ids:
            placeholders = ",".join("?" for _ in delete_ids)
            db.conn.execute(
                f"DELETE FROM preference_lineage WHERE child_memory_id IN ({placeholders}) OR parent_memory_id IN ({placeholders})",
                (*delete_ids, *delete_ids),
            )
            db.conn.execute(
                f"DELETE FROM preference_usage WHERE memory_id IN ({placeholders})",
                tuple(delete_ids),
            )
            db.conn.execute(
                f"DELETE FROM preference_sources WHERE memory_id IN ({placeholders})",
                tuple(delete_ids),
            )
            db.conn.execute(
                f"DELETE FROM preferences WHERE id IN ({placeholders})",
                tuple(delete_ids),
            )
            deleted_source_ids = delete_ids
    db.conn.commit()

    return {
        "status": "ok",
        "merged_memory_id": merged_memory_id,
        "source_ids": [payload.left_id, payload.right_id],
        "deleted_source_ids": deleted_source_ids,
        "memory": {
            "id": merged_memory_id,
            "category": category,
            "key": key,
            "value": merged_value[:1000],
            "confidence": merged_confidence,
            "priority": merged_priority,
            "client_rules": merged_rules,
        },
    }


@app.delete("/api/memories/{memory_id:int}")
async def delete_memory(memory_id: int):
    db.conn.execute("DELETE FROM preference_lineage WHERE child_memory_id = ? OR parent_memory_id = ?", (memory_id, memory_id))
    db.conn.execute("DELETE FROM preference_usage WHERE memory_id = ?", (memory_id,))
    db.conn.execute("DELETE FROM preference_sources WHERE memory_id = ?", (memory_id,))
    cursor = db.conn.execute("DELETE FROM preferences WHERE id = ?", (memory_id,))
    db.conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "ok", "memory_id": memory_id, "deleted": True}


@app.post("/api/memories/extract/{conversation_id}")
async def extract_memories_from_conversation(conversation_id: str):
    record = _get_conversation_record(conversation_id)
    content = str(record.get("full_content") or "")

    patterns = [
        (r"(我喜欢[^。\n]{0,120})", "preference"),
        (r"(我偏好[^。\n]{0,120})", "preference"),
        (r"(我倾向于[^。\n]{0,120})", "workflow"),
        (r"(我不喜欢[^。\n]{0,120})", "avoid"),
        (r"(避免[^。\n]{0,120})", "avoid"),
        (r"(我通常[^。\n]{0,120})", "workflow"),
        (r"(我习惯[^。\n]{0,120})", "workflow"),
    ]

    inserted = []
    seen = set()
    for pattern, category in patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            statement = match.group(1).strip("：: ,-")
            normalized = statement.lower()
            if len(statement) < 4 or normalized in seen:
                continue
            seen.add(normalized)
            memory_id, memory_inserted = _upsert_preference_exact(
                category=category,
                key=category,
                value=statement[:300],
                confidence=0.72,
                priority=0,
                client_rules_json=_serialize_client_rules({}),
                status="active",
            )
            source_changes_before = db.conn.total_changes
            db.conn.execute(
                """
                INSERT OR IGNORE INTO preference_sources (memory_id, conversation_id, created_at)
                VALUES (?, ?, ?)
                """,
                (memory_id, conversation_id, datetime.now().isoformat()),
            )
            source_inserted = db.conn.total_changes > source_changes_before
            if memory_inserted or source_inserted:
                inserted.append({
                    "id": memory_id,
                    "category": category,
                    "key": category,
                    "value": statement[:300],
                    "confidence": 0.72,
                })
            if len(inserted) >= 12:
                break
        if len(inserted) >= 12:
            break

    db.conn.commit()
    return {
        "conversation_id": conversation_id,
        "inserted_count": len(inserted),
        "memories": inserted,
    }


@app.get("/api/conversations/{conversation_id}/memories")
async def list_conversation_memories(conversation_id: str):
    _get_conversation_record(conversation_id)
    memories = _get_memories_for_conversation(conversation_id)
    return {
        "conversation_id": conversation_id,
        "memories": memories,
        "count": len(memories),
    }


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a single conversation by ID with full content."""
    return _get_conversation_record(conversation_id)


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete one conversation from the database and vector store."""
    _get_conversation_record(conversation_id)
    deleted = db.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")

    vector_store.delete_conversation(conversation_id)
    return {
        "status": "ok",
        "conversation_id": conversation_id,
        "deleted": True,
    }


@app.post("/api/conversations/{conversation_id}/memory-tier")
async def update_conversation_memory_tier(conversation_id: str, payload: MemoryTierInput):
    """Update one conversation's memory tier."""
    memory_tier = str(payload.memory_tier or "").strip().lower()
    if memory_tier not in {"temporary", "saved", "pinned"}:
        raise HTTPException(status_code=400, detail="invalid memory_tier")

    _get_conversation_record(conversation_id)
    updated = db.update_memory_tier(conversation_id, memory_tier)
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "status": "ok",
        "conversation_id": conversation_id,
        "memory_tier": memory_tier,
    }


@app.get("/api/export/clients")
async def list_export_clients():
    """List supported local client export targets."""
    return {
        "clients": [
            {
                "client": profile.client_id,
                "display_name": profile.display_name,
                "target_relpath": profile.target_relpath,
                "filename": profile.filename,
                "format_hint": profile.format_hint,
                "description": profile.description,
            }
            for profile in CLIENT_EXPORT_PROFILES.values()
        ]
    }


@app.post("/api/memories/export-simulate")
async def simulate_memory_export(payload: MemoryExportSimulationInput):
    prompt = str(payload.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    synthetic_conversation = {
        "id": "memory-export-simulator",
        "platform": "memory_hub",
        "timestamp": datetime.now().isoformat(),
        "project": str(payload.project or "").strip(),
        "provider": "",
        "model": "",
        "assistant_label": "Memory Simulator",
        "summary": prompt[:280],
        "full_content": f"user: {prompt}",
    }

    try:
        result = build_export_package(
            synthetic_conversation,
            payload.client,
            _get_pinned_memories(),
            payload.selected_memory_ids or [],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        **result,
        "simulation": {
            "project": synthetic_conversation["project"],
            "prompt": prompt,
        },
    }


@app.get("/api/conversations/{conversation_id}/export")
async def export_conversation(conversation_id: str, client: str, selected_memory_ids: Optional[str] = None):
    """Generate a client-specific resume package for one conversation."""
    conversation = _get_conversation_record(conversation_id)
    parsed_memory_ids = [int(part) for part in str(selected_memory_ids or "").split(",") if str(part).strip().isdigit()]
    try:
        return build_export_package(conversation, client, _get_pinned_memories(), parsed_memory_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/conversations/{conversation_id}/export/apply")
async def apply_conversation_export(conversation_id: str, payload: ExportApplyInput):
    """Write a client-specific resume package into a local workspace."""
    conversation = _get_conversation_record(conversation_id)
    try:
        result = apply_export_package(
            conversation,
            payload.client,
            payload.workspace_path,
            _get_pinned_memories(),
            payload.selected_memory_ids or [],
        )
        for memory_id in result.get("selected_memory_ids", []):
            if not memory_id:
                continue
            db.conn.execute(
                """
                INSERT OR IGNORE INTO preference_usage (memory_id, client_id, conversation_id, used_at)
                VALUES (?, ?, ?, ?)
                """,
                (int(memory_id), payload.client, conversation_id, datetime.now().isoformat()),
            )
        db.conn.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/analyze/{conversation_id}")
async def analyze_conversation(conversation_id: str):
    """Run AI analysis on a stored conversation and persist a better summary."""
    cursor = db.conn.execute(
        "SELECT full_content, summary FROM conversations WHERE id = ?",
        (conversation_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await analyzer.generate_summary(row["full_content"] or "")

    generated_summary = result.get("summary")
    if generated_summary and analyzer.is_ai_available():
        db.conn.execute(
            "UPDATE conversations SET summary = ? WHERE id = ?",
            (generated_summary, conversation_id),
        )
        db.conn.commit()

    return {
        "conversation_id": conversation_id,
        "ai_available": analyzer.is_ai_available(),
        "analysis": result,
    }


@app.post("/api/conversations/resummarize")
async def resummarize_conversations(payload: ResummarizeInput):
    """Generate better summaries for a batch of conversations."""
    if not payload.conversation_ids:
        raise HTTPException(status_code=400, detail="conversation_ids is required")
    if len(payload.conversation_ids) > 50:
        raise HTTPException(status_code=400, detail="conversation_ids must contain at most 50 items")

    results = []
    for conversation_id in payload.conversation_ids:
        record = _get_conversation_record(conversation_id)
        current_summary = record.get("summary")
        if not payload.force and not _summary_needs_upgrade(current_summary, record.get("project")):
            results.append({
                "conversation_id": conversation_id,
                "updated": False,
                "summary": current_summary,
                "reason": "summary already looks usable",
            })
            continue

        analysis = await analyzer.generate_summary(record.get("full_content") or "")
        generated_summary = str(analysis.get("summary") or "").strip()
        if not generated_summary:
            results.append({
                "conversation_id": conversation_id,
                "updated": False,
                "summary": current_summary,
                "reason": "no summary generated",
            })
            continue

        _update_conversation_summary(conversation_id, generated_summary)
        results.append({
            "conversation_id": conversation_id,
            "updated": True,
            "summary": generated_summary,
            "ai_generated": bool(analysis.get("ai_generated")),
        })

    return {
        "updated_count": len([item for item in results if item.get("updated")]),
        "results": results,
        "ai_available": analyzer.is_ai_available(),
    }


@app.post("/api/conversations/resummarize-ugly")
async def resummarize_ugly_conversations(payload: ResummarizeUglyInput):
    """Generate better summaries only for conversations whose current titles look unreadable."""
    if payload.limit < 1 or payload.limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")

    candidates = []
    for record in db.get_conversations_for_resummary(limit=max(payload.limit * 4, payload.limit)):
        if payload.force or _summary_needs_upgrade(record.get("summary"), record.get("project")):
            candidates.append(record["id"])
        if len(candidates) >= payload.limit:
            break

    return await resummarize_conversations(
        ResummarizeInput(conversation_ids=candidates, force=payload.force)
    )


@app.get("/api/ai/status")
async def ai_status():
    """Return current AI analyzer availability."""
    provider_name = analyzer.provider.__class__.__name__ if analyzer.provider else None
    return {
        "available": analyzer.is_ai_available(),
        "provider": provider_name,
        "config_path": str(AI_CONFIG_PATH),
    }


@app.post("/api/ai/reload")
async def reload_ai_config():
    """Reload AI configuration without restarting the backend."""
    analyzer.reload_config()
    provider_name = analyzer.provider.__class__.__name__ if analyzer.provider else None
    return {
        "status": "reloaded",
        "available": analyzer.is_ai_available(),
        "provider": provider_name,
    }


@app.post("/api/import/local")
async def import_local_sessions(payload: LocalImportInput):
    """Import locally stored CLI sessions into Memory Hub."""
    if payload.limit < 1 or payload.limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")

    sources = ["codex", "claude_code", "gemini_cli", "antigravity"] if payload.source == "all" else [payload.source]

    try:
        result = import_sources(sources, payload.limit, payload.dry_run, _persist_conversation_payload)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported source: {payload.source}") from exc

    imported_ids: list[str] = []
    for item in result.get("sources", []):
        imported_ids.extend(item.get("conversation_ids", []))

    auto_summary_result = None
    if payload.auto_summarize and not payload.dry_run and imported_ids:
        auto_summary_result = await resummarize_conversations(
            ResummarizeInput(conversation_ids=imported_ids, force=False)
        )

    result["dry_run"] = payload.dry_run
    result["requested_source"] = payload.source
    result["auto_summarize"] = auto_summary_result
    return result


@app.post("/api/backup/export")
async def export_backup_bundle():
    """Create a local backup bundle for all stored conversations."""
    return create_backup_bundle(db.conn, DATA_DIR)


@app.get("/api/backup/settings")
async def get_backup_settings():
    settings = load_backup_settings(DATA_DIR)
    return {
        "settings": settings,
        "backups": list_backups(DATA_DIR)[:20],
    }


@app.post("/api/backup/settings")
async def update_backup_settings(payload: BackupSettingsInput):
    if payload.interval_hours < 1 or payload.interval_hours > 720:
        raise HTTPException(status_code=400, detail="interval_hours must be between 1 and 720")
    if payload.retention_count < 1 or payload.retention_count > 200:
        raise HTTPException(status_code=400, detail="retention_count must be between 1 and 200")

    settings = save_backup_settings(
        DATA_DIR,
        {
            "enabled": payload.enabled,
            "interval_hours": payload.interval_hours,
            "retention_count": payload.retention_count,
            "backup_root": payload.backup_root or None,
        },
    )
    return {
        "settings": settings,
        "backups": list_backups(DATA_DIR)[:20],
    }


@app.post("/api/backup/restore")
async def restore_backup(payload: BackupRestoreInput):
    source_path = Path(payload.source_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Backup source not found")

    safety_backup = create_backup_bundle(db.conn, DATA_DIR)
    try:
        result = restore_backup_source(DATA_DIR, source_path)
        _reload_runtime_state()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        **result,
        "safety_backup": safety_backup,
        "backups": list_backups(DATA_DIR)[:20],
    }


@app.get("/api/backup/preview")
async def preview_backup(source_path: str):
    source = Path(source_path)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Backup source not found")

    try:
        return read_backup_manifest(source)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/backup/validate")
async def validate_backup(source_path: str):
    source = Path(source_path)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Backup source not found")

    try:
        return validate_backup_source(source)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# V2 API endpoints: CLI Switch & Working Memory
# ---------------------------------------------------------------------------

from database_v2 import DatabaseV2
from models_v2 import SwitchInput, SwitchPreviewInput, WorkingMemoryInput
from switch_engine import (
    execute_switch,
    preview_switch,
    get_switch_history,
    get_working_memory,
    upsert_working_memory,
    delete_working_memory,
    list_working_memories,
)

# Initialize V2 database (uses same DB file, adds V2 tables if needed)
db_v2 = DatabaseV2(str(DATA_DIR / "memory.db"))

# Share this instance with api_v2 to avoid duplicate connections
try:
    from api_v2 import set_db_v2, set_vector_store_v2
    set_db_v2(db_v2)
    set_vector_store_v2(vector_store)
except ImportError:
    pass


@app.post("/api/v2/switch")
async def v2_switch(payload: SwitchInput):
    """Execute CLI switch with context injection."""
    try:
        result = execute_switch(
            conn=db_v2.conn,
            to_cli=payload.to_cli,
            workspace_path=payload.workspace_path,
            from_cli=payload.from_cli,
            from_session_id=payload.from_session_id,
            token_budget=payload.token_budget,
            include_archive_turns=payload.include_archive_turns,
            conversation_ids=payload.conversation_ids,
            custom_context=payload.custom_context,
            write_file=True,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v2/switch/preview")
async def v2_switch_preview(payload: SwitchPreviewInput):
    """Preview what would be injected (dry run)."""
    try:
        return preview_switch(
            conn=db_v2.conn,
            to_cli=payload.to_cli,
            workspace_path=payload.workspace_path,
            token_budget=payload.token_budget,
            conversation_ids=payload.conversation_ids,
            custom_context=payload.custom_context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v2/switch/history")
async def v2_switch_history(limit: int = 20):
    """List recent switch events."""
    return {"history": get_switch_history(db_v2.conn, limit)}


@app.get("/api/v2/working-memory")
async def v2_list_working_memories():
    """List all active working memories."""
    return {"working_memories": list_working_memories(db_v2.conn)}


@app.get("/api/v2/working-memory/{workspace_path:path}")
async def v2_get_working_memory(workspace_path: str):
    """Get working memory for a workspace."""
    import urllib.parse
    decoded = urllib.parse.unquote(workspace_path)
    result = get_working_memory(db_v2.conn, decoded)
    if not result:
        raise HTTPException(status_code=404, detail="No working memory found")
    return result


@app.put("/api/v2/working-memory/{workspace_path:path}")
async def v2_upsert_working_memory(workspace_path: str, payload: WorkingMemoryInput):
    """Update working memory for a workspace (upsert)."""
    import urllib.parse
    decoded = urllib.parse.unquote(workspace_path)

    data = payload.model_dump()
    data["workspace_path"] = decoded

    # Serialize list fields for the raw SQL upsert
    result = upsert_working_memory(db_v2.conn, data)
    return result


@app.delete("/api/v2/working-memory/{workspace_path:path}")
async def v2_delete_working_memory(workspace_path: str):
    """Clear working memory for a workspace."""
    import urllib.parse
    decoded = urllib.parse.unquote(workspace_path)
    deleted = delete_working_memory(db_v2.conn, decoded)
    if not deleted:
        raise HTTPException(status_code=404, detail="No working memory found")
    return {"status": "ok", "deleted": True}


@app.get("/api/v2/stats")
async def v2_stats():
    """Get V2 database statistics."""
    return db_v2.get_stats()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
