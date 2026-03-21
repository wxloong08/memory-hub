"""
Memory Hub V2 -- Context Assembly Engine

Assembles three-layer context (working + core + archive) for CLI switching.
Respects per-CLI token budgets and formats output for the target CLI's context file.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from client_exports import ClientExportProfile, get_export_profile, CLIENT_EXPORT_PROFILES
from message_compressor import estimate_tokens
from compression import get_display_content


# ---------------------------------------------------------------------------
# Token budgets per CLI (max tokens for injected context)
# ---------------------------------------------------------------------------

CLI_TOKEN_BUDGETS: dict[str, dict[str, int]] = {
    "claude_code": {
        "working": 3000,
        "core": 5000,
        "archive": 20000,
        "total": 28000,
    },
    "codex": {
        "working": 2000,
        "core": 4000,
        "archive": 10000,
        "total": 16000,
    },
    "gemini_cli": {
        "working": 3000,
        "core": 8000,
        "archive": 100000,
        "total": 111000,
    },
    "antigravity": {
        "working": 2000,
        "core": 4000,
        "archive": 10000,
        "total": 16000,
    },
}


def get_budget(cli: str, override: int | None = None) -> dict[str, int]:
    """Get the token budget for a CLI target."""
    budget = CLI_TOKEN_BUDGETS.get(cli, CLI_TOKEN_BUDGETS["codex"]).copy()
    if override and override > 0:
        ratio = override / budget["total"]
        budget = {k: max(500, int(v * ratio)) for k, v in budget.items()}
        budget["total"] = override
    return budget


# ---------------------------------------------------------------------------
# Working memory formatting
# ---------------------------------------------------------------------------

def format_working_memory(working: dict | None) -> str:
    """Format working memory into a markdown section."""
    if not working:
        return ""

    lines = ["## Current Task (Working Memory)", ""]

    active_task = working.get("active_task")
    if active_task:
        lines.append(f"**Task**: {active_task}")

    plan = working.get("current_plan")
    if plan:
        if isinstance(plan, str):
            try:
                plan = json.loads(plan)
            except (json.JSONDecodeError, TypeError):
                plan = [plan]
        if isinstance(plan, list) and plan:
            lines.append("**Plan**:")
            for i, step in enumerate(plan, 1):
                lines.append(f"  {i}. {step}")

    progress = working.get("progress")
    if progress:
        if isinstance(progress, str):
            try:
                progress = json.loads(progress)
            except (json.JSONDecodeError, TypeError):
                progress = [progress]
        if isinstance(progress, list) and progress:
            lines.append("**Completed**:")
            for item in progress:
                lines.append(f"  - {item}")

    open_issues = working.get("open_issues")
    if open_issues:
        if isinstance(open_issues, str):
            try:
                open_issues = json.loads(open_issues)
            except (json.JSONDecodeError, TypeError):
                open_issues = [open_issues]
        if isinstance(open_issues, list) and open_issues:
            lines.append("**Open Issues**:")
            for item in open_issues:
                lines.append(f"  - {item}")

    recent_changes = working.get("recent_changes")
    if recent_changes:
        lines.append(f"**Recent Changes**: {recent_changes}")

    last_cli = working.get("last_cli")
    if last_cli:
        lines.append(f"**Last CLI**: {last_cli}")

    context_snippet = working.get("context_snippet")
    if context_snippet:
        lines.append("")
        lines.append("**Last Context**:")
        lines.append(context_snippet)

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core memory formatting
# ---------------------------------------------------------------------------

def format_core_memories(memories: list[dict], budget: int) -> tuple[str, int]:
    """Format core memories into a markdown section, respecting token budget.

    Returns (formatted_text, count_injected).
    """
    if not memories:
        return "", 0

    # Sort: pinned first, then priority DESC, then confidence DESC
    sorted_mems = sorted(
        memories,
        key=lambda m: (
            -int(m.get("pinned", 0) or 0),
            -int(m.get("priority", 0) or 0),
            -float(m.get("confidence", 0) or 0),
        ),
    )

    lines = ["## Key Context (Core Memory)", ""]
    current_category = None
    injected = 0
    tokens_used = estimate_tokens("\n".join(lines))

    for mem in sorted_mems:
        category = str(mem.get("category") or "general").strip()
        key = str(mem.get("key") or category).strip()
        value = str(mem.get("value") or "").strip()
        if not value:
            continue

        entry_lines = []
        if category != current_category:
            entry_lines.append(f"### {category}")
            current_category = category

        pinned_prefix = "[Pinned] " if int(mem.get("pinned", 0) or 0) > 0 or int(mem.get("priority", 0) or 0) > 0 else ""
        entry_lines.append(f"- {pinned_prefix}**{key}**: {value}")

        candidate = "\n".join(entry_lines)
        candidate_tokens = estimate_tokens(candidate)

        if tokens_used + candidate_tokens > budget:
            break

        lines.extend(entry_lines)
        tokens_used += candidate_tokens
        injected += 1

    lines.append("")
    return "\n".join(lines), injected


# ---------------------------------------------------------------------------
# Archive excerpt formatting
# ---------------------------------------------------------------------------

def format_archive_excerpt(
    sessions: list[dict],
    budget: int,
    max_turns: int | None = None,
) -> tuple[str, int]:
    """Format archive session excerpts into a markdown section.

    Each session dict should have:
      - id, platform, started_at, summary, messages (list of message dicts)

    Returns (formatted_text, turns_injected).
    """
    if not sessions:
        return "", 0

    lines = ["## Recent Conversation (Archive Excerpt)", ""]
    total_turns = 0
    tokens_used = estimate_tokens("\n".join(lines))

    for session in sessions:
        platform = session.get("platform", "unknown")
        started_at = session.get("started_at", "")
        summary = session.get("summary", "")

        header = f"### Session: {started_at} ({platform})"
        if summary:
            header += f"\n_{summary}_"

        header_tokens = estimate_tokens(header)
        if tokens_used + header_tokens > budget:
            break

        lines.append(header)
        lines.append("")
        tokens_used += header_tokens

        messages = session.get("messages", [])
        session_start_turns = total_turns
        for msg_idx, msg in enumerate(messages):
            if max_turns is not None and total_turns >= max_turns:
                break

            role = msg.get("role", "unknown")
            display = get_display_content(msg)

            if role == "user":
                entry = f"User: {display}"
            elif role == "assistant":
                entry = f"Assistant: {display}"
            elif role == "system":
                continue
            else:
                entry = display

            entry_tokens = estimate_tokens(entry)
            if tokens_used + entry_tokens > budget:
                remaining = len(messages) - msg_idx
                if remaining > 0:
                    lines.append(f"[...{remaining} more messages truncated]")
                break

            lines.append(entry)
            tokens_used += entry_tokens
            total_turns += 1

        lines.append("")

        if max_turns is not None and total_turns >= max_turns:
            break

    return "\n".join(lines), total_turns


# ---------------------------------------------------------------------------
# Full context assembly
# ---------------------------------------------------------------------------

def assemble_switch_context(
    target_cli: str,
    working_memory: dict | None = None,
    core_memories: list[dict] | None = None,
    archive_sessions: list[dict] | None = None,
    token_budget: int | None = None,
    include_archive_turns: int | None = None,
    from_cli: str | None = None,
    switch_count: int = 0,
) -> dict:
    """Assemble full context for CLI switch injection.

    Returns a dict with:
      - content: formatted markdown string
      - target_file: relative path for the CLI's context file
      - working_memory_tokens: tokens used for working layer
      - core_memory_tokens: tokens used for core layer
      - archive_tokens: tokens used for archive layer
      - total_tokens: total tokens
      - core_memories_injected: count
      - archive_turns_injected: count
    """
    profile = get_export_profile(target_cli)
    budget = get_budget(target_cli, token_budget)

    # Header
    task_desc = ""
    if working_memory and working_memory.get("active_task"):
        task_desc = working_memory["active_task"]
    title = task_desc or "Context Resume"

    header_lines = [f"# Resume Context: {title}", ""]
    if from_cli:
        header_lines.append(f"_Switched from {from_cli} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    if switch_count > 0:
        header_lines.append(f"_Switch #{switch_count} for this workspace_")
    header_lines.append("")

    header = "\n".join(header_lines)
    header_tokens = estimate_tokens(header)
    remaining = budget["total"] - header_tokens

    # 1. Working memory (always injected in full, capped by working budget)
    working_section = format_working_memory(working_memory)
    working_tokens = estimate_tokens(working_section)
    if working_tokens > budget["working"]:
        # Truncate if too large
        working_section = working_section[:budget["working"] * 4] + "\n[...working memory truncated]\n"
        working_tokens = estimate_tokens(working_section)
    remaining -= working_tokens

    # 2. Core memories (filtered by priority and relevance)
    core_budget = min(budget["core"], int(remaining * 0.4))
    core_section, core_count = format_core_memories(core_memories or [], core_budget)
    core_tokens = estimate_tokens(core_section)
    remaining -= core_tokens

    # 3. Archive excerpt (compressed recent turns)
    archive_budget = min(budget["archive"], remaining)
    archive_section, archive_turns = "", 0
    if archive_budget > 500 and archive_sessions:
        archive_section, archive_turns = format_archive_excerpt(
            archive_sessions,
            archive_budget,
            max_turns=include_archive_turns,
        )
    archive_tokens = estimate_tokens(archive_section)

    # Footer
    footer = "\n---\n_Context assembled by Memory Hub V2_\n"

    # Assemble
    content = header + working_section + core_section + archive_section + footer
    total_tokens = estimate_tokens(content)

    return {
        "content": content,
        "target_file": profile.target_relpath,
        "target_cli": target_cli,
        "context_assembled": {
            "working_memory_tokens": working_tokens,
            "core_memory_tokens": core_tokens,
            "archive_tokens": archive_tokens,
            "total_tokens": total_tokens,
        },
        "core_memories_injected": core_count,
        "archive_turns_injected": archive_turns,
    }
