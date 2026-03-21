"""
Tests for local_importer module
Tests conversation parsing, message normalization, and utility functions
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from local_importer import (
    collapse_messages,
    derive_markdown_title,
    flatten_text,
    infer_platform_from_path,
    normalize_message_text,
    parse_generic_jsonl,
)


class TestFlattenText:
    """Test text flattening from various formats"""

    def test_string_input(self):
        assert flatten_text("hello world") == "hello world"

    def test_none_input(self):
        assert flatten_text(None) == ""

    def test_list_of_strings(self):
        result = flatten_text(["hello", "world"])
        assert "hello" in result
        assert "world" in result

    def test_dict_with_text(self):
        result = flatten_text({"text": "hello"})
        assert result == "hello"

    def test_dict_with_content(self):
        result = flatten_text({"content": "hello"})
        assert result == "hello"

    def test_dict_with_type_and_text(self):
        result = flatten_text({"type": "input_text", "text": "hello"})
        assert result == "hello"

    def test_nested_list_of_dicts(self):
        result = flatten_text([{"text": "hello"}, {"text": "world"}])
        assert "hello" in result
        assert "world" in result

    def test_empty_string(self):
        assert flatten_text("") == ""

    def test_whitespace_stripped(self):
        assert flatten_text("  hello  ") == "hello"


class TestNormalizeMessageText:
    """Test message text normalization"""

    def test_normal_text(self):
        assert normalize_message_text("Hello world") == "Hello world"

    def test_empty_text(self):
        assert normalize_message_text("") == ""

    def test_none_text(self):
        assert normalize_message_text(None) == ""

    def test_skip_agents_md(self):
        assert normalize_message_text("# AGENTS.md instructions\nSome content") == ""

    def test_skip_permissions(self):
        assert normalize_message_text("<permissions instructions>...") == ""

    def test_skip_environment_context(self):
        assert normalize_message_text("<environment_context>...") == ""

    def test_skip_command_message(self):
        assert normalize_message_text("<command-message>...") == ""

    def test_whitespace_stripped(self):
        assert normalize_message_text("  hello  ") == "hello"


class TestDeriveMarkdownTitle:
    """Test title derivation from markdown"""

    def test_heading(self):
        assert derive_markdown_title("# My Title\n\nContent") == "My Title"

    def test_no_heading(self):
        result = derive_markdown_title("Some plain text content")
        assert result == "Some plain text content"

    def test_empty_string(self):
        assert derive_markdown_title("") == ""

    def test_multiple_headings(self):
        assert derive_markdown_title("# First\n## Second") == "First"

    def test_long_line_truncated(self):
        long_text = "A" * 200
        result = derive_markdown_title(long_text)
        assert len(result) <= 120

    def test_leading_empty_lines(self):
        result = derive_markdown_title("\n\n# Title")
        assert result == "Title"


class TestCollapseMessages:
    """Test consecutive same-role message collapsing"""

    def test_no_collapse_needed(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = collapse_messages(messages)
        assert len(result) == 2

    def test_collapses_consecutive_user(self):
        messages = [
            {"role": "user", "content": "Part 1"},
            {"role": "user", "content": "Part 2"},
            {"role": "assistant", "content": "Response"},
        ]
        result = collapse_messages(messages)
        assert len(result) == 2
        assert "Part 1" in result[0]["content"]
        assert "Part 2" in result[0]["content"]

    def test_collapses_consecutive_assistant(self):
        messages = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Part A"},
            {"role": "assistant", "content": "Part B"},
        ]
        result = collapse_messages(messages)
        assert len(result) == 2
        assert "Part A" in result[1]["content"]
        assert "Part B" in result[1]["content"]

    def test_empty_content_skipped(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "Hi"},
        ]
        result = collapse_messages(messages)
        assert len(result) == 2

    def test_missing_role_skipped(self):
        messages = [
            {"content": "No role"},
            {"role": "user", "content": "Has role"},
        ]
        result = collapse_messages(messages)
        assert len(result) == 1

    def test_empty_input(self):
        assert collapse_messages([]) == []


class TestInferPlatformFromPath:
    """Test platform inference from file paths"""

    def test_codex_path(self):
        path = Path("/home/user/.codex/sessions/session1.jsonl")
        assert infer_platform_from_path(path) == "codex"

    def test_claude_code_path(self):
        path = Path("/home/user/.claude/projects/proj/session.jsonl")
        assert infer_platform_from_path(path) == "claude_code"

    def test_antigravity_path(self):
        path = Path("/home/user/.gemini/antigravity/conversations/abc.pb")
        assert infer_platform_from_path(path) == "antigravity"

    def test_gemini_path(self):
        path = Path("/home/user/.gemini/tmp/session.json")
        assert infer_platform_from_path(path) == "gemini_cli"

    def test_unknown_path(self):
        path = Path("/home/user/random/file.txt")
        assert infer_platform_from_path(path) == "manual_import"


class TestParseGenericJsonl:
    """Test JSONL file parsing"""

    @pytest.fixture
    def sample_jsonl(self, tmp_path):
        """Create a sample JSONL file"""
        data = [
            {"type": "user", "message": {"role": "user", "content": "Hello"}},
            {"type": "assistant", "message": {"role": "assistant", "content": "Hi there!"}},
        ]
        path = tmp_path / "session.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")
        return path

    def test_parses_messages(self, sample_jsonl):
        messages, metadata = parse_generic_jsonl(sample_jsonl)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_metadata_has_timestamp(self, sample_jsonl):
        messages, metadata = parse_generic_jsonl(sample_jsonl)
        assert "timestamp" in metadata

    def test_metadata_has_project(self, sample_jsonl):
        messages, metadata = parse_generic_jsonl(sample_jsonl)
        assert metadata["project"] == "session"  # From filename stem

    def test_skips_meta_entries(self, tmp_path):
        data = [
            {"isMeta": True, "message": {"role": "user", "content": "Skip me"}},
            {"type": "user", "message": {"role": "user", "content": "Keep me"}},
            {"type": "assistant", "message": {"role": "assistant", "content": "Response"}},
        ]
        path = tmp_path / "test.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")
        messages, _ = parse_generic_jsonl(path)
        assert len(messages) == 2
        assert messages[0]["content"] == "Keep me"

    def test_session_meta_updates_metadata(self, tmp_path):
        data = [
            {"type": "session_meta", "payload": {"cwd": "/test/dir", "model": "gpt-5", "model_provider": "openai"}},
            {"type": "user", "message": {"role": "user", "content": "Hello"}},
            {"type": "assistant", "message": {"role": "assistant", "content": "Hi"}},
        ]
        path = tmp_path / "test.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")
        messages, metadata = parse_generic_jsonl(path)
        assert metadata["working_dir"] == "/test/dir"
        assert metadata["model"] == "gpt-5"
        assert metadata["provider"] == "openai"

    def test_empty_file(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        messages, _ = parse_generic_jsonl(path)
        assert messages == []

    def test_invalid_json_lines_skipped(self, tmp_path):
        path = tmp_path / "mixed.jsonl"
        content = 'not json\n{"type": "user", "message": {"role": "user", "content": "Valid"}}\n{"type": "assistant", "message": {"role": "assistant", "content": "Also valid"}}\n'
        path.write_text(content, encoding="utf-8")
        messages, _ = parse_generic_jsonl(path)
        assert len(messages) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
