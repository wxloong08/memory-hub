from pathlib import Path
import sys
import tempfile

from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main  # noqa: E402


client = TestClient(main.app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_ai_status_endpoint_contract():
    response = client.get("/api/ai/status")
    assert response.status_code == 200

    body = response.json()
    assert "available" in body
    assert "provider" in body
    assert "config_path" in body


def test_conversation_list_endpoint_contract():
    response = client.get("/api/conversations/list", params={"limit": 5, "offset": 0})
    assert response.status_code == 200

    body = response.json()
    assert "conversations" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body
    assert "has_more" in body
    assert isinstance(body["conversations"], list)

    if body["conversations"]:
        first = body["conversations"][0]
        assert "id" in first
        assert "platform" in first
        assert "provider" in first
        assert "model" in first
        assert "assistant_label" in first
        assert "timestamp" in first
        assert "summary" in first
        assert "importance" in first
        assert "summary_source" in first
        assert "recovery_mode" in first


def test_conversation_filters_endpoint_contract():
    response = client.get("/api/conversations/filters")
    assert response.status_code == 200

    body = response.json()
    assert "platforms" in body
    assert "models" in body
    assert "summary_sources" in body
    assert "recovery_modes" in body
    assert isinstance(body["platforms"], list)
    assert isinstance(body["models"], list)


def test_delete_conversation_endpoint_contract():
    payload = {
        "platform": "codex",
        "timestamp": "2026-03-15T10:00:00",
        "project": "delete test",
        "provider": "openai",
        "model": "gpt-5-codex",
        "assistant_label": "Codex",
        "summary": "delete test",
        "messages": [
            {"role": "user", "content": "请删除这条记录"},
            {"role": "assistant", "content": "可以删除。"},
        ],
    }
    create_response = client.post("/api/conversations", json=payload)
    assert create_response.status_code == 200
    conversation_id = create_response.json()["conversation_id"]

    delete_response = client.delete(f"/api/conversations/{conversation_id}")
    assert delete_response.status_code == 200
    body = delete_response.json()
    assert body["status"] == "ok"
    assert body["conversation_id"] == conversation_id
    assert body["deleted"] is True


def test_update_memory_tier_endpoint_contract():
    payload = {
        "platform": "codex",
        "timestamp": "2026-03-15T10:10:00",
        "project": "memory tier test",
        "provider": "openai",
        "model": "gpt-5-codex",
        "assistant_label": "Codex",
        "summary": "memory tier test",
        "messages": [
            {"role": "user", "content": "把这条会话设成长期记忆"},
            {"role": "assistant", "content": "可以标成保留或固定。"},
        ],
    }
    create_response = client.post("/api/conversations", json=payload)
    assert create_response.status_code == 200
    conversation_id = create_response.json()["conversation_id"]

    update_response = client.post(
        f"/api/conversations/{conversation_id}/memory-tier",
        json={"memory_tier": "saved"},
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["status"] == "ok"
    assert body["conversation_id"] == conversation_id
    assert body["memory_tier"] == "saved"


def test_memories_endpoint_contract():
    create_response = client.post(
        "/api/memories",
        json={
            "category": "general",
            "key": "preference",
            "value": "我喜欢简洁直接的回答。",
            "confidence": 0.9,
        },
    )
    assert create_response.status_code == 200
    memory_id = create_response.json()["memory_id"]

    list_response = client.get("/api/memories")
    assert list_response.status_code == 200
    body = list_response.json()
    assert "memories" in body
    assert isinstance(body["memories"], list)
    assert any(item["id"] == memory_id for item in body["memories"])
    created = next(item for item in body["memories"] if item["id"] == memory_id)
    assert "usage_count" in created
    assert "last_used_at" in created
    assert "client_usage" in created

    delete_response = client.delete(f"/api/memories/{memory_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True


def test_update_memory_endpoint_contract():
    create_response = client.post(
        "/api/memories",
        json={
            "category": "general",
            "key": "editing_test",
            "value": "原始记忆内容",
            "confidence": 0.6,
        },
    )
    assert create_response.status_code == 200
    memory_id = create_response.json()["memory_id"]

    update_response = client.post(
        f"/api/memories/{memory_id}",
        json={
            "category": "workflow",
            "key": "editing_test_updated",
            "value": "更新后的记忆内容",
            "confidence": 0.9,
        },
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert body["status"] == "ok"
    assert body["memory_id"] == memory_id
    assert body["updated"] is True

    list_response = client.get("/api/memories")
    assert list_response.status_code == 200
    updated = next(item for item in list_response.json()["memories"] if item["id"] == memory_id)
    assert updated["category"] == "workflow"
    assert updated["key"] == "editing_test_updated"
    assert updated["value"] == "更新后的记忆内容"
    assert float(updated["confidence"]) == 0.9


def test_update_memory_status_endpoint_contract():
    create_response = client.post(
        "/api/memories",
        json={
            "category": "general",
            "key": "archive_test",
            "value": "这条记忆稍后归档",
            "confidence": 0.7,
        },
    )
    assert create_response.status_code == 200
    memory_id = create_response.json()["memory_id"]

    status_response = client.post(
        f"/api/memories/{memory_id}/status",
        json={"status": "archived"},
    )
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "ok"
    assert body["memory_id"] == memory_id
    assert body["memory_status"] == "archived"

    list_response = client.get("/api/memories")
    assert list_response.status_code == 200
    archived = next(item for item in list_response.json()["memories"] if item["id"] == memory_id)
    assert archived["status"] == "archived"


def test_update_memory_priority_endpoint_contract():
    create_response = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "priority_test",
            "value": "这条记忆需要优先注入",
            "confidence": 0.8,
        },
    )
    assert create_response.status_code == 200
    memory_id = create_response.json()["memory_id"]

    priority_response = client.post(
        f"/api/memories/{memory_id}/priority",
        json={"priority": 100},
    )
    assert priority_response.status_code == 200
    body = priority_response.json()
    assert body["status"] == "ok"
    assert body["memory_id"] == memory_id
    assert body["priority"] == 100

    list_response = client.get("/api/memories")
    assert list_response.status_code == 200
    prioritized = next(item for item in list_response.json()["memories"] if item["id"] == memory_id)
    assert prioritized["priority"] == 100


def test_update_memory_client_rules_endpoint_contract():
    create_response = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "client_rules_test",
            "value": "这条记忆需要绑定客户端策略",
            "confidence": 0.75,
        },
    )
    assert create_response.status_code == 200
    memory_id = create_response.json()["memory_id"]

    rules_response = client.post(
        f"/api/memories/{memory_id}/client-rules",
        json={"client_rules": {"codex": "include", "gemini_cli": "exclude"}},
    )
    assert rules_response.status_code == 200
    body = rules_response.json()
    assert body["status"] == "ok"
    assert body["memory_id"] == memory_id
    assert body["client_rules"]["codex"] == "include"
    assert body["client_rules"]["gemini_cli"] == "exclude"

    list_response = client.get("/api/memories")
    assert list_response.status_code == 200
    updated = next(item for item in list_response.json()["memories"] if item["id"] == memory_id)
    assert updated["client_rules"]["codex"] == "include"
    assert updated["client_rules"]["gemini_cli"] == "exclude"


