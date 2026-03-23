from __future__ import annotations

import json
import os
import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
import shutil


DEFAULT_BACKUP_SETTINGS = {
    "enabled": False,
    "interval_hours": 24,
    "retention_count": 10,
    "backup_root": None,
    "last_run_at": None,
    "last_backup_dir": None,
    "last_backup_zip": None,
    "last_error": "",
}


def _settings_path(data_dir: Path) -> Path:
    return data_dir / "backup_settings.json"


def load_backup_settings(data_dir: Path) -> dict:
    path = _settings_path(data_dir)
    if not path.exists():
        return dict(DEFAULT_BACKUP_SETTINGS)

    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_BACKUP_SETTINGS)

    settings = dict(DEFAULT_BACKUP_SETTINGS)
    settings.update({key: stored.get(key) for key in settings.keys() if key in stored})
    return settings


def save_backup_settings(data_dir: Path, updates: dict) -> dict:
    settings = load_backup_settings(data_dir)
    settings.update(updates)
    path = _settings_path(data_dir)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings


def _resolve_backup_root(data_dir: Path, settings: dict | None = None) -> Path:
    settings = settings or load_backup_settings(data_dir)
    configured = settings.get("backup_root")
    if configured:
        return Path(configured)
    return data_dir / "backups"


def list_backups(data_dir: Path) -> list[dict]:
    backups_dir = _resolve_backup_root(data_dir)
    if not backups_dir.exists():
        return []

    items = []
    for entry in sorted(backups_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not entry.is_dir():
            continue
        items.append(
            {
                "path": str(entry),
                "name": entry.name,
                "modified_at": datetime.fromtimestamp(entry.stat().st_mtime).isoformat(),
                "zip_path": str(entry.with_suffix(".zip")) if entry.with_suffix(".zip").exists() else None,
            }
        )
    return items


def _prune_old_backups(data_dir: Path, retention_count: int) -> None:
    if retention_count < 1:
        retention_count = 1

    backups = list_backups(data_dir)
    for item in backups[retention_count:]:
        path = Path(item["path"])
        zip_path = Path(item["zip_path"]) if item.get("zip_path") else None
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                child.rmdir()
        path.rmdir()
        if zip_path and zip_path.exists():
            zip_path.unlink(missing_ok=True)


def _create_backup_zip(bundle_dir: Path) -> Path:
    zip_path = bundle_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in bundle_dir.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, arcname=file_path.relative_to(bundle_dir))
    return zip_path


def create_backup_bundle(db_connection, data_dir: Path) -> dict:
    settings = load_backup_settings(data_dir)
    backups_dir = _resolve_backup_root(data_dir, settings)
    backups_dir.mkdir(parents=True, exist_ok=True)

    bundle_dir = None
    for attempt in range(10):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        candidate = backups_dir / f"memory-backup-{timestamp}"
        if attempt:
            candidate = backups_dir / f"memory-backup-{timestamp}-{attempt}"
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            bundle_dir = candidate
            break
        except FileExistsError:
            continue

    if bundle_dir is None:
        raise FileExistsError("Failed to create a unique backup directory")

    cursor = db_connection.execute(
        """
        SELECT id, platform, timestamp, project, working_dir, provider, model,
               assistant_label, summary, full_content, importance, status, created_at
        FROM conversations
        ORDER BY timestamp DESC
        """
    )
    records = [dict(row) for row in cursor.fetchall()]

    conversations_path = bundle_dir / "conversations.jsonl"
    with conversations_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    manifest = {
        "created_at": datetime.now().isoformat(),
        "conversation_count": len(records),
        "files": {
            "conversations_jsonl": str(conversations_path),
        },
    }

    source_db_path = data_dir / "memory.db"
    db_backup_path = bundle_dir / "memory.db"
    if source_db_path.exists():
        source_conn = sqlite3.connect(str(source_db_path))
        try:
            target_conn = sqlite3.connect(str(db_backup_path))
            try:
                source_conn.backup(target_conn)
            finally:
                target_conn.close()
        finally:
            source_conn.close()
        manifest["files"]["memory_db"] = str(db_backup_path)

    import_state_path = data_dir / "client_import_state.json"
    if import_state_path.exists():
        copied_state = bundle_dir / "client_import_state.json"
        copied_state.write_text(import_state_path.read_text(encoding="utf-8"), encoding="utf-8")
        manifest["files"]["client_import_state"] = str(copied_state)

    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    zip_path = _create_backup_zip(bundle_dir)
    settings = save_backup_settings(
        data_dir,
        {
            "last_run_at": datetime.now().isoformat(),
            "last_backup_dir": str(bundle_dir),
            "last_backup_zip": str(zip_path),
            "last_error": "",
        },
    )
    _prune_old_backups(data_dir, int(settings.get("retention_count") or DEFAULT_BACKUP_SETTINGS["retention_count"]))

    return {
        "backup_dir": str(bundle_dir),
        "backup_zip": str(zip_path),
        "conversation_count": len(records),
        "files": manifest["files"],
        "manifest_path": str(manifest_path),
    }


def should_run_scheduled_backup(settings: dict, now: datetime | None = None) -> bool:
    if not settings.get("enabled"):
        return False

    now = now or datetime.now()
    interval_hours = max(1, int(settings.get("interval_hours") or DEFAULT_BACKUP_SETTINGS["interval_hours"]))
    last_run_at = settings.get("last_run_at")
    if not last_run_at:
        return True

    try:
        last_run = datetime.fromisoformat(last_run_at)
    except ValueError:
        return True

    return now - last_run >= timedelta(hours=interval_hours)


