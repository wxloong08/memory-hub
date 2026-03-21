# Memory Hub V2 — 跨 CLI 记忆中心设计文档

**日期**: 2026-03-17
**状态**: 设计中（核心架构已确认，细节持续完善）
**目标**: 个人记忆中心，在多个 AI CLI 之间无缝切换上下文

---

## 一、终极目标

当一个 CLI 的额度用完时，能**一条命令切换到另一个 CLI**，无需重新梳理上下文即可继续执行。同时提供 Web UI 管理所有对话和记忆的完整 CRUD。

**支持的 CLI**：Claude Code、Codex CLI、Gemini CLI、Antigravity

---

## 二、设计决策总结

| # | 决策项 | 选择 | 说明 |
|---|--------|------|------|
| 1 | 记忆粒度 | **混合模式** | 完整对话 + 结构化摘要，根据目标 CLI 的 context window 智能选择 |
| 2 | 切换方式 | **自动注入 + 手动命令** | 日常用 hook 自动注入，紧急切换用 `memory-hub switch` 命令 |
| 3 | 记忆架构 | **MemGPT 三层分层** | 工作记忆 / 核心记忆 / 存档记忆 |
| 4 | 内容精简 | **规则表 + AI 兜底** | 预定义类型映射表覆盖 90%，AI 处理剩余 10% |
| 5 | 交互界面 | **Web UI + CLI 并重** | Web UI 浏览/编辑，CLI 快速切换/批量操作 |
| 6 | 数据同步 | **Hook + 文件监听 + 手动导入** | 按 CLI 能力选择最优采集方式 |

---

## 三、调研基础

### 3.1 关键论文

