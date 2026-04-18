import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from engine import ReviewEngine, CommentDeduplicator, ReviewCache, PRChunker
from llm import ReviewRouter, ResilientReviewRouter
from models import Review


@pytest.fixture
def mock_router():
    mock = MagicMock(spec=ReviewRouter)
    mock.config = {"primary_model": "deepseek-chat"}
    mock.review = AsyncMock(return_value={
        "issues": [
            {
                "file": "src/main.py",
                "line": 10,
                "severity": "critical",
                "description": "Bug",
                "confidence": 0.95,
            }
        ],
        "summary": "1 issue",
        "risk_level": "high",
    })
    return mock


@pytest.fixture
def mock_cache():
    mock = MagicMock(spec=ReviewCache)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=None)
    return mock


@pytest.mark.asyncio
async def test_review_engine_run(async_db_session: AsyncSession, mock_router, mock_cache):
    # Seed a review
    from repositories import ReviewRepository
    review = await ReviewRepository(async_db_session).create(
        platform="github", repo_id="o/r", pr_number=1, status="pending"
    )

    engine = ReviewEngine(async_db_session, mock_router, mock_cache)
    result = await engine.run(review.id, "diff content", pr_size_tokens=1000)

    assert result["issues"][0]["severity"] == "critical"
    assert result.get("cached") is None

    # Verify review status updated
    fetched = await ReviewRepository(async_db_session).get_by_id(review.id)
    assert fetched.status == "completed"

    # Verify finding persisted
    from repositories import FindingRepository
    findings = await FindingRepository(async_db_session).get_by_review(review.id)
    assert len(findings) == 1
    assert findings[0].file_path == "src/main.py"

    # Verify cache set
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_review_engine_cache_hit(async_db_session: AsyncSession, mock_router, mock_cache):
    from repositories import ReviewRepository
    review = await ReviewRepository(async_db_session).create(
        platform="github", repo_id="o/r", pr_number=2, status="pending"
    )

    cached_result = {
        "issues": [{"file": "a.py", "line": 1, "severity": "info", "description": "style"}],
        "summary": "cached",
    }
    mock_cache.get = AsyncMock(return_value=cached_result)

    engine = ReviewEngine(async_db_session, mock_router, mock_cache)
    result = await engine.run(review.id, "same diff", pr_size_tokens=100)

    assert result["cached"] is True
    mock_router.review.assert_not_called()
    mock_cache.set.assert_not_called()


@pytest.mark.asyncio
async def test_comment_deduplicator(async_db_session: AsyncSession):
    from repositories import ReviewRepository, FindingRepository
    review = await ReviewRepository(async_db_session).create(
        platform="github", repo_id="o/r", pr_number=3
    )
    await FindingRepository(async_db_session).create(
        review_id=review.id, file_path="src/main.py", line_number=10, description="First"
    )

    dedup = CommentDeduplicator(async_db_session)
    # Without preload, fallback path still works
    assert await dedup.should_comment(review.id, "src/main.py", 10) is False
    assert await dedup.should_comment(review.id, "src/main.py", 11) is True

    # With preload, uses in-memory set (batch-loaded)
    dedup2 = CommentDeduplicator(async_db_session)
    await dedup2.preload_existing(review.id)
    assert await dedup2.should_comment(review.id, "src/main.py", 10) is False
    assert await dedup2.should_comment(review.id, "src/main.py", 11) is True


@pytest.mark.asyncio
async def test_review_cache_redis():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock(return_value=None)

    cache = ReviewCache(redis_client=mock_redis)

    result = await cache.get("diff", "v1", "deepseek-chat")
    assert result is None
    mock_redis.get.assert_called_once()

    await cache.set("diff", "v1", "deepseek-chat", {"issues": []})
    mock_redis.setex.assert_called_once()
    key = cache._make_key("diff", "v1", "deepseek-chat")
    assert mock_redis.setex.call_args[0][0] == key


def test_pr_chunker_by_file():
    diff = (
        "diff --git a/src/a.py b/src/a.py\n"
        "--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-old\n+new\n"
        "diff --git a/src/b.py b/src/b.py\n"
        "--- a/src/b.py\n+++ b/src/b.py\n@@ -2 +2 @@\n-bad\n+good\n"
    )
    chunker = PRChunker(max_chunk_tokens=10000)
    chunks = chunker.chunk(diff)
    assert len(chunks) == 2
    assert "src/a.py" in chunks[0]["content"]
    assert "src/b.py" in chunks[1]["content"]


def test_pr_chunker_by_function():
    # Simulate a single file with many hunks exceeding token limit
    lines = ["diff --git a/src/big.py b/src/big.py\n--- a/src/big.py\n+++ b/src/big.py\n"]
    for i in range(200):
        lines.append(f"@@ -{i},1 +{i},1 @@\n-old{i}\n+new{i}\n")
    diff = "".join(lines)

    chunker = PRChunker(max_chunk_tokens=100)
    chunks = chunker.chunk(diff)
    assert len(chunks) > 1


