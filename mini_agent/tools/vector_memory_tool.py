"""Workspace-aware semantic memory tools.

This module intentionally uses a small local vector store so the feature works
without heavyweight runtime dependencies. The embedding is hashing-based, which
is suitable for demos and tests; production deployments can replace the store or
embedding provider behind the same Tool interface.
"""

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .base import Tool, ToolResult
from .memory_path import get_workspace_id


class HashingEmbeddingProvider:
    """Deterministic lightweight embedding provider."""

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class LocalVectorMemoryStore:
    """JSON-backed vector store with workspace metadata filtering."""

    def __init__(self, persist_dir: str, collection_name: str = "mini_agent_memory"):
        self.persist_dir = Path(persist_dir).expanduser()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.store_file = self.persist_dir / f"{collection_name}.json"

    def _load(self) -> list[dict[str, Any]]:
        if not self.store_file.exists():
            return []
        try:
            data = json.loads(self.store_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save(self, records: list[dict[str, Any]]) -> None:
        self.store_file.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, record: dict[str, Any]) -> None:
        records = self._load()
        records.append(record)
        self._save(records)

    def query(
        self,
        query_embedding: list[float],
        workspace_id: str,
        top_k: int,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        candidates = []
        for record in self._load():
            if record.get("workspace_id") != workspace_id:
                continue
            if category and record.get("category") != category:
                continue
            score = cosine_similarity(query_embedding, record.get("embedding", []))
            candidates.append((score, record))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                **record,
                "score": round(score, 4),
            }
            for score, record in candidates[: max(1, top_k)]
        ]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


class VectorRecordNoteTool(Tool):
    """Record a note into workspace-scoped semantic memory."""

    def __init__(self, workspace_dir: str, persist_dir: str, collection_name: str = "mini_agent_memory"):
        self.workspace_id = get_workspace_id(workspace_dir)
        self.store = LocalVectorMemoryStore(persist_dir=persist_dir, collection_name=collection_name)
        self.embedder = HashingEmbeddingProvider()

    @property
    def name(self) -> str:
        return "record_semantic_note"

    @property
    def description(self) -> str:
        return (
            "Record important information into workspace-scoped semantic memory. "
            "Use this for project facts, decisions, preferences, and recurring issues that should be retrieved later."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The note content to remember"},
                "category": {"type": "string", "description": "Optional category", "default": "general"},
            },
            "required": ["content"],
        }

    async def execute(self, content: str, category: str = "general") -> ToolResult:
        try:
            record = {
                "id": str(uuid4()),
                "workspace_id": self.workspace_id,
                "timestamp": datetime.now().isoformat(),
                "category": category,
                "content": content,
                "embedding": self.embedder.embed(content),
            }
            self.store.add(record)
            return ToolResult(success=True, content=f"Recorded semantic note: {content} (category: {category})")
        except Exception as e:
            return ToolResult(success=False, content="", error=f"Failed to record semantic note: {e}")


class SemanticRecallTool(Tool):
    """Recall notes by semantic similarity within the current workspace."""

    def __init__(
        self,
        workspace_dir: str,
        persist_dir: str,
        collection_name: str = "mini_agent_memory",
        default_top_k: int = 5,
    ):
        self.workspace_id = get_workspace_id(workspace_dir)
        self.store = LocalVectorMemoryStore(persist_dir=persist_dir, collection_name=collection_name)
        self.embedder = HashingEmbeddingProvider()
        self.default_top_k = default_top_k

    @property
    def name(self) -> str:
        return "semantic_recall_notes"

    @property
    def description(self) -> str:
        return (
            "Recall semantically relevant notes from the current workspace memory. "
            "Use this before answering questions about prior project context, decisions, preferences, or recurring issues."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Semantic memory search query"},
                "top_k": {"type": "integer", "description": "Number of notes to return", "default": self.default_top_k},
                "category": {"type": "string", "description": "Optional category filter"},
            },
            "required": ["query"],
        }

    async def execute(self, query: str, top_k: int | None = None, category: str | None = None) -> ToolResult:
        try:
            results = self.store.query(
                query_embedding=self.embedder.embed(query),
                workspace_id=self.workspace_id,
                top_k=top_k or self.default_top_k,
                category=category,
            )
            if not results:
                return ToolResult(success=True, content="No relevant semantic notes found.")

            lines = []
            for idx, item in enumerate(results, 1):
                lines.append(
                    f"{idx}. [score={item['score']}] [{item.get('category', 'general')}] {item.get('content', '')}\n"
                    f"   recorded at {item.get('timestamp', 'unknown')}"
                )
            return ToolResult(success=True, content="Relevant semantic notes:\n" + "\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, content="", error=f"Failed to recall semantic notes: {e}")


def create_vector_memory_tools(
    workspace_dir: str,
    persist_dir: str,
    collection_name: str = "mini_agent_memory",
    top_k: int = 5,
) -> list[Tool]:
    """Create vector memory tools for a workspace."""
    return [
        VectorRecordNoteTool(
            workspace_dir=workspace_dir,
            persist_dir=persist_dir,
            collection_name=collection_name,
        ),
        SemanticRecallTool(
            workspace_dir=workspace_dir,
            persist_dir=persist_dir,
            collection_name=collection_name,
            default_top_k=top_k,
        ),
    ]
