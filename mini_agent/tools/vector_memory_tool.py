"""Workspace-aware semantic memory tools backed by Chroma."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .base import Tool, ToolResult
from .memory_path import get_workspace_id


class SentenceTransformerEmbeddingProvider:
    """Embedding provider using a local sentence-transformers model."""

    def __init__(self, model_path: str):
        self.model_path = str(Path(model_path).expanduser())
        self.model = None

    def embed(self, text: str) -> list[float]:
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "Vector memory requires sentence-transformers. "
                    "Install project dependencies with `uv sync` or reinstall mini-agent."
                ) from exc
            self.model = SentenceTransformer(self.model_path)

        embedding = self.model.encode(text, normalize_embeddings=True)
        return [float(value) for value in embedding.tolist()]


class ChromaVectorMemoryStore:
    """Chroma-backed vector store with workspace metadata filtering."""

    def __init__(self, persist_dir: str, collection_name: str = "mini_agent_memory"):
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
        os.environ.setdefault("CHROMA_TELEMETRY", "False")
        try:
            import chromadb
            from chromadb.config import Settings
            from chromadb.telemetry.product.posthog import Posthog
        except ImportError as exc:
            raise RuntimeError(
                "Vector memory requires chromadb. Install project dependencies with `uv sync` or reinstall mini-agent."
            ) from exc

        Posthog._direct_capture = lambda _self, _event: None
        self.persist_dir = Path(persist_dir).expanduser()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, record: dict[str, Any], embedding: list[float]) -> None:
        metadata = {
            "workspace_id": record["workspace_id"],
            "timestamp": record["timestamp"],
            "category": record["category"],
        }
        self.collection.add(
            ids=[record["id"]],
            documents=[record["content"]],
            embeddings=[embedding],
            metadatas=[metadata],
        )

    def query(
        self,
        query_embedding: list[float],
        workspace_id: str,
        top_k: int,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        where: dict[str, Any]
        if category:
            where = {"$and": [{"workspace_id": workspace_id}, {"category": category}]}
        else:
            where = {"workspace_id": workspace_id}

        count = self.collection.count()
        if count == 0:
            return []

        data = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(max(1, top_k), count),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        ids = data.get("ids", [[]])[0]
        documents = data.get("documents", [[]])[0]
        metadatas = data.get("metadatas", [[]])[0]
        distances = data.get("distances", [[]])[0]

        results = []
        for item_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            score = 1.0 - float(distance)
            results.append(
                {
                    "id": item_id,
                    "score": round(score, 4),
                    "category": metadata.get("category", "general") if metadata else "general",
                    "timestamp": metadata.get("timestamp", "unknown") if metadata else "unknown",
                    "content": document or "",
                }
            )
        return results


class VectorRecordNoteTool(Tool):
    """Record a note into workspace-scoped semantic memory."""

    def __init__(
        self,
        workspace_dir: str,
        persist_dir: str,
        embedding_model: str,
        collection_name: str = "mini_agent_memory",
        store: ChromaVectorMemoryStore | None = None,
        embedder: SentenceTransformerEmbeddingProvider | None = None,
    ):
        self.workspace_id = get_workspace_id(workspace_dir)
        self.store = store or ChromaVectorMemoryStore(persist_dir=persist_dir, collection_name=collection_name)
        self.embedder = embedder or SentenceTransformerEmbeddingProvider(embedding_model)

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
            }
            self.store.add(record, self.embedder.embed(content))
            return ToolResult(success=True, content=f"Recorded semantic note: {content} (category: {category})")
        except Exception as e:
            return ToolResult(success=False, content="", error=f"Failed to record semantic note: {e}")


class SemanticRecallTool(Tool):
    """Recall notes by semantic similarity within the current workspace."""

    def __init__(
        self,
        workspace_dir: str,
        persist_dir: str,
        embedding_model: str,
        collection_name: str = "mini_agent_memory",
        default_top_k: int = 5,
        store: ChromaVectorMemoryStore | None = None,
        embedder: SentenceTransformerEmbeddingProvider | None = None,
    ):
        self.workspace_id = get_workspace_id(workspace_dir)
        self.store = store or ChromaVectorMemoryStore(persist_dir=persist_dir, collection_name=collection_name)
        self.embedder = embedder or SentenceTransformerEmbeddingProvider(embedding_model)
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
            result_limit = top_k or self.default_top_k
            results = self.store.query(
                query_embedding=self.embedder.embed(query),
                workspace_id=self.workspace_id,
                top_k=result_limit,
                category=category,
            )
            used_fallback = False
            if not results and category:
                results = self.store.query(
                    query_embedding=self.embedder.embed(query),
                    workspace_id=self.workspace_id,
                    top_k=result_limit,
                    category=None,
                )
                used_fallback = bool(results)

            if not results:
                return ToolResult(success=True, content="No relevant semantic notes found.")

            lines = []
            for idx, item in enumerate(results, 1):
                lines.append(
                    f"{idx}. [score={item['score']}] [{item.get('category', 'general')}] {item.get('content', '')}\n"
                    f"   recorded at {item.get('timestamp', 'unknown')}"
                )
            prefix = "Relevant semantic notes:"
            if used_fallback:
                prefix = f"No notes found in category '{category}'. Relevant semantic notes from all categories:"
            return ToolResult(success=True, content=prefix + "\n" + "\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, content="", error=f"Failed to recall semantic notes: {e}")


def create_vector_memory_tools(
    workspace_dir: str,
    persist_dir: str,
    embedding_model: str,
    collection_name: str = "mini_agent_memory",
    top_k: int = 5,
) -> list[Tool]:
    """Create Chroma vector memory tools for a workspace."""
    store = ChromaVectorMemoryStore(persist_dir=persist_dir, collection_name=collection_name)
    embedder = SentenceTransformerEmbeddingProvider(embedding_model)
    return [
        VectorRecordNoteTool(
            workspace_dir=workspace_dir,
            persist_dir=persist_dir,
            embedding_model=embedding_model,
            collection_name=collection_name,
            store=store,
            embedder=embedder,
        ),
        SemanticRecallTool(
            workspace_dir=workspace_dir,
            persist_dir=persist_dir,
            embedding_model=embedding_model,
            collection_name=collection_name,
            default_top_k=top_k,
            store=store,
            embedder=embedder,
        ),
    ]
