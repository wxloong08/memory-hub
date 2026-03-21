"""
Tests for VectorStore module
Tests vector storage, search, and embedding functionality
"""

import os
import shutil
import tempfile

import pytest

from backend.vector_store import LocalHashEmbeddingFunction, VectorStore


@pytest.fixture
def temp_vector_dir():
    """Create temporary directory for vector store"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def vector_store(temp_vector_dir):
    """Create a VectorStore instance with temp directory"""
    return VectorStore(temp_vector_dir)


class TestLocalHashEmbeddingFunction:
    """Test the local hash embedding function"""

    def test_produces_correct_dimensions(self):
        ef = LocalHashEmbeddingFunction(dimensions=128)
        result = ef(["hello world"])
        assert len(result) == 1
        assert len(result[0]) == 128

    def test_default_dimensions(self):
        ef = LocalHashEmbeddingFunction()
        result = ef(["test"])
        assert len(result[0]) == 256

    def test_multiple_inputs(self):
        ef = LocalHashEmbeddingFunction()
        result = ef(["hello", "world", "test"])
        assert len(result) == 3

    def test_empty_string(self):
        ef = LocalHashEmbeddingFunction()
        result = ef([""])
        assert len(result) == 1
        assert all(v == 0.0 for v in result[0])

    def test_none_input(self):
        ef = LocalHashEmbeddingFunction()
        result = ef([None])
        assert len(result) == 1
        assert all(v == 0.0 for v in result[0])

    def test_normalized_output(self):
        ef = LocalHashEmbeddingFunction()
        result = ef(["hello world this is a test"])
        vector = result[0]
        norm = sum(v * v for v in vector) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_deterministic(self):
        ef = LocalHashEmbeddingFunction()
        r1 = ef(["hello world"])
        r2 = ef(["hello world"])
        assert r1 == r2

    def test_different_texts_different_embeddings(self):
        ef = LocalHashEmbeddingFunction()
        r1 = ef(["hello world"])[0]
        r2 = ef(["goodbye universe"])[0]
        assert r1 != r2

    def test_unicode_text(self):
        ef = LocalHashEmbeddingFunction()
        result = ef(["你好世界 这是测试"])
        assert len(result) == 1
        assert len(result[0]) == 256
        norm = sum(v * v for v in result[0]) ** 0.5
        assert abs(norm - 1.0) < 1e-6


class TestVectorStoreInit:
    """Test VectorStore initialization"""

    def test_creates_directory(self, temp_vector_dir):
        sub_dir = os.path.join(temp_vector_dir, "sub", "vectors")
        vs = VectorStore(sub_dir)
        assert os.path.exists(sub_dir)

    def test_starts_empty(self, vector_store):
        stats = vector_store.get_stats()
        assert stats["total_documents"] == 0

    def test_stats_structure(self, vector_store):
        stats = vector_store.get_stats()
        assert "total_documents" in stats
        assert "collection_name" in stats
        assert "embedding" in stats
        assert stats["embedding"] == "local_hash_v1"


class TestVectorStoreOperations:
    """Test VectorStore CRUD operations"""

    def test_add_conversation(self, vector_store):
        result = vector_store.add_conversation(
            "conv-1",
            "This is a test conversation about FastAPI",
            {"platform": "claude_web", "importance": 8},
        )
        assert result is True
        assert vector_store.get_stats()["total_documents"] == 1

    def test_add_multiple_conversations(self, vector_store):
        for i in range(5):
            vector_store.add_conversation(
                f"conv-{i}",
                f"Conversation {i} about topic {i}",
                {"platform": "claude_web"},
            )
        assert vector_store.get_stats()["total_documents"] == 5

    def test_upsert_same_id(self, vector_store):
        meta = {"platform": "test"}
        vector_store.add_conversation("conv-1", "Original content", meta)
        vector_store.add_conversation("conv-1", "Updated content", meta)
        assert vector_store.get_stats()["total_documents"] == 1

    def test_delete_conversation(self, vector_store):
        vector_store.add_conversation("conv-1", "Test content", {"platform": "test"})
        assert vector_store.get_stats()["total_documents"] == 1

        result = vector_store.delete_conversation("conv-1")
        assert result is True
        assert vector_store.get_stats()["total_documents"] == 0

    def test_delete_nonexistent(self, vector_store):
        result = vector_store.delete_conversation("nonexistent")
        assert result is True  # ChromaDB doesn't error on missing IDs

    def test_reset(self, vector_store):
        for i in range(3):
            vector_store.add_conversation(f"conv-{i}", f"Content {i}", {"platform": "test"})
        assert vector_store.get_stats()["total_documents"] == 3

        vector_store.reset()
        assert vector_store.get_stats()["total_documents"] == 0


class TestVectorStoreSearch:
    """Test VectorStore search functionality"""

    @pytest.fixture(autouse=True)
    def populate_store(self, vector_store):
        conversations = [
            ("conv-1", "Building a FastAPI web service with authentication"),
            ("conv-2", "Designing a database schema for user management"),
            ("conv-3", "Implementing machine learning model training pipeline"),
            ("conv-4", "Debugging React frontend component rendering issues"),
            ("conv-5", "Setting up CI/CD pipeline with GitHub Actions"),
        ]
        for conv_id, content in conversations:
            vector_store.add_conversation(
                conv_id, content, {"platform": "claude_web", "importance": 7}
            )

    def test_search_returns_results(self, vector_store):
        results = vector_store.search("FastAPI web service", top_k=3)
        assert len(results) > 0
        assert len(results) <= 3

    def test_search_result_structure(self, vector_store):
        results = vector_store.search("database", top_k=1)
        assert len(results) >= 1
        result = results[0]
        assert "id" in result
        assert "content" in result
        assert "distance" in result
        assert "metadata" in result

    def test_search_empty_query(self, vector_store):
        results = vector_store.search("", top_k=3)
        assert isinstance(results, list)

    def test_search_top_k_limit(self, vector_store):
        results = vector_store.search("programming", top_k=2)
        assert len(results) <= 2

    def test_find_related_conversations(self, vector_store):
        results = vector_store.find_related_conversations("conv-1", top_k=2)
        assert len(results) <= 2
        assert all(r["id"] != "conv-1" for r in results)

    def test_find_related_nonexistent(self, vector_store):
        results = vector_store.find_related_conversations("nonexistent", top_k=2)
        assert results == []


class TestVectorStoreSyncFromRecords:
    """Test bulk sync functionality"""

    def test_sync_from_records(self, vector_store):
        records = [
            {
                "id": f"conv-{i}",
                "full_content": f"Content for conversation {i}",
                "platform": "claude_web",
                "timestamp": "2026-03-10T10:00:00",
                "project": "test",
                "provider": "anthropic",
                "model": "claude-sonnet",
                "assistant_label": "Claude",
                "importance": 7,
                "summary": f"Summary {i}",
            }
            for i in range(5)
        ]
        vector_store.sync_from_records(records)
        assert vector_store.get_stats()["total_documents"] == 5

    def test_sync_empty_records(self, vector_store):
        vector_store.sync_from_records([])
        assert vector_store.get_stats()["total_documents"] == 0

    def test_sync_records_with_missing_fields(self, vector_store):
        records = [
            {"id": "conv-1", "full_content": "Some content"},
            {"id": "conv-2"},  # Missing full_content
        ]
        vector_store.sync_from_records(records)
        assert vector_store.get_stats()["total_documents"] == 2

    def test_sync_records_without_id_skipped(self, vector_store):
        records = [
            {"full_content": "No ID"},
            {"id": "conv-1", "full_content": "Has ID"},
        ]
        vector_store.sync_from_records(records)
        assert vector_store.get_stats()["total_documents"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
