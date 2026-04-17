import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from feedback.metrics import ReviewMetricsService
from models import Review, ReviewFinding, DeveloperFeedback


@pytest.mark.asyncio
async def test_review_metrics_service(async_db_session: AsyncSession) -> None:
    # Seed reviews and findings
    review1 = Review(platform="github", repo_id="owner/repo", pr_number=1)
    review2 = Review(platform="github", repo_id="owner/repo", pr_number=2)
    review3 = Review(platform="github", repo_id="other/repo", pr_number=3)
    async_db_session.add_all([review1, review2, review3])
    await async_db_session.commit()
    await async_db_session.refresh(review1)
    await async_db_session.refresh(review2)
    await async_db_session.refresh(review3)

    findings = [
        ReviewFinding(review_id=review1.id, file_path="a.py", severity="critical", description="Bug"),
        ReviewFinding(review_id=review1.id, file_path="b.py", severity="warning", description="Style"),
        ReviewFinding(review_id=review2.id, file_path="c.py", severity="warning", description="Perf"),
    ]
    async_db_session.add_all(findings)
    await async_db_session.commit()
    await async_db_session.refresh(findings[0])
    await async_db_session.refresh(findings[1])

    # One false positive feedback
    feedback = DeveloperFeedback(finding_id=findings[0].id, is_false_positive=True, comment="Not a bug")
    async_db_session.add(feedback)
    await async_db_session.commit()

    service = ReviewMetricsService(async_db_session)
    result = await service.get_repo_metrics("owner/repo")

    assert result["metrics"]["total_reviews"] == 2
    assert result["metrics"]["total_findings"] == 3
    assert result["metrics"]["false_positive_rate"] == pytest.approx(1 / 3, 0.01)
    assert result["severity_distribution"]["critical"] == 1
    assert result["severity_distribution"]["warning"] == 2


@pytest.mark.asyncio
async def test_review_metrics_empty_repo(async_db_session: AsyncSession) -> None:
    service = ReviewMetricsService(async_db_session)
    result = await service.get_repo_metrics("nonexistent/repo")
    assert result["metrics"]["total_reviews"] == 0
    assert result["metrics"]["total_findings"] == 0
    assert result["metrics"]["false_positive_rate"] == 0.0
