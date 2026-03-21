#!/usr/bin/env python3
"""CLI entrypoint for importing local client sessions into Memory Hub."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import requests

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from local_importer import import_sources  # noqa: E402

MEMORY_HUB_URL = "http://127.0.0.1:8765"


def send_payload(payload: dict) -> bool:
    response = requests.post(f"{MEMORY_HUB_URL}/api/conversations", json=payload, timeout=20)
    response.raise_for_status()
    return True


def import_via_backend(source: str, limit: int, dry_run: bool) -> dict | None:
    response = requests.post(
        f"{MEMORY_HUB_URL}/api/import/local",
        json={
            "source": source,
            "limit": limit,
            "dry_run": dry_run,
            "auto_summarize": True,
        },
        timeout=120,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import local client sessions into Memory Hub")
    parser.add_argument("--source", choices=["all", "codex", "claude_code", "gemini_cli", "antigravity"], default="all")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    backend_result = import_via_backend(args.source, args.limit, args.dry_run)
    if backend_result is not None:
        result = backend_result
    else:
        selected_sources = ["codex", "claude_code", "gemini_cli", "antigravity"] if args.source == "all" else [args.source]
        result = import_sources(selected_sources, args.limit, args.dry_run, send_payload)

    print("\nSummary")
    for item in result["sources"]:
        note = f", note={item['note']}" if item.get("note") else ""
        print(
            f"- {item['source']}: scanned={item['scanned']}, "
            f"detected={item['detected']}, imported={item['imported']}{note}"
        )


if __name__ == "__main__":
    main()