def test_memory_merge_endpoint_contract():
    left = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "answer_style",
            "value": "用户偏好简洁直接的回答。",
            "confidence": 0.8,
        },
    )
    right = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "answer_style",
            "value": "用户偏好简洁直接的回答，减少铺垫。",
            "confidence": 0.9,
        },
    )
    assert left.status_code == 200
    assert right.status_code == 200

    response = client.post(
        "/api/memories/merge",
        json={
            "left_id": left.json()["memory_id"],
            "right_id": right.json()["memory_id"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "merged_memory_id" in body
    assert body["memory"]["key"] == "answer_style"
    assert body["deleted_source_ids"] == []

    list_response = client.get("/api/memories")
    assert list_response.status_code == 200
    memories = list_response.json()["memories"]
    merged = next(item for item in memories if item["id"] == body["merged_memory_id"])
    assert "parent_memories" in merged
    assert len(merged["parent_memories"]) >= 2
    assert "timeline" in merged
    assert isinstance(merged["timeline"], list)
    assert merged["timeline"]


def test_memory_merge_and_delete_sources_endpoint_contract():
    left = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "follow_up",
            "value": "用户喜欢直接给出下一步行动。",
            "confidence": 0.7,
        },
    )
    right = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "follow_up",
            "value": "用户喜欢直接给出下一步行动，减少背景铺垫。",
            "confidence": 0.85,
        },
    )
    assert left.status_code == 200
    assert right.status_code == 200

    response = client.post(
        "/api/memories/merge",
        json={
            "left_id": left.json()["memory_id"],
            "right_id": right.json()["memory_id"],
            "delete_sources": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert sorted(body["deleted_source_ids"]) == sorted([left.json()["memory_id"], right.json()["memory_id"]])


def test_memory_conflicts_endpoint_contract():
    left = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "answer_style",
            "value": "我喜欢简洁直接的回答。",
            "confidence": 0.88,
        },
    )
    right = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "answer_style",
            "value": "我不喜欢简洁直接的回答，避免过于简短。",
            "confidence": 0.91,
        },
    )
    assert left.status_code == 200
    assert right.status_code == 200

    response = client.get("/api/memories/conflicts", params={"limit": 20})
    assert response.status_code == 200
    body = response.json()
    assert "conflicts" in body
    assert "count" in body
    assert isinstance(body["conflicts"], list)
    assert body["count"] >= 1


