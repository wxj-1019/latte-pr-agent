import pytest
from models import get_db
from main import app
from repositories import ReviewRepository


@pytest.mark.asyncio
async def test_stats_empty(async_client_with_db):
    response = await async_client_with_db.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_reviews"] == 0
    assert data["pending_reviews"] == 0
    assert data["completed_reviews"] == 0
    assert data["high_risk_count"] == 0
    assert data["total_findings_today"] == 0
    assert data["recent_reviews"] == []


@pytest.mark.asyncio
async def test_stats_with_reviews(async_client_with_db):
    db_gen = app.dependency_overrides[get_db]()
    session = await db_gen.__anext__()

    await ReviewRepository(session).create(
        platform="github", repo_id="org/repo", pr_number=1, status="completed"
    )
    await ReviewRepository(session).create(
        platform="github", repo_id="org/repo", pr_number=2, status="pending"
    )
    await session.commit()

    response = await async_client_with_db.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_reviews"] == 2
    assert data["pending_reviews"] == 1
    assert data["completed_reviews"] == 1
    assert len(data["recent_reviews"]) == 2
