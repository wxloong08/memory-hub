# 历史对话导入指南

## 📚 问题：如何导入历史对话？

浏览器插件只能捕获**从安装后开始的新对话**，无法自动获取历史对话。

但我们提供了多种方式来导入你的历史对话！

---

## 🎯 导入方式对比

| 方式 | 难度 | 速度 | 适用场景 |
|------|------|------|---------|
| **方式1：手动复制粘贴** | ⭐ 简单 | 慢 | 少量重要对话 |
| **方式2：文本文件导入** | ⭐⭐ 中等 | 中 | 多个对话 |
| **方式3：JSON批量导入** | ⭐⭐⭐ 复杂 | 快 | 大量对话 |
| **方式4：逐个打开对话** | ⭐ 简单 | 慢 | 让插件自动捕获 |

---

## 方式1：手动复制粘贴（推荐新手）

### 步骤

1. **启动 Memory Hub**
```bash
cd "D:\python project\claude-memory-system\backend"
uvicorn main:app --port 8765
```

2. **运行导入工具**
```bash
cd "D:\python project\claude-memory-system\scripts"
python import_conversations.py
```

3. **选择选项 2（直接粘贴文本）**

4. **从 Claude.ai 复制对话**
   - 打开 claude.ai 的历史对话
   - 选中对话内容，Ctrl+C 复制

5. **粘贴到终端**
   - 格式：
   ```
   User: 你的问题
   Assistant: Claude的回复
   User: 下一个问题
   Assistant: 下一个回复
   ```

6. **输入 `END` 完成**

### 示例

```bash
$ python import_conversations.py

请选择导入方式：
1. 从文件导入
2. 直接粘贴文本
3. 退出

请选择 (1-3): 2

请粘贴对话内容（格式：User: ... / Assistant: ...）
输入完成后，单独一行输入 'END' 结束：

User: 什么是POD系统？
Assistant: POD系统是一个多智能体协作框架...
User: 如何实现？
Assistant: 可以使用LangGraph来实现...
END

📝 解析到 4 条消息
确认导入？(y/n): y
✅ 成功导入 4 条消息
```

---

## 方式2：文本文件导入

### 步骤

1. **创建文本文件**

创建 `conversation1.txt`：
```
User: 我想开发一个记忆系统
Assistant: 好的，让我们讨论一下需求...
User: 需要支持跨平台
Assistant: 可以使用以下架构...
```

2. **导入文件**
```bash
python import_conversations.py conversation1.txt
```

### 批量导入多个文件

```bash
# 将所有对话保存为 .txt 文件，放在一个目录
mkdir my_conversations
# 保存 conversation1.txt, conversation2.txt, ...

# 批量导入
python batch_import.py my_conversations/
```

---

## 方式3：JSON 批量导入（高级）

### 步骤

1. **创建 JSON 模板**
```bash
python batch_import.py --template
```

这会创建 `conversation_template.json`：
```json
{
  "messages": [
    {
      "role": "user",
      "content": "你的问题内容"
    },
    {
      "role": "assistant",
      "content": "Claude 的回复内容"
    }
  ],
  "project": "项目名称（可选）",
  "timestamp": "2025-03-09T18:00:00Z"
}
```

2. **编辑 JSON 文件**

填入你的对话内容：
```json
{
  "messages": [
    {
      "role": "user",
      "content": "我想开发一个记忆系统"
    },
    {
      "role": "assistant",
      "content": "好的，让我们讨论一下需求。你希望这个系统主要解决什么问题？"
    },
    {
      "role": "user",
      "content": "让Claude能在不同平台间共享上下文"
    },
    {
      "role": "assistant",
      "content": "明白了。我们可以设计一个三层架构..."
    }
  ],
  "project": "跨平台记忆系统",
  "timestamp": "2025-03-09T10:00:00Z"
}
```

3. **导入**
```bash
python batch_import.py conversation_template.json
```

### 批量导入多个 JSON

如果你有多个对话的 JSON 文件：
```json
// conversations.json
{
  "conversations": [
    {
      "title": "POD系统讨论",
      "created_at": "2025-03-08T10:00:00Z",
      "messages": [...]
    },
    {
      "title": "记忆系统设计",
      "created_at": "2025-03-09T14:00:00Z",
      "messages": [...]
    }
  ]
}
```

导入：
```bash
python batch_import.py conversations.json
```

---

## 方式4：让插件自动捕获（最简单但最慢）

### 原理
浏览器插件会捕获**当前打开页面**的对话内容。

### 步骤

1. **安装并启动插件**
   - 确保 Memory Hub 运行中
   - 浏览器插件已安装

2. **逐个打开历史对话**
   - 在 claude.ai 打开一个历史对话
   - 等待 3-5 秒（插件自动捕获）
   - 点击插件图标，确认已同步
   - 打开下一个对话

3. **优点**
   - ✅ 无需手动复制
   - ✅ 格式完全准确
   - ✅ 自动处理

4. **缺点**
   - ❌ 需要逐个打开
   - ❌ 耗时较长
   - ❌ 适合对话数量少的情况

