from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
STATE_PATH = BASE_DIR / "data" / "client_import_state.json"
HOME = Path.home()

SOURCE_DIRS = {
    "codex": HOME / ".codex" / "sessions",
    "claude_code": HOME / ".claude" / "projects",
    "gemini_cli": HOME / ".gemini" / "tmp",
    "antigravity": HOME / ".gemini" / "antigravity" / "conversations",
}
ANTIGRAVITY_BRAIN_DIR = HOME / ".gemini" / "antigravity" / "brain"
ANTIGRAVITY_IMPORTER_VERSION = "ag_live_rpc_v1"
ANTIGRAVITY_CERT_PATH = (
    HOME.parent
    / "wu"
    / "AppData"
    / "Local"
    / "Programs"
    / "Antigravity"
    / "resources"
    / "app"
    / "extensions"
    / "antigravity"
    / "dist"
    / "languageServer"
    / "cert.pem"
)
ANTIGRAVITY_LS_PROCESS_PATTERN = "language_server_windows_x64.exe"
ANTIGRAVITY_SUMMARY_CACHE: dict[str, dict] | None = None


def _is_antigravity_conversation_path(path: Path) -> bool:
    normalized = str(path).lower().replace("/", "\\")
    return "\\.gemini\\antigravity\\conversations\\" in normalized and path.suffix.lower() == ".pb"


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def should_skip(path: Path, state: dict) -> bool:
    key = str(path)
    fingerprint = f"{path.stat().st_mtime_ns}:{path.stat().st_size}"
    saved = state.get(key)
    if _is_antigravity_conversation_path(path):
        return saved == f"{fingerprint}|{ANTIGRAVITY_IMPORTER_VERSION}"
    return saved == fingerprint


def mark_imported(path: Path, state: dict) -> None:
    fingerprint = f"{path.stat().st_mtime_ns}:{path.stat().st_size}"
    if _is_antigravity_conversation_path(path):
        fingerprint = f"{fingerprint}|{ANTIGRAVITY_IMPORTER_VERSION}"
    state[str(path)] = fingerprint


def flatten_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [flatten_text(item) for item in content]
        return "\n\n".join(part for part in parts if part).strip()
    if isinstance(content, dict):
        if "text" in content:
            return flatten_text(content["text"])
        if "content" in content:
            return flatten_text(content["content"])
        if content.get("type") in {"input_text", "output_text", "text"}:
            return flatten_text(content.get("text") or content.get("content"))
    return ""


