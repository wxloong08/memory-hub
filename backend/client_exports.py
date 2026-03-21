from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
import re


@dataclass(frozen=True)
class ClientExportProfile:
    client_id: str
    display_name: str
    target_relpath: str
    filename: str
    format_hint: str
    description: str
    preferred_categories: tuple[str, ...] = ()
    category_bonus: dict[str, float] | None = None
    default_limit: int = 8
    strategy_summary: str = ""


CLIENT_EXPORT_PROFILES: dict[str, ClientExportProfile] = {
    "claude_code": ClientExportProfile(
        client_id="claude_code",
        display_name="Claude Code",
        target_relpath=".claude/CLAUDE.md",
        filename="CLAUDE.md",
        format_hint="claude_md",
        description="Write resume context into .claude/CLAUDE.md for Claude Code.",
        preferred_categories=("identity", "preference", "workflow"),
        category_bonus={"identity": 4.0, "preference": 3.0, "workflow": 2.0, "avoid": 2.0},
        default_limit=8,
        strategy_summary="Prefer coding style, project constraints, user preferences, and working conventions.",
    ),
    "codex": ClientExportProfile(
        client_id="codex",
        display_name="Codex",
        target_relpath="AGENTS.md",
        filename="AGENTS.md",
        format_hint="agents_md",
        description="Write resume context into AGENTS.md so Codex can pick it up.",
        preferred_categories=("workflow", "avoid", "identity"),
        category_bonus={"workflow": 4.0, "avoid": 3.5, "identity": 2.0, "preference": 1.5},
        default_limit=8,
        strategy_summary="Prefer technical workflow, guardrails, avoid-items, and implementation habits.",
    ),
    "gemini_cli": ClientExportProfile(
        client_id="gemini_cli",
        display_name="Gemini CLI",
        target_relpath="GEMINI.md",
        filename="GEMINI.md",
        format_hint="gemini_md",
        description="Write resume context into GEMINI.md for Gemini CLI.",
        preferred_categories=("identity", "workflow", "preference"),
        category_bonus={"identity": 3.5, "workflow": 3.0, "preference": 2.0, "avoid": 1.5},
        default_limit=10,
        strategy_summary="Prefer current goals, identity context, and task-oriented working preferences.",
    ),
    "antigravity": ClientExportProfile(
        client_id="antigravity",
        display_name="Antigravity",
        target_relpath=".antigravity/context.md",
        filename="context.md",
        format_hint="antigravity_md",
        description="Write resume context for Antigravity sessions.",
        preferred_categories=("identity", "workflow", "decision"),
        category_bonus={"identity": 3.0, "workflow": 3.0, "decision": 2.5, "preference": 2.0},
        default_limit=10,
        strategy_summary="Prefer identity, workflow patterns, and key decisions for task continuity.",
    ),
}


def get_export_profile(client_id: str) -> ClientExportProfile:
    normalized = str(client_id or "").strip().lower()
    if normalized not in CLIENT_EXPORT_PROFILES:
        supported = ", ".join(CLIENT_EXPORT_PROFILES)
        raise ValueError(f"Unsupported export client '{client_id}'. Supported: {supported}")
    return CLIENT_EXPORT_PROFILES[normalized]


def parse_full_content(full_content: str) -> list[dict]:
    lines = str(full_content or "").replace("\r", "").split("\n")
    messages: list[dict] = []
    current: dict | None = None

    for raw_line in lines:
        match = re.match(r"^(user|assistant):\s?(.*)$", raw_line)
        if match:
            if current and str(current.get("content", "")).strip():
                current["content"] = str(current["content"]).strip()
                messages.append(current)
            current = {"role": match.group(1), "content": match.group(2) or ""}
            continue

        if current is None:
            continue

        current["content"] = f"{current['content']}\n{raw_line}" if current["content"] else raw_line

    if current and str(current.get("content", "")).strip():
        current["content"] = str(current["content"]).strip()
        messages.append(current)

    return messages


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"\w+|[\u4e00-\u9fff]", str(text or "").lower(), flags=re.UNICODE)
        if token
    }


def _conversation_tokens(conversation: dict) -> set[str]:
    return _tokenize(
        " ".join([
            str(conversation.get("project") or ""),
            str(conversation.get("summary") or ""),
            str(conversation.get("full_content") or "")[:4000],
            str(conversation.get("model") or ""),
            str(conversation.get("provider") or ""),
        ])
    )


def _memory_tokens_for_selection(memory: dict) -> set[str]:
    return _tokenize(
        " ".join([
            str(memory.get("category") or ""),
            str(memory.get("key") or ""),
            str(memory.get("value") or ""),
        ])
    )


