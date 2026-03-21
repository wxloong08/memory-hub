# Phase 4.3: AI Enhanced Analysis Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
> **评审状态:** 已合并 Gemini/Codex/Claude 三方评审修订 (2026-03-12)

**Goal:** Add configurable AI-powered analysis (summaries, key info extraction) using multiple LLM providers with OpenAI-compatible API pattern.

**Architecture:** A provider-based AI analyzer that supports Claude, DeepSeek, Qwen, Kimi, MiniMax, GLM, and custom OpenAI-compatible endpoints. Falls back to regex extraction when no API key is configured.

**Tech Stack:** Python, httpx (async HTTP, already in requirements.txt), OpenAI-compatible API format

**前置依赖:** Phase 0 数据契约已完成

---

## Chunk 1: AI Provider System

### Task 1: Create AI provider base and OpenAI-compatible implementation

**Files:**
- Create: `backend/ai_providers.py`

- [ ] **Step 1: Create ai_providers.py**

```python
# backend/ai_providers.py
"""
Multi-provider AI analysis system.
Most providers use OpenAI-compatible API format.
Claude uses its own format via the Anthropic SDK pattern.
"""

import httpx
import json
import os

# Default provider configurations
PROVIDER_DEFAULTS = {
    "claude": {
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-20250514",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-turbo",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
    },
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "default_model": "abab6.5-chat",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
}


class AIProvider:
    """Base class for AI providers."""

    def __init__(self, api_key: str, model: str = None, base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        """Send a chat completion request. Returns the response text."""
        raise NotImplementedError


class OpenAICompatibleProvider(AIProvider):
    """
    Provider for OpenAI-compatible APIs.
    Works with: OpenAI, DeepSeek, Qwen, Kimi, MiniMax, GLM, and any custom endpoint.
    [FIX P1-12] Uses a shared httpx.AsyncClient for connection pooling.
    """

    def __init__(self, api_key: str, model: str, base_url: str):
        super().__init__(api_key, model, base_url)
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2000,
        }

        client = self._get_client()
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


class ClaudeProvider(AIProvider):
    """Provider for Anthropic Claude API (uses Messages API format).
    [FIX P1-12] Uses a shared httpx.AsyncClient for connection pooling.
    """

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
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Convert from OpenAI format to Claude format
        system_msg = ""
        claude_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                claude_messages.append(msg)

        payload = {
            "model": self.model,
            "messages": claude_messages,
            "max_tokens": 2000,
            "temperature": temperature,
        }
        if system_msg:
            payload["system"] = system_msg

        client = self._get_client()
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]


def create_provider(provider_name: str, config: dict) -> AIProvider:
    """Factory function to create the right provider instance.
    [FIX P1-14] Explicit validation for custom provider.
    """
    api_key = config.get("api_key", "")
    model = config.get("model")
    base_url = config.get("base_url")

    if not api_key:
        return None

    if provider_name == "claude":
        return ClaudeProvider(api_key, model, base_url)

    # Custom provider must have base_url and model explicitly set
    if provider_name == "custom":
        if not base_url or not model:
            print(f"Warning: custom provider requires both base_url and model")
            return None
        return OpenAICompatibleProvider(api_key, model, base_url)

    # Standard providers use defaults
    defaults = PROVIDER_DEFAULTS.get(provider_name, {})
    return OpenAICompatibleProvider(
        api_key=api_key,
        model=model or defaults.get("default_model", ""),
        base_url=base_url or defaults.get("base_url", ""),
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/ai_providers.py
git commit -m "feat: add multi-provider AI system with connection pooling"
```

---

### Task 2: Create AI analyzer

**Files:**
- Create: `backend/ai_analyzer.py`
- Create: `backend/data/ai_config.example.json` (NOT ai_config.json - see P0-3)

- [ ] **Step 1: Create example config file (template only, no real keys)**

> **[FIX P0-3] 安全修复**: 使用 .example.json 模板，真实配置走环境变量或本地忽略文件。

