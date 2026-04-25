from datetime import timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Review, ReviewFinding
from models.commit_analysis import CommitAnalysis
from models.commit_finding import CommitFinding
from models.project_repo import ProjectRepo
from utils.timezone import get_beijing_start_of_day, format_iso_beijing, beijing_now


class StatsService:
    """Dashboard 首页概览数据统计服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_dashboard_summary(self) -> Dict:
        # PR review 统计
        pr_total = await self._count_reviews()
        pr_pending = await self._count_reviews_by_status("pending")
        pr_running = await self._count_reviews_by_status("running")
        pr_completed = await self._count_reviews_by_status("completed")
        pr_failed = await self._count_reviews_by_status("failed")
        pr_skipped = await self._count_reviews_by_status("skipped")
        pr_high_risk = await self._count_high_risk()
        pr_findings_today = await self._count_findings_today()

        # Commit analysis 统计
        ca_total = await self._count_commit_analyses()
        ca_pending = await self._count_commit_analyses_by_status("pending")
        ca_running = await self._count_commit_analyses_by_status("running")
        ca_completed = await self._count_commit_analyses_by_status("completed")
        ca_failed = await self._count_commit_analyses_by_status("failed")
        ca_skipped = 0  # CommitAnalysis 没有 skipped 状态
        ca_high_risk = await self._count_commit_high_risk()
        ca_findings_today = await self._count_commit_findings_today()

        # 合并统计
        total_reviews = pr_total + ca_total
        pending_reviews = pr_pending + ca_pending
        running_reviews = pr_running + ca_running
        completed_reviews = pr_completed + ca_completed
        failed_reviews = pr_failed + ca_failed
        skipped_reviews = pr_skipped + ca_skipped
        high_risk_count = pr_high_risk + ca_high_risk
        total_findings_today = pr_findings_today + ca_findings_today

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

    # ── Combined Metrics (PR review + commit analysis) ──────────────────

    async def get_combined_metrics(self, repo_id: str, range: str = "7d") -> Dict:
        """合并 PR review 指标和 commit analysis 指标。

        返回前端指标页所需的完整数据，包括两类审查的 findings 合并统计。
        """
        days = 7
        if range == "30d":
            days = 30
        elif range == "90d":
            days = 90

        # ── PR review 数据 ──
        pr_total_reviews = await self._count_pr_reviews(repo_id)
        pr_total_findings = await self._count_pr_findings(repo_id)
        pr_fp_count = await self._count_pr_false_positives(repo_id)
        pr_avg_confidence = await self._avg_pr_confidence(repo_id)
        pr_severity = await self._pr_severity_distribution(repo_id)
        pr_category = await self._pr_category_distribution(repo_id)

        fp_rate = 0.0
        if pr_total_findings > 0:
            fp_rate = round(pr_fp_count / pr_total_findings, 4)

        # ── Commit analysis 数据 ──
        project_id = await self._resolve_project_id(repo_id)
        commit_data = {}
        commit_findings_total = 0
        commit_category: Dict[str, int] = {}
        commit_severity: Dict[str, int] = {}
        commit_chart: List[Dict] = []
        contributors: List[Dict] = []
        code_changes = {"additions": 0, "deletions": 0, "files": 0}

        if project_id is not None:
            commits_total = await self._count_commits(project_id)
            analyzed = await self._count_analyzed_commits(project_id)
            commit_findings_total = await self._count_commit_findings(project_id)
            commit_severity = await self._commit_severity_distribution(project_id)
            commit_category = await self._commit_category_distribution(project_id)
            commit_chart = await self._commit_volume_chart(project_id, days=days)
            contributors = await self._top_contributors(project_id)
            code_changes = await self._code_changes_stats(project_id)
            commit_data = {
                "project_id": project_id,
                "total_commits": commits_total,
                "analyzed_commits": analyzed,
                "total_findings": commit_findings_total,
                "severity_distribution": commit_severity,
            }

        # ── 合并数据 ──
        merged_category: Dict[str, int] = dict(pr_category)
        for cat, count in commit_category.items():
            merged_category[cat] = merged_category.get(cat, 0) + count

        merged_severity: Dict[str, int] = dict(pr_severity)
        for sev, count in commit_severity.items():
            merged_severity[sev] = merged_severity.get(sev, 0) + count

        # 合并图表数据（PR reviews + commit findings）
        chart = await self._merge_volume_chart(repo_id, project_id, days)

        return {
            "repo_id": repo_id,
            "metrics": {
                "total_reviews": pr_total_reviews,
                "total_pr_findings": pr_total_findings,
                "total_commit_findings": commit_findings_total,
                "total_findings": pr_total_findings + commit_findings_total,
                "false_positive_rate": fp_rate,
                "avg_confidence": pr_avg_confidence,
            },
            "commit": commit_data,
            "chart": chart,
            "severity_distribution": merged_severity,
            "category_distribution": merged_category,
            "contributors": contributors,
            "code_changes": code_changes,
        }

    # ── PR review helpers ──

    async def _count_pr_reviews(self, repo_id: str) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Review).where(Review.repo_id == repo_id)
        )
        return result.scalar() or 0

    async def _count_pr_findings(self, repo_id: str) -> int:
        from models import ReviewFinding as RF
        result = await self.session.execute(
            select(func.count())
            .select_from(RF)
            .join(Review, RF.review_id == Review.id)
            .where(Review.repo_id == repo_id)
        )
        return result.scalar() or 0

    async def _count_pr_false_positives(self, repo_id: str) -> int:
        from models import ReviewFinding as RF, DeveloperFeedback as DF
        result = await self.session.execute(
            select(func.count())
            .select_from(DF)
            .join(RF, DF.finding_id == RF.id)
            .join(Review, RF.review_id == Review.id)
            .where(Review.repo_id == repo_id, DF.is_false_positive.is_(True))
        )
        return result.scalar() or 0

    async def _avg_pr_confidence(self, repo_id: str) -> float:
        from models import ReviewFinding as RF
        result = await self.session.execute(
            select(func.avg(RF.confidence))
            .join(Review, RF.review_id == Review.id)
            .where(Review.repo_id == repo_id)
        )
        val = result.scalar()
        return round(float(val), 4) if val is not None else 0.0

    async def _pr_severity_distribution(self, repo_id: str) -> Dict[str, int]:
        from models import ReviewFinding as RF
        result = await self.session.execute(
            select(RF.severity, func.count())
            .join(Review, RF.review_id == Review.id)
            .where(Review.repo_id == repo_id)
            .group_by(RF.severity)
        )
        return {row[0] or "unknown": row[1] for row in result.all()}

    async def _pr_category_distribution(self, repo_id: str) -> Dict[str, int]:
        from models import ReviewFinding as RF
        result = await self.session.execute(
            select(RF.category, func.count())
            .join(Review, RF.review_id == Review.id)
            .where(Review.repo_id == repo_id)
            .group_by(RF.category)
        )
        return {row[0] or "unknown": row[1] for row in result.all()}

    async def _pr_volume_chart(self, repo_id: str, days: int = 7) -> List[Dict]:
        from models import ReviewFinding as RF
        end = beijing_now()
        start = get_beijing_start_of_day(end - timedelta(days=days - 1))

        reviews_result = await self.session.execute(
            select(
                func.date(Review.created_at).label("day"),
                func.count(Review.id).label("cnt"),
            )
            .where(Review.repo_id == repo_id, Review.created_at >= start)
            .group_by("day").order_by("day")
        )
        reviews_by_day = {
            (row.day.strftime("%Y-%m-%d") if hasattr(row.day, "strftime") else str(row.day)): row.cnt
            for row in reviews_result.all()
        }

        findings_result = await self.session.execute(
            select(
                func.date(RF.created_at).label("day"),
                func.count(RF.id).label("cnt"),
            )
            .join(Review, RF.review_id == Review.id)
            .where(Review.repo_id == repo_id, RF.created_at >= start)
            .group_by("day").order_by("day")
        )
        findings_by_day = {
            (row.day.strftime("%Y-%m-%d") if hasattr(row.day, "strftime") else str(row.day)): row.cnt
            for row in findings_result.all()
        }

        chart = []
        for i in range(days):
            day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            chart.append({
                "date": day,
                "reviews": reviews_by_day.get(day, 0),
                "findings": findings_by_day.get(day, 0),
            })
        return chart

    # ── Commit analysis helpers ──

    async def _resolve_project_id(self, repo_id: str) -> int | None:
        result = await self.session.execute(
            select(ProjectRepo.id).where(ProjectRepo.repo_id == repo_id).limit(1)
        )
        row = result.scalar_one_or_none()
        return row

    async def _count_commits(self, project_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).where(CommitAnalysis.project_id == project_id)
        )
        return result.scalar() or 0

    async def _count_analyzed_commits(self, project_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).where(
                CommitAnalysis.project_id == project_id,
                CommitAnalysis.status == "completed",
            )
        )
        return result.scalar() or 0

    async def _count_commit_findings(self, project_id: int) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(CommitFinding)
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
        )
        return result.scalar() or 0

    async def _commit_severity_distribution(self, project_id: int) -> Dict[str, int]:
        result = await self.session.execute(
            select(CommitFinding.severity, func.count())
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
            .group_by(CommitFinding.severity)
        )
        return {row[0] or "unknown": row[1] for row in result.all()}

    async def _commit_category_distribution(self, project_id: int) -> Dict[str, int]:
        result = await self.session.execute(
            select(CommitFinding.category, func.count())
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
            .group_by(CommitFinding.category)
        )
        return {row[0] or "unknown": row[1] for row in result.all()}

    async def _commit_volume_chart(self, project_id: int, days: int = 7) -> List[Dict]:
        """获取 commit analysis 的每日分析量与发现项数。"""
        end = beijing_now()
        start = get_beijing_start_of_day(end - timedelta(days=days - 1))

        analyses_result = await self.session.execute(
            select(
                func.date(CommitAnalysis.analyzed_at).label("day"),
                func.count(CommitAnalysis.id).label("cnt"),
            )
            .where(CommitAnalysis.project_id == project_id, CommitAnalysis.analyzed_at >= start)
            .group_by("day").order_by("day")
        )
        analyses_by_day = {
            (row.day.strftime("%Y-%m-%d") if hasattr(row.day, "strftime") else str(row.day)): row.cnt
            for row in analyses_result.all()
        }

        findings_result = await self.session.execute(
            select(
                func.date(CommitFinding.created_at).label("day"),
                func.count(CommitFinding.id).label("cnt"),
            )
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id, CommitFinding.created_at >= start)
            .group_by("day").order_by("day")
        )
        findings_by_day = {
            (row.day.strftime("%Y-%m-%d") if hasattr(row.day, "strftime") else str(row.day)): row.cnt
            for row in findings_result.all()
        }

        chart = []
        for i in range(days):
            day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            chart.append({
                "date": day,
                "analyses": analyses_by_day.get(day, 0),
                "findings": findings_by_day.get(day, 0),
            })
        return chart

    async def _merge_volume_chart(
        self,
        repo_id: str,
        project_id: Optional[int],
        days: int = 7,
    ) -> List[Dict]:
        """合并 PR review 和 commit analysis 的时间序列图表。

        返回的每个点包含：date, reviews(PR), pr_findings, analyses(commit), commit_findings。
        """
        end = beijing_now()
        start = get_beijing_start_of_day(end - timedelta(days=days - 1))

        # PR reviews
        reviews_result = await self.session.execute(
            select(
                func.date(Review.created_at).label("day"),
                func.count(Review.id).label("cnt"),
            )
            .where(Review.repo_id == repo_id, Review.created_at >= start)
            .group_by("day").order_by("day")
        )
        reviews_by_day = {
            (row.day.strftime("%Y-%m-%d") if hasattr(row.day, "strftime") else str(row.day)): row.cnt
            for row in reviews_result.all()
        }

        # PR findings
        from models import ReviewFinding as RF
        pr_findings_result = await self.session.execute(
            select(
                func.date(RF.created_at).label("day"),
                func.count(RF.id).label("cnt"),
            )
            .join(Review, RF.review_id == Review.id)
            .where(Review.repo_id == repo_id, RF.created_at >= start)
            .group_by("day").order_by("day")
        )
        pr_findings_by_day = {
            (row.day.strftime("%Y-%m-%d") if hasattr(row.day, "strftime") else str(row.day)): row.cnt
            for row in pr_findings_result.all()
        }

        # Commit analyses
        analyses_by_day: Dict[str, int] = {}
        commit_findings_by_day: Dict[str, int] = {}
        if project_id is not None:
            analyses_result = await self.session.execute(
                select(
                    func.date(CommitAnalysis.analyzed_at).label("day"),
                    func.count(CommitAnalysis.id).label("cnt"),
                )
                .where(CommitAnalysis.project_id == project_id, CommitAnalysis.analyzed_at >= start)
                .group_by("day").order_by("day")
            )
            analyses_by_day = {
                (row.day.strftime("%Y-%m-%d") if hasattr(row.day, "strftime") else str(row.day)): row.cnt
                for row in analyses_result.all()
            }

            commit_findings_result = await self.session.execute(
                select(
                    func.date(CommitFinding.created_at).label("day"),
                    func.count(CommitFinding.id).label("cnt"),
                )
                .join(CommitFinding.analysis)
                .where(CommitAnalysis.project_id == project_id, CommitFinding.created_at >= start)
                .group_by("day").order_by("day")
            )
            commit_findings_by_day = {
                (row.day.strftime("%Y-%m-%d") if hasattr(row.day, "strftime") else str(row.day)): row.cnt
                for row in commit_findings_result.all()
            }

        chart = []
        for i in range(days):
            day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            chart.append({
                "date": day,
                "reviews": reviews_by_day.get(day, 0),
                "pr_findings": pr_findings_by_day.get(day, 0),
                "analyses": analyses_by_day.get(day, 0),
                "commit_findings": commit_findings_by_day.get(day, 0),
            })
        return chart

    async def _top_contributors(self, project_id: int, limit: int = 5) -> List[Dict]:
        """统计发现问题最多的贡献者（按 commit author）。"""
        result = await self.session.execute(
            select(
                CommitAnalysis.author_name,
                func.count(CommitFinding.id).label("finding_count"),
                func.count(func.distinct(CommitAnalysis.id)).label("commit_count"),
            )
            .join(CommitFinding, CommitFinding.commit_analysis_id == CommitAnalysis.id)
            .where(CommitAnalysis.project_id == project_id)
            .group_by(CommitAnalysis.author_name)
            .order_by(func.count(CommitFinding.id).desc())
            .limit(limit)
        )
        return [
            {
                "author": row[0] or "unknown",
                "finding_count": row[1],
                "commit_count": row[2],
            }
            for row in result.all()
        ]

    async def _code_changes_stats(self, project_id: int) -> Dict[str, int]:
        """统计 commit 代码变更总量。"""
        result = await self.session.execute(
            select(
                func.coalesce(func.sum(CommitAnalysis.additions), 0),
                func.coalesce(func.sum(CommitAnalysis.deletions), 0),
                func.coalesce(func.sum(CommitAnalysis.changed_files), 0),
            )
            .where(CommitAnalysis.project_id == project_id)
        )
        row = result.one_or_none()
        if row:
            return {
                "additions": int(row[0]),
                "deletions": int(row[1]),
                "files": int(row[2]),
            }
        return {"additions": 0, "deletions": 0, "files": 0}

    # ── Dashboard summary helpers (unchanged) ──

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
        from models import ReviewFinding as RF
        today = get_beijing_start_of_day()
        result = await self.session.execute(
            select(func.count()).select_from(RF).where(RF.created_at >= today)
        )
        return result.scalar() or 0

    # ── Commit analysis dashboard helpers ──

    async def _count_commit_analyses(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(CommitAnalysis))
        return result.scalar() or 0

    async def _count_commit_analyses_by_status(self, status: str) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(CommitAnalysis).where(CommitAnalysis.status == status)
        )
        return result.scalar() or 0

    async def _count_commit_high_risk(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(CommitAnalysis)
            .where(CommitAnalysis.risk_level.in_(["high", "critical"]))
        )
        return result.scalar() or 0

    async def _count_commit_findings_today(self) -> int:
        today = get_beijing_start_of_day()
        result = await self.session.execute(
            select(func.count()).select_from(CommitFinding).where(CommitFinding.created_at >= today)
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
                "created_at": format_iso_beijing(r.created_at),
            }
            for r in reviews
        ]
