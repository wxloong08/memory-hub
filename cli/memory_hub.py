#!/usr/bin/env python3
"""
memory-hub -- CLI tool for Memory Hub V2.

Quick switch between AI CLIs with full context continuity.

Usage:
    memory-hub switch --to <cli> [--workspace <path>] [--budget <tokens>]
    memory-hub status [--workspace <path>]
    memory-hub save-state --task <desc> [--plan <steps>] [--workspace <path>]
    memory-hub import --source <src> [--limit <n>]
    memory-hub search <query> [--limit <n>]
    memory-hub history [--limit <n>]
"""

from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlencode
import sys
from pathlib import Path

# Add backend to Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

MEMORY_HUB_URL = os.environ.get("MEMORY_HUB_URL", "http://localhost:8765")


def _api_request(method: str, path: str, data: dict | None = None) -> dict:
    """Make an HTTP request to the Memory Hub API."""
    import urllib.request
    import urllib.error

    url = f"{MEMORY_HUB_URL}{path}"
    headers = {"Content-Type": "application/json"}

    if data is not None:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
    else:
        req = urllib.request.Request(url, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Error: API returned {exc.code}")
        print(f"  {body}")
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Error: Cannot connect to Memory Hub at {MEMORY_HUB_URL}")
        print(f"  Make sure the server is running: uvicorn main:app --port 8765")
        print(f"  Details: {exc}")
        sys.exit(1)


def _check_health() -> bool:
    """Check if Memory Hub is running."""
    try:
        result = _api_request("GET", "/health")
        return result.get("status") == "healthy"
    except SystemExit:
        return False


def cmd_switch(args: argparse.Namespace) -> None:
    """Execute a CLI switch."""
    workspace = args.workspace or os.getcwd()
    workspace = str(Path(workspace).resolve())

    print(f"Switching to {args.to}...")
    print(f"  Workspace: {workspace}")

    payload = {
        "to_cli": args.to,
        "workspace_path": workspace,
    }
    if args.budget:
        payload["token_budget"] = args.budget
    if args.turns:
        payload["include_archive_turns"] = args.turns

    if args.preview:
        params = urlencode({"to_cli": args.to, "workspace_path": workspace})
        result = _api_request("GET", f"/api/v2/switch/preview?{params}")
        print(f"\n--- Preview (dry run) ---")
        print(f"  Target file: {result.get('target_file', 'N/A')}")
        ctx = result.get("context_assembled", {})
        print(f"  Working memory: {ctx.get('working_memory_tokens', 0)} tokens")
        print(f"  Core memories: {ctx.get('core_memory_tokens', 0)} tokens ({result.get('core_memories_injected', 0)} items)")
        print(f"  Archive: {ctx.get('archive_tokens', 0)} tokens ({result.get('archive_turns_injected', 0)} turns)")
        print(f"  Total: {ctx.get('total_tokens', 0)} tokens")
        if args.verbose:
            print(f"\n--- Content ---")
            print(result.get("content_preview", ""))
        return

    result = _api_request("POST", "/api/v2/switch", payload)

    if result.get("status") == "ok":
        ctx = result.get("context_assembled", {})
        print(f"\n  Switch #{result.get('switch_number', '?')} completed!")
        print(f"  Target file: {result.get('target_file', 'N/A')}")
        print(f"  Tokens injected: {ctx.get('total_tokens', 0)}")
        print(f"    Working memory: {ctx.get('working_memory_tokens', 0)}")
        print(f"    Core memories: {ctx.get('core_memory_tokens', 0)} ({result.get('core_memories_injected', 0)} items)")
        print(f"    Archive: {ctx.get('archive_tokens', 0)} ({result.get('archive_turns_injected', 0)} turns)")
        if not args.quiet:
            print(f"\n  Now start {args.to} in: {workspace}")
    else:
        print(f"  Switch failed: {result}")
        sys.exit(1)


def cmd_status(args: argparse.Namespace) -> None:
    """Show current working memory status."""
    workspace = args.workspace or os.getcwd()
    workspace = str(Path(workspace).resolve())

    # URL-encode the workspace path
    import urllib.parse
    encoded = urllib.parse.quote(workspace, safe="")

    result = _api_request("GET", f"/api/v2/working-memory/{encoded}")

    if not result or result.get("detail") == "No working memory found":
        print(f"No working memory for: {workspace}")
        return

    print(f"Working Memory: {workspace}")
    print(f"  Task: {result.get('active_task', 'None')}")
    print(f"  Last CLI: {result.get('last_cli', 'None')}")
    print(f"  Switches: {result.get('switch_count', 0)}")
    print(f"  Updated: {result.get('updated_at', 'N/A')}")

    plan = result.get("current_plan")
    if plan:
        print(f"  Plan:")
        if isinstance(plan, list):
            for i, step in enumerate(plan, 1):
                print(f"    {i}. {step}")
        else:
            print(f"    {plan}")

    progress = result.get("progress")
    if progress:
        print(f"  Completed:")
        if isinstance(progress, list):
            for item in progress:
                print(f"    - {item}")

    issues = result.get("open_issues")
    if issues:
        print(f"  Open Issues:")
        if isinstance(issues, list):
            for item in issues:
                print(f"    - {item}")


def cmd_save_state(args: argparse.Namespace) -> None:
    """Save current working state."""
    workspace = args.workspace or os.getcwd()
    workspace = str(Path(workspace).resolve())

    import urllib.parse
    encoded = urllib.parse.quote(workspace, safe="")

    payload: dict = {"workspace_path": workspace}
    if args.task:
        payload["active_task"] = args.task
    if args.plan:
        payload["current_plan"] = [s.strip() for s in args.plan.split(",")]
    if args.cli:
        payload["last_cli"] = args.cli

    result = _api_request("PUT", f"/api/v2/working-memory/{encoded}", payload)
    print(f"Working memory saved for: {workspace}")
    if args.task:
        print(f"  Task: {args.task}")


def cmd_import(args: argparse.Namespace) -> None:
    """Import local CLI sessions."""
    payload = {
        "source": args.source,
        "limit": args.limit,
    }
    result = _api_request("POST", "/api/v2/import/local", payload)
    imported = result.get("imported", 0)
    skipped = result.get("skipped", 0)
    print(f"Import complete: {imported} imported, {skipped} skipped")


def cmd_search(args: argparse.Namespace) -> None:
    """Search conversations."""
    import urllib.parse
    query = urllib.parse.quote(args.query)
    result = _api_request("GET", f"/api/search?query={query}&limit={args.limit}")

    results = result.get("results", [])
    memories = result.get("memory_results", [])

    if not results and not memories:
        print(f"No results for: {args.query}")
        return

    if results:
        print(f"Conversations ({len(results)}):")
        for r in results:
            print(f"  [{r.get('platform', '?')}] {r.get('summary', 'No summary')}")
            print(f"    Importance: {r.get('importance', '?')}/10  |  {r.get('timestamp', '')}")

    if memories:
        print(f"\nMemories ({len(memories)}):")
        for m in memories:
            print(f"  [{m.get('category', '?')}] {m.get('key', '')}: {m.get('value', '')}")


def cmd_history(args: argparse.Namespace) -> None:
    """Show switch history."""
    result = _api_request("GET", f"/api/v2/switch/history?limit={args.limit}")
    history = result.get("history", [])

    if not history:
        print("No switch history found.")
        return

    print(f"Switch History ({len(history)} entries):")
    for entry in history:
        from_cli = entry.get("from_cli", "?")
        to_cli = entry.get("to_cli", "?")
        workspace = entry.get("workspace_path", "?")
        tokens = entry.get("tokens_injected", 0)
        when = entry.get("switched_at", "?")
        print(f"  {from_cli} -> {to_cli}  |  {tokens} tokens  |  {when}")
        print(f"    Workspace: {workspace}")


def main():
    global MEMORY_HUB_URL

    parser = argparse.ArgumentParser(
        prog="memory-hub",
        description="Memory Hub V2 -- CLI tool for cross-CLI context switching",
    )
    parser.add_argument("--url", default=MEMORY_HUB_URL, help="Memory Hub API URL")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # switch
    switch_parser = subparsers.add_parser("switch", help="Switch to another CLI with context")
    switch_parser.add_argument("--to", required=True, choices=["claude_code", "codex", "gemini_cli", "antigravity"],
                               help="Target CLI")
    switch_parser.add_argument("--workspace", "-w", help="Workspace path (default: cwd)")
    switch_parser.add_argument("--budget", type=int, help="Override token budget")
    switch_parser.add_argument("--turns", type=int, help="Max archive turns to include")
    switch_parser.add_argument("--preview", action="store_true", help="Dry run (don't write files)")
    switch_parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    switch_parser.add_argument("--verbose", "-v", action="store_true", help="Show full content")

    # status
    status_parser = subparsers.add_parser("status", help="Show working memory status")
    status_parser.add_argument("--workspace", "-w", help="Workspace path (default: cwd)")

    # save-state
    save_parser = subparsers.add_parser("save-state", help="Save working state manually")
    save_parser.add_argument("--task", help="Current task description")
    save_parser.add_argument("--plan", help="Comma-separated plan steps")
    save_parser.add_argument("--cli", help="Current CLI name")
    save_parser.add_argument("--workspace", "-w", help="Workspace path (default: cwd)")

    # import
    import_parser = subparsers.add_parser("import", help="Import local CLI sessions")
    import_parser.add_argument("--source", default="all",
                               choices=["all", "claude_code", "codex", "gemini_cli", "antigravity"],
                               help="Import source")
    import_parser.add_argument("--limit", type=int, default=20, help="Max sessions to import")

    # search
    search_parser = subparsers.add_parser("search", help="Search conversations")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=5, help="Max results")

    # history
    history_parser = subparsers.add_parser("history", help="Show switch history")
    history_parser.add_argument("--limit", type=int, default=20, help="Max entries")

    args = parser.parse_args()

    if args.url:
        MEMORY_HUB_URL = args.url

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if not _check_health():
        print("Error: Memory Hub is not running.")
        print(f"  Start it with: cd backend && uvicorn main:app --port 8765")
        sys.exit(1)

    commands = {
        "switch": cmd_switch,
        "status": cmd_status,
        "save-state": cmd_save_state,
        "import": cmd_import,
        "search": cmd_search,
        "history": cmd_history,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
