from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from repositories import FindingRepository

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/{finding_id}")
async def submit_feedback(
    finding_id: int,
    is_false_positive: bool,
    comment: str = "",
    db: AsyncSession = Depends(get_db),
) -> dict:
    finding_repo = FindingRepository(db)
    # Verify finding exists
    from sqlalchemy import select
    from models import ReviewFinding
    result = await db.execute(select(ReviewFinding).where(ReviewFinding.id == finding_id))
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    feedback = await finding_repo.add_feedback(
        finding_id=finding_id,
        is_false_positive=is_false_positive,
        comment=comment,
    )
    return {
        "id": feedback.id,
        "finding_id": feedback.finding_id,
        "is_false_positive": feedback.is_false_positive,
        "comment": feedback.comment,
    }
