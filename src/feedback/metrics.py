from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Review, ReviewFinding, DeveloperFeedback


class ReviewMetricsService:
    """基于 developer_feedback 和 findings 的审查质量度量服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_repo_metrics(self, repo_id: str) -> Dict:
        total_reviews = await self._count_reviews(repo_id)
        total_findings = await self._count_findings(repo_id)
        false_positive_count = await self._count_false_positives(repo_id)
        severity_distribution = await self._severity_distribution(repo_id)
        category_distribution = await self._category_distribution(repo_id)
        prompt_version_metrics = await self._prompt_version_metrics(repo_id)

        fp_rate = 0.0
        if total_findings > 0:
            fp_rate = round(false_positive_count / total_findings, 4)

        return {
            "repo_id": repo_id,
            "total_reviews": total_reviews,
            "total_findings": total_findings,
            "false_positives": false_positive_count,
            "false_positive_rate": fp_rate,
            "severity_distribution": severity_distribution,
            "category_distribution": category_distribution,
            "prompt_version_metrics": prompt_version_metrics,
        }

    async def _count_reviews(self, repo_id: str) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Review).where(Review.repo_id == repo_id)
        )
        return result.scalar() or 0

    async def _count_findings(self, repo_id: str) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(ReviewFinding)
            .join(Review, ReviewFinding.review_id == Review.id)
            .where(Review.repo_id == repo_id)
        )
        return result.scalar() or 0

    async def _count_false_positives(self, repo_id: str) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(DeveloperFeedback)
            .join(ReviewFinding, DeveloperFeedback.finding_id == ReviewFinding.id)
            .join(Review, ReviewFinding.review_id == Review.id)
            .where(Review.repo_id == repo_id, DeveloperFeedback.is_false_positive.is_(True))
        )
        return result.scalar() or 0

    async def _severity_distribution(self, repo_id: str) -> Dict[str, int]:
        result = await self.session.execute(
            select(ReviewFinding.severity, func.count())
            .join(Review, ReviewFinding.review_id == Review.id)
            .where(Review.repo_id == repo_id)
            .group_by(ReviewFinding.severity)
        )
        return {row[0] or "unknown": row[1] for row in result.all()}

    async def _category_distribution(self, repo_id: str) -> Dict[str, int]:
        result = await self.session.execute(
            select(ReviewFinding.category, func.count())
            .join(Review, ReviewFinding.review_id == Review.id)
            .where(Review.repo_id == repo_id)
            .group_by(ReviewFinding.category)
        )
        return {row[0] or "unknown": row[1] for row in result.all()}

    async def _prompt_version_metrics(self, repo_id: str) -> List[Dict]:
        """按 prompt_version 统计 findings 和 false positive 率。"""
        result = await self.session.execute(
            select(
                Review.prompt_version,
                func.count(ReviewFinding.id).label("total"),
                func.count(DeveloperFeedback.id).filter(
                    DeveloperFeedback.is_false_positive.is_(True)
                ).label("fp"),
            )
            .join(ReviewFinding, ReviewFinding.review_id == Review.id)
            .outerjoin(DeveloperFeedback, ReviewFinding.id == DeveloperFeedback.finding_id)
            .where(Review.repo_id == repo_id)
            .group_by(Review.prompt_version)
        )
        metrics = []
        for row in result.all():
            version, total, fp = row
            metrics.append({
                "prompt_version": version or "unknown",
                "total_findings": total,
                "false_positives": fp,
                "false_positive_rate": round(fp / total, 4) if total else 0.0,
            })
        return metrics