def _memory_selection_reasons(
    conversation_tokens: set[str],
    memory: dict,
    profile: ClientExportProfile,
    explicit: bool = False,
) -> list[str]:
    reasons: list[str] = []
    rule = str((memory.get("client_rules") or {}).get(profile.client_id, "default")).strip().lower()
    if explicit:
        reasons.append("manualSelection")
    if rule == "include":
        reasons.append("clientRuleInclude")
    if int(memory.get("priority") or 0) > 0:
        reasons.append("memoryPriority")

    category = str(memory.get("category") or "").strip().lower()
    if category and category in profile.preferred_categories:
        reasons.append("clientCategoryMatch")

    overlap = len(conversation_tokens & _memory_tokens_for_selection(memory)) if conversation_tokens else 0
    if overlap > 0:
        reasons.append("conversationRelevance")

    confidence = float(memory.get("effective_confidence") or memory.get("confidence") or 0.0)
    if confidence >= 0.85:
        reasons.append("highConfidence")

    return reasons or ["defaultStrategy"]


def select_relevant_memories(
    conversation: dict,
    memories: Iterable[dict],
    profile: ClientExportProfile,
    limit: int | None = None,
) -> list[dict]:
    memory_list = list(memories or [])
    if not memory_list:
        return []
    selected_limit = limit or profile.default_limit
    conversation_tokens = _conversation_tokens(conversation)
    forced_include: list[dict] = []
    ranked_candidates: list[dict] = []
    for memory in memory_list:
        rule = str((memory.get("client_rules") or {}).get(profile.client_id, "default")).strip().lower()
        if rule == "exclude":
            continue
        if rule == "include":
            forced_include.append(memory)
            continue
        ranked_candidates.append(memory)

    ranked: list[tuple[float, dict]] = []
    for index, memory in enumerate(ranked_candidates):
        memory_tokens = _memory_tokens_for_selection(memory)
        overlap = len(conversation_tokens & memory_tokens) if conversation_tokens and memory_tokens else 0
        confidence = float(memory.get("effective_confidence") or memory.get("confidence") or 0.0)
        priority = float(memory.get("priority") or 0.0)
        category = str(memory.get("category") or "").strip().lower()
        category_bonus = float((profile.category_bonus or {}).get(category, 0.0))
        preferred_bonus = 1.5 if category and category in profile.preferred_categories else 0.0
        score = overlap * 10 + confidence + (priority / 10) + category_bonus + preferred_bonus
        ranked.append((score + (1 / (index + 1000)), memory))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected: list[dict] = []
    seen_ids: set[int] = set()
    for memory in forced_include:
        memory_id = int(memory.get("id") or 0)
        if memory_id and memory_id not in seen_ids:
            selected.append(memory)
            seen_ids.add(memory_id)

    for score, memory in ranked:
        if len(selected) >= selected_limit:
            break
        memory_id = int(memory.get("id") or 0)
        if memory_id and memory_id not in seen_ids and score > 0:
            selected.append(memory)
            seen_ids.add(memory_id)

    if selected:
        return selected

    return sorted(
        forced_include + ranked_candidates,
        key=lambda item: (
            1 if str((item.get("client_rules") or {}).get(profile.client_id, "default")).strip().lower() == "include" else 0,
            float(item.get("priority") or 0.0),
            float((profile.category_bonus or {}).get(str(item.get("category") or "").strip().lower(), 0.0)),
            float(item.get("effective_confidence") or item.get("confidence") or 0.0),
        ),
        reverse=True,
    )[: min(selected_limit, len(memory_list))]


def build_memory_section(memories: Iterable[dict]) -> str:
    grouped: dict[str, list[dict]] = {}
    for memory in memories:
        category = str(memory.get("category") or "general").strip() or "general"
        grouped.setdefault(category, []).append(memory)

    if not grouped:
        return "No pinned memories available."

    chunks: list[str] = []
    for category in sorted(grouped):
        chunks.append(f"### {category}")
        chunks.append("")
        for memory in grouped[category]:
            key = str(memory.get("key") or category).strip() or category
            value = str(memory.get("value") or "").strip()
            confidence = memory.get("effective_confidence") or memory.get("confidence")
            priority = int(memory.get("priority") or 0)
            confidence_text = ""
            if confidence is not None:
                try:
                    confidence_text = f" ({float(confidence):.1f})"
                except (TypeError, ValueError):
                    confidence_text = ""
            prefix = "[Pinned] " if priority > 0 else ""
            if value:
                chunks.append(f"- {prefix}**{key}**{confidence_text}: {value}")
        chunks.append("")

    return "\n".join(chunks).strip()


