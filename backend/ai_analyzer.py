"""
AI Analyzer module for conversation analysis.
Supports multiple AI providers with fallback to regex-based extraction.
"""

import json
import logging
import os
import re
from pathlib import Path

from ai_providers import create_provider, PROVIDER_DEFAULTS

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """Analyzes conversations using AI providers or regex fallback."""

    def __init__(self):
        self.provider = None
        self._load_config()

    def _load_config(self):
        """Load AI config from env vars first, then config file."""
        self.provider = None

        # Try environment variables first: AI_{PROVIDER}_API_KEY
        for provider_name in PROVIDER_DEFAULTS:
            env_key = f"AI_{provider_name.upper()}_API_KEY"
            api_key = os.environ.get(env_key)
            if api_key:
                config = {"api_key": api_key}
                # Check for optional env overrides
                env_model = os.environ.get(f"AI_{provider_name.upper()}_MODEL")
                env_base_url = os.environ.get(f"AI_{provider_name.upper()}_BASE_URL")
                if env_model:
                    config["model"] = env_model
                if env_base_url:
                    config["base_url"] = env_base_url
                self.provider = create_provider(provider_name, config)
                if self.provider:
                    logger.info("AI Analyzer: using provider '%s' from environment", provider_name)
                    return

        # Check for custom provider via env
        custom_key = os.environ.get("AI_CUSTOM_API_KEY")
        if custom_key:
            config = {
                "api_key": custom_key,
                "model": os.environ.get("AI_CUSTOM_MODEL", ""),
                "base_url": os.environ.get("AI_CUSTOM_BASE_URL", ""),
            }
            self.provider = create_provider("custom", config)
            if self.provider:
                logger.info("AI Analyzer: using custom provider from environment")
                return

        # Fall back to config file
        config_path = Path(__file__).parent / "data" / "ai_config.json"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            logger.info("AI Analyzer: no config file found, running in fallback mode")
            return

        default_provider = file_config.get("default_provider", "")
        providers = file_config.get("providers", {})

        # If a default provider is set, try that first
        if default_provider and default_provider in providers:
            provider_conf = providers[default_provider]
            if provider_conf.get("api_key"):
                self.provider = create_provider(default_provider, provider_conf)
                if self.provider:
                    logger.info("AI Analyzer: using provider '%s' from config file", default_provider)
                    return

        # Otherwise try each provider that has an API key
        for name, provider_conf in providers.items():
            if provider_conf.get("api_key"):
                self.provider = create_provider(name, provider_conf)
                if self.provider:
                    logger.info("AI Analyzer: using provider '%s' from config file", name)
                    return

        logger.info("AI Analyzer: no configured provider found, running in fallback mode")

    def is_ai_available(self) -> bool:
        """Check if an AI provider is configured and available."""
        return self.provider is not None

    def reload_config(self):
        """Hot reload configuration."""
        self._load_config()

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Parse JSON from AI response using balanced-brace algorithm."""
        # Find the first '{' character
        start = text.find("{")
        if start == -1:
            return {}

        # Use balanced brace counting to find the matching '}'
        depth = 0
        in_string = False
        escape_next = False

        for i in range(start, len(text)):
            ch = text[i]

            if escape_next:
                escape_next = False
                continue

            if ch == "\\":
                if in_string:
                    escape_next = True
                continue

            if ch == '"' and not escape_next:
                in_string = not in_string
                continue

            if in_string:
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    json_str = text[start:i + 1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        return {}

        return {}

    def _fallback_summary(self, content: str) -> dict:
        """Generate summary using regex when no AI provider is available."""
        lines = content.strip().split("\n")

        # Extract user messages
        user_messages = []
        assistant_messages = []
        for line in lines:
            line = line.strip()
            if line.startswith("user:"):
                user_messages.append(line[5:].strip())
            elif line.startswith("assistant:"):
                assistant_messages.append(line[10:].strip())

        # Build summary from first user message
        if user_messages:
            summary = user_messages[0][:200]
        else:
            summary = content[:200]

        # Extract topics using simple keyword extraction
        all_text = " ".join(user_messages + assistant_messages)
        # Find capitalized words and common tech terms as topics
        words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', all_text)
        topics = list(set(words))[:5] if words else []

        return {
            "summary": summary,
            "topics": topics,
            "message_count": len(user_messages) + len(assistant_messages),
            "key_points": [msg[:100] for msg in user_messages[:3]],
            "ai_generated": False,
        }

    def _fallback_context_injection(self, conversations: list[dict], pinned_memories: list[dict] | None = None) -> str:
        """Generate context injection using simple formatting."""
        if not conversations and not pinned_memories:
            return ""

        lines = []
        if pinned_memories:
            lines.append("Pinned memory:")
            for memory in pinned_memories[:8]:
                category = memory.get("category", "general")
                key = memory.get("key", category)
                value = memory.get("value", "")
                if value:
                    lines.append(f"- [{category}] {key}: {value}")
            lines.append("")

        for conv in conversations[:5]:
            platform = conv.get("platform", "unknown")
            summary = conv.get("summary", "")
            importance = conv.get("importance", 5)
            if summary:
                lines.append(f"- [{platform}] (importance: {importance}/10) {summary}")

        return "\n".join(lines) if lines else ""

    def _fallback_key_info(self, content: str) -> dict:
        """Extract key info using regex."""
        # Find code-like patterns
        code_blocks = re.findall(r'```[\s\S]*?```', content)
        # Find URLs
        urls = re.findall(r'https?://[^\s\)\"\']+', content)
        # Find file paths
        file_paths = re.findall(r'(?:[A-Za-z]:\\|/)[^\s\)\"\']+\.\w+', content)

        return {
            "code_blocks": len(code_blocks),
            "urls": urls[:10],
            "file_paths": file_paths[:10],
            "ai_generated": False,
        }

    async def generate_summary(self, content: str) -> dict:
        """Generate a summary of conversation content."""
        if not self.provider:
            return self._fallback_summary(content)

        # Truncate very long content
        truncated = content[:8000] if len(content) > 8000 else content

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a conversation analyzer. Given a conversation, return a JSON object with: "
                    '"summary" (1-2 sentence summary), '
                    '"topics" (list of key topics), '
                    '"key_points" (list of important points), '
                    '"message_count" (number of messages). '
                    "Return ONLY valid JSON, no other text."
                ),
            },
            {"role": "user", "content": f"Analyze this conversation:\n\n{truncated}"},
        ]

        try:
            response = await self.provider.chat(messages)
            result = self._parse_json_response(response)
            if result:
                result["ai_generated"] = True
                return result
            # If JSON parsing failed, wrap the raw response
            return {"summary": response[:500], "ai_generated": True, "topics": [], "key_points": []}
        except Exception as e:
            logger.error("AI analysis failed: %s", e)
            return self._fallback_summary(content)

    async def generate_context_injection(self, conversations: list[dict], pinned_memories: list[dict] | None = None) -> str:
        """Generate AI-synthesized context from recent conversations."""
        if not self.provider:
            return self._fallback_context_injection(conversations, pinned_memories)

        conv_text = json.dumps(conversations[:10], default=str, ensure_ascii=False)
        memory_text = json.dumps((pinned_memories or [])[:12], default=str, ensure_ascii=False)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a context synthesizer. Given a list of recent conversations, "
                    "plus a list of pinned long-term memories, produce a concise, actionable context summary "
                    "that helps an AI assistant understand what the user has been working on and how to work with them. "
                    "Focus on: current projects, recent decisions, unresolved questions, user preferences, and stable working patterns. "
                    "Keep it under 300 words. Return plain text, not JSON."
                ),
            },
            {"role": "user", "content": f"Pinned memories:\n\n{memory_text}\n\nRecent conversations:\n\n{conv_text}"},
        ]

        try:
            response = await self.provider.chat(messages)
            return response.strip()
        except Exception as e:
            logger.error("AI context injection failed: %s", e)
            return self._fallback_context_injection(conversations, pinned_memories)

    async def extract_key_info(self, content: str) -> dict:
        """Extract key information from conversation content."""
        if not self.provider:
            return self._fallback_key_info(content)

        truncated = content[:8000] if len(content) > 8000 else content

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an information extractor. Given a conversation, return a JSON object with: "
                    '"decisions" (list of decisions made), '
                    '"action_items" (list of action items/TODOs), '
                    '"code_references" (list of code snippets or file references mentioned), '
                    '"questions" (list of unresolved questions). '
                    "Return ONLY valid JSON, no other text."
                ),
            },
            {"role": "user", "content": f"Extract key info from:\n\n{truncated}"},
        ]

        try:
            response = await self.provider.chat(messages)
            result = self._parse_json_response(response)
            if result:
                result["ai_generated"] = True
                return result
            return {"summary": response[:500], "ai_generated": True}
        except Exception as e:
            logger.error("AI key info extraction failed: %s", e)
            return self._fallback_key_info(content)


# Singleton instance
analyzer = AIAnalyzer()
