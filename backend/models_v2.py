"""
Memory Hub V2 -- Pydantic models for the three-layer memory architecture.

Archive Layer: Full conversation transcripts with structured messages
Core Layer: Structured knowledge (facts, decisions, preferences)
Working Layer: Active task context per workspace
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Archive Layer models
# ---------------------------------------------------------------------------

class MessageInput(BaseModel):
    """A single message in a conversation."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str = Field(min_length=1)
    content_type: Literal["text", "tool_use", "tool_result", "image", "thinking"] = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkingStateInput(BaseModel):
    """Optional working state captured at session end."""
    active_task: Optional[str] = None
    plan: Optional[List[str]] = None
    progress: Optional[List[str]] = None
    open_issues: Optional[List[str]] = None
    recent_changes: Optional[str] = None


class ConversationV2Input(BaseModel):
    """V2 conversation ingest contract."""
    platform: str = Field(min_length=1)
    session_id: Optional[str] = None
    workspace_path: Optional[str] = None
    started_at: str = Field(min_length=1)
    ended_at: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    assistant_label: Optional[str] = None
    messages: List[MessageInput] = Field(min_length=1)
    working_state: Optional[WorkingStateInput] = None
    summary: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Fields carried over for backward compatibility with V1 importers
    source_path: Optional[str] = None
    source_fingerprint: Optional[str] = None
    project: Optional[str] = None


class ConversationV2Response(BaseModel):
    """V2 conversation ingest response."""
    status: str = "ok"
    conversation_id: str
    message_count: int
    token_estimate: int
    summary: Optional[str] = None
    working_memory_updated: bool = False


class MessageRecord(BaseModel):
    """Stored message record (read from DB)."""
    id: int
    conversation_id: str
    ordinal: int = Field(ge=0)
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    content_type: Literal["text", "tool_use", "tool_result", "image", "thinking"] = "text"
    compressed: Optional[str] = None
    token_estimate: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationV2Record(BaseModel):
    """Stored conversation record (read from DB)."""
    id: str
    platform: str = Field(min_length=1)
    session_id: Optional[str] = None
    workspace_path: Optional[str] = None
    started_at: str
    ended_at: Optional[str] = None
    message_count: int = Field(default=0, ge=0)
    token_estimate: int = Field(default=0, ge=0)
    summary: Optional[str] = None
    summary_source: str = "fallback"
    importance: int = Field(default=5, ge=1, le=10)
    provider: Optional[str] = None
    model: Optional[str] = None
    assistant_label: Optional[str] = None
    source_path: Optional[str] = None
    source_fingerprint: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Working Layer models
# ---------------------------------------------------------------------------

class WorkingMemoryInput(BaseModel):
    """Working memory upsert request."""
    workspace_path: str = Field(min_length=1)
    active_task: Optional[str] = None
    current_plan: Optional[List[str]] = None
    progress: Optional[List[str]] = None
    open_issues: Optional[List[str]] = None
    recent_changes: Optional[str] = None
    last_cli: Optional[str] = None
    last_session_id: Optional[str] = None
    context_snippet: Optional[str] = None


class WorkingMemoryRecord(BaseModel):
    """Stored working memory record."""
    id: int
    workspace_path: str
    active_task: Optional[str] = None
    current_plan: Optional[List[str]] = None
    progress: Optional[List[str]] = None
    open_issues: Optional[List[str]] = None
    recent_changes: Optional[str] = None
    last_cli: Optional[str] = None
    last_session_id: Optional[str] = None
    context_snippet: Optional[str] = None
    switch_count: int = Field(default=0, ge=0)
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Switch models
# ---------------------------------------------------------------------------

class SwitchInput(BaseModel):
    """CLI switch request."""
    from_cli: Optional[str] = None
    to_cli: str = Field(min_length=1)
    workspace_path: str = Field(min_length=1)
    from_session_id: Optional[str] = None
    token_budget: Optional[int] = Field(default=None, gt=0)
    include_archive_turns: Optional[int] = Field(default=None, ge=0)


class SwitchResponse(BaseModel):
    """CLI switch response."""
    status: str = "ok"
    target_file: str
    target_cli: str
    context_assembled: dict[str, int] = Field(default_factory=dict)
    core_memories_injected: int = 0
    archive_turns_injected: int = 0
    switch_number: int = 0
    content_preview: Optional[str] = None


# ---------------------------------------------------------------------------
# Import models
# ---------------------------------------------------------------------------

class LocalImportV2Input(BaseModel):
    """Enhanced local import request."""
    source: str = "all"
    limit: int = 20
    dry_run: bool = False
    auto_summarize: bool = True
    auto_compress: bool = True
