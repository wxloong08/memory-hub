"""
Memory Hub V2 -- Content Compression Engine

Thin compatibility layer over message_compressor.py (created by dev-sync).
Adds additional utilities for the context assembly and switch engine.
"""

from __future__ import annotations

# Re-export core functions from message_compressor for backward compat
from message_compressor import (
    compress_message,
    compress_messages,
    estimate_tokens,
    compression_ratio,
)


def get_display_content(message: dict) -> str:
    """Get the best content to display for a message (compressed if available)."""
    return message.get("compressed") or message.get("content", "")
