import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from pathlib import Path

from sqlalchemy import text

from rag import EmbeddingClient, BugKnowledgeRepository, BugKnowledgeBuilder, RAGRetriever


# ==================== Fake Embedding Client ====================

class FakeEmbeddingClient:
    """返回固定向量的伪 EmbeddingClient。"""

    def __init__(self, vector=None, dimensions=1536):
        self.vector = vector or ([1.0] * dimensions)
        self.dimensions = dimensions

    async def embed(self, text: str):
        variant = [0.0] * self.dimensions
        if "sql injection" in text.lower():
            variant[0] = 1.0
        elif "null pointer" in text.lower():
            variant[1] = 1.0
        return [self.vector[i] + variant[i] for i in range(self.dimensions)]

    async def embed_batch(self, texts):
        return [await self.embed(t) for t in texts]


# ==================== BugKnowledgeRepository Tests ====================

@pytest.mark.asyncio
async def test_bug_knowledge_repository_insert_sql():
    mock_session = AsyncMock()
    vec = [0.1] * 1536

    await BugKnowledgeRepository.insert(
        mock_session,
        org_id="default",
        repo_id="repo1",
        bug_pattern="SQLi fix",
        embedding=vec,
        file_path="src/app.py",
        severity="critical",
        fix_commit="abc123",
        fix_description="Fix SQL injection",
    )

    call_args = mock_session.execute.call_args
    sql = call_args.args[0]
    params = call_args.args[1]

    assert "INSERT INTO bug_knowledge" in str(sql)
    assert ":embedding::vector" in str(sql)
    assert params["bug_pattern"] == "SQLi fix"
    assert params["embedding"] == vec


@pytest.mark.asyncio
async def test_bug_knowledge_repository_search_sql():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {
            "id": 1,
            "file_path": "src/app.py",
            "bug_pattern": "SQLi fix",
            "severity": "critical",
            "fix_commit": "abc123",
            "fix_description": "Fix SQL injection",
            "similarity": 0.92,
        }
    ]
    mock_session.execute.return_value = mock_result

    vec = [0.1] * 1536
    results = await BugKnowledgeRepository.search_similar(
        mock_session, vec, "repo1", limit=3, min_similarity=0.75
    )

    call_args = mock_session.execute.call_args
    sql = call_args.args[0]
    params = call_args.args[1]

    assert "1 - (embedding <=> :embedding::vector) AS similarity" in str(sql)
    assert "repo_id = :repo_id" in str(sql)
    assert params["repo_id"] == "repo1"
    assert params["limit"] == 3

    assert len(results) == 1
    assert results[0]["similarity"] == 0.92


@pytest.mark.asyncio
async def test_bug_knowledge_repository_min_similarity_filter():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {"id": 1, "bug_pattern": "High", "severity": "high", "fix_commit": None, "fix_description": None, "file_path": None, "similarity": 0.95},
        {"id": 2, "bug_pattern": "Low", "severity": "low", "fix_commit": None, "fix_description": None, "file_path": None, "similarity": 0.50},
    ]
    mock_session.execute.return_value = mock_result

    vec = [0.1] * 1536
    results = await BugKnowledgeRepository.search_similar(
        mock_session, vec, "repo1", limit=5, min_similarity=0.75
    )

    assert len(results) == 1
    assert results[0]["bug_pattern"] == "High"


# ==================== BugKnowledgeBuilder Tests ====================

@pytest.mark.asyncio
async def test_bug_knowledge_builder_scan_from_git_history(tmp_path):
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)

    # fix commit
    (repo / "bug.py").write_text("print('fixed')\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Fix SQL injection in auth module"], cwd=repo, check=True, capture_output=True)

    # filtered doc commit
    (repo / "README.md").write_text("# docs\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: update readme"], cwd=repo, check=True, capture_output=True)

    fake_embedder = FakeEmbeddingClient()
    mock_session = AsyncMock()

    with patch("rag.builder.BugKnowledgeRepository.insert") as mock_insert:
        builder = BugKnowledgeBuilder(mock_session, embedder=fake_embedder)
        count = await builder.scan_from_git_history(str(repo), "default", "test-repo")

    assert count == 1
    mock_insert.assert_awaited_once()
    call_kwargs = mock_insert.call_args.kwargs
    assert call_kwargs["org_id"] == "default"
    assert call_kwargs["repo_id"] == "test-repo"
    assert "SQL injection" in call_kwargs["fix_description"]
    assert call_kwargs["severity"] == "low"
    assert len(call_kwargs["embedding"]) == 1536
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_bug_knowledge_builder_skip_non_bug_commits(tmp_path):
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)

    (repo / "feat.py").write_text("pass\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add new feature"], cwd=repo, check=True, capture_output=True)

    fake_embedder = FakeEmbeddingClient()
    mock_session = AsyncMock()

    with patch("rag.builder.BugKnowledgeRepository.insert") as mock_insert:
        builder = BugKnowledgeBuilder(mock_session, embedder=fake_embedder)
        count = await builder.scan_from_git_history(str(repo), "default", "test-repo")

    assert count == 0
    mock_insert.assert_not_called()


# ==================== RAGRetriever Tests ====================

@pytest.mark.asyncio
async def test_rag_retriever_calls_embed_and_search():
    mock_session = AsyncMock()
    fake_embedder = FakeEmbeddingClient()

    with patch("rag.retriever.BugKnowledgeRepository.search_similar", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [
            {"bug_pattern": "NPE guard", "severity": "high", "similarity": 0.88}
        ]
        retriever = RAGRetriever(embedder=fake_embedder)
        results = await retriever.retrieve(
            mock_session, "Fix null pointer", "repo-rag", limit=3, min_similarity=0.5
        )

    assert len(results) == 1
    assert results[0]["bug_pattern"] == "NPE guard"
    mock_search.assert_awaited_once_with(
        session=mock_session,
        embedding=ANY,
        repo_id="repo-rag",
        limit=3,
        min_similarity=0.5,
        org_id="default",
    )


# ==================== EmbeddingClient Tests ====================

@pytest.mark.asyncio
async def test_embedding_client_calls_openai():
    with patch("rag.embedder.AsyncOpenAI") as MockClient:
        mock_instance = MagicMock()
        mock_instance.embeddings.create = AsyncMock(return_value=MagicMock(
            data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
        ))
        MockClient.return_value = mock_instance

        client = EmbeddingClient(api_key="fake-key", model="text-embedding-3-small", dimensions=3)
        result = await client.embed("hello")

        assert result == [0.1, 0.2, 0.3]
        mock_instance.embeddings.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_embedding_client_batch():
    with patch("rag.embedder.AsyncOpenAI") as MockClient:
        mock_instance = MagicMock()
        mock_instance.embeddings.create = AsyncMock(return_value=MagicMock(
            data=[MagicMock(embedding=[0.1]), MagicMock(embedding=[0.2])]
        ))
        MockClient.return_value = mock_instance

        client = EmbeddingClient(api_key="fake-key", model="text-embedding-3-small", dimensions=1)
        results = await client.embed_batch(["a", "b"])

        assert results == [[0.1], [0.2]]
