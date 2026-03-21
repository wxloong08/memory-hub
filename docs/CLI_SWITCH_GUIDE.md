# Memory Hub V2 -- CLI 切换操作指南

**版本**: 2.0
**更新日期**: 2026-03-19

---

## 目录

1. [安装与配置](#1-安装与配置)
2. [memory-hub switch -- 切换CLI](#2-memory-hub-switch----切换cli)
3. [memory-hub status -- 查看工作状态](#3-memory-hub-status----查看工作状态)
4. [memory-hub save-state -- 手动保存状态](#4-memory-hub-save-state----手动保存状态)
5. [memory-hub import -- 导入会话](#5-memory-hub-import----导入会话)
6. [memory-hub search -- 搜索对话](#6-memory-hub-search----搜索对话)
7. [memory-hub history -- 切换历史](#7-memory-hub-history----切换历史)
8. [典型场景：额度用完后切换CLI](#8-典型场景额度用完后切换cli)
9. [常见问题与排障](#9-常见问题与排障)

---

## 1. 安装与配置

### 1.1 前置条件

- Python 3.10+
- Memory Hub 后端服务正在运行

### 1.2 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 1.3 启动 Memory Hub 后端

```bash
cd backend
uvicorn main:app --reload --port 8765
```

服务启动后可通过 `http://localhost:8765/health` 验证运行状态。

### 1.4 配置 CLI 工具

**Linux/macOS:**

```bash
# 添加 CLI 到 PATH
export PATH="$PATH:$(pwd)/cli"

# 可选：设置 Memory Hub 地址（默认 http://localhost:8765）
export MEMORY_HUB_URL=http://localhost:8765
```

**Windows:**

```cmd
set PATH=%PATH%;%cd%\cli
set MEMORY_HUB_URL=http://localhost:8765
```

### 1.5 验证安装

```bash
python cli/memory_hub.py --help
```

应看到如下输出：

```
usage: memory-hub [-h] [--url URL] {switch,status,save-state,import,search,history} ...

Memory Hub V2 -- CLI tool for cross-CLI context switching
```

---

## 2. memory-hub switch -- 切换CLI

`switch` 是 Memory Hub 的核心命令，用于在不同 AI CLI 之间切换，并自动携带完整上下文。

### 2.1 基本用法

```bash
memory-hub switch --to <目标CLI>
```

**支持的目标 CLI**：

| CLI | 标识符 | 目标文件 | Token 预算 |
|-----|--------|---------|-----------|
| Claude Code | `claude_code` | `.claude/CLAUDE.md` | 28,000 |
| Codex CLI | `codex` | `AGENTS.md` | 16,000 |
| Gemini CLI | `gemini_cli` | `GEMINI.md` | 111,000 |
| Antigravity | `antigravity` | `.antigravity/context.md` | 16,000 |

### 2.2 常用选项

```bash
# 基础切换（使用当前目录作为工作区）
memory-hub switch --to codex

# 指定工作区路径
memory-hub switch --to gemini_cli --workspace D:\pythonproject\my-project

# 自定义 Token 预算
memory-hub switch --to codex --budget 20000

# 限制存档对话轮数
memory-hub switch --to codex --turns 5

# 预览模式（不写入文件）
memory-hub switch --to codex --preview

# 预览并显示完整内容
memory-hub switch --to codex --preview --verbose

# 安静模式（最小输出）
memory-hub switch --to codex --quiet
```

### 2.3 完整参数列表

| 参数 | 简写 | 必填 | 说明 |
|------|------|------|------|
| `--to` | | 是 | 目标 CLI：`claude_code`, `codex`, `gemini_cli`, `antigravity` |
| `--workspace` | `-w` | 否 | 工作区路径，默认为当前目录 |
| `--budget` | | 否 | 覆盖默认 Token 预算 |
| `--turns` | | 否 | 最大存档对话轮数 |
| `--preview` | | 否 | 预览模式，不写入文件 |
| `--verbose` | `-v` | 否 | 显示完整上下文内容 |
| `--quiet` | `-q` | 否 | 最小输出 |

### 2.4 输出示例

```
Switching to codex...
  Workspace: D:\pythonproject\my-project

  Switch #3 completed!
  Target file: D:\pythonproject\my-project\AGENTS.md
  Tokens injected: 12700
    Working memory: 1200
    Core memories: 3500 (8 items)
    Archive: 8000 (12 turns)

  Now start codex in: D:\pythonproject\my-project
```

### 2.5 切换流程说明

执行 `switch` 命令时，系统按以下步骤运作：

1. **读取工作记忆** -- 获取当前工作区的任务状态（正在做什么、计划、进度、问题）
2. **收集核心记忆** -- 读取用户偏好、编码风格、决策记录等长期知识
3. **提取存档摘要** -- 从最近的对话历史中提取压缩后的上下文
4. **组装上下文文档** -- 按照目标 CLI 的 Token 预算，将三层记忆组装为 Markdown 文档
5. **写入目标文件** -- 将文档写入目标 CLI 的上下文文件（如 `AGENTS.md`），原文件自动备份为 `.bak`
6. **记录切换事件** -- 保存切换历史，更新工作记忆的 CLI 标记

---

## 3. memory-hub status -- 查看工作状态

查看当前工作区的工作记忆状态。

### 3.1 用法

```bash
# 查看当前目录的工作状态
memory-hub status

# 查看指定工作区
memory-hub status --workspace D:\pythonproject\my-project
```

### 3.2 输出示例

```
Working Memory: D:\pythonproject\my-project
  Task: Fix auth token refresh bug
  Last CLI: claude_code
  Switches: 2
  Updated: 2026-03-18T10:45:00
  Plan:
    1. Investigate root cause
    2. Apply fix
    3. Write tests
  Completed:
    - Investigated - found race condition
  Open Issues:
    - Need retry logic
```

---

## 4. memory-hub save-state -- 手动保存状态

手动保存当前工作状态到工作记忆中。当自动 Hook 未能完整捕获状态时特别有用。

### 4.1 用法

```bash
# 保存任务描述
memory-hub save-state --task "实现 JWT 认证流程"

# 保存任务和计划（逗号分隔的步骤）
memory-hub save-state --task "实现 JWT 认证" --plan "设计数据库表, 实现接口, 编写测试"

# 标记当前使用的 CLI
memory-hub save-state --task "修复 Bug" --cli claude_code

# 指定工作区
memory-hub save-state --task "部署配置" --workspace D:\pythonproject\my-project
```

### 4.2 完整参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--task` | | 当前任务描述 |
| `--plan` | | 逗号分隔的计划步骤 |
| `--cli` | | 当前 CLI 名称 |
| `--workspace` | `-w` | 工作区路径，默认为当前目录 |

---

## 5. memory-hub import -- 导入会话

从本地 CLI 会话目录导入历史对话到 V2 存档。

### 5.1 用法

```bash
# 导入所有来源（每个来源默认最多 20 条）
memory-hub import --source all

# 仅导入 Claude Code 会话
memory-hub import --source claude_code --limit 50

# 导入 Codex 会话
memory-hub import --source codex --limit 10
```

### 5.2 来源目录

| 来源 | 本地路径 |
|------|---------|
| `claude_code` | `~/.claude/projects/` |
| `codex` | `~/.codex/sessions/` |
| `gemini_cli` | `~/.gemini/tmp/` |
| `antigravity` | `~/.gemini/antigravity/conversations/` |

### 5.3 输出示例

```
Import complete: 8 imported, 42 skipped
```

已导入的会话不会被重复导入（基于内容哈希去重）。

---

## 6. memory-hub search -- 搜索对话

跨平台搜索历史对话和记忆。

### 6.1 用法

```bash
# 基本搜索
memory-hub search "auth token bug"

# 限制结果数量
memory-hub search "数据库迁移" --limit 10
```

### 6.2 输出示例

```
Conversations (3):
  [claude_code] Fix auth token refresh race condition
    Importance: 8/10  |  2026-03-18T10:00:00
  [codex] Auth system JWT implementation
    Importance: 7/10  |  2026-03-17T14:30:00
  [claude_web] Discussion about token refresh strategies
    Importance: 6/10  |  2026-03-16T09:00:00

Memories (1):
  [decision] auth_design: Using JWT with rotating refresh tokens
```

---

## 7. memory-hub history -- 切换历史

查看 CLI 切换事件的历史记录。

### 7.1 用法

```bash
# 查看最近 20 条记录（默认）
memory-hub history

# 限制显示条数
memory-hub history --limit 5
```

### 7.2 输出示例

```
Switch History (3 entries):
  claude_code -> codex  |  12700 tokens  |  2026-03-18T10:50:00
    Workspace: D:\pythonproject\my-project
  codex -> gemini_cli  |  45000 tokens  |  2026-03-18T11:30:00
    Workspace: D:\pythonproject\my-project
  gemini_cli -> claude_code  |  22000 tokens  |  2026-03-18T14:00:00
    Workspace: D:\pythonproject\my-project
```

---

## 8. 典型场景：额度用完后切换CLI

### 场景描述

你正在使用 Claude Code 开发一个功能，但 Anthropic API 额度用完了（或触发了速率限制）。你需要立即切换到 Gemini CLI 继续工作，而不丢失当前上下文。

### 操作步骤

**第一步：保存当前工作状态**

```bash
# 在项目目录下，保存当前任务和进度
memory-hub save-state \
  --task "实现用户认证模块" \
  --plan "设计JWT方案, 实现登录接口, 添加中间件, 编写测试" \
  --cli claude_code
```

**第二步：预览切换内容**

```bash
# 先预览，确认上下文正确
memory-hub switch --to gemini_cli --preview
```

预览输出：

```
--- Preview (dry run) ---
  Target file: GEMINI.md
  Working memory: 850 tokens
  Core memories: 2400 tokens (6 items)
  Archive: 15000 tokens (8 turns)
  Total: 18250 tokens
```

**第三步：执行切换**

```bash
memory-hub switch --to gemini_cli
```

输出：

```
Switching to gemini_cli...
  Workspace: D:\pythonproject\my-project

  Switch #1 completed!
  Target file: D:\pythonproject\my-project\GEMINI.md
  Tokens injected: 18250
    Working memory: 850
    Core memories: 2400 (6 items)
    Archive: 15000 (8 turns)

  Now start gemini_cli in: D:\pythonproject\my-project
```

**第四步：启动目标 CLI**

```bash
# 在同一目录下启动 Gemini CLI
gemini
```

Gemini CLI 会自动读取 `GEMINI.md`，看到完整的上下文，包括：
- 你正在做的任务和计划
- 你的编码偏好和工作习惯
- 最近的对话历史摘要

你可以直接继续工作，无需重新解释上下文。

**第五步（可选）：切换回 Claude Code**

当额度恢复后：

```bash
memory-hub switch --to claude_code
claude
```

### 其他常见场景

**场景 A：不同 CLI 有不同优势**

```bash
# 用 Claude Code 做代码重构，然后切换到 Gemini CLI 利用其大上下文窗口做文档审查
memory-hub switch --to gemini_cli --budget 80000
```

**场景 B：团队协作，不同成员使用不同 CLI**

```bash
# 同事在 Codex 上做了一半，你用 Claude Code 接手
memory-hub switch --to claude_code --workspace /shared/project
```

---

## 9. 常见问题与排障

### Q1: "Error: Cannot connect to Memory Hub"

**原因**：Memory Hub 后端未运行。

**解决**：

```bash
cd backend
uvicorn main:app --port 8765
```

验证：

```bash
curl http://localhost:8765/health
# 应返回 {"status": "healthy"}
```

### Q2: "Error: Memory Hub is not running"

**原因**：和 Q1 相同，CLI 工具无法连接到后端服务。

**解决**：确认后端正在运行，且 `MEMORY_HUB_URL` 环境变量正确。

```bash
echo $MEMORY_HUB_URL
# 默认为 http://localhost:8765
```

### Q3: 切换后目标 CLI 没有读取上下文

**原因**：目标 CLI 可能不会自动读取生成的上下文文件。

**排查**：

1. 确认文件已生成：

```bash
# Claude Code
cat .claude/CLAUDE.md

# Codex
cat AGENTS.md

# Gemini CLI
cat GEMINI.md

# Antigravity
cat .antigravity/context.md
```

2. 确认你在正确的工作区目录下启动目标 CLI。

### Q4: Token 预算不够，上下文被截断

**解决**：使用 `--budget` 参数增大预算。

```bash
# Gemini CLI 有 1M 上下文窗口，可以给更多预算
memory-hub switch --to gemini_cli --budget 200000
```

### Q5: 切换前忘记保存状态

**解决**：如果之前在 CLI 中的对话已经通过 Hook 或导入功能存档，`switch` 命令仍然可以从存档中提取上下文。如果没有存档，先手动保存：

```bash
memory-hub save-state --task "你正在做的任务描述"
memory-hub switch --to <目标CLI>
```

### Q6: 想查看某次切换注入了什么内容

**解决**：使用 `--preview --verbose` 预览完整内容，或查看已备份的文件。

```bash
# 预览
memory-hub switch --to codex --preview --verbose

# 切换时会自动备份，查看备份
cat AGENTS.md.pre-switch.bak
```

### Q7: 如何清空工作区的工作记忆

**解决**：通过 API 删除：

```bash
# URL 编码工作区路径
curl -X DELETE "http://localhost:8765/api/v2/working-memory/D%3A%5Cpythonproject%5Cmy-project"
```

### Q8: 如何查看所有活跃的工作区

**解决**：

```bash
curl http://localhost:8765/api/v2/working-memory
```

---

## 附录：Token 预算分配

切换时的上下文由三层记忆组装而成，每层有独立的 Token 预算：

| CLI | 工作记忆 | 核心记忆 | 存档摘要 | 总计 |
|-----|---------|---------|---------|------|
| Claude Code (~200K) | 3,000 | 5,000 | 20,000 | 28,000 |
| Codex CLI (~128K) | 2,000 | 4,000 | 10,000 | 16,000 |
| Gemini CLI (~1M) | 3,000 | 8,000 | 100,000 | 111,000 |
| Antigravity (~128K) | 2,000 | 4,000 | 10,000 | 16,000 |

- **工作记忆**：始终完整注入，包含当前任务、计划、进度
- **核心记忆**：按优先级排序注入，占剩余预算的 40%
- **存档摘要**：使用压缩后的最近对话，填充剩余预算
