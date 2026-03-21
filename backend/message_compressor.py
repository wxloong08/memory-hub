"""
Message Compressor — rule-based content compression for CLI conversation transcripts.

Implements the compression rules from the V2 design document (section 6.1):
- Tool-use blocks (Read, Bash, Edit, Search/Grep, Write, WebSearch, Agent)
- Long code blocks (>20 lines)
- Error stack traces (>10 lines)
- Thinking blocks

The goal is to reduce token count while preserving semantic meaning so that
compressed conversations can be injected into target CLIs with limited context windows.
"""

from __future__ import annotations

import re
from typing import Iterable


# ---------------------------------------------------------------------------
# Tool-use compressors
# ---------------------------------------------------------------------------

def _compress_tool_read(block: str) -> str:
    """Compress Read tool output: [读取文件: {path}, {lines}行]"""
    path_match = re.search(r"(?:path|file)[:\s]+[\"']?([^\s\"',]+)", block, re.IGNORECASE)
    path = path_match.group(1) if path_match else "unknown"
    lines = block.count("\n")
    return f"[读取文件: {path}, {lines}行]"


def _compress_tool_bash(block: str) -> str:
    """Compress Bash tool output: [执行: {cmd} → {summary}]"""
    cmd_match = re.search(r"(?:command|cmd)[:\s]+[\"']?(.+?)(?:[\"']?\s*$|[\"']?\s*\n)", block, re.IGNORECASE | re.MULTILINE)
    cmd = cmd_match.group(1).strip()[:80] if cmd_match else "unknown"
    # Try to detect exit status
    exit_match = re.search(r"(?:exit[_ ]?code|status|returncode)[:\s]+(\d+)", block, re.IGNORECASE)
    if exit_match:
        code = int(exit_match.group(1))
        status = "成功" if code == 0 else f"失败(code={code})"
    else:
        status = "完成"
    return f"[执行: {cmd} → {status}]"


def _compress_tool_edit(block: str) -> str:
    """Compress Edit tool output: [编辑 {file}: {description}]"""
    file_match = re.search(r"(?:file|path)[:\s]+[\"']?([^\s\"',]+)", block, re.IGNORECASE)
    file_name = file_match.group(1) if file_match else "unknown"
    return f"[编辑: {file_name}]"


def _compress_tool_search(block: str) -> str:
    """Compress Search/Grep tool output: [搜索 "{query}" → {n}个匹配]"""
    query_match = re.search(r"(?:query|pattern|search)[:\s]+[\"']?(.+?)(?:[\"']?\s*$|[\"']?\s*\n)", block, re.IGNORECASE | re.MULTILINE)
    query = query_match.group(1).strip()[:60] if query_match else "unknown"
    count_match = re.search(r"(\d+)\s*(?:match|result|hit|个匹配|条结果)", block, re.IGNORECASE)
    count = count_match.group(1) if count_match else "?"
    return f'[搜索: "{query}" → {count}个匹配]'


def _compress_tool_write(block: str) -> str:
    """Compress Write tool output: [创建文件: {path}, {lines}行]"""
    path_match = re.search(r"(?:path|file)[:\s]+[\"']?([^\s\"',]+)", block, re.IGNORECASE)
    path = path_match.group(1) if path_match else "unknown"
    content_match = re.search(r"(?:content)[:\s]", block, re.IGNORECASE)
    if content_match:
        remaining = block[content_match.end():]
        lines = remaining.count("\n") + 1
    else:
        lines = "?"
    return f"[创建文件: {path}, {lines}行]"


def _compress_tool_websearch(block: str) -> str:
    """Compress WebSearch tool output: [网络搜索: "{query}"]"""
    query_match = re.search(r"(?:query|search)[:\s]+[\"']?(.+?)(?:[\"']?\s*$|[\"']?\s*\n)", block, re.IGNORECASE | re.MULTILINE)
    query = query_match.group(1).strip()[:60] if query_match else "unknown"
    return f'[网络搜索: "{query}"]'


def _compress_tool_agent(block: str) -> str:
    """Compress Agent tool output: [子代理: {description}]"""
    desc_match = re.search(r"(?:description|task|prompt)[:\s]+[\"']?(.+?)(?:[\"']?\s*$|[\"']?\s*\n)", block, re.IGNORECASE | re.MULTILINE)
    desc = desc_match.group(1).strip()[:80] if desc_match else "子任务"
    return f"[子代理: {desc}]"


TOOL_COMPRESSORS = {
    "read": _compress_tool_read,
    "bash": _compress_tool_bash,
    "edit": _compress_tool_edit,
    "search": _compress_tool_search,
    "grep": _compress_tool_search,
    "glob": _compress_tool_search,
    "write": _compress_tool_write,
    "websearch": _compress_tool_websearch,
    "web_search": _compress_tool_websearch,
    "agent": _compress_tool_agent,
}


# ---------------------------------------------------------------------------
# Tool-use block detection (JSON-style tool calls in conversation text)
# ---------------------------------------------------------------------------

_TOOL_USE_PATTERN = re.compile(
    r"^Tool:\s*(\w+)\s*\n```(?:json)?\s*\n([\s\S]*?)\n```",
    re.MULTILINE,
)