def test_memory_cleanup_suggestions_endpoint_contract():
    create_response = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "temporary_note",
            "value": "这个记忆目前还没有被任何客户端真正用到。",
            "confidence": 0.6,
        },
    )
    assert create_response.status_code == 200

    response = client.get("/api/memories/cleanup-suggestions", params={"limit": 20})
    assert response.status_code == 200
    body = response.json()
    assert "suggestions" in body
    assert "count" in body
    assert isinstance(body["suggestions"], list)
    assert body["count"] >= 1
    candidate = next(item for item in body["suggestions"] if item["memory"]["id"] == create_response.json()["memory_id"])
    assert "reasons" in candidate
    assert "unused_in_exports" in candidate["reasons"]


def test_memory_conflict_resolution_endpoint_contract():
    left = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "verbosity",
            "value": "我喜欢简洁直接的回答。",
            "confidence": 0.82,
        },
    )
    right = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "verbosity",
            "value": "我不喜欢过于简洁的回答，避免太短。",
            "confidence": 0.87,
        },
    )
    assert left.status_code == 200
    assert right.status_code == 200

    keep_response = client.post(
        "/api/memories/conflicts/resolve",
        json={
            "left_id": left.json()["memory_id"],
            "right_id": right.json()["memory_id"],
            "action": "keep_left",
        },
    )
    assert keep_response.status_code == 200
    keep_body = keep_response.json()
    assert keep_body["status"] == "ok"
    assert keep_body["action"] == "keep_left"
    assert keep_body["kept_memory_id"] == left.json()["memory_id"]
    assert keep_body["deleted_memory_id"] == right.json()["memory_id"]

    merge_left = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "follow_up_style",
            "value": "我通常希望先给结论。",
            "confidence": 0.8,
        },
    )
    merge_right = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "follow_up_style",
            "value": "我不希望一开始就只给结论，避免太武断。",
            "confidence": 0.86,
        },
    )
    assert merge_left.status_code == 200
    assert merge_right.status_code == 200

    merge_response = client.post(
        "/api/memories/conflicts/resolve",
        json={
            "left_id": merge_left.json()["memory_id"],
            "right_id": merge_right.json()["memory_id"],
            "action": "merge_new",
        },
    )
    assert merge_response.status_code == 200
    merge_body = merge_response.json()
    assert merge_body["status"] == "ok"
    assert merge_body["action"] == "merge_new"
    assert merge_body["merged_memory_id"] is not None


