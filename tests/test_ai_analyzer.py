"""
Tests for ai_analyzer module
Tests fallback analysis, JSON parsing, and summary generation
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from ai_analyzer import AIAnalyzer


@pytest.fixture
def analyzer():
    """Create analyzer instance (no AI provider configured)"""
    a = AIAnalyzer()
    a.provider = None  # Ensure fallback mode
    return a


class TestParseJsonResponse:
    """Test JSON extraction from AI responses"""

    def test_clean_json(self):
        text = '{"summary": "test", "topics": ["a", "b"]}'
        result = AIAnalyzer._parse_json_response(text)
        assert result["summary"] == "test"
        assert result["topics"] == ["a", "b"]

    def test_json_with_surrounding_text(self):
        text = 'Here is the analysis:\n{"summary": "test"}\nDone.'
        result = AIAnalyzer._parse_json_response(text)
        assert result["summary"] == "test"

    def test_nested_json(self):
        text = '{"outer": {"inner": "value"}, "list": [1, 2]}'
        result = AIAnalyzer._parse_json_response(text)
        assert result["outer"]["inner"] == "value"

    def test_no_json(self):
        text = "This is just plain text with no JSON"
        result = AIAnalyzer._parse_json_response(text)
        assert result == {}

    def test_empty_string(self):
        result = AIAnalyzer._parse_json_response("")
        assert result == {}

    def test_json_with_escaped_quotes(self):
        text = '{"summary": "He said \\"hello\\""}'
        result = AIAnalyzer._parse_json_response(text)
        assert "hello" in result.get("summary", "")

    def test_malformed_json(self):
        text = '{"summary": "unclosed'
        result = AIAnalyzer._parse_json_response(text)
        assert result == {}

    def test_json_in_markdown_code_block(self):
        text = '```json\n{"summary": "test"}\n```'
        result = AIAnalyzer._parse_json_response(text)
        assert result["summary"] == "test"


class TestFallbackSummary:
    """Test regex-based summary generation"""

    def test_basic_conversation(self, analyzer):
        content = "user: How do I build a FastAPI app?\nassistant: Let me help you set up FastAPI..."
        result = analyzer._fallback_summary(content)
        assert "summary" in result
        assert "FastAPI" in result["summary"]
        assert result["ai_generated"] is False
        assert result["message_count"] == 2

    def test_empty_content(self, analyzer):
        result = analyzer._fallback_summary("")
        assert "summary" in result
        assert result["message_count"] == 0

    def test_long_content_truncated(self, analyzer):
        long_message = "A" * 500
        content = f"user: {long_message}"
        result = analyzer._fallback_summary(content)
        assert len(result["summary"]) <= 200

    def test_multiple_messages(self, analyzer):
        content = "user: Question 1\nassistant: Answer 1\nuser: Question 2\nassistant: Answer 2"
        result = analyzer._fallback_summary(content)
        assert result["message_count"] == 4

    def test_key_points_extracted(self, analyzer):
        content = "user: First question\nuser: Second question\nuser: Third question\nassistant: Answers"
        result = analyzer._fallback_summary(content)
        assert len(result["key_points"]) <= 3


class TestFallbackContextInjection:
    """Test fallback context injection generation"""

    def test_with_conversations(self, analyzer):
        conversations = [
            {"platform": "claude_web", "summary": "Build a web app", "importance": 8},
            {"platform": "codex", "summary": "Debug API issue", "importance": 7},
        ]
        result = analyzer._fallback_context_injection(conversations)
        assert "Build a web app" in result
        assert "Debug API issue" in result
        assert "[claude_web]" in result

    def test_empty_conversations(self, analyzer):
        result = analyzer._fallback_context_injection([])
        assert result == ""

    def test_with_pinned_memories(self, analyzer):
        memories = [
            {"category": "workflow", "key": "style", "value": "Be concise"},
        ]
        result = analyzer._fallback_context_injection([], pinned_memories=memories)
        assert "Pinned memory" in result
        assert "Be concise" in result

    def test_with_both(self, analyzer):
        conversations = [{"platform": "codex", "summary": "Test", "importance": 5}]
        memories = [{"category": "general", "key": "note", "value": "Important"}]
        result = analyzer._fallback_context_injection(conversations, pinned_memories=memories)
        assert "Pinned memory" in result
        assert "Test" in result

    def test_limits_conversations(self, analyzer):
        conversations = [
            {"platform": "claude_web", "summary": f"Conv {i}", "importance": 5}
            for i in range(10)
        ]
        result = analyzer._fallback_context_injection(conversations)
        # Should limit to 5
        assert result.count("[claude_web]") <= 5


class TestFallbackKeyInfo:
    """Test fallback key information extraction"""

    def test_extracts_urls(self, analyzer):
        content = "Check https://example.com and http://test.org for details"
        result = analyzer._fallback_key_info(content)
        assert len(result["urls"]) == 2
        assert result["ai_generated"] is False

    def test_extracts_file_paths(self, analyzer):
        content = "Edit /home/user/project/main.py and C:\\Users\\wu\\file.txt"
        result = analyzer._fallback_key_info(content)
        assert len(result["file_paths"]) >= 1

    def test_counts_code_blocks(self, analyzer):
        content = "Here:\n```python\nprint('hello')\n```\nAnd:\n```js\nconsole.log('hi')\n```"
        result = analyzer._fallback_key_info(content)
        assert result["code_blocks"] == 2

    def test_empty_content(self, analyzer):
        result = analyzer._fallback_key_info("")
        assert result["urls"] == []
        assert result["file_paths"] == []
        assert result["code_blocks"] == 0


class TestAIAnalyzerState:
    """Test analyzer state and configuration"""

    def test_no_provider_available(self, analyzer):
        assert analyzer.is_ai_available() is False

    def test_reload_config(self, analyzer):
        analyzer.reload_config()
        # Should not crash, just reload


class TestGenerateSummaryFallback:
    """Test async generate_summary in fallback mode"""

    @pytest.mark.asyncio
    async def test_fallback_summary(self, analyzer):
        content = "user: How to test?\nassistant: Use pytest."
        result = await analyzer.generate_summary(content)
        assert "summary" in result
        assert result["ai_generated"] is False

    @pytest.mark.asyncio
    async def test_fallback_context_injection(self, analyzer):
        conversations = [{"platform": "test", "summary": "Test conv", "importance": 5}]
        result = await analyzer.generate_context_injection(conversations)
        assert "Test conv" in result

    @pytest.mark.asyncio
    async def test_fallback_key_info(self, analyzer):
        content = "Visit https://example.com"
        result = await analyzer.extract_key_info(content)
        assert len(result["urls"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
