import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models import ReviewFinding
from repositories import ReviewRepository, FindingRepository


@pytest.mark.asyncio
async def test_review_repo_create_and_get(async_db_session: AsyncSession) -> None:
    repo = ReviewRepository(async_db_session)
    review = await repo.create(
        platform="github",
        repo_id="test/repo",
        pr_number=42,
        pr_title="Add feature",
        head_sha="abc123",
        trigger_type="pull_request.opened",
    )

    fetched = await repo.get_by_id(review.id)
    assert fetched is not None
    assert fetched.pr_title == "Add feature"
    assert fetched.status == "pending"


@pytest.mark.asyncio
async def test_review_repo_get_by_platform_repo_pr_sha(async_db_session: AsyncSession) -> None:
    repo = ReviewRepository(async_db_session)
    await repo.create(
        platform="github",
        repo_id="test/repo",
        pr_number=42,
        head_sha="sha256",
    )

    fetched = await repo.get_by_platform_repo_pr_sha(
        "github", "test/repo", 42, "sha256"
    )
    assert fetched is not None

    not_found = await repo.get_by_platform_repo_pr_sha(
        "github", "test/repo", 42, "other"
    )
    assert not_found is None


@pytest.mark.asyncio
async def test_review_repo_update_status(async_db_session: AsyncSession) -> None:
    repo = ReviewRepository(async_db_session)
    review = await repo.create(
        platform="github", repo_id="test/repo", pr_number=1
    )

    updated = await repo.update_status(review.id, "completed", risk_level="low")
    assert updated is not None
    assert updated.status == "completed"
    assert updated.risk_level == "low"

    missing = await repo.update_status(99999, "completed")
    assert missing is None


@pytest.mark.asyncio
async def test_review_repo_add_pr_files(async_db_session: AsyncSession) -> None:
    repo = ReviewRepository(async_db_session)
    review = await repo.create(
        platform="github", repo_id="test/repo", pr_number=1
    )

    await repo.add_pr_files(
        review.id,
        [
            {"file_path": "a.py", "change_type": "added", "additions": 10},
            {"file_path": "b.py", "change_type": "modified", "deletions": 5},
        ],
    )

    fetched = await repo.get_by_id(review.id)
    assert fetched is not None
    await async_db_session.refresh(fetched, ["pr_files"])
    assert len(fetched.pr_files) == 2
    assert fetched.pr_files[0].file_path == "a.py"


@pytest.mark.asyncio
async def test_finding_repo_create_and_get(async_db_session: AsyncSession) -> None:
    review_repo = ReviewRepository(async_db_session)
    finding_repo = FindingRepository(async_db_session)

    review = await review_repo.create(
        platform="github", repo_id="test/repo", pr_number=1
    )
    finding = await finding_repo.create(
        review_id=review.id,
        file_path="src/main.py",
        description="Bug found",
        severity="warning",
        confidence=0.85,
    )

    assert finding.id is not None
    findings = await finding_repo.get_by_review(review.id)
    assert len(findings) == 1
    assert findings[0].severity == "warning"


@pytest.mark.asyncio
async def test_finding_repo_feedback(async_db_session: AsyncSession) -> None:
    review_repo = ReviewRepository(async_db_session)
    finding_repo = FindingRepository(async_db_session)

    review = await review_repo.create(
        platform="github", repo_id="test/repo", pr_number=1
    )
    finding = await finding_repo.create(
        review_id=review.id,
        file_path="src/main.py",
        description="Potential issue",
    )

    feedback = await finding_repo.add_feedback(
        finding.id, is_false_positive=True, comment="Not applicable"
    )
    assert feedback.finding_id == finding.id
    assert feedback.is_false_positive is True