def test_extract_memory_keeps_conversation_source_contract():
    payload = {
        "platform": "codex",
        "timestamp": "2026-03-16T09:00:00",
        "project": "memory source test",
        "provider": "openai",
        "model": "gpt-5-codex",
        "assistant_label": "Codex",
        "summary": "memory source test",
        "messages": [
            {"role": "user", "content": "我喜欢简洁直接的回答，而且我通常先看结论再看细节。"},
            {"role": "assistant", "content": "收到，我会先给结论。"},
        ],
    }
    create_response = client.post("/api/conversations", json=payload)
    assert create_response.status_code == 200
    conversation_id = create_response.json()["conversation_id"]

    extract_response = client.post(f"/api/memories/extract/{conversation_id}")
    assert extract_response.status_code == 200

    memories_response = client.get("/api/memories")
    assert memories_response.status_code == 200
    body = memories_response.json()
    assert "memories" in body
    sourced = [item for item in body["memories"] if item.get("source_count", 0) > 0]
    assert sourced
    assert any(
        source.get("conversation_id") == conversation_id
        for item in sourced
        for source in item.get("sources", [])
    )
    assert any(float(item.get("effective_confidence") or 0) >= float(item.get("confidence") or 0) for item in sourced)


def test_conversation_memories_endpoint_contract():
    payload = {
        "platform": "codex",
        "timestamp": "2026-03-16T09:10:00",
        "project": "conversation memories test",
        "provider": "openai",
        "model": "gpt-5-codex",
        "assistant_label": "Codex",
        "summary": "conversation memories test",
        "messages": [
            {"role": "user", "content": "我喜欢先看结论再看细节。"},
            {"role": "assistant", "content": "我会先给结论。"},
        ],
    }
    create_response = client.post("/api/conversations", json=payload)
    assert create_response.status_code == 200
    conversation_id = create_response.json()["conversation_id"]

    extract_response = client.post(f"/api/memories/extract/{conversation_id}")
    assert extract_response.status_code == 200

    response = client.get(f"/api/conversations/{conversation_id}/memories")
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == conversation_id
    assert "memories" in body
    assert "count" in body
    assert isinstance(body["memories"], list)


def test_search_endpoint_contract():
    memory_create = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "search_pref",
            "value": "用户希望跨客户端记忆中心能接上之前的上下文。",
            "confidence": 0.85,
        },
    )
    assert memory_create.status_code == 200

    response = client.get("/api/search", params={"query": "跨平台记忆系统", "limit": 3})
    assert response.status_code == 200

    body = response.json()
    assert body["query"] == "跨平台记忆系统"
    assert "results" in body
    assert "memory_results" in body
    assert "count" in body
    assert "memory_count" in body
    assert isinstance(body["results"], list)
    assert isinstance(body["memory_results"], list)

    if body["results"]:
        first = body["results"][0]
        assert "id" in first
        assert "platform" in first
        assert "provider" in first
        assert "model" in first
        assert "assistant_label" in first
        assert "summary" in first
        assert "timestamp" in first
        assert "similarity" in first
        assert "content_preview" in first

    if body["memory_results"]:
        memory_first = body["memory_results"][0]
        assert "id" in memory_first
        assert "category" in memory_first
        assert "key" in memory_first
        assert "value" in memory_first


