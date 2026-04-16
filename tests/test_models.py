import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Review, ReviewFinding, PRFile, DeveloperFeedback, ProjectConfig


@pytest.mark.asyncio
async def test_review_creation(async_db_session: AsyncSession) -> None:
    review = Review(
        platform="github",
        repo_id="owner/repo",
        pr_number=1,
        pr_title="Test PR",
        status="pending",
    )
    async_db_session.add(review)
    await async_db_session.commit()
    await async_db_session.refresh(review)

    assert review.id is not None
    assert review.platform == "github"
    assert review.pr_title == "Test PR"


@pytest.mark.asyncio
async def test_review_with_findings(async_db_session: AsyncSession) -> None:
    review = Review(platform="github", repo_id="owner/repo", pr_number=2)
    async_db_session.add(review)
    await async_db_session.commit()
    await async_db_session.refresh(review)

    finding = ReviewFinding(
        review_id=review.id,
        file_path="src/main.py",
        line_number=10,
        category="security",
        severity="critical",
        description="SQL injection risk",
        confidence=0.95,
    )
    async_db_session.add(finding)
    await async_db_session.commit()

    result = await async_db_session.execute(
        select(Review).where(Review.id == review.id)
    )
    fetched = result.scalar_one()
    await async_db_session.refresh(fetched, ["findings"])
    assert len(fetched.findings) == 1
    assert fetched.findings[0].description == "SQL injection risk"


@pytest.mark.asyncio
async def test_review_with_pr_files(async_db_session: AsyncSession) -> None:
    review = Review(platform="gitlab", repo_id="group/project", pr_number=5)
    async_db_session.add(review)
    await async_db_session.commit()
    await async_db_session.refresh(review)

    pr_file = PRFile(
        review_id=review.id,
        file_path="src/app.py",
        change_type="modified",
        additions=10,
        deletions=2,
    )
    async_db_session.add(pr_file)
    await async_db_session.commit()

    result = await async_db_session.execute(
        select(Review).where(Review.id == review.id)
    )
    fetched = result.scalar_one()
    await async_db_session.refresh(fetched, ["pr_files"])
    assert len(fetched.pr_files) == 1
    assert fetched.pr_files[0].additions == 10


@pytest.mark.asyncio
async def test_developer_feedback(async_db_session: AsyncSession) -> None:
    review = Review(platform="github", repo_id="owner/repo", pr_number=3)
    async_db_session.add(review)
    await async_db_session.commit()
    await async_db_session.refresh(review)

    finding = ReviewFinding(
        review_id=review.id,
        file_path="src/auth.py",
        description="Hardcoded secret",
    )
    async_db_session.add(finding)
    await async_db_session.commit()
    await async_db_session.refresh(finding)

    feedback = DeveloperFeedback(
        finding_id=finding.id,
        is_false_positive=True,
        comment="This is a test secret",
    )
    async_db_session.add(feedback)
    await async_db_session.commit()
    await async_db_session.refresh(finding, ["feedback"])

    assert finding.feedback is not None
    assert finding.feedback.is_false_positive is True


@pytest.mark.asyncio
async def test_project_config_unique_constraint(async_db_session: AsyncSession) -> None:
    config1 = ProjectConfig(
        org_id="default",
        platform="github",
        repo_id="owner/repo",
        config_json={"language": "python"},
    )
    config2 = ProjectConfig(
        org_id="default",
        platform="github",
        repo_id="owner/repo",
        config_json={"language": "go"},
    )
    async_db_session.add(config1)
    await async_db_session.commit()

    async_db_session.add(config2)
    with pytest.raises(Exception):
        await async_db_session.commit()
