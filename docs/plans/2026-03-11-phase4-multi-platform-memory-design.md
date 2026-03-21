# Phase 4 设计文档：多平台智能记忆系统

**日期**: 2026-03-11
**状态**: 已批准

---

## 概述

扩展 Claude Memory System，增加 Web UI、多平台浏览器插件支持、手动同步控制和 AI 增强分析功能。

## 核心需求

1. **智能摘要 + 按需展开**：默认注入精炼摘要，需要时可查看完整对话细节
2. **Web UI**：Vue 3 + Vite + Tailwind CSS，查看对话信息的可视化界面
3. **手动同步控制**：改为手动触发，避免不必要的对话被同步
4. **多平台支持**：Claude、ChatGPT、Gemini、Grok、DeepSeek
5. **AI 增强分析**：可配置多 Provider（Claude、DeepSeek、千问、Kimi、MiniMax、GLM、自定义）

---

## 架构设计

```
┌──────────────────────────────────────────┐
│         浏览器插件（统一架构）              │
│  Claude | ChatGPT | Gemini | Grok | DS   │
│         手动触发同步按钮                   │
└────────────────┬─────────────────────────┘
                 │ 原始对话
                 ▼
┌──────────────────────────────────────────┐
│            Memory Hub (FastAPI)           │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐ │
│  │ AI 摘要  │  │ 向量索引  │  │ 偏好库  │ │
│  │(多API)   │  │(ChromaDB)│  │(SQLite) │ │
│  └─────────┘  └──────────┘  └─────────┘ │
└──────────┬───────────────┬───────────────┘
           │               │
     ┌─────▼─────┐  ┌─────▼─────┐
     │ Claude Code│  │ Web UI    │
     │ (Hook注入) │  │ (Vue 3)   │
     └───────────┘  └───────────┘
```

---

## 第一部分：浏览器插件多平台架构

### 文件结构

```
browser-extension/
├── manifest.json              # 统一配置，声明所有平台的 URL 匹配
├── popup.html                 # 弹窗 UI
├── popup.js                   # 弹窗逻辑
├── background.js              # 后台服务
├── core/
│   ├── extractor.js           # 通用提取接口
│   └── sync-manager.js        # 同步管理（手动触发）
└── platforms/
    ├── claude.js              # claude.ai DOM 解析
    ├── chatgpt.js             # chatgpt.com DOM 解析
    ├── gemini.js              # gemini.google.com DOM 解析
    ├── grok.js                # grok.com DOM 解析
    └── deepseek.js            # chat.deepseek.com DOM 解析
```

### 统一接口

```javascript
class PlatformExtractor {
  getPlatformName()        // 返回平台名
  isOnPlatform()           // 检测当前是否在该平台
  extractConversation()    // 提取对话内容 → { title, messages[], url }
}
```

### 工作方式

1. 用户在任意 AI 平台对话
2. 点击插件图标 → 弹窗显示当前对话摘要
3. 点击「同步到 Memory Hub」按钮
4. 插件调用对应平台的解析器提取对话
5. 发送到 Memory Hub，AI 自动生成摘要

### 弹窗 UI

- 显示当前平台名称和对话标题
- 「同步此对话」按钮
- 最近同步记录列表
- 同步状态指示（成功/失败）

---

## 第二部分：Web UI

### 技术栈

Vue 3 + Vite + Tailwind CSS

### 文件结构

```
web-ui/
├── package.json
├── vite.config.js
├── index.html
└── src/
    ├── App.vue
    ├── router/index.js
    ├── views/
    │   ├── Dashboard.vue           # 首页仪表板
    │   ├── Conversations.vue       # 对话列表
    │   ├── ConversationDetail.vue  # 对话详情
    │   ├── Search.vue              # 语义搜索
    │   └── Settings.vue            # 设置页
    ├── components/
    │   ├── ConversationCard.vue
    │   ├── PlatformBadge.vue
    │   ├── ImportanceTag.vue
    │   └── SearchBar.vue
    └── api/
        └── memory-hub.js
```

### 页面设计

1. **Dashboard**：统计卡片、最近同步对话、偏好标签云
2. **Conversations**：时间排序、平台筛选、搜索排序
3. **ConversationDetail**：AI 摘要、完整对话（折叠/展开）、关键决策、相关推荐
4. **Search**：语义搜索、相似度排序、高亮匹配
5. **Settings**：AI API 配置、连接状态、数据管理

---

## 第三部分：AI 增强分析

### 多 Provider 架构

```python
class OpenAICompatibleProvider:
    """千问、Kimi、MiniMax、GLM、DeepSeek 都走这个"""
    def __init__(self, base_url, api_key, model): ...
    def summarize(self, content): ...
    def extract_info(self, content): ...

PROVIDER_DEFAULTS = {
    "claude":   {"base_url": "https://api.anthropic.com/v1"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1"},
    "openai":   {"base_url": "https://api.openai.com/v1"},
    "qwen":     {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "kimi":     {"base_url": "https://api.moonshot.cn/v1"},
    "minimax":  {"base_url": "https://api.minimax.chat/v1"},
    "glm":      {"base_url": "https://open.bigmodel.cn/api/paas/v4"},
}
```

### 配置文件

```json
{
  "default_provider": "deepseek",
  "providers": {
    "claude": { "api_key": "sk-ant-...", "model": "claude-sonnet-4-20250514" },
    "deepseek": { "api_key": "sk-...", "model": "deepseek-chat" },
    "qwen": { "api_key": "sk-...", "model": "qwen-turbo" },
    "kimi": { "api_key": "sk-...", "model": "moonshot-v1-8k" },
    "minimax": { "api_key": "...", "model": "abab6.5-chat" },
    "glm": { "api_key": "...", "model": "glm-4" },
    "custom": { "base_url": "http://localhost:11434/v1", "model": "qwen2.5" }
  }
}
```

### 功能

1. **智能摘要生成**：同步时自动调用 AI，生成主题、关键决策、待办、技术要点
2. **上下文注入优化**：AI 将多条摘要整合为连贯上下文，按需展开查询完整细节
3. **关键信息提取**：自动识别技术决策、偏好、TODO、问题和解决方案

### 降级策略

无 API key 时退回正则提取 + 关键词摘要。

---

## 实施计划

### Phase 4.1：插件重构 + 多平台支持
- 重构浏览器插件为统一架构
- 改为手动同步（弹窗按钮触发）
- 实现 5 个平台解析器

### Phase 4.2：Web UI
- Vue 3 + Vite + Tailwind CSS
- 5 个页面
- 连接现有 Memory Hub API

### Phase 4.3：AI 增强分析
- 可配置多 AI Provider
- OpenAI 兼容基类
- 智能摘要、上下文注入、关键信息提取

---

## 新增/修改文件清单

```
claude-memory-system/
├── backend/
│   ├── ai_analyzer.py          # [新增]
│   ├── ai_providers.py         # [新增]
│   ├── main.py                 # [修改]
│   └── data/ai_config.json     # [新增]
├── browser-extension/
│   ├── manifest.json           # [重构]
│   ├── popup.html              # [重构]
│   ├── popup.js                # [新增]
│   ├── background.js           # [修改]
│   ├── core/
│   │   ├── extractor.js        # [新增]
│   │   └── sync-manager.js     # [新增]
│   └── platforms/
│       ├── claude.js           # [重构]
│       ├── chatgpt.js          # [新增]
│       ├── gemini.js           # [新增]
│       ├── grok.js             # [新增]
│       └── deepseek.js         # [新增]
├── web-ui/                     # [新增]
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
└── docs/plans/
    └── 2026-03-11-phase4-design.md
```