def test_memory_export_simulator_endpoint_contract():
    create_response = client.post(
        "/api/memories",
        json={
            "category": "workflow",
            "key": "simulator_pref",
            "value": "用户希望接手前端重构时先看任务目标、约束和下一步行动。",
            "confidence": 0.9,
        },
    )
    assert create_response.status_code == 200

    response = client.post(
        "/api/memories/export-simulate",
        json={
            "client": "codex",
            "project": "travelmind",
            "prompt": "我要让 Codex 接手一个前端重构任务，需要知道目标、约束和工作流。",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["client"] == "codex"
    assert "strategy_summary" in body
    assert "selected_memories" in body
    assert "simulation" in body
    assert body["simulation"]["project"] == "travelmind"
    assert body["simulation"]["prompt"]
    assert isinstance(body["selected_memories"], list)


def test_resummarize_endpoint_contract():
    payload = {
        "platform": "codex",
        "timestamp": "2026-03-13T12:30:00",
        "project": "rollout-2026-03-13T12-51-12-019ce588-c72e-75d2-8e2c-6e0c97a87eff",
        "provider": "openai",
        "model": "gpt-5-codex",
        "assistant_label": "Codex",
        "summary": "rollout-2026-03-13T12-51-12-019ce588-c72e-75d2-8e2c-6e0c97a87eff",
        "messages": [
            {"role": "user", "content": "帮我分析这个 rollout 的问题定位步骤。"},
            {"role": "assistant", "content": "先检查日志、回滚策略和受影响服务，再整理修复方案。"},
        ],
    }
    create_response = client.post("/api/conversations", json=payload)
    assert create_response.status_code == 200
    conversation_id = create_response.json()["conversation_id"]

    response = client.post(
        "/api/conversations/resummarize",
        json={"conversation_ids": [conversation_id], "force": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert "updated_count" in body
    assert "results" in body
    assert body["results"][0]["conversation_id"] == conversation_id


def test_resummarize_ugly_endpoint_contract():
    payload = {
        "platform": "claude_code",
        "timestamp": "2026-03-13T13:10:00",
        "project": "agent-a5bf2679d75af9e20",
        "provider": "anthropic",
        "model": "claude-sonnet",
        "assistant_label": "Claude Code",
        "summary": "agent-a5bf2679d75af9e20",
        "messages": [
            {"role": "user", "content": "帮我整理这个 agent 会话的主要目标。"},
            {"role": "assistant", "content": "主要目标是梳理任务、定位问题并给出后续动作。"},
        ],
    }
    create_response = client.post("/api/conversations", json=payload)
    assert create_response.status_code == 200

    response = client.post("/api/conversations/resummarize-ugly", json={"limit": 10, "force": False})
    assert response.status_code == 200
    body = response.json()
    assert "updated_count" in body
    assert "results" in body


def test_add_conversation_deduplicates_same_source_payload():
    payload = {
        "platform": "codex",
        "timestamp": "2026-03-13T13:00:00",
        "project": "dedupe test",
        "provider": "openai",
        "model": "gpt-5-codex",
        "assistant_label": "Codex",
        "summary": "dedupe test",
        "source_path": "C:\\Users\\wu\\.codex\\sessions\\dedupe.jsonl",
        "source_fingerprint": "123:456",
        "content_hash": "abc123dedupe",
        "messages": [
            {"role": "user", "content": "第一条"},
            {"role": "assistant", "content": "第二条"},
        ],
    }
    first = client.post("/api/conversations", json=payload)
    second = client.post("/api/conversations", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["conversation_id"] == second.json()["conversation_id"]


def test_analyze_endpoint_contract():
    list_response = client.get("/api/conversations/list", params={"limit": 1})
    assert list_response.status_code == 200
    conversations = list_response.json()["conversations"]
    assert conversations

    conversation_id = conversations[0]["id"]
    response = client.post(f"/api/analyze/{conversation_id}")
    assert response.status_code == 200

    body = response.json()
    assert body["conversation_id"] == conversation_id
    assert "ai_available" in body
    assert "analysis" in body
    assert "summary" in body["analysis"]


def test_add_conversation_prefers_provided_summary():
    payload = {
        "platform": "claude_web",
        "timestamp": "2026-03-12T12:00:00",
        "project": "decode测评",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "assistant_label": "Claude Sonnet 4",
        "summary": "Official export style summary from Claude.",
        "messages": [
            {"role": "user", "content": "怎么测试这个代理？"},
            {"role": "assistant", "content": "可以先用 curl 和浏览器代理配置测试。"},
        ],
    }

    create_response = client.post("/api/conversations", json=payload)
    assert create_response.status_code == 200

    conversation_id = create_response.json()["conversation_id"]
    get_response = client.get(f"/api/conversations/{conversation_id}")
    assert get_response.status_code == 200

    body = get_response.json()
    assert body["summary"] == payload["summary"]
    assert body["summary_source"] == "imported"
    assert body["provider"] == payload["provider"]
    assert body["model"] == payload["model"]
    assert body["assistant_label"] == payload["assistant_label"]


def test_derive_summary_builds_overview_when_no_summary_provided():
    summary = main._derive_summary(
        [
            {"role": "user", "content": "怎么用 fast.com 测试 socks5 代理？"},
            {"role": "assistant", "content": "可以先在浏览器中配置代理，再访问 fast.com 进行测速。"},
        ],
        "decode测评",
        None,
    )

    assert "decode测评" in summary
    assert "fast.com" in summary


def test_export_clients_endpoint_contract():
    response = client.get("/api/export/clients")
    assert response.status_code == 200

    body = response.json()
    assert "clients" in body
    assert isinstance(body["clients"], list)
    assert any(item["client"] == "codex" for item in body["clients"])


def test_conversation_export_preview_and_apply():
    memory_create = client.post(
        "/api/memories",
        json={
            "category": "preference",
            "key": "answer_style",
            "value": "用户偏好简洁直接的回答。",
            "confidence": 0.9,
        },
    )
    assert memory_create.status_code == 200

    payload = {
        "platform": "codex",
        "timestamp": "2026-03-13T12:00:00",
        "project": "resume test",
        "provider": "openai",
        "model": "gpt-5-codex",
        "assistant_label": "Codex",
        "summary": "Resume export test conversation.",
        "messages": [
            {"role": "user", "content": "继续这个会话"},
            {"role": "assistant", "content": "好的，我会保留之前的上下文。"},
        ],
    }

    create_response = client.post("/api/conversations", json=payload)
    assert create_response.status_code == 200
    conversation_id = create_response.json()["conversation_id"]

    preview_response = client.get(
        f"/api/conversations/{conversation_id}/export",
        params={"client": "codex"},
    )
    assert preview_response.status_code == 200
    preview_body = preview_response.json()
    assert preview_body["client"] == "codex"
    assert preview_body["filename"] == "AGENTS.md"
    assert preview_body["memory_count"] >= 1
    assert preview_body["total_memory_count"] >= preview_body["memory_count"]
    assert "strategy_summary" in preview_body
    assert "selected_memories" in preview_body
    assert isinstance(preview_body["selected_memories"], list)
    assert "reasons" in preview_body["selected_memories"][0]
    assert "Resume Context" in preview_body["content"]
    assert "Pinned Memory" in preview_body["content"]
    assert "answer_style" in preview_body["content"]

    explicit_preview_response = client.get(
        f"/api/conversations/{conversation_id}/export",
        params={"client": "codex", "selected_memory_ids": str(memory_id)},
    )
    assert explicit_preview_response.status_code == 200
    explicit_preview_body = explicit_preview_response.json()
    assert explicit_preview_body["selected_memory_ids"] == [memory_id]
    assert explicit_preview_body["memory_count"] == 1

    forced_memory = client.post(
        "/api/memories",
        json={
            "category": "preference",
            "key": "forced_for_codex",
            "value": "这条记忆应该总是导给 Codex。",
            "confidence": 0.4,
        },
    )
    assert forced_memory.status_code == 200
    forced_memory_id = forced_memory.json()["memory_id"]
    forced_rules = client.post(
        f"/api/memories/{forced_memory_id}/client-rules",
        json={"client_rules": {"codex": "include"}},
    )
    assert forced_rules.status_code == 200

    forced_preview_response = client.get(
        f"/api/conversations/{conversation_id}/export",
        params={"client": "codex"},
    )
    assert forced_preview_response.status_code == 200
    forced_preview_body = forced_preview_response.json()
    assert forced_memory_id in forced_preview_body["selected_memory_ids"]

    with tempfile.TemporaryDirectory() as temp_dir:
        apply_response = client.post(
            f"/api/conversations/{conversation_id}/export/apply",
            json={"client": "codex", "workspace_path": temp_dir, "selected_memory_ids": [memory_id]},
        )
        assert apply_response.status_code == 200
        apply_body = apply_response.json()
        target_path = Path(apply_body["target_path"])
        assert target_path.exists()
        assert target_path.name == "AGENTS.md"
        assert "Resume Context" in target_path.read_text(encoding="utf-8")
        assert "Pinned Memory" in target_path.read_text(encoding="utf-8")

    memories_after_apply = client.get("/api/memories")
    assert memories_after_apply.status_code == 200
    applied_memory = next(item for item in memories_after_apply.json()["memories"] if item["id"] == memory_id)
    assert applied_memory["usage_count"] >= 1
    assert any(client_usage["client_id"] == "codex" for client_usage in applied_memory["client_usage"])


def test_backup_export_endpoint_contract():
    response = client.post("/api/backup/export")
    assert response.status_code == 200

    body = response.json()
    assert "backup_dir" in body
    assert "backup_zip" in body
    assert "conversation_count" in body
    assert "files" in body
    assert "manifest_path" in body

    backup_dir = Path(body["backup_dir"])
    manifest_path = Path(body["manifest_path"])
    assert backup_dir.exists()
    assert manifest_path.exists()
    assert (backup_dir / "conversations.jsonl").exists()
    assert Path(body["backup_zip"]).exists()


def test_backup_settings_endpoint_contract():
    response = client.get("/api/backup/settings")
    assert response.status_code == 200

    body = response.json()
    assert "settings" in body
    assert "backups" in body
    assert "enabled" in body["settings"]
    assert "interval_hours" in body["settings"]
    assert "retention_count" in body["settings"]
    assert "backup_root" in body["settings"]

    update_response = client.post(
        "/api/backup/settings",
        json={"enabled": True, "interval_hours": 12, "retention_count": 5, "backup_root": None},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["settings"]["enabled"] is True
    assert updated["settings"]["interval_hours"] == 12
    assert updated["settings"]["retention_count"] == 5


def test_backup_restore_endpoint_contract():
    export_response = client.post("/api/backup/export")
    assert export_response.status_code == 200
    backup_dir = export_response.json()["backup_dir"]
    backup_zip = export_response.json()["backup_zip"]

    restore_response = client.post("/api/backup/restore", json={"source_path": backup_dir})
    assert restore_response.status_code == 200

    body = restore_response.json()
    assert body["restored_from"] == backup_dir
    assert "restored_at" in body
    assert "restored_db_path" in body
    assert "safety_backup" in body

    zip_restore_response = client.post("/api/backup/restore", json={"source_path": backup_zip})
    assert zip_restore_response.status_code == 200
    zip_body = zip_restore_response.json()
    assert zip_body["source_type"] == "zip"
    assert zip_body["restored_from_zip"] == backup_zip


def test_backup_preview_endpoint_contract():
    export_response = client.post("/api/backup/export")
    assert export_response.status_code == 200
    backup_dir = export_response.json()["backup_dir"]
    backup_zip = export_response.json()["backup_zip"]

    dir_preview = client.get("/api/backup/preview", params={"source_path": backup_dir})
    assert dir_preview.status_code == 200
    assert dir_preview.json()["source_type"] == "directory"
    assert "manifest" in dir_preview.json()

    zip_preview = client.get("/api/backup/preview", params={"source_path": backup_zip})
    assert zip_preview.status_code == 200
    assert zip_preview.json()["source_type"] == "zip"
    assert "manifest" in zip_preview.json()


def test_backup_validate_endpoint_contract():
    export_response = client.post("/api/backup/export")
    assert export_response.status_code == 200
    backup_dir = export_response.json()["backup_dir"]
    backup_zip = export_response.json()["backup_zip"]

    dir_validation = client.get("/api/backup/validate", params={"source_path": backup_dir})
    assert dir_validation.status_code == 200
    dir_body = dir_validation.json()
    assert "valid" in dir_body
    assert "checks" in dir_body
    assert "errors" in dir_body

    zip_validation = client.get("/api/backup/validate", params={"source_path": backup_zip})
    assert zip_validation.status_code == 200
    zip_body = zip_validation.json()
    assert "valid" in zip_body
    assert "checks" in zip_body
    assert "errors" in zip_body
