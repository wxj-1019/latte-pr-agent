import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from repositories import FindingRepository
from feedback.metrics import ReviewMetricsService

router = APIRouter(prefix="/feedback", tags=["feedback"])
logger = logging.getLogger(__name__)


@router.get("/metrics/{repo_id}")
async def get_metrics(
    repo_id: str,
    range: str = "7d",
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        service = ReviewMetricsService(db)
        return await service.get_repo_metrics(repo_id, range=range)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get metrics for repo %s: %s", repo_id, exc)
        raise HTTPException(status_code=500, detail=f"获取指标失败: {exc}")


@router.post("/{finding_id}")
async def submit_feedback(
    finding_id: int,
    is_false_positive: bool,
    comment: str = "",
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        finding_repo = FindingRepository(db)
        # Verify finding exists
        from sqlalchemy import select
        from models import ReviewFinding
        result = await db.execute(select(ReviewFinding).where(ReviewFinding.id == finding_id))
        finding = result.scalar_one_or_none()
        if not finding:
            raise HTTPException(status_code=404, detail="审查发现项不存在")

        feedback = await finding_repo.add_feedback(
            finding_id=finding_id,
            is_false_positive=is_false_positive,
            comment=comment,
        )
        await db.commit()
        return {
            "id": feedback.id,
            "finding_id": feedback.finding_id,
            "is_false_positive": feedback.is_false_positive,
            "comment": feedback.comment,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to submit feedback for finding %s: %s", finding_id, exc)
        raise HTTPException(status_code=500, detail=f"提交反馈失败: {exc}")