@pytest.mark.asyncio
async def test_review_cache_uses_connection_pool():
    from engine.cache import get_redis_client, _redis_pool
    mock_pool = MagicMock()
    with patch("engine.cache.redis.ConnectionPool.from_url", return_value=mock_pool):
        import engine.cache as cache_module
        original_pool = cache_module._redis_pool
        cache_module._redis_pool = None
        client = await get_redis_client()
        assert client.connection_pool is mock_pool
        cache_module._redis_pool = original_pool


# ==================== ProjectConfig Model Override Tests ====================

@pytest.mark.asyncio
async def test_review_engine_uses_project_config_model(async_db_session: AsyncSession, mock_router, mock_cache):
    from config.project_config import ReviewConfig

    # Set up providers attribute so _get_effective_router can clone the router
    mock_router.providers = {"deepseek": MagicMock(), "anthropic": MagicMock()}

    config = ReviewConfig(ai_model={"primary": "claude-3-5-sonnet"})
    engine = ReviewEngine(async_db_session, mock_router, mock_cache, project_config=config)

    # Verify effective router was created with claude config
    effective_router = engine._get_effective_router()
    assert effective_router.config["primary_model"] == "claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_review_engine_chunking_for_large_pr(async_db_session: AsyncSession, mock_router, mock_cache):
    from repositories import ReviewRepository

    review = await ReviewRepository(async_db_session).create(
        platform="github", repo_id="o/r", pr_number=21, status="pending"
    )

    # Simulate a large diff with multiple files so chunking produces >1 chunks
    parts = []
    for i in range(20):
        parts.append(f"diff --git a/src/f{i}.py b/src/f{i}.py\n--- a/src/f{i}.py\n+++ b/src/f{i}.py\n")
        parts.append("@@ -1,1 +1,1 @@\n-old\n+new\n" * 100)
    large_diff = "".join(parts)

    mock_router.review = AsyncMock(return_value={"issues": [], "summary": "ok", "risk_level": "low"})

    engine = ReviewEngine(async_db_session, mock_router, mock_cache)
    result = await engine.run(review.id, large_diff, pr_size_tokens=20000)

    # Chunking should cause multiple review calls
    assert mock_router.review.call_count > 1


# ==================== Static Analysis Integration Tests ====================

@pytest.mark.asyncio
async def test_review_engine_with_static_analysis(async_db_session: AsyncSession, mock_router, mock_cache):
    from repositories import ReviewRepository
    review = await ReviewRepository(async_db_session).create(
        platform="github", repo_id="o/r", pr_number=10, status="pending"
    )

    engine = ReviewEngine(async_db_session, mock_router, mock_cache, enable_static_analysis=True)

    with patch("engine.review_engine.SemgrepAnalyzer.analyze", return_value=[
        {"file": "src/main.py", "line": 5, "category": "security", "severity": "critical", "description": "SQLi", "confidence": 0.9, "source": "semgrep"}
    ]):
        result = await engine.run(
            review.id,
            "diff --git a/src/main.py b/src/main.py\n@@ -1 +1 @@\n-old\n+new\n",
            pr_size_tokens=100,
            repo_path="/fake/repo",
            changed_files=["src/main.py"],
        )

    # AI finding + static finding merged (different lines)
    assert len(result["issues"]) == 2
    sources = set()
    for issue in result["issues"]:
        sources.update(issue.get("sources", [issue.get("source", "ai")]))
    assert "semgrep" in sources


@pytest.mark.asyncio
async def test_review_engine_with_degraded(async_db_session: AsyncSession, mock_cache):
    from repositories import ReviewRepository
    review = await ReviewRepository(async_db_session).create(
        platform="github", repo_id="o/r", pr_number=11, status="pending"
    )

    mock_resilient = MagicMock(spec=ResilientReviewRouter)
    mock_resilient.config = {"primary_model": "deepseek-chat"}
    mock_resilient.review = AsyncMock(return_value={
        "issues": [],
        "summary": "Unavailable",
        "risk_level": "low",
        "degraded": True,
    })

    engine = ReviewEngine(async_db_session, mock_resilient, mock_cache, enable_static_analysis=True)

    with patch("engine.review_engine.SemgrepAnalyzer.analyze", return_value=[
        {"file": "src/main.py", "line": 1, "category": "security", "severity": "warning", "description": "Static issue", "confidence": 0.8, "source": "semgrep"}
    ]):
        result = await engine.run(
            review.id,
            "diff content",
            pr_size_tokens=100,
            repo_path="/fake/repo",
            changed_files=["src/main.py"],
        )

    assert result["degraded"] is True
    assert len(result["issues"]) == 1
    assert result["issues"][0]["source"] == "semgrep"