_TOOL_RESULT_PATTERN = re.compile(
    r"^>\s*(?:Result from|Tool Result)[:\s]*(.+?)$",
    re.MULTILINE,
)


def _compress_tool_blocks(text: str) -> str:
    """Find and compress tool-use blocks in assistant messages."""

    def replace_tool(match: re.Match) -> str:
        tool_name = match.group(1).strip().lower()
        tool_body = match.group(2)
        compressor = TOOL_COMPRESSORS.get(tool_name)
        if compressor:
            return compressor(tool_body)
        return f"[工具调用: {match.group(1).strip()}]"

    result = _TOOL_USE_PATTERN.sub(replace_tool, text)
    return result


# ---------------------------------------------------------------------------
# Long code block compression
# ---------------------------------------------------------------------------

_CODE_BLOCK_PATTERN = re.compile(r"```(\w*)\n([\s\S]*?)\n```")


def _compress_code_blocks(text: str, max_lines: int = 20) -> str:
    """Compress code blocks longer than max_lines."""

    def replace_code(match: re.Match) -> str:
        lang = match.group(1) or ""
        code = match.group(2)
        lines = code.split("\n")
        if len(lines) <= max_lines:
            return match.group(0)
        head = "\n".join(lines[:5])
        tail = "\n".join(lines[-3:])
        omitted = len(lines) - 8
        return f"```{lang}\n{head}\n// ... ({omitted}行省略)\n{tail}\n```"

    return _CODE_BLOCK_PATTERN.sub(replace_code, text)


# ---------------------------------------------------------------------------
# Error stack trace compression
# ---------------------------------------------------------------------------

_TRACEBACK_PATTERN = re.compile(
    r"((?:Traceback \(most recent call last\):|(?:\w+)?Error:).+?)(?=\n\n|\n[A-Z]|\Z)",
    re.DOTALL,
)

_GENERIC_STACK_PATTERN = re.compile(
    r"((?:^\s+at .+\n){5,})",
    re.MULTILINE,
)


def _compress_error_stacks(text: str, max_lines: int = 10) -> str:
    """Compress error stack traces longer than max_lines."""

    def replace_traceback(match: re.Match) -> str:
        block = match.group(1)
        lines = block.strip().split("\n")
        if len(lines) <= max_lines:
            return match.group(0)
        first = lines[0]
        last = lines[-1]
        # Try to find the root cause line (last line starting without whitespace, or the error message)
        root_cause = last
        for line in reversed(lines[1:]):
            stripped = line.strip()
            if stripped and not stripped.startswith("at ") and not stripped.startswith("File "):
                root_cause = stripped
                break
        return f"{first}\n  ... ({len(lines) - 2}行堆栈省略)\n{root_cause}"

    def replace_generic_stack(match: re.Match) -> str:
        block = match.group(1)
        lines = block.strip().split("\n")
        if len(lines) <= max_lines:
            return match.group(0)
        return f"{lines[0]}\n  ... ({len(lines) - 2}行堆栈省略)\n{lines[-1]}\n"

    result = _TRACEBACK_PATTERN.sub(replace_traceback, text)
    result = _GENERIC_STACK_PATTERN.sub(replace_generic_stack, result)
    return result


# ---------------------------------------------------------------------------
# Thinking block compression
# ---------------------------------------------------------------------------

_THINKING_PATTERN = re.compile(
    r"<details>\s*\n\s*<summary>Full Thinking</summary>\s*\n([\s\S]*?)\n\s*</details>",
    re.IGNORECASE,
)

_THOUGHT_SUMMARY_PATTERN = re.compile(
    r">\s*Thought Summary:\s*(.+?)$",
    re.MULTILINE,
)


def _compress_thinking_blocks(text: str) -> str:
    """Remove full thinking blocks, keep only thought summaries."""

    def replace_thinking(match: re.Match) -> str:
        return "[思考过程已省略]"

    return _THINKING_PATTERN.sub(replace_thinking, text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compress_message(text: str) -> str:
    """Apply all compression rules to a single message text."""
    if not text:
        return text
    if not text.strip():
        return ""

    result = text
    result = _compress_tool_blocks(result)
    result = _compress_code_blocks(result)
    result = _compress_error_stacks(result)
    result = _compress_thinking_blocks(result)

    # Clean up excessive whitespace introduced by replacements
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def compress_messages(messages: Iterable[dict]) -> list[dict]:
    """Compress a list of conversation messages.

    Only assistant messages are compressed; user messages are preserved as-is
    to maintain the original intent and context.
    """
    compressed = []
    for message in messages:
        role = message.get("role", "")
        content = message.get("content", "")

        if role == "assistant" and content:
            compressed_content = compress_message(content)
            compressed.append({"role": role, "content": compressed_content})
        else:
            compressed.append({"role": role, "content": content})

    return compressed


def estimate_tokens(text: str) -> int:
    """Rough token count estimate (1 token ~ 4 chars for English, ~1.5 chars for Chinese)."""
    if not text:
        return 0
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def compression_ratio(original: str, compressed: str) -> float:
    """Calculate the compression ratio (0-1, lower = more compression)."""
    original_tokens = estimate_tokens(original)
    if original_tokens == 0:
        return 1.0
    return estimate_tokens(compressed) / original_tokens