---

## 🎯 推荐策略

### 对于不同数量的历史对话

| 对话数量 | 推荐方式 | 预计时间 |
|---------|---------|---------|
| **1-5个** | 方式4（逐个打开） | 5-10分钟 |
| **5-20个** | 方式1（手动粘贴） | 20-40分钟 |
| **20-50个** | 方式2（文本文件） | 1-2小时 |
| **50+个** | 方式3（JSON批量） | 2-4小时 |

### 对于重要程度

**高优先级对话**（必须导入）：
- 重要的项目讨论
- 关键决策记录
- 技术方案设计

**中优先级对话**（建议导入）：
- 常用的代码模式
- 工作流程讨论
- 学习笔记

**低优先级对话**（可选导入）：
- 简单问答
- 测试对话
- 闲聊内容

---

## 📝 实用技巧

### 技巧1：分批导入

不要一次性导入所有对话，分批进行：

```bash
# 第一批：最近一周的重要对话
python batch_import.py recent_important/

# 第二批：项目相关对话
python batch_import.py project_conversations/

# 第三批：其他对话
python batch_import.py other_conversations/
```

### 技巧2：使用标签分类

在导入时添加项目标签：

```json
{
  "messages": [...],
  "project": "POD系统",  // 添加项目标签
  "timestamp": "2025-03-08T10:00:00Z"
}
```

这样在 Claude Code 中可以按项目过滤上下文。

### 技巧3：验证导入结果

导入后检查数据库：

```bash
# 查看导入的对话数量
sqlite3 "D:\python project\claude-memory-system\data\memory.db" \
  "SELECT COUNT(*) FROM conversations;"

# 查看最近导入的对话
sqlite3 "D:\python project\claude-memory-system\data\memory.db" \
  "SELECT platform, summary, timestamp FROM conversations ORDER BY timestamp DESC LIMIT 5;"
```

### 技巧4：导出备份

导入前先备份原始对话：

```bash
# 创建备份目录
mkdir backup_conversations

# 将所有对话保存为文本文件
# 然后再导入到系统
```

---

## ⚠️ 注意事项

### 1. 格式要求

**文本格式**必须遵循：
```
User: 问题内容
Assistant: 回复内容
```

或者：
```
你: 问题内容
Claude: 回复内容
```

**不支持**的格式：
```
问题内容
回复内容
```

### 2. 特殊字符

如果对话包含特殊字符，使用 JSON 格式更安全：
```json
{
  "role": "user",
  "content": "代码中的 \"引号\" 和 \n 换行"
}
```

### 3. 长对话

对于非常长的对话（>100条消息），建议：
- 分段导入
- 或只导入关键部分

### 4. 时间戳

如果知道对话的准确时间，建议填写：
```json
{
  "timestamp": "2025-03-08T14:30:00Z"
}
```

这样可以保持时间线的准确性。

---

## 🔧 故障排除

### 问题1：导入失败

**症状**：`❌ 无法连接到 Memory Hub`

**解决**：
```bash
# 确保 Memory Hub 正在运行
curl http://localhost:8765/health

# 如果没有运行，启动它
cd backend
uvicorn main:app --port 8765
```

### 问题2：解析失败

**症状**：`❌ 未能解析出有效消息`

**解决**：
- 检查格式是否正确（`User:` 和 `Assistant:`）
- 确保每条消息都有内容
- 尝试使用 JSON 格式

### 问题3：中文乱码

**症状**：导入的中文显示为乱码

**解决**：
```bash
# 确保文件使用 UTF-8 编码
# 在记事本中：另存为 → 编码选择 UTF-8
```

---

## 📊 导入后验证

### 1. 检查数据库

```bash
sqlite3 "D:\python project\claude-memory-system\data\memory.db"

# 查看总对话数
SELECT COUNT(*) FROM conversations;

# 查看各平台的对话数
SELECT platform, COUNT(*) FROM conversations GROUP BY platform;

# 查看最近的对话
SELECT summary, timestamp FROM conversations ORDER BY timestamp DESC LIMIT 10;
```

### 2. 测试上下文注入

```bash
# 在任意项目中打开 Claude Code
cd "D:\python project\claude-memory-system"
claude

# 检查 CLAUDE.md
cat .claude/CLAUDE.md
```

你应该能看到导入的历史对话！

### 3. 使用 API 查询

```bash
# 获取最近24小时的上下文
curl "http://localhost:8765/api/context?hours=24"

# 获取特定项目的上下文
curl "http://localhost:8765/api/context?project=POD系统"
```

---

## 🎉 总结

### 快速开始（5分钟）

1. 启动 Memory Hub
2. 运行 `python import_conversations.py`
3. 选择方式2，粘贴对话
4. 完成！

### 完整导入（1-2小时）

1. 整理所有历史对话
2. 按重要性分类
3. 使用批量导入工具
4. 验证导入结果

### 持续使用

- ✅ 安装浏览器插件
- ✅ 新对话自动捕获
- ✅ 无需再手动导入

---

**现在就开始导入你的历史对话吧！** 🚀
