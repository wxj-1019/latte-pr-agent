import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock

from repositories import ReviewRepository, FindingRepository
from feedback import FeedbackFormatter, ReviewPublisher
from models import ReviewFinding


@pytest.mark.asyncio
async def test_feedback_submission(async_client_with_db):
    from models import get_db
    from main import app
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    db_gen = app.dependency_overrides[get_db]()
    session = await db_gen.__anext__()

    review = await ReviewRepository(session).create(
        platform="github", repo_id="o/r", pr_number=1
    )
    finding = await FindingRepository(session).create(
        review_id=review.id, file_path="src/a.py", description="bug"
    )
    await session.commit()

    response = await async_client_with_db.post(
        f"/feedback/{finding.id}?is_false_positive=true&comment=Not a bug",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_false_positive"] is True
    assert data["comment"] == "Not a bug"


@pytest.mark.asyncio
async def test_feedback_not_found(async_client_with_db) -> None:
    response = await async_client_with_db.post(
        "/feedback/99999?is_false_positive=true",
    )
    assert response.status_code == 404
