"""
Claude Memory System - Vector Store
Uses ChromaDB with a deterministic local embedding function so search works
without downloading external ONNX models at runtime.
"""

import math
import os
import re
from hashlib import sha256
from typing import Dict, Iterable, List

import chromadb
from chromadb.config import Settings


class LocalHashEmbeddingFunction:
    """Small deterministic embedding function for offline semantic retrieval."""

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def __call__(self, input: Iterable[str]) -> List[List[float]]:
        return [self._embed(text or "") for text in input]

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        normalized = (text or "").lower()

        tokens = re.findall(r"\w+|[\u4e00-\u9fff]", normalized, flags=re.UNICODE)
        if not tokens:
            return vector

        for token in tokens:
            self._add_feature(vector, token, 1.0)

        compact = re.sub(r"\s+", "", normalized)
        for index in range(max(0, len(compact) - 2)):
            self._add_feature(vector, compact[index:index + 3], 0.35)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def _add_feature(self, vector: List[float], token: str, weight: float):
        digest = sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % self.dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign * weight


class VectorStore:
    COLLECTION_NAME = "conversations_local_v1"

    def __init__(self, persist_directory: str = "data/vectors"):
        """初始化向量存储"""
        os.makedirs(persist_directory, exist_ok=True)

        self.embedding_function = LocalHashEmbeddingFunction()
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.embedding_function,
        )

        print(f"✅ VectorStore initialized with {self.collection.count()} documents")

    def add_conversation(self, conv_id: str, content: str, metadata: Dict = None):
        """添加或更新对话到向量存储"""
        try:
            self.collection.upsert(
                ids=[conv_id],
                documents=[content],
                metadatas=[metadata or {}],
            )
            print(f"✅ Indexed conversation {conv_id[:8]}... in vector store")
            return True
        except Exception as e:
            print(f"❌ Error adding to vector store: {e}")
            return False

    def sync_from_records(self, records: List[Dict]):
        """Bulk upsert database records into the vector store."""
        if not records:
            return

        ids = []
        documents = []
        metadatas = []
        for record in records:
            conv_id = record.get("id")
            if not conv_id:
                continue
            ids.append(conv_id)
            documents.append(record.get("full_content", "") or "")
            metadatas.append({
                "platform": record.get("platform", "unknown"),
                "timestamp": str(record.get("timestamp", "") or ""),
                "project": record.get("project", "") or "",
                "provider": record.get("provider", "") or "",
                "model": record.get("model", "") or "",
                "assistant_label": record.get("assistant_label", "") or "",
                "importance": int(record.get("importance", 5) or 5),
                "summary": record.get("summary", "") or "",
            })

        if not ids:
            return

        try:
            self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            print(f"✅ Synced {len(ids)} conversations into vector store")
        except Exception as e:
            print(f"❌ Error syncing vector store: {e}")

    def search(self, query: str, top_k: int = 5, filter_metadata: Dict = None) -> List[Dict]:
        """搜索相似对话"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=filter_metadata,
            )

            formatted_results = []
            if results["ids"] and len(results["ids"][0]) > 0:
                for index in range(len(results["ids"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][index],
                        "content": results["documents"][0][index],
                        "distance": results["distances"][0][index] if "distances" in results else None,
                        "metadata": results["metadatas"][0][index] if "metadatas" in results else {},
                    })

            return formatted_results
        except Exception as e:
            print(f"❌ Error searching vector store: {e}")
            return []

    def find_related_conversations(self, conv_id: str, top_k: int = 3) -> List[Dict]:
        """查找与指定对话相关的其他对话"""
        try:
            result = self.collection.get(ids=[conv_id], include=["documents", "metadatas"])
            documents = result.get("documents") or []
            if not documents:
                return []

            content = documents[0]
            all_results = self.search(content, top_k=top_k + 1)
            return [item for item in all_results if item["id"] != conv_id][:top_k]
        except Exception as e:
            print(f"❌ Error finding related conversations: {e}")
            return []

    def delete_conversation(self, conv_id: str):
        """删除对话"""
        try:
            self.collection.delete(ids=[conv_id])
            print(f"✅ Deleted conversation {conv_id[:8]}... from vector store")
            return True
        except Exception as e:
            print(f"❌ Error deleting from vector store: {e}")
            return False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_documents": self.collection.count(),
            "collection_name": self.collection.name,
            "embedding": "local_hash_v1",
        }

    def reset(self):
        """重置向量存储（谨慎使用）"""
        self.client.reset()
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.embedding_function,
        )
        print("⚠️  Vector store has been reset")