```json
{
  "_comment": "Copy this file to ai_config.json and fill in your API keys. ai_config.json is gitignored.",
  "default_provider": "",
  "providers": {
    "claude": { "api_key": "", "model": "claude-sonnet-4-20250514" },
    "openai": { "api_key": "", "model": "gpt-4o-mini" },
    "deepseek": { "api_key": "", "model": "deepseek-chat" },
    "qwen": { "api_key": "", "model": "qwen-turbo" },
    "kimi": { "api_key": "", "model": "moonshot-v1-8k" },
    "minimax": { "api_key": "", "model": "abab6.5-chat" },
    "glm": { "api_key": "", "model": "glm-4-flash" },
    "custom": { "api_key": "", "model": "", "base_url": "" }
  }
}
```

同时将 `backend/data/ai_config.json` 加入 `.gitignore`：

```bash
echo "backend/data/ai_config.json" >> .gitignore
```

- [ ] **Step 2: Create ai_analyzer.py**

```python
# backend/ai_analyzer.py
"""
AI-powered conversation analysis.
[FIX P0-3] API keys loaded from env vars first, config file as fallback.
[FIX P1-7] Config parsing wrapped in try/except for robustness.
[FIX P1-13] JSON parsing uses safe balanced-brace algorithm instead of greedy regex.
[FIX P2-17] Added reload_config() for hot reload.
"""

import json
import os
import re
from ai_providers import create_provider, AIProvider

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "ai_config.json")


class AIAnalyzer:
    def __init__(self):
        self.provider: AIProvider | None = None
        self.config = {}
        self._load_config()

    def _load_config(self):
        """Load AI configuration. Priority: env vars > config file."""
        self.provider = None
        self.config = {}

        # Try loading config file (with error handling for P1-7)
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load AI config: {e}")
                self.config = {}

        providers_config = self.config.get("providers", {})

        # Override with environment variables (P0-3 security fix)
        for name in list(providers_config.keys()) + ["claude", "openai", "deepseek", "qwen", "kimi", "minimax", "glm"]:
            env_key = f"AI_{name.upper()}_API_KEY"
            env_val = os.environ.get(env_key)
            if env_val:
                if name not in providers_config:
                    providers_config[name] = {}
                providers_config[name]["api_key"] = env_val

        # Create the default provider
        default_name = self.config.get("default_provider", "")
        if default_name and default_name in providers_config:
            self.provider = create_provider(default_name, providers_config[default_name])

        if not self.provider:
            # Try to find any configured provider
            for name, cfg in providers_config.items():
                if cfg.get("api_key"):
                    self.provider = create_provider(name, cfg)
                    if self.provider:
                        break

    def reload_config(self):
        """[FIX P2-17] Hot reload config without restart."""
        self._load_config()

    def is_ai_available(self) -> bool:
        """Check if an AI provider is configured and available."""
        return self.provider is not None

    def _parse_json_response(self, response: str) -> dict | None:
        """[FIX P1-13] Safely extract JSON from AI response using balanced braces."""
        # Try direct parse first
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass

        # Find balanced braces
        start = response.find('{')
        if start >= 0:
            depth = 0
            for i in range(start, len(response)):
                if response[i] == '{':
                    depth += 1
                elif response[i] == '}':
                    depth -= 1
                if depth == 0:
                    try:
                        return json.loads(response[start:i + 1])
                    except json.JSONDecodeError:
                        break
        return None

    async def generate_summary(self, conversation_content: str) -> dict:
        """Generate a smart summary of a conversation."""
        if not self.provider:
            return self._fallback_summary(conversation_content)

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a conversation analyzer. Given a conversation, extract:\n"
                        "1. A concise summary (2-3 sentences)\n"
                        "2. Key decisions made\n"
                        "3. TODO items or action items\n"
                        "4. Technical points or concepts discussed\n\n"
                        "Respond in JSON format:\n"
                        '{"summary": "...", "key_decisions": ["..."], "todos": ["..."], "tech_points": ["..."]}\n'
                        "Respond in the same language as the conversation."
                    ),
                },
                {"role": "user", "content": conversation_content[:8000]},
            ]

            response = await self.provider.chat(messages)
            parsed = self._parse_json_response(response)
            if parsed:
                return parsed
            return {"summary": response, "key_decisions": [], "todos": [], "tech_points": []}

        except Exception as e:
            print(f"AI summary failed: {e}, falling back to regex")
            return self._fallback_summary(conversation_content)

    async def generate_context_injection(self, conversations: list[dict]) -> str:
        """Generate optimized context for Claude Code injection."""
        if not self.provider or not conversations:
            return self._fallback_context(conversations)

        try:
            conv_text = "\n\n".join(
                f"[{c.get('platform', '?')} - {c.get('timestamp', '?')}]\n"
                f"Summary: {c.get('summary', 'No summary')}\n"
                f"Importance: {c.get('importance', 5)}/10"
                for c in conversations[:10]
            )

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a context synthesizer. Given recent conversation summaries, "
                        "create a brief, coherent context paragraph that helps an AI assistant "
                        "understand what the user has been working on, key decisions made, "
                        "and current priorities. Be concise (3-5 sentences max). "
                        "Write in the same language as the conversations."
                    ),
                },
                {"role": "user", "content": conv_text},
            ]

            return await self.provider.chat(messages)

        except Exception as e:
            print(f"AI context generation failed: {e}")
            return self._fallback_context(conversations)

    async def extract_key_info(self, conversation_content: str) -> dict:
        """Extract structured key information from a conversation."""
        if not self.provider:
            return self._fallback_extraction(conversation_content)

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Extract key information from this conversation:\n"
                        "1. Decisions: technical or design decisions made\n"
                        "2. Preferences: user preferences expressed\n"
                        "3. Problems: issues or bugs discussed\n"
                        "4. Solutions: solutions found or proposed\n\n"
                        "Respond in JSON:\n"
                        '{"decisions": ["..."], "preferences": ["..."], "problems": ["..."], "solutions": ["..."]}\n'
                        "Respond in the same language as the conversation."
                    ),
                },
                {"role": "user", "content": conversation_content[:8000]},
            ]

            response = await self.provider.chat(messages)
            parsed = self._parse_json_response(response)
            if parsed:
                return parsed
            return {"decisions": [], "preferences": [], "problems": [], "solutions": []}

        except Exception as e:
            print(f"AI extraction failed: {e}")
            return self._fallback_extraction(conversation_content)

    # --- Fallback methods (no AI required) ---

    def _fallback_summary(self, content: str) -> dict:
        """Regex-based summary extraction."""
        lines = content.split("\n")
        summary_lines = [l.strip() for l in lines if l.strip() and len(l.strip()) > 10][:3]
        summary = " ".join(summary_lines)[:200]

        decisions = []
        for line in lines:
            if re.search(r"(决定|选择|采用|decided|chose|selected)", line, re.I):
                decisions.append(line.strip()[:100])

        todos = []
        for line in lines:
            if re.search(r"(TODO|待办|需要|should|要做|接下来)", line, re.I):
                todos.append(line.strip()[:100])

        return {
            "summary": summary or "No summary available",
            "key_decisions": decisions[:5],
            "todos": todos[:5],
            "tech_points": [],
        }

    def _fallback_context(self, conversations: list[dict]) -> str:
        if not conversations:
            return "No recent conversations."
        lines = []
        for c in conversations[:5]:
            lines.append(
                f"- [{c.get('platform', '?')}] {c.get('summary', 'No summary')}"
                f" (importance: {c.get('importance', 5)}/10)"
            )
        return "Recent activity:\n" + "\n".join(lines)

    def _fallback_extraction(self, content: str) -> dict:
        return {"decisions": [], "preferences": [], "problems": [], "solutions": []}


# Singleton instance
analyzer = AIAnalyzer()
```