| 论文 | 核心思想 | 对本项目的启发 |
|------|---------|---------------|
| [A Survey of Context Engineering for LLMs](https://arxiv.org/abs/2507.13334) (2025.07) | Context Engineering 是一门系统化优化 LLM 信息负载的学科，涵盖检索、生成、处理、管理 | 我们的导出适配器本质上就是 Context Engineering 的实践 |
| [Memory in the Age of AI Agents](https://arxiv.org/abs/2512.13564) (2025.12) | 区分事实记忆、经验记忆、工作记忆；分析记忆的形成、演化、检索 | 三层模型的理论基础 |
| [Active Context Compression](https://arxiv.org/abs/2601.07190) (2026.01) | 代理自主将关键学习整合到"Knowledge Block"，同时裁剪原始交互历史 | 核心层就是 Knowledge Block，存档层就是原始历史 |
| [MemOS: A Memory OS for AI System](https://arxiv.org/pdf/2507.03724) (2025.07) | 记忆即操作系统：记忆地址空间、调度器、权限控制 | 未来可参考其调度算法 |
| [Memory as a Service (MaaS)](https://arxiv.org/html/2506.22815v1) (2025.06) | 将记忆解耦为独立可调用的服务模块 | 我们的 Memory Hub API 就是 MaaS 模式 |
| [Collaborative Memory](https://arxiv.org/html/2505.18279v1) (2025.05) | 多用户记忆共享 + 动态访问控制 | 未来多设备同步可参考 |
| [A Survey on Memory Mechanism of LLM-based Agents](https://arxiv.org/abs/2404.13501) (2024.04) | 系统性综述 LLM agent 的记忆设计和评估方法 | 记忆评估指标参考 |

### 3.2 开源项目对比

| 项目 | 架构 | 优势 | 劣势 | 可借鉴 |
|------|------|------|------|--------|
| **mem0** | 专用记忆层，提取→存储→检索 | 准确率 66.9%，延迟 1.4s，比 OpenAI Memory 快 91% | 云服务依赖，非本地优先 | 记忆提取和检索算法 |
| **MemGPT/Letta** | LLM 即 OS，分层记忆（main↔archival） | 透明的内存管理，可查看 main/archival 内容 | 复杂度高，专用场景 | **三层分层架构（核心参考）** |
| **Zep** | 时序知识图谱，强调 episodic memory | 时间线结构化，关系追踪好 | 架构较重 | 时序记忆组织方式 |
| **LangMem** | 三类记忆：semantic/procedural/episodic | LangChain 生态集成好 | 依赖 LangChain | 记忆分类体系 |

### 3.3 Codex 对现有代码的分析

现有项目已具备大部分基础组件：
- **导入**：已支持 4 个 CLI（`local_importer.py` 覆盖 codex/claude_code/gemini_cli/antigravity）
- **导出**：仅覆盖 3 个（`client_exports.py` 缺 Antigravity）
- **自动注入**：仅 Claude Code 有 hook（`session-start.sh`）
- **主要缺口**：缺少 `memory-hub switch` 一键切换命令，缺少其他 CLI 的 hook

---

## 四、核心架构

### 4.1 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Memory Hub (核心服务)                      │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ 工作记忆  │  │ 核心记忆  │  │ 存档记忆  │  ← 三层记忆     │
│  │ (当前任务 │  │ (提炼事实 │  │ (完整对话 │                  │
│  │  上下文)  │  │  决策偏好) │  │  原文)    │                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       └──────────────┼────────────┘                         │
│                      ▼                                      │
│  ┌─────────────────────────────────┐                        │
│  │      智能压缩引擎                │                        │
│  │  规则表(90%) + AI兜底(10%)      │                        │
│  └─────────────────────────────────┘                        │
│                      ▼                                      │
│  ┌─────────────────────────────────┐                        │
│  │      导出适配器                  │                        │
│  │  CLAUDE.md | AGENTS.md | GEMINI.md | Antigravity         │
│  └─────────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
       ▲ 采集                              ▼ 注入
┌──────┴──────────────────────────────────┴──────┐
│  Claude Code  │  Codex CLI  │  Gemini CLI  │  Antigravity   │
│  (hook)       │  (hook)     │  (file watch) │  (gRPC+file)  │
└────────────────────────────────────────────────┘
       ▲                                   ▲
       │         ┌──────────┐              │
       └─────────│ CLI 工具  │──────────────┘
                 │ memory-hub│
                 └──────────┘
       ▲
       │         ┌──────────┐
       └─────────│  Web UI  │
                 └──────────┘
```

### 4.2 核心数据流

- **采集**：CLI hook/文件监听/手动导入 → Memory Hub API → 存入存档层（完整对话）→ 压缩引擎提炼 → 存入核心层
- **切换**：`memory-hub switch --to codex` → 从工作层+核心层组装上下文 → 导出适配器转为目标格式 → 注入目标 CLI
- **日常**：启动 CLI 时 hook 自动从核心层注入相关上下文

---

## 五、三层记忆数据模型

### 5.1 存档层（Archive Memory）

存储完整对话原文，是数据的"真相来源"。支持完整 CRUD。

```sql
CREATE TABLE archive_conversations (
    id                  INTEGER PRIMARY KEY,
    platform            TEXT NOT NULL,       -- claude_code | codex | gemini_cli | antigravity
    session_id          TEXT,                -- 原始会话ID
    workspace_path      TEXT,                -- 工作目录
    started_at          TEXT NOT NULL,       -- 会话开始时间
    ended_at            TEXT,                -- 会话结束时间
    raw_messages        TEXT NOT NULL,       -- JSON: 完整消息列表（原文保留）
    compressed_messages TEXT,                -- JSON: 精简后的消息列表（tool_use等已压缩）
    message_count       INTEGER DEFAULT 0,   -- 消息数量
    token_estimate      INTEGER DEFAULT 0,   -- 预估 token 数
    summary             TEXT,                -- 对话摘要
    importance          INTEGER DEFAULT 5,   -- 重要性评分 1-10
    provider            TEXT,                -- AI provider (claude/openai/google/etc)
    model               TEXT,                -- 模型名称
    metadata            TEXT,                -- JSON: 其他元信息
    content_hash        TEXT UNIQUE,         -- 去重哈希
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,

    -- 索引
    -- idx_archive_platform_time ON (platform, started_at)
    -- idx_archive_workspace ON (workspace_path)
    -- idx_archive_hash ON (content_hash)
);
```

### 5.2 核心层（Core Memory）

提炼的结构化知识，**常驻注入**到每个 CLI 会话。支持完整 CRUD。

```sql
CREATE TABLE core_memories (
    id              INTEGER PRIMARY KEY,
    category        TEXT NOT NULL,           -- fact | decision | preference | task_state | codebase
    key             TEXT NOT NULL,           -- 如 "auth_system_design"
    content         TEXT NOT NULL,           -- 记忆内容（简洁文本）
    source_ids      TEXT,                    -- JSON: 关联的存档对话ID列表
    confidence      REAL DEFAULT 0.7,        -- 置信度 0-1
    priority        INTEGER DEFAULT 5,       -- 优先级 1-10（注入时排序用）
    pinned          INTEGER DEFAULT 0,       -- 是否置顶（用户手动标记，永不衰减）
    tags            TEXT,                    -- JSON: 标签列表
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    accessed_at     TEXT DEFAULT CURRENT_TIMESTAMP, -- 最后被注入/查看的时间（用于衰减）

    -- 唯一约束
    UNIQUE(category, key)
);
```

### 5.3 工作层（Working Memory）

当前活跃任务的临时上下文，**切换时完整迁移**。

```sql
CREATE TABLE working_memory (
    id              INTEGER PRIMARY KEY,
    workspace_path  TEXT NOT NULL UNIQUE,    -- 绑定工作目录（一个项目一个工作记忆）
    active_task     TEXT,                    -- 当前任务描述
    current_plan    TEXT,                    -- JSON: 当前执行计划（步骤列表）
    progress        TEXT,                    -- JSON: 已完成的步骤
    open_issues     TEXT,                    -- JSON: 待解决的问题
    recent_changes  TEXT,                    -- 最近的代码变更摘要
    last_cli        TEXT,                    -- 最后使用的 CLI
    last_session_id TEXT,                    -- 最后的会话ID（关联存档层）
    context_snippet TEXT,                    -- 最近对话的关键片段（快速注入用）
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 5.4 切换时的注入策略

```
目标 CLI 的 context window 大小
         │
         ▼
┌─────────────────────────────────────────────┐
│ 1. 工作层（全部注入，~500-2000 tokens）       │
│    → 告诉新 CLI "你在做什么、做到哪了"         │
├─────────────────────────────────────────────┤
│ 2. 核心层（按优先级+相关性选取 top N）         │
│    → 告诉新 CLI "关键背景知识"                │
│    → pinned 记忆始终包含                      │
│    → 按 workspace_path 过滤相关记忆            │
│    → 按 priority DESC, accessed_at DESC 排序  │
├─────────────────────────────────────────────┤
│ 3. 存档层（按 context window 余量决定）        │
│                                             │
│    小窗口 (≤32K): 不注入存档                  │
│    中窗口 (32K-200K): 注入最近1-2轮压缩对话   │
│    大窗口 (200K-1M): 注入最近3-5轮完整对话    │
│    超大窗口 (>1M): 注入相关的完整对话历史      │
└─────────────────────────────────────────────┘
```

**各 CLI 的 context window 预设**：

| CLI | 配置文件 | 预估 Context Window | 注入策略 |
|-----|---------|-------------------|---------|
| Claude Code | CLAUDE.md | ~200K tokens | 工作层 + 核心层 + 最近压缩对话 |
| Codex CLI | AGENTS.md | ~128K tokens | 工作层 + 核心层 + 最近压缩对话 |
| Gemini CLI | GEMINI.md | ~1M tokens | 工作层 + 核心层 + 完整对话历史 |
| Antigravity | (待确认) | ~128K tokens | 工作层 + 核心层 + 最近压缩对话 |

---

## 六、智能内容精简系统

### 6.1 规则表（覆盖 ~90% 场景，零成本）

| 内容类型 | 检测方式 | 精简规则 | 示例 |
|---------|---------|---------|------|
| **tool_use: Read** | `tool: Read, path:` | `[读取文件: {path}, {lines}行]` | `[读取文件: src/main.py, 238行]` |
| **tool_use: Bash** | `tool: Bash, command:` | `[执行: {cmd} → {exit_code}, {summary}]` | `[执行: npm test → 成功, 12 passed]` |
| **tool_use: Edit** | `tool: Edit, file:` | `[编辑 {file}:L{start}-L{end}: {description}]` | `[编辑 main.py:L42-45: 修复空指针检查]` |
| **tool_use: Search/Grep** | `tool: Grep/Search` | `[搜索 "{query}" → {n}个匹配: {top_results}]` | `[搜索 "handleError" → 5个匹配: utils.js, api.js...]` |
| **tool_use: Write** | `tool: Write, path:` | `[创建文件: {path}, {lines}行, {purpose}]` | `[创建文件: test_auth.py, 85行, 认证测试]` |
| **tool_use: WebSearch** | `tool: WebSearch` | `[网络搜索: "{query}" → {n}条结果, 关键: {top1}]` | `[网络搜索: "React 19" → 8条结果, 关键: React 19正式发布]` |
| **tool_use: Agent** | `tool: Agent` | `[子代理: {description} → {result_summary}]` | `[子代理: 探索项目结构 → 发现15个模块]` |
| **长代码块** | ` ```{lang}\n` > 20行 | 保留前5行 + `// ... ({n}行省略)` + 末3行 | |
| **错误堆栈** | `Traceback\|Error:` > 10行 | 保留首行 + 根因行 + 末行 | `Error: ENOENT at fs.readFile (node:fs:123)` |
| **thinking block** | `