"""
Tests for client_exports module
Tests export profile selection, memory ranking, and markdown generation
"""

import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from client_exports import (
    CLIENT_EXPORT_PROFILES,
    build_export_package,
    build_memory_section,
    build_resume_markdown,
    get_export_profile,
    parse_full_content,
    select_relevant_memories,
    apply_export_package,
)


class TestGetExportProfile:
    """Test export profile lookup"""

    def test_get_claude_code_profile(self):
        profile = get_export_profile("claude_code")
        assert profile.client_id == "claude_code"
        assert profile.filename == "CLAUDE.md"
        assert profile.target_relpath == ".claude/CLAUDE.md"

    def test_get_codex_profile(self):
        profile = get_export_profile("codex")
        assert profile.client_id == "codex"
        assert profile.filename == "AGENTS.md"

    def test_get_gemini_cli_profile(self):
        profile = get_export_profile("gemini_cli")
        assert profile.client_id == "gemini_cli"
        assert profile.filename == "GEMINI.md"

    def test_unsupported_client_raises(self):
        with pytest.raises(ValueError, match="Unsupported export client"):
            get_export_profile("unknown_client")

    def test_case_insensitive(self):
        profile = get_export_profile("Claude_Code")
        assert profile.client_id == "claude_code"

    def test_all_profiles_have_required_fields(self):
        for client_id, profile in CLIENT_EXPORT_PROFILES.items():
            assert profile.client_id
            assert profile.display_name
            assert profile.target_relpath
            assert profile.filename
            assert profile.format_hint
            assert profile.description


class TestParseFullContent:
    """Test conversation content parsing"""

    def test_basic_parsing(self):
        content = "user: Hello\nassistant: Hi there!"
        messages = parse_full_content(content)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"

    def test_multiline_content(self):
        content = "user: Line 1\nLine 2\nLine 3\nassistant: Response"
        messages = parse_full_content(content)
        assert len(messages) == 2
        assert "Line 2" in messages[0]["content"]
        assert "Line 3" in messages[0]["content"]

    def test_empty_content(self):
        messages = parse_full_content("")
        assert messages == []

    def test_none_content(self):
        messages = parse_full_content(None)
        assert messages == []


class TestSelectRelevantMemories:
    """Test memory selection and ranking"""

    @pytest.fixture
    def sample_conversation(self):
        return {
            "platform": "codex",
            "project": "web-app",
            "summary": "Building a FastAPI web application",
            "full_content": "user: Build a FastAPI app\nassistant: Sure, let's start...",
            "model": "gpt-5",
            "provider": "openai",
        }

    @pytest.fixture
    def sample_memories(self):
        return [
            {"id": 1, "category": "workflow", "key": "coding_style", "value": "Prefer concise code", "confidence": 0.9, "priority": 0, "client_rules": {}},
            {"id": 2, "category": "preference", "key": "framework", "value": "Use FastAPI for web apps", "confidence": 0.8, "priority": 0, "client_rules": {}},
            {"id": 3, "category": "identity", "key": "role", "value": "Senior engineer", "confidence": 0.95, "priority": 0, "client_rules": {}},
            {"id": 4, "category": "avoid", "key": "no_django", "value": "Avoid Django", "confidence": 0.7, "priority": 0, "client_rules": {}},
        ]

    def test_selects_up_to_limit(self, sample_conversation, sample_memories):
        profile = get_export_profile("claude_code")
        selected = select_relevant_memories(sample_conversation, sample_memories, profile, limit=2)
        assert len(selected) <= 2

    def test_empty_memories(self, sample_conversation):
        profile = get_export_profile("claude_code")
        selected = select_relevant_memories(sample_conversation, [], profile)
        assert selected == []

    def test_forced_include(self, sample_conversation, sample_memories):
        sample_memories[0]["client_rules"] = {"codex": "include"}
        profile = get_export_profile("codex")
        selected = select_relevant_memories(sample_conversation, sample_memories, profile, limit=2)
        assert any(m["id"] == 1 for m in selected)

    def test_exclude_respected(self, sample_conversation, sample_memories):
        sample_memories[0]["client_rules"] = {"codex": "exclude"}
        profile = get_export_profile("codex")
        selected = select_relevant_memories(sample_conversation, sample_memories, profile)
        assert not any(m["id"] == 1 for m in selected)


class TestBuildMemorySection:
    """Test memory section markdown generation"""

    def test_empty_memories(self):
        result = build_memory_section([])
        assert "No pinned memories" in result

    def test_single_memory(self):
        memories = [{"category": "workflow", "key": "style", "value": "Concise code", "confidence": 0.9}]
        result = build_memory_section(memories)
        assert "### workflow" in result
        assert "**style**" in result
        assert "Concise code" in result

    def test_grouped_by_category(self):
        memories = [
            {"category": "workflow", "key": "k1", "value": "v1", "confidence": 0.5},
            {"category": "identity", "key": "k2", "value": "v2", "confidence": 0.8},
            {"category": "workflow", "key": "k3", "value": "v3", "confidence": 0.6},
        ]
        result = build_memory_section(memories)
        assert "### identity" in result
        assert "### workflow" in result

    def test_pinned_memory(self):
        memories = [{"category": "general", "key": "note", "value": "Important", "priority": 1}]
        result = build_memory_section(memories)
        assert "[Pinned]" in result


