import pytest

from mini_agent.tools import vector_memory_tool


class DummyEmbeddingProvider:
    def __init__(self, model_path: str):
        self.model_path = model_path

    def embed(self, text: str) -> list[float]:
        if "Chroma" in text or "后端" in text:
            return [1.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0]


@pytest.mark.asyncio
async def test_chroma_vector_memory_record_and_recall(tmp_path, monkeypatch):
    monkeypatch.setattr(vector_memory_tool, "SentenceTransformerEmbeddingProvider", DummyEmbeddingProvider)

    record_tool, recall_tool = vector_memory_tool.create_vector_memory_tools(
        workspace_dir=str(tmp_path / "workspace"),
        persist_dir=str(tmp_path / "chroma"),
        embedding_model="dummy-model",
        collection_name="test_memory",
        top_k=1,
    )

    record_result = await record_tool.execute("Mini-Agent 使用 Chroma 作为向量记忆后端", category="architecture")
    recall_result = await recall_tool.execute("当前项目的记忆后端是什么？")
    fallback_result = await recall_tool.execute("当前项目的记忆后端是什么？", category="wrong_category")

    assert record_result.success
    assert recall_result.success
    assert fallback_result.success
    assert "Chroma" in recall_result.content
    assert "Chroma" in fallback_result.content
    assert "wrong_category" in fallback_result.content