- [ ] **Step 3: Commit**

```bash
git add backend/ai_analyzer.py backend/data/ai_config.example.json .gitignore
git commit -m "feat: add AI analyzer with safe config, connection pooling, and balanced JSON parsing"
```

---

### Task 3: Integrate AI analyzer into Memory Hub API

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add AI analysis endpoints**

Add to `backend/main.py` imports:

```python
from ai_analyzer import analyzer
```

Add new endpoints:

```python
@app.post("/api/analyze/{conversation_id}")
async def analyze_conversation(conversation_id: str):
    """Run AI analysis on a stored conversation."""
    cursor = db.conn.execute(
        "SELECT full_content, summary FROM conversations WHERE id = ?",
        (conversation_id,)
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    content = row["full_content"]
    result = await analyzer.generate_summary(content)

    # Update summary if AI generated a better one
    if result.get("summary") and analyzer.is_ai_available():
        db.conn.execute(
            "UPDATE conversations SET summary = ? WHERE id = ?",
            (result["summary"], conversation_id)
        )
        db.conn.commit()

    return {
        "conversation_id": conversation_id,
        "ai_available": analyzer.is_ai_available(),
        "analysis": result
    }


@app.get("/api/ai/status")
async def ai_status():
    """Check AI provider status."""
    return {
        "available": analyzer.is_ai_available(),
        "config_path": "backend/data/ai_config.json"
    }


@app.post("/api/ai/reload")
async def reload_ai_config():
    """[FIX P2-17] Hot reload AI config."""
    analyzer.reload_config()
    return {"status": "reloaded", "available": analyzer.is_ai_available()}
```