def normalize_message_text(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""

    skip_prefixes = (
        "# AGENTS.md instructions",
        "<permissions instructions>",
        "<environment_context>",
        "<command-message>",
    )
    if text.startswith(skip_prefixes):
        return ""

    return text


def derive_markdown_title(text: str) -> str:
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            return line.lstrip("#").strip()
        return line[:120].strip()
    return ""


def collapse_messages(messages: Iterable[dict]) -> list[dict]:
    collapsed: list[dict] = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if not role or not content:
            continue
        if collapsed and collapsed[-1]["role"] == role:
            collapsed[-1]["content"] += f"\n\n{content}"
        else:
            collapsed.append({"role": role, "content": content})
    return collapsed


def infer_platform_from_path(path: Path) -> str:
    path_str = str(path).lower()
    if ".codex" in path_str:
        return "codex"
    if ".claude" in path_str:
        return "claude_code"
    if "antigravity" in path_str:
        return "antigravity"
    if ".gemini" in path_str:
        return "gemini_cli"
    return "manual_import"


def list_antigravity_markdown_artifacts(path: Path) -> list[Path]:
    artifacts: list[Path] = []
    for candidate in sorted(path.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        if candidate.name in {"walkthrough.md", "implementation_plan.md"}:
            continue
        artifacts.append(candidate)
    return artifacts


def has_antigravity_artifacts(path: Path) -> bool:
    if (path / "task.md").exists():
        return True
    if list_antigravity_markdown_artifacts(path):
        return True
    if any(path.glob("*.resolved*")):
        return True
    return False


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _load_antigravity_metadata(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def _pick_antigravity_primary_artifact(path: Path) -> Path | None:
    markdown_artifacts = list_antigravity_markdown_artifacts(path)
    if not markdown_artifacts and not (path / "task.md").exists():
        return None

    scored: list[tuple[int, float, Path]] = []
    for candidate in markdown_artifacts:
        metadata_path = path / f"{candidate.name}.metadata.json"
        metadata = _load_antigravity_metadata(metadata_path) if metadata_path.exists() else {}
        summary = str(metadata.get("summary") or "").strip()
        score = 0
        if summary:
            score += 50
        if candidate.name != "task.md":
            score += 30
        if candidate.stem not in {"walkthrough", "implementation_plan"}:
            score += 10
        score += min(int(candidate.stat().st_size / 1024), 20)
        scored.append((score, candidate.stat().st_mtime, candidate))

    if scored:
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored[0][2]

    task_file = path / "task.md"
    return task_file if task_file.exists() else None


def _extract_antigravity_user_prompt(path: Path, primary_artifact: Path | None) -> str:
    task_file = path / "task.md"
    task_text = _read_text_file(task_file) if task_file.exists() else ""
    if task_text:
        return task_text
    if primary_artifact is not None:
        return _read_text_file(primary_artifact)
    return ""


def _extract_antigravity_assistant_chunks(path: Path, primary_artifact: Path | None) -> list[str]:
    chunks: list[str] = []

    def add_chunk(text: str) -> None:
        text = text.strip()
        if text and text not in chunks:
            chunks.append(text)

    if primary_artifact is not None:
        for candidate in sorted(
            path.glob(f"{primary_artifact.name}.resolved*"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )[:4]:
            add_chunk(_read_text_file(candidate))

        if not chunks and primary_artifact.name != "task.md":
            add_chunk(_read_text_file(primary_artifact))

    if not chunks:
        for candidate_name in ("walkthrough.md", "implementation_plan.md"):
            candidate = path / candidate_name
            if candidate.exists():
                add_chunk(_read_text_file(candidate))

    for candidate in sorted((path / "browser").glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)[:3]:
        add_chunk(_read_text_file(candidate))

    if not chunks:
        task_file = path / "task.md"
        for candidate in sorted(path.glob(f"{task_file.name}.resolved*"), key=lambda item: item.stat().st_mtime, reverse=True)[:2]:
            add_chunk(_read_text_file(candidate))

    return chunks


def parse_generic_jsonl(path: Path) -> tuple[list[dict], dict]:
    messages: list[dict] = []
    metadata = {
        "project": path.stem,
        "working_dir": None,
        "timestamp": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        "model": "",
        "assistant_label": "",
        "provider": "",
    }

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        if item.get("isMeta"):
            continue

        item_type = item.get("type")
        if item_type == "session_meta":
            payload = item.get("payload", {})
            metadata["working_dir"] = payload.get("cwd") or metadata["working_dir"]
            metadata["timestamp"] = payload.get("timestamp") or metadata["timestamp"]
            metadata["model"] = payload.get("model") or metadata["model"]
            metadata["provider"] = payload.get("model_provider") or metadata["provider"]
            continue

        role = None
        content = ""

        if item_type in {"user", "assistant"}:
            role = item_type
            message = item.get("message", {})
            if isinstance(message, dict):
                role = message.get("role", role)
                content = flatten_text(message.get("content"))
                metadata["model"] = message.get("model") or metadata["model"]
        elif item_type == "response_item":
            payload = item.get("payload", {})
            if payload.get("type") == "message" and payload.get("role") in {"user", "assistant"}:
                role = payload.get("role")
                content = flatten_text(payload.get("content"))

        content = normalize_message_text(content)
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    if not metadata["assistant_label"]:
        metadata["assistant_label"] = {
            "codex": "Codex",
            "claude_code": "Claude Code",
        }.get(infer_platform_from_path(path), "Assistant")

    return collapse_messages(messages), metadata


def _read_varint(buffer: bytes, offset: int) -> tuple[int, int]:
    shift = 0
    value = 0
    while offset < len(buffer):
        byte = buffer[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return value, offset
        shift += 7
    raise ValueError("Unexpected EOF while reading varint")


def _iter_protobuf_fields(buffer: bytes) -> Iterable[tuple[int, int, object]]:
    offset = 0
    while offset < len(buffer):
        try:
            key, offset = _read_varint(buffer, offset)
        except ValueError:
            return
        field = key >> 3
        wire_type = key & 0x07
        if wire_type == 0:
            try:
                value, offset = _read_varint(buffer, offset)
            except ValueError:
                return
            yield field, wire_type, value
        elif wire_type == 1:
            if offset + 8 > len(buffer):
                return
            yield field, wire_type, buffer[offset:offset + 8]
            offset += 8
        elif wire_type == 2:
            try:
                length, offset = _read_varint(buffer, offset)
            except ValueError:
                return
            if offset + length > len(buffer):
                return
            yield field, wire_type, buffer[offset:offset + length]
            offset += length
        elif wire_type == 5:
            if offset + 4 > len(buffer):
                return
            yield field, wire_type, buffer[offset:offset + 4]
            offset += 4
        else:
            return


def _protobuf_field_values(buffer: bytes, field_number: int, wire_type: int | None = None) -> list[object]:
    values: list[object] = []
    for field, current_wire_type, value in _iter_protobuf_fields(buffer):
        if field != field_number:
            continue
        if wire_type is not None and current_wire_type != wire_type:
            continue
        values.append(value)
    return values


def _decode_text(buffer: bytes) -> str:
    try:
        return buffer.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _unwrap_grpc_message(buffer: bytes) -> bytes:
    if len(buffer) < 5:
        return b""
    frame_length = int.from_bytes(buffer[1:5], "big")
    end = min(len(buffer), 5 + frame_length)
    return buffer[5:end]


def _encode_varint(value: int) -> bytes:
    parts = bytearray()
    while value > 0x7F:
        parts.append((value & 0x7F) | 0x80)
        value >>= 7
    parts.append(value)
    return bytes(parts)


def _encode_string_field(field_number: int, value: str) -> bytes:
    payload = value.encode("utf-8")
    return _encode_varint((field_number << 3) | 2) + _encode_varint(len(payload)) + payload


def _wrap_grpc_request(message: bytes) -> bytes:
    return b"\x00" + len(message).to_bytes(4, "big") + message


def _extract_printable_texts(buffer: bytes, minimum_length: int = 20) -> list[str]:
    try:
        text = buffer.decode("utf-8", errors="ignore")
    except Exception:
        return []
    pattern = rf"[\u4e00-\u9fffA-Za-z0-9`~!@#$%^&*()_+\-=\[\]{{}};':\",./<>?\\| \n\r\t]{{{minimum_length},}}"
    values = []
    for match in re.finditer(pattern, text):
        value = match.group(0).strip()
        if value:
            values.append(value)
    return values


def _extract_timestamp_iso(buffer: bytes) -> str:
    seconds = next((value for value in _protobuf_field_values(buffer, 1, 0) if isinstance(value, int)), 0)
    if not seconds:
        return ""
    nanos = next((value for value in _protobuf_field_values(buffer, 2, 0) if isinstance(value, int)), 0)
    try:
        return datetime.fromtimestamp(seconds + (nanos / 1_000_000_000)).isoformat()
    except Exception:
        return ""


def _discover_antigravity_language_server() -> tuple[str, list[int]] | None:
    powershell_script = r"""
$proc = Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'language_server_windows_x64\.exe' -and $_.CommandLine -match '--csrf_token' } |
  Select-Object -First 1 ProcessId, CommandLine
if (-not $proc) { return }
$ports = Get-NetTCPConnection -State Listen -OwningProcess $proc.ProcessId -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty LocalPort
[pscustomobject]@{
  CommandLine = $proc.CommandLine
  Ports = @($ports | Sort-Object -Unique)
} | ConvertTo-Json -Compress
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", powershell_script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return None

    command_line = str(payload.get("CommandLine") or "")
    token_match = re.search(r"--csrf_token\s+([0-9a-fA-F-]+)", command_line)
    if not token_match:
        return None
    token = token_match.group(1)

    ports = payload.get("Ports") or []
    normalized_ports = []
    for port in ports:
        try:
            normalized_ports.append(int(port))
        except Exception:
            continue
    return token, sorted(set(normalized_ports))


def _call_antigravity_rpc(method: str, request_message: bytes = b"") -> bytes | None:
    discovery = _discover_antigravity_language_server()
    if discovery is None or not ANTIGRAVITY_CERT_PATH.exists():
        return None

    token, ports = discovery
    if not ports:
        return None

    node_script = r"""
const fs = require('node:fs');
const http2 = require('node:http2');

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const payload = Buffer.from(input.payload_b64, 'base64');

async function callPort(port) {
  return await new Promise((resolve) => {
    const client = http2.connect(`https://127.0.0.1:${port}`, {
      ca: fs.readFileSync(input.cert_path),
    });
    client.on('error', () => resolve(null));

    const req = client.request({
      ':method': 'POST',
      ':path': `/exa.language_server_pb.LanguageServerService/${input.method}`,
      'content-type': 'application/grpc+proto',
      'te': 'trailers',
      'user-agent': 'connect-es/2.1.1',
      'x-codeium-csrf-token': input.token,
    });

    const chunks = [];
    let headers = {};
    let trailers = {};

    req.on('response', (value) => { headers = value; });
    req.on('trailers', (value) => { trailers = value; });
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('error', () => {
      try { client.close(); } catch {}
      resolve(null);
    });
    req.on('end', () => {
      try { client.close(); } catch {}
      resolve({
        status: headers[':status'],
        grpc_status: trailers['grpc-status'] || '',
        grpc_message: trailers['grpc-message'] || '',
        body_b64: Buffer.concat(chunks).toString('base64'),
      });
    });
    req.end(payload);
  });
}

(async () => {
  for (const port of input.ports) {
    const result = await callPort(port);
    if (result && result.status === 200 && result.grpc_status === '0') {
      process.stdout.write(JSON.stringify({ ...result, port }));
      return;
    }
  }
  process.stdout.write('');
})();
"""
    request_json = json.dumps(
        {
            "method": method,
            "token": token,
            "ports": ports,
            "cert_path": str(ANTIGRAVITY_CERT_PATH),
            "payload_b64": base64.b64encode(_wrap_grpc_request(request_message)).decode("ascii"),
        }
    )

    try:
        rpc_result = subprocess.run(
            ["node", "-e", node_script],
            input=request_json,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception:
        return None
    if rpc_result.returncode != 0 or not rpc_result.stdout.strip():
        return None
    try:
        data = json.loads(rpc_result.stdout)
    except json.JSONDecodeError:
        return None
    body_b64 = str(data.get("body_b64") or "").strip()
    if not body_b64:
        return None
    try:
        return base64.b64decode(body_b64)
    except Exception:
        return None


def _extract_antigravity_summary_map() -> dict[str, dict]:
    global ANTIGRAVITY_SUMMARY_CACHE
    if ANTIGRAVITY_SUMMARY_CACHE is not None:
        return ANTIGRAVITY_SUMMARY_CACHE

    response = _call_antigravity_rpc("GetAllCascadeTrajectories")
    if not response:
        return {}

    payload = _unwrap_grpc_message(response)
    summaries: dict[str, dict] = {}
    for _, wire_type, value in _iter_protobuf_fields(payload):
        if wire_type != 2 or not isinstance(value, bytes):
            continue
        conversation_id = next((_decode_text(item) for item in _protobuf_field_values(value, 1, 2) if isinstance(item, bytes) and _decode_text(item)), "")
        if not conversation_id:
            continue
        details = next((item for item in _protobuf_field_values(value, 2, 2) if isinstance(item, bytes)), b"")
        title = ""
        timestamp = ""
        if details:
            title = next((_decode_text(item) for item in _protobuf_field_values(details, 1, 2) if _decode_text(item)), "")
            raw_timestamp = next((item for item in _protobuf_field_values(details, 10, 2) if isinstance(item, bytes)), None)
            if raw_timestamp is None:
                raw_timestamp = next((item for item in _protobuf_field_values(details, 7, 2) if isinstance(item, bytes)), None)
            if raw_timestamp is None:
                raw_timestamp = next((item for item in _protobuf_field_values(details, 3, 2) if isinstance(item, bytes)), None)
            if isinstance(raw_timestamp, bytes):
                timestamp = _extract_timestamp_iso(raw_timestamp)
        summaries[conversation_id] = {"title": title or conversation_id, "timestamp": timestamp}
    ANTIGRAVITY_SUMMARY_CACHE = summaries
    return summaries


def _clean_antigravity_text(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    skip_markers = (
        "<EPHEMERAL_MESSAGE>",
        "The following is an <EPHEMERAL_MESSAGE>",
        "The user is asking",
        "The user confirms",
        "no_active_task_reminder",
        "file:///",
    )
    if any(marker in text for marker in skip_markers):
        return ""
    return normalize_message_text(text)


def _extract_antigravity_user_message(step: bytes) -> str:
    container = next((item for item in _protobuf_field_values(step, 19, 2) if isinstance(item, bytes)), b"")
    if not container:
        return ""
    for field_number in (2, 3, 1):
        for candidate in _protobuf_field_values(container, field_number, 2):
            if not isinstance(candidate, bytes):
                continue
            text = _clean_antigravity_text(_decode_text(candidate))
            if text:
                return text
    return ""


def _looks_like_human_answer(text: str) -> bool:
    text = text.strip()
    if len(text) < 20:
        return False
    if text.startswith("The user is "):
        return False
    if text.startswith("file:///"):
        return False
    if text.startswith("Et") or text.startswith("Ev"):
        return False
    return True


def _extract_antigravity_assistant_message(step: bytes) -> str:
    container = next((item for item in _protobuf_field_values(step, 20, 2) if isinstance(item, bytes)), b"")
    if not container:
        return ""
    candidates: list[str] = []
    for field_number in (1, 8, 2, 3):
        for candidate in _protobuf_field_values(container, field_number, 2):
            if not isinstance(candidate, bytes):
                continue
            text = _clean_antigravity_text(_decode_text(candidate))
            if _looks_like_human_answer(text):
                candidates.append(text)
    if not candidates:
        candidates.extend(
            text for text in _extract_printable_texts(container, minimum_length=80)
            if _looks_like_human_answer(_clean_antigravity_text(text))
        )
    unique_candidates = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
    if not unique_candidates:
        return ""
    unique_candidates.sort(key=len, reverse=True)
    return unique_candidates[0]


def _extract_antigravity_step_summary(step: bytes) -> str:
    candidates: list[str] = []
    for field_number in (30,):
        for candidate in _protobuf_field_values(step, field_number, 2):
            if not isinstance(candidate, bytes):
                continue
            for text in _extract_printable_texts(candidate, minimum_length=60):
                cleaned = _clean_antigravity_text(text)
                if cleaned and cleaned not in candidates:
                    candidates.append(cleaned)
    if not candidates:
        return ""
    candidates.sort(key=len, reverse=True)
    return candidates[0]


def _build_antigravity_fallback_user(summary_text: str, project: str) -> str:
    summary_text = _clean_antigravity_text(summary_text)
    if summary_text:
        lines = [line.strip() for line in summary_text.splitlines() if line.strip()]
        if lines:
            return lines[0][:1000]
    return f"Task started: {project}"


def _load_antigravity_transcript(session_id: str) -> tuple[list[dict], dict] | None:
    summaries = _extract_antigravity_summary_map()
    summary = summaries.get(session_id, {})

    response = _call_antigravity_rpc("GetCascadeTrajectorySteps", _encode_string_field(1, session_id))
    if not response:
        return None

    payload = _unwrap_grpc_message(response)
    if not payload:
        return None

    messages: list[dict] = []
    summary_messages: list[str] = []
    for field, wire_type, step in _iter_protobuf_fields(payload):
        if field != 1 or wire_type != 2 or not isinstance(step, bytes):
            continue
        step_type = next((value for value in _protobuf_field_values(step, 1, 0) if isinstance(value, int)), None)
        if step_type == 14:
            text = _extract_antigravity_user_message(step)
            if text:
                messages.append({"role": "user", "content": text})
        elif step_type == 15:
            text = _extract_antigravity_assistant_message(step)
            if text:
                messages.append({"role": "assistant", "content": text})
        elif step_type == 23:
            text = _extract_antigravity_step_summary(step)
            if text and text not in summary_messages:
                summary_messages.append(text)

    recovery_mode = "live-rpc"

    if not any(message["role"] == "user" for message in messages) and summary_messages:
        messages.insert(
            0,
            {
                "role": "user",
                "content": _build_antigravity_fallback_user(summary_messages[0], str(summary.get("title") or session_id)),
            },
        )
        recovery_mode = "live-rpc-summary-fallback"

    if not any(message["role"] == "assistant" for message in messages) and summary_messages:
        messages.append({"role": "assistant", "content": summary_messages[0]})
        recovery_mode = "live-rpc-summary-fallback"

    if len(messages) < 2:
        return None

    metadata = {
        "project": str(summary.get("title") or session_id),
        "working_dir": None,
        "timestamp": str(summary.get("timestamp") or datetime.now().isoformat()),
        "model": "",
        "assistant_label": "Antigravity",
        "provider": "google",
        "source_fingerprint_extra": ANTIGRAVITY_IMPORTER_VERSION,
        "recovery_mode": recovery_mode,
    }
    return collapse_messages(messages), metadata


def parse_antigravity_session(path: Path) -> tuple[list[dict], dict] | None:
    session_id = path.stem
    transcript = _load_antigravity_transcript(session_id)
    if transcript is not None:
        messages, metadata = transcript
        metadata.setdefault("source_fingerprint_extra", ANTIGRAVITY_IMPORTER_VERSION)
        return collapse_messages(messages), metadata

    metadata = {
        "project": session_id,
        "working_dir": None,
        "timestamp": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        "model": "",
        "assistant_label": "Antigravity",
        "provider": "google",
        "source_fingerprint_extra": ANTIGRAVITY_IMPORTER_VERSION,
        "recovery_mode": "pb-undecoded",
    }
    messages = [
        {
            "role": "user",
            "content": (
                f"Antigravity session {session_id} exists locally as a .pb conversation file, "
                "but the transcript could not be fetched from the live language server."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "This import intentionally excludes brain artifacts because they are not the "
                "original conversation transcript."
            ),
        },
    ]
    return collapse_messages(messages), metadata


def parse_gemini_session(path: Path) -> tuple[list[dict], dict] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None

    raw_messages = payload.get("messages")
    if not isinstance(raw_messages, list):
        return None

    messages: list[dict] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue

        message_type = str(item.get("type") or "").strip().lower()
        role = "assistant" if message_type == "gemini" else "user" if message_type == "user" else None
        if not role:
            continue

        content = normalize_message_text(flatten_text(item.get("content")))
        if content:
            messages.append({"role": role, "content": content})

    project = path.parent.parent.name if path.parent.name == "chats" and path.parent.parent else path.stem
    metadata = {
        "project": project,
        "working_dir": None,
        "timestamp": payload.get("lastUpdated") or payload.get("startTime") or datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        "model": "",
        "assistant_label": "Gemini CLI",
        "provider": "google",
    }

    last_message = next(
        (item for item in reversed(raw_messages) if isinstance(item, dict) and str(item.get("type") or "").strip().lower() == "gemini"),
        None,
    )
    if isinstance(last_message, dict):
        metadata["model"] = str(last_message.get("model") or "").strip()

    return collapse_messages(messages), metadata


def iter_source_items(source: str) -> Iterable[Path]:
    base = SOURCE_DIRS[source]
    if not base.exists():
        return []
    if source in {"codex", "claude_code"}:
        return sorted(base.rglob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    if source == "antigravity":
        return sorted(base.glob("*.pb"), key=lambda item: item.stat().st_mtime, reverse=True)
    if source == "gemini_cli":
        return sorted(base.rglob("session-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    return []


def build_payload(path: Path, source: str) -> dict | None:
    if source in {"codex", "claude_code"}:
        messages, metadata = parse_generic_jsonl(path)
    elif source == "gemini_cli":
        parsed = parse_gemini_session(path)
        if not parsed:
            return None
        messages, metadata = parsed
    elif source == "antigravity":
        parsed = parse_antigravity_session(path)
        if not parsed:
            return None
        messages, metadata = parsed
    else:
        return None

    if len(messages) < 2:
        return None

    full_content = "\n\n".join([
        f"{message['role']}: {message['content']}"
        for message in messages
    ])

    source_fingerprint = f"{path.stat().st_mtime_ns}:{path.stat().st_size}"
    if metadata.get("source_fingerprint_extra"):
        source_fingerprint = f"{source_fingerprint}|{metadata['source_fingerprint_extra']}"

    return {
        "platform": source,
        "timestamp": metadata["timestamp"],
        "messages": messages,
        "working_dir": metadata["working_dir"],
        "project": metadata["project"],
        "provider": metadata["provider"],
        "model": metadata["model"],
        "assistant_label": metadata["assistant_label"],
        "summary": metadata["project"],
        "recovery_mode": metadata.get("recovery_mode"),
        "source_path": str(path),
        "source_fingerprint": source_fingerprint,
        "content_hash": hashlib.sha256(full_content.encode("utf-8")).hexdigest(),
    }


def import_sources(
    sources: list[str],
    limit: int,
    dry_run: bool,
    persist_callback,
) -> dict:
    state = load_state()
    summary = []

    for source in sources:
        imported = 0
        scanned = 0
        detected = 0
        imported_items: list[str] = []
        imported_conversation_ids: list[str] = []

        for path in iter_source_items(source):
            if limit and scanned >= limit:
                break
            scanned += 1

            if should_skip(path, state):
                continue

            payload = build_payload(path, source)
            if not payload:
                continue

            detected += 1

            if dry_run:
                imported += 1
                imported_items.append(str(path))
                continue

            conversation_id = persist_callback(payload)
            mark_imported(path, state)
            imported += 1
            imported_items.append(str(path))
            if conversation_id:
                imported_conversation_ids.append(str(conversation_id))

        summary.append(
            {
                "source": source,
                "scanned": scanned,
                "detected": detected,
                "imported": imported,
                "items": imported_items[:10],
                "conversation_ids": imported_conversation_ids[:50],
                "note": "no local transcript files found" if source == "gemini_cli" and detected == 0 else "",
            }
        )

    if not dry_run:
        save_state(state)

    return {"sources": summary}
