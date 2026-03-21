# Phase 0: 统一数据契约（前置任务）

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan.
> **评审来源**: Gemini 建议"先定义数据契约"，Codex 确认前后端字段不匹配，Claude 综合裁决。

**Goal:** 在后端定义统一的 API 响应格式，确保 Web UI 和浏览器插件能正确消费数据。

**预计耗时:** 30 分钟

---

### Task 1: 转换 /api/search 响应为前端友好格式

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 修改 search endpoint**

当前后端返回 vector_store 原始格式 `{id, content, distance, metadata}`，前端需要 `{id, platform, summary, timestamp, similarity}`。

将 `backend/main.py` 中的 `/api/search` 端点替换为：

```python
@app.get("/api/search")
async def search_conversations(query: str, limit: int = 5):
    """Semantic search for conversations"""
    raw_results = vector_store.search(query, top_k=limit)

    # Transform to frontend-friendly format
    results = []
    for r in raw_results:
        meta = r.get("metadata", {})
        results.append({
            "id": r["id"],
            "platform": meta.get("platform", "unknown"),
            "summary": meta.get("summary", r.get("content", "")[:200]),
            "timestamp": meta.get("timestamp", ""),
            "similarity": round(1 - r.get("distance", 0), 3) if r.get("distance") is not None else 0,
            "content_preview": r.get("content", "")[:300]
        })

    return {
        "query": query,
        "results": results,
        "count": len(results)
    }
```

- [ ] **Step 2: 同样转换 /api/related 端点**

```python
@app.get("/api/related/{conversation_id}")
async def get_related_conversations(conversation_id: str, limit: int = 3):
    """Get related conversations based on similarity"""
    raw_related = vector_store.find_related_conversations(conversation_id, top_k=limit)

    related = []
    for r in raw_related:
        meta = r.get("metadata", {})
        related.append({
            "id": r["id"],
            "platform": meta.get("platform", "unknown"),
            "summary": meta.get("summary", r.get("content", "")[:200]),
            "similarity": round(1 - r.get("distance", 0), 3) if r.get("distance") is not None else 0,
        })

    return {
        "conversation_id": conversation_id,
        "related": related,
        "count": len(related)
    }
```

---

### Task 2: 新增结构化对话列表 API

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: 添加 /api/conversations/list 端点**

```python
@app.get("/api/conversations/list")
async def list_conversations(
    hours: int = 720,
    min_importance: int = 1,
    platform: str = None,
    limit: int = 50
):
    """List conversations as structured JSON for Web UI."""
    conversations = db.get_recent_conversations(
        hours=hours,
        min_importance=min_importance,
        working_dir=None
    )

    results = []
    for conv in conversations:
        if platform and conv.get('platform') != platform:
            continue
        results.append({
            'id': conv.get('id', ''),
            'platform': conv.get('platform', 'unknown'),
            'timestamp': conv.get('timestamp', ''),
            'summary': conv.get('summary', ''),
            'importance': conv.get('importance', 5),
            'project': conv.get('project', None),
            'status': conv.get('status', 'completed')
        })

    return {
        'conversations': results[:limit],
        'total': len(results)
    }
```

- [ ] **Step 2: 添加 /api/conversations/{id} 端点**

```python
@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a single conversation by ID with full content."""
    cursor = db.conn.execute(
        "SELECT * FROM conversations WHERE id = ?",
        (conversation_id,)
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return dict(row)
```

- [ ] **Step 3: Commit**

```bash
cd "D:/python project/claude-memory-system"
git add backend/main.py
git commit -m "feat: add structured JSON API endpoints and transform search/related responses"
```
