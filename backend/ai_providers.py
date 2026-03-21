"""
Multi-provider AI analysis system.
Most providers use OpenAI-compatible API format.
Claude uses its own format via the Anthropic SDK pattern.
"""

import httpx
import json
import os

PROVIDER_DEFAULTS = {
    "claude": {"base_url": "https://api.anthropic.com", "default_model": "claude-sonnet-4-20250514"},
    "openai": {"base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "default_model": "deepseek-chat"},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "default_model": "qwen-turbo"},
    "kimi": {"base_url": "https://api.moonshot.cn/v1", "default_model": "moonshot-v1-8k"},
    "minimax": {"base_url": "https://api.minimax.chat/v1", "default_model": "abab6.5-chat"},
    "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "default_model": "glm-4-flash"},
}


class AIProvider:
    """Base class for AI providers."""
    def __init__(self, api_key: str, model: str = None, base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        raise NotImplementedError


class OpenAICompatibleProvider(AIProvider):
    """Provider for OpenAI-compatible APIs. Uses shared httpx.AsyncClient for connection pooling."""
    def __init__(self, api_key: str, model: str, base_url: str):
        super().__init__(api_key, model, base_url)
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": 2000}
        client = self._get_client()
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


class ClaudeProvider(AIProvider):
    """Provider for Anthropic Claude API (Messages API format). Shared httpx client."""
    def __init__(self, api_key: str, model: str = None, base_url: str = None):
        super().__init__(
            api_key,
            model or PROVIDER_DEFAULTS["claude"]["default_model"],
            base_url or PROVIDER_DEFAULTS["claude"]["base_url"],
        )
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        url = f"{self.base_url.rstrip('/')}/v1/messages"
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        system_msg = ""
        claude_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                claude_messages.append(msg)
        payload = {"model": self.model, "messages": claude_messages, "max_tokens": 2000, "temperature": temperature}
        if system_msg:
            payload["system"] = system_msg
        client = self._get_client()
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]


def create_provider(provider_name: str, config: dict) -> AIProvider:
    """Factory function to create the right provider instance."""
    api_key = config.get("api_key", "")
    model = config.get("model")
    base_url = config.get("base_url")

    if not api_key:
        return None

    if provider_name == "claude":
        return ClaudeProvider(api_key, model, base_url)

    if provider_name == "custom":
        if not base_url or not model:
            print(f"Warning: custom provider requires both base_url and model")
            return None
        return OpenAICompatibleProvider(api_key, model, base_url)

    defaults = PROVIDER_DEFAULTS.get(provider_name, {})
    return OpenAICompatibleProvider(
        api_key=api_key,
        model=model or defaults.get("default_model", ""),
        base_url=base_url or defaults.get("base_url", ""),
    )