def build_resume_markdown(conversation: dict, profile: ClientExportProfile, memories: Iterable[dict] | None = None) -> str:
    title = str(conversation.get("summary") or conversation.get("project") or "Conversation Resume").strip()
    platform = str(conversation.get("platform") or "unknown").strip()
    provider = str(conversation.get("provider") or "").strip()
    model = str(conversation.get("model") or "").strip()
    assistant_label = str(conversation.get("assistant_label") or "").strip() or "Assistant"
    timestamp = str(conversation.get("timestamp") or "").strip()
    summary = str(conversation.get("summary") or "").strip()
    project = str(conversation.get("project") or "").strip()
    messages = parse_full_content(conversation.get("full_content") or "")
    memory_section = build_memory_section(memories or [])
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    metadata_lines = [
        f"- Source platform: {platform}",
        f"- Export target: {profile.display_name}",
        f"- Conversation time: {timestamp or 'unknown'}",
    ]
    if project:
        metadata_lines.append(f"- Project/title: {project}")
    if provider:
        metadata_lines.append(f"- Provider: {provider}")
    if model:
        metadata_lines.append(f"- Model: {model}")
    if assistant_label:
        metadata_lines.append(f"- Assistant label: {assistant_label}")

    transcript_chunks = []
    for message in messages:
        role = "You" if message.get("role") == "user" else assistant_label
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        transcript_chunks.append(f"### {role}\n\n{content}")

    transcript = "\n\n".join(transcript_chunks) if transcript_chunks else "No transcript available."

    return (
        f"# Resume Context: {title}\n\n"
        f"_Generated by Claude Memory System on {generated_at}_\n\n"
        f"## Usage\n\n"
        f"- Continue from this conversation instead of starting fresh.\n"
        f"- Preserve previous technical decisions, constraints, and pending tasks.\n"
        f"- If the next user prompt is short, assume it refers to the context below.\n\n"
        f"## Metadata\n\n"
        f"{chr(10).join(metadata_lines)}\n\n"
        f"## Summary\n\n"
        f"{summary or 'No summary available.'}\n\n"
        f"## Pinned Memory\n\n"
        f"{memory_section}\n\n"
        f"## Transcript\n\n"
        f"{transcript}\n"
    )


def _build_selected_memory_details(
    conversation: dict,
    memories: Iterable[dict],
    profile: ClientExportProfile,
    explicit_ids: set[int] | None = None,
) -> list[dict]:
    conversation_tokens = _conversation_tokens(conversation)
    details: list[dict] = []
    for memory in memories:
        memory_id = int(memory.get("id") or 0)
        details.append({
            "id": memory_id,
            "category": memory.get("category") or "",
            "key": memory.get("key") or "",
            "value": memory.get("value") or "",
            "priority": int(memory.get("priority") or 0),
            "confidence": memory.get("effective_confidence") or memory.get("confidence"),
            "reasons": _memory_selection_reasons(
                conversation_tokens,
                memory,
                profile,
                explicit=memory_id in (explicit_ids or set()),
            ),
        })
    return details


def build_export_package(
    conversation: dict,
    client_id: str,
    memories: Iterable[dict] | None = None,
    selected_memory_ids: Iterable[int] | None = None,
) -> dict:
    profile = get_export_profile(client_id)
    all_memories = list(memories or [])
    explicit_ids = {int(memory_id) for memory_id in (selected_memory_ids or [])}
    if explicit_ids:
        selected_memories = [memory for memory in all_memories if int(memory.get("id") or 0) in explicit_ids]
    else:
        selected_memories = select_relevant_memories(conversation, all_memories, profile)
    content = build_resume_markdown(conversation, profile, selected_memories)
    selected_memory_details = _build_selected_memory_details(conversation, selected_memories, profile, explicit_ids)
    return {
        "client": profile.client_id,
        "client_display_name": profile.display_name,
        "target_relpath": profile.target_relpath,
        "filename": profile.filename,
        "format_hint": profile.format_hint,
        "description": profile.description,
        "memory_count": len(selected_memories),
        "total_memory_count": len(all_memories),
        "selected_memory_ids": [int(memory.get("id")) for memory in selected_memories if memory.get("id") is not None],
        "selected_memories": selected_memory_details,
        "strategy_summary": profile.strategy_summary,
        "content": content,
    }


def apply_export_package(
    conversation: dict,
    client_id: str,
    workspace_path: str,
    memories: Iterable[dict] | None = None,
    selected_memory_ids: Iterable[int] | None = None,
) -> dict:
    profile = get_export_profile(client_id)
    workspace = Path(workspace_path).expanduser()
    if not workspace.is_absolute():
        raise ValueError("workspace_path must be an absolute path")

    workspace.mkdir(parents=True, exist_ok=True)
    target_path = workspace / Path(profile.target_relpath)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    backup_path = None
    if target_path.exists():
        backup_path = target_path.with_suffix(target_path.suffix + ".memory-hub.bak")
        backup_path.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")

    package = build_export_package(conversation, client_id, memories, selected_memory_ids)
    target_path.write_text(package["content"], encoding="utf-8")

    return {
        **package,
        "workspace_path": str(workspace),
        "target_path": str(target_path),
        "backup_path": str(backup_path) if backup_path else None,
    }