class TestBuildResumeMarkdown:
    """Test resume markdown generation"""

    @pytest.fixture
    def sample_conversation(self):
        return {
            "platform": "codex",
            "project": "test-project",
            "summary": "Test conversation summary",
            "full_content": "user: Hello\nassistant: Hi!",
            "provider": "openai",
            "model": "gpt-5",
            "assistant_label": "Codex",
            "timestamp": "2026-03-10T10:00:00",
        }

    def test_contains_required_sections(self, sample_conversation):
        profile = get_export_profile("codex")
        result = build_resume_markdown(sample_conversation, profile)
        assert "# Resume Context" in result
        assert "## Usage" in result
        assert "## Metadata" in result
        assert "## Summary" in result
        assert "## Pinned Memory" in result
        assert "## Transcript" in result

    def test_contains_metadata(self, sample_conversation):
        profile = get_export_profile("codex")
        result = build_resume_markdown(sample_conversation, profile)
        assert "codex" in result
        assert "openai" in result
        assert "gpt-5" in result
        assert "test-project" in result

    def test_with_memories(self, sample_conversation):
        profile = get_export_profile("codex")
        memories = [{"category": "workflow", "key": "style", "value": "Be concise", "confidence": 0.9}]
        result = build_resume_markdown(sample_conversation, profile, memories)
        assert "Be concise" in result


class TestBuildExportPackage:
    """Test export package building"""

    @pytest.fixture
    def sample_conversation(self):
        return {
            "platform": "codex",
            "project": "test-project",
            "summary": "Test summary",
            "full_content": "user: Hello\nassistant: Hi!",
            "provider": "openai",
            "model": "gpt-5",
            "assistant_label": "Codex",
            "timestamp": "2026-03-10T10:00:00",
        }

    def test_package_structure(self, sample_conversation):
        package = build_export_package(sample_conversation, "codex")
        assert package["client"] == "codex"
        assert package["filename"] == "AGENTS.md"
        assert "content" in package
        assert "memory_count" in package
        assert "total_memory_count" in package
        assert "selected_memory_ids" in package

    def test_package_with_memories(self, sample_conversation):
        memories = [
            {"id": 1, "category": "workflow", "key": "k", "value": "v", "confidence": 0.9, "priority": 0, "client_rules": {}},
        ]
        package = build_export_package(sample_conversation, "codex", memories)
        assert package["total_memory_count"] == 1

    def test_package_with_explicit_memory_ids(self, sample_conversation):
        memories = [
            {"id": 1, "category": "workflow", "key": "k1", "value": "v1", "confidence": 0.9, "priority": 0, "client_rules": {}},
            {"id": 2, "category": "general", "key": "k2", "value": "v2", "confidence": 0.5, "priority": 0, "client_rules": {}},
        ]
        package = build_export_package(sample_conversation, "codex", memories, selected_memory_ids=[1])
        assert package["selected_memory_ids"] == [1]
        assert package["memory_count"] == 1


class TestApplyExportPackage:
    """Test applying export to filesystem"""

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_conversation(self):
        return {
            "platform": "codex",
            "project": "test",
            "summary": "Test",
            "full_content": "user: Hi\nassistant: Hello!",
            "provider": "openai",
            "model": "gpt-5",
            "assistant_label": "Codex",
            "timestamp": "2026-03-10T10:00:00",
        }

    def test_creates_file(self, temp_workspace, sample_conversation):
        result = apply_export_package(sample_conversation, "codex", temp_workspace)
        target_path = Path(result["target_path"])
        assert target_path.exists()
        assert target_path.name == "AGENTS.md"
        content = target_path.read_text(encoding="utf-8")
        assert "Resume Context" in content

    def test_creates_backup_if_exists(self, temp_workspace, sample_conversation):
        # Create initial file
        apply_export_package(sample_conversation, "codex", temp_workspace)
        # Apply again - should create backup
        result = apply_export_package(sample_conversation, "codex", temp_workspace)
        assert result["backup_path"] is not None
        assert Path(result["backup_path"]).exists()

    def test_claude_code_export(self, temp_workspace, sample_conversation):
        result = apply_export_package(sample_conversation, "claude_code", temp_workspace)
        target_path = Path(result["target_path"])
        assert target_path.exists()
        assert target_path.name == "CLAUDE.md"

    def test_relative_path_raises(self, sample_conversation):
        with pytest.raises(ValueError, match="absolute path"):
            apply_export_package(sample_conversation, "codex", "relative/path")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
