from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ReviewFinding, DeveloperFeedback


class FindingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        review_id: int,
        file_path: str,
        description: str,
        line_number: Optional[int] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        suggestion: Optional[str] = None,
        confidence: Optional[float] = None,
        ai_model: Optional[str] = None,
        raw_response: Optional[dict] = None,
    ) -> ReviewFinding:
        finding = ReviewFinding(
            review_id=review_id,
            file_path=file_path,
            line_number=line_number,
            category=category,
            severity=severity,
            description=description,
            suggestion=suggestion,
            confidence=confidence,
            ai_model=ai_model,
            raw_response=raw_response,
        )
        self.session.add(finding)
        await self.session.commit()
        await self.session.refresh(finding)
        return finding

    async def get_by_review(self, review_id: int) -> list[ReviewFinding]:
        result = await self.session.execute(
            select(ReviewFinding).where(ReviewFinding.review_id == review_id)
        )
        return list(result.scalars().all())

    async def add_feedback(
        self, finding_id: int, is_false_positive: bool, comment: Optional[str] = None
    ) -> DeveloperFeedback:
        feedback = DeveloperFeedback(
            finding_id=finding_id,
            is_false_positive=is_false_positive,
            comment=comment,
        )
        self.session.add(feedback)
        await self.session.commit()
        await self.session.refresh(feedback)
        return feedback