- [ ] **Step 2: Enhance context endpoint with AI**

Add after the context markdown is built in `/api/context`:

```python
    # If AI is available, generate optimized context
    if analyzer.is_ai_available() and conversations:
        try:
            ai_context = await analyzer.generate_context_injection(
                [{"platform": c.get("platform"), "timestamp": c.get("timestamp"),
                  "summary": c.get("summary"), "importance": c.get("importance")}
                 for c in conversations]
            )
            if ai_context:
                context = f"# AI-Synthesized Context\n\n{ai_context}\n\n---\n\n{context}"
        except Exception:
            pass  # Fall back to regular context
```

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: integrate AI analyzer into Memory Hub API"
```

---

### ~~Task 4: Add httpx to requirements~~ SKIPPED

> **[FIX P2-18]** `httpx==0.27.0` 已存在于 `backend/requirements.txt`，无需重复添加。

---

### Task 5: End-to-end test

- [ ] **Step 1: Test without AI (fallback mode)**

```bash
cd "D:/python project/claude-memory-system/backend"
python -c "
import asyncio
from ai_analyzer import analyzer
print('AI available:', analyzer.is_ai_available())
result = asyncio.run(analyzer.generate_summary('user: How to use Python? assistant: Python is great.'))
print('Fallback summary:', result)
"
```
Expected: AI available: False, summary generated via fallback

- [ ] **Step 2: Test AI status endpoint**

```bash
python main.py &
curl http://localhost:8765/api/ai/status
```
Expected: `{"available": false, "config_path": "backend/data/ai_config.json"}`

- [ ] **Step 3: Test analyze endpoint (fallback)**

> **[FIX] 使用 POST 而非 GET**

```bash
curl -X POST http://localhost:8765/api/analyze/<some_conversation_id>
```
Expected: Analysis result with fallback data

- [ ] **Step 4: (Optional) Test with real API key**

> **[FIX P0-3] 使用环境变量而非编辑配置文件**

```bash
# 方式1: 环境变量 (推荐)
AI_DEEPSEEK_API_KEY=sk-xxx python main.py

# 方式2: 复制模板文件并编辑 (不会被 git 跟踪)
cp backend/data/ai_config.example.json backend/data/ai_config.json
# 编辑 ai_config.json 填入 key
python main.py
```

```bash
curl http://localhost:8765/api/ai/status
# Should show available: true

curl -X POST http://localhost:8765/api/analyze/<conversation_id>
# Should show AI-generated analysis
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete Phase 4.3 AI enhanced analysis"
```