def run_scheduled_backup_if_due(db_connection, data_dir: Path) -> dict | None:
    settings = load_backup_settings(data_dir)
    if not should_run_scheduled_backup(settings):
        return None

    try:
        return create_backup_bundle(db_connection, data_dir)
    except Exception as exc:
        save_backup_settings(
            data_dir,
            {
                "last_run_at": datetime.now().isoformat(),
                "last_error": str(exc),
            },
        )
        raise


def restore_backup_bundle(data_dir: Path, backup_dir: Path) -> dict:
    backup_dir = Path(backup_dir)
    backup_db_path = backup_dir / "memory.db"
    if not backup_dir.exists() or not backup_dir.is_dir():
        raise FileNotFoundError(f"Backup directory not found: {backup_dir}")
    if not backup_db_path.exists():
        raise FileNotFoundError(f"Backup database not found: {backup_db_path}")

    target_db_path = data_dir / "memory.db"
    source_conn = sqlite3.connect(str(backup_db_path))
    try:
        target_conn = sqlite3.connect(str(target_db_path))
        try:
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
    finally:
        source_conn.close()

    backup_state_path = backup_dir / "client_import_state.json"
    if backup_state_path.exists():
        (data_dir / "client_import_state.json").write_text(
            backup_state_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    return {
        "restored_from": str(backup_dir),
        "restored_at": datetime.now().isoformat(),
        "restored_db_path": str(target_db_path),
    }


def restore_backup_source(data_dir: Path, source_path: Path) -> dict:
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Backup source not found: {source_path}")

    if source_path.is_dir():
        result = restore_backup_bundle(data_dir, source_path)
        result["source_type"] = "directory"
        return result

    if source_path.is_file() and source_path.suffix.lower() == ".zip":
        temp_root = data_dir / "restore-temp"
        temp_root.mkdir(parents=True, exist_ok=True)
        extract_dir = temp_root / f"restore-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
        extract_dir.mkdir(parents=True, exist_ok=False)
        try:
            with zipfile.ZipFile(source_path, "r") as archive:
                extract_path = Path(extract_dir).resolve()
                for member in archive.namelist():
                    member_path = (extract_path / member).resolve()
                    if not member_path.is_relative_to(extract_path):
                        raise ValueError(f"Zip Slip path traversal detected: {member}")
                archive.extractall(extract_dir)
            result = restore_backup_bundle(data_dir, extract_dir)
            result["restored_from"] = str(source_path)
            result["restored_from_zip"] = str(source_path)
            result["source_type"] = "zip"
            return result
        finally:
            shutil.rmtree(extract_dir, ignore_errors=True)

    raise FileNotFoundError(f"Unsupported backup source: {source_path}")


def read_backup_manifest(source_path: Path) -> dict:
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Backup source not found: {source_path}")

    if source_path.is_dir():
        manifest_path = source_path / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found in backup directory: {source_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            "source_type": "directory",
            "source_path": str(source_path),
            "manifest": manifest,
        }

    if source_path.is_file() and source_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(source_path, "r") as archive:
            try:
                manifest_text = archive.read("manifest.json").decode("utf-8")
            except KeyError as exc:
                raise FileNotFoundError(f"Manifest not found in backup zip: {source_path}") from exc
        manifest = json.loads(manifest_text)
        return {
            "source_type": "zip",
            "source_path": str(source_path),
            "manifest": manifest,
        }

    raise FileNotFoundError(f"Unsupported backup source: {source_path}")


def validate_backup_source(source_path: Path) -> dict:
    source_path = Path(source_path)
    preview = read_backup_manifest(source_path)
    manifest = preview["manifest"]

    errors: list[str] = []
    checks: dict[str, bool] = {
        "manifest_readable": True,
        "conversation_count_matches": False,
        "has_memory_db": False,
        "has_conversations_jsonl": False,
    }
    jsonl_count = 0

    if preview["source_type"] == "directory":
        backup_dir = source_path
        jsonl_path = backup_dir / "conversations.jsonl"
        db_path = backup_dir / "memory.db"

        checks["has_conversations_jsonl"] = jsonl_path.exists()
        checks["has_memory_db"] = db_path.exists()

        if jsonl_path.exists():
            jsonl_count = sum(1 for line in jsonl_path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())
    else:
        with zipfile.ZipFile(source_path, "r") as archive:
            names = set(archive.namelist())
            checks["has_conversations_jsonl"] = "conversations.jsonl" in names
            checks["has_memory_db"] = "memory.db" in names

            if checks["has_conversations_jsonl"]:
                jsonl_text = archive.read("conversations.jsonl").decode("utf-8", errors="ignore")
                jsonl_count = sum(1 for line in jsonl_text.splitlines() if line.strip())

    expected_count = int(manifest.get("conversation_count") or 0)
    checks["conversation_count_matches"] = jsonl_count == expected_count

    if not checks["has_conversations_jsonl"]:
        errors.append("Missing conversations.jsonl")
    if not checks["has_memory_db"]:
        errors.append("Missing memory.db")
    if not checks["conversation_count_matches"]:
        errors.append(f"Manifest conversation_count={expected_count}, but jsonl has {jsonl_count} rows")

    return {
        "source_type": preview["source_type"],
        "source_path": preview["source_path"],
        "valid": not errors,
        "checks": checks,
        "manifest_conversation_count": expected_count,
        "jsonl_conversation_count": jsonl_count,
        "errors": errors,
    }
