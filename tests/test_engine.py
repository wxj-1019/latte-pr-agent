import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from engine import ReviewEngine, CommentDeduplicator, ReviewCache, PRChunker
from llm import ReviewRouter
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
    assert await dedup.should_comment(review.id, "src/main.py", 10) is False
    assert await dedup.should_comment(review.id, "src/main.py", 11) is True


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
