from datetime import datetime, timedelta, timezone
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Review, ReviewFinding


class StatsService:
    """Dashboard 首页概览数据统计服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_dashboard_summary(self) -> Dict:
        total_reviews = await self._count_reviews()
        pending_reviews = await self._count_reviews_by_status("pending")
        running_reviews = await self._count_reviews_by_status("running")
        completed_reviews = await self._count_reviews_by_status("completed")
        failed_reviews = await self._count_reviews_by_status("failed")
        skipped_reviews = await self._count_reviews_by_status("skipped")
        high_risk_count = await self._count_high_risk()
        total_findings_today = await self._count_findings_today()
        recent_reviews = await self._recent_reviews(limit=5)

        return {
            "total_reviews": total_reviews,
            "pending_reviews": pending_reviews,
            "running_reviews": running_reviews,
            "completed_reviews": completed_reviews,
            "failed_reviews": failed_reviews,
            "skipped_reviews": skipped_reviews,
            "high_risk_count": high_risk_count,
            "total_findings_today": total_findings_today,
            "recent_reviews": recent_reviews,
        }

    async def _count_reviews(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Review))
        return result.scalar() or 0

    async def _count_reviews_by_status(self, status: str) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Review).where(Review.status == status)
        )
        return result.scalar() or 0

    async def _count_high_risk(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Review)
            .where(Review.risk_level.in_(["high", "critical"]))
        )
        return result.scalar() or 0

    async def _count_findings_today(self) -> int:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count()).select_from(ReviewFinding).where(ReviewFinding.created_at >= today)
        )
        return result.scalar() or 0

    async def _recent_reviews(self, limit: int = 5) -> List[Dict]:
        result = await self.session.execute(
            select(Review)
            .order_by(Review.created_at.desc())
            .limit(limit)
        )
        reviews = result.scalars().all()
        return [
            {
                "id": r.id,
                "repo_id": r.repo_id,
                "pr_number": r.pr_number,
                "pr_title": r.pr_title,
                "status": r.status,
                "risk_level": r.risk_level,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ]
