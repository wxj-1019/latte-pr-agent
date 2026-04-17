from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models import Review, PRFile


class ReviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        platform: str,
        repo_id: str,
        pr_number: int,
        org_id: str = "default",
        pr_title: Optional[str] = None,
        pr_author: Optional[str] = None,
        head_sha: Optional[str] = None,
        status: str = "pending",
        trigger_type: Optional[str] = None,
    ) -> Optional[Review]:
        review = Review(
            platform=platform,
            repo_id=repo_id,
            pr_number=pr_number,
            org_id=org_id,
            pr_title=pr_title,
            pr_author=pr_author,
            head_sha=head_sha,
            status=status,
            trigger_type=trigger_type,
        )
        self.session.add(review)
        try:
            await self.session.commit()
            await self.session.refresh(review)
            return review
        except IntegrityError:
            await self.session.rollback()
            if head_sha:
                return await self.get_by_platform_repo_pr_sha(platform, repo_id, pr_number, head_sha)
            return None

    async def get_by_id(self, review_id: int) -> Optional[Review]:
        result = await self.session.execute(select(Review).where(Review.id == review_id))
        return result.scalar_one_or_none()

    async def list_all(
        self,
        status: Optional[str] = None,
        repo_filter: Optional[str] = None,
        risk: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[Review]:
        stmt = select(Review).order_by(Review.created_at.desc())
        if status:
            stmt = stmt.where(Review.status == status)
        if repo_filter:
            stmt = stmt.where(Review.repo_id.contains(repo_filter))
        if risk:
            stmt = stmt.where(Review.risk_level == risk)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_all(
        self,
        status: Optional[str] = None,
        repo_filter: Optional[str] = None,
        risk: Optional[str] = None,
    ) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(Review)
        if status:
            stmt = stmt.where(Review.status == status)
        if repo_filter:
            stmt = stmt.where(Review.repo_id.contains(repo_filter))
        if risk:
            stmt = stmt.where(Review.risk_level == risk)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_by_platform_repo_pr_sha(
        self, platform: str, repo_id: str, pr_number: int, head_sha: str
    ) -> Optional[Review]:
        result = await self.session.execute(
            select(Review).where(
                Review.platform == platform,
                Review.repo_id == repo_id,
                Review.pr_number == pr_number,
                Review.head_sha == head_sha,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, review_id: int, status: str, risk_level: Optional[str] = None
    ) -> Optional[Review]:
        review = await self.get_by_id(review_id)
        if review is None:
            return None
        review.status = status
        if risk_level is not None:
            review.risk_level = risk_level
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def add_pr_files(self, review_id: int, files: list[dict]) -> None:
        pr_files = [
            PRFile(
                review_id=review_id,
                file_path=f["file_path"],
                change_type=f.get("change_type"),
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                diff_content=f.get("diff_content"),
            )
            for f in files
        ]
        self.session.add_all(pr_files)
        await self.session.commit()
