import logging
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from commits.schemas import CommitInfo
from models.commit_analysis import CommitAnalysis
from models.commit_finding import CommitFinding
from models.project_repo import ProjectRepo

logger = logging.getLogger(__name__)


class CommitService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_project(self, project_id: int) -> Optional[ProjectRepo]:
        result = await self.session.execute(select(ProjectRepo).where(ProjectRepo.id == project_id))
        return result.scalar_one_or_none()

    async def save_commits(self, project_id: int, commits: List[CommitInfo]) -> int:
        saved = 0
        for ci in commits:
            result = await self.session.execute(
                select(CommitAnalysis).where(
                    CommitAnalysis.project_id == project_id,
                    CommitAnalysis.commit_hash == ci.hash,
                )
            )
            if result.scalar_one_or_none():
                continue

            ca = CommitAnalysis(
                project_id=project_id,
                commit_hash=ci.hash,
                parent_hash=ci.parent_hash or None,
                author_name=ci.author_name,
                author_email=ci.author_email,
                message=ci.message,
                commit_ts=ci.timestamp,
                additions=ci.additions,
                deletions=ci.deletions,
                changed_files=ci.changed_files,
                status="pending",
            )
            self.session.add(ca)
            saved += 1
        await self.session.commit()
        return saved

    async def list_commits(
        self, project_id: int, page: int = 1, page_size: int = 20, risk_level: Optional[str] = None
    ) -> dict:
        query = select(CommitAnalysis).where(CommitAnalysis.project_id == project_id)
        if risk_level:
            query = query.where(CommitAnalysis.risk_level == risk_level)
        query = query.order_by(CommitAnalysis.commit_ts.desc())

        count_q = select(func.count()).select_from(CommitAnalysis).where(CommitAnalysis.project_id == project_id)
        if risk_level:
            count_q = count_q.where(CommitAnalysis.risk_level == risk_level)
        total = (await self.session.execute(count_q)).scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        commits = list(result.scalars().all())
        return {"commits": commits, "total": total, "page": page, "page_size": page_size}

    async def get_commit(self, project_id: int, commit_hash: str) -> Optional[CommitAnalysis]:
        result = await self.session.execute(
            select(CommitAnalysis).where(
                CommitAnalysis.project_id == project_id,
                CommitAnalysis.commit_hash == commit_hash,
            )
        )
        return result.scalar_one_or_none()

    async def get_commit_findings(self, commit_analysis_id: int) -> List[CommitFinding]:
        result = await self.session.execute(
            select(CommitFinding).where(CommitFinding.commit_analysis_id == commit_analysis_id)
        )
        return list(result.scalars().all())

    async def get_project_findings(
        self, project_id: int, severity: Optional[str] = None, page: int = 1, page_size: int = 20
    ) -> dict:
        query = (
            select(CommitFinding, CommitAnalysis.commit_hash, CommitAnalysis.message.label("commit_message"))
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
        )
        if severity:
            query = query.where(CommitFinding.severity == severity)

        total = (await self.session.execute(
            select(func.count()).select_from(CommitFinding)
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
        )).scalar() or 0

        query = query.order_by(CommitFinding.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        rows = result.all()
        findings = []
        for row in rows:
            finding = row[0]
            findings.append({
                "id": finding.id,
                "commit_hash": row[1],
                "commit_message": row[2],
                "file_path": finding.file_path,
                "line_number": finding.line_number,
                "severity": finding.severity,
                "category": finding.category,
                "description": finding.description,
                "suggestion": finding.suggestion,
                "confidence": finding.confidence,
            })
        return {"findings": findings, "total": total, "page": page}

    async def get_project_stats(self, project_id: int) -> dict:
        commits_total = (await self.session.execute(
            select(func.count()).where(CommitAnalysis.project_id == project_id)
        )).scalar() or 0

        analyzed = (await self.session.execute(
            select(func.count()).where(
                CommitAnalysis.project_id == project_id,
                CommitAnalysis.status == "completed",
            )
        )).scalar() or 0

        findings_total = (await self.session.execute(
            select(func.count())
            .select_from(CommitFinding)
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
        )).scalar() or 0

        sev_result = await self.session.execute(
            select(CommitFinding.severity, func.count())
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
            .group_by(CommitFinding.severity)
        )
        severity_dist = {row[0]: row[1] for row in sev_result.all()}

        cat_result = await self.session.execute(
            select(CommitFinding.category, func.count())
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
            .group_by(CommitFinding.category)
        )
        category_dist = {row[0]: row[1] for row in cat_result.all()}

        return {
            "total_commits": commits_total,
            "analyzed_commits": analyzed,
            "total_findings": findings_total,
            "severity_distribution": severity_dist,
            "category_distribution": category_dist,
        }

    async def get_contributor_analysis(self, project_id: int) -> dict:
        commit_rows = (await self.session.execute(
            select(
                CommitAnalysis.author_name,
                CommitAnalysis.author_email,
                func.count(CommitAnalysis.id).label("commit_count"),
                func.sum(CommitAnalysis.additions).label("total_additions"),
                func.sum(CommitAnalysis.deletions).label("total_deletions"),
                func.sum(CommitAnalysis.changed_files).label("total_files"),
                func.max(CommitAnalysis.commit_ts).label("latest_commit"),
            )
            .where(CommitAnalysis.project_id == project_id)
            .group_by(CommitAnalysis.author_name, CommitAnalysis.author_email)
            .order_by(func.count(CommitAnalysis.id).desc())
        )).all()

        contributors = []
        for row in commit_rows:
            name, email, commits, adds, dels, files, latest = row
            sev_rows = (await self.session.execute(
                select(CommitFinding.severity, func.count())
                .join(CommitFinding.analysis)
                .where(
                    CommitAnalysis.project_id == project_id,
                    CommitAnalysis.author_name == name,
                    CommitAnalysis.author_email == email,
                )
                .group_by(CommitFinding.severity)
            )).all()
            sev_map = {r[0]: r[1] for r in sev_rows}

            critical_count = sev_map.get("critical", 0)
            warning_count = sev_map.get("warning", 0)
            info_count = sev_map.get("info", 0)
            total_findings = critical_count + warning_count + info_count

            penalty = critical_count * 15 + warning_count * 5 + info_count * 1
            quality_score = max(0, 100 - penalty)

            analyzed_commits = (await self.session.execute(
                select(func.count()).where(
                    CommitAnalysis.project_id == project_id,
                    CommitAnalysis.author_name == name,
                    CommitAnalysis.author_email == email,
                    CommitAnalysis.status == "completed",
                )
            )).scalar() or 0

            finding_density = round(total_findings / max(analyzed_commits, 1), 2) if analyzed_commits > 0 else 0.0

            contributors.append({
                "author_name": name or "Unknown",
                "author_email": email or "",
                "commit_count": commits,
                "analyzed_commits": analyzed_commits,
                "total_additions": int(adds or 0),
                "total_deletions": int(dels or 0),
                "total_files_changed": int(files or 0),
                "latest_commit": latest.isoformat() if latest else None,
                "findings": {
                    "critical": critical_count,
                    "warning": warning_count,
                    "info": info_count,
                    "total": total_findings,
                },
                "finding_density": finding_density,
                "quality_score": quality_score,
                "grade": self._score_to_grade(quality_score),
            })

        return {"contributors": contributors, "total": len(contributors)}

    async def get_contributor_detail(self, project_id: int, author_email: str) -> dict:
        base_q = select(CommitAnalysis).where(
            CommitAnalysis.project_id == project_id,
            CommitAnalysis.author_email == author_email,
        ).order_by(CommitAnalysis.commit_ts.desc())

        total = (await self.session.execute(
            select(func.count()).select_from(CommitAnalysis).where(
                CommitAnalysis.project_id == project_id,
                CommitAnalysis.author_email == author_email,
            )
        )).scalar() or 0

        commits_result = await self.session.execute(base_q.limit(50))
        commits = list(commits_result.scalars().all())

        # Batch load findings to avoid N+1 queries
        commit_ids = [c.id for c in commits]
        findings_map: dict = {}
        if commit_ids:
            findings_result = await self.session.execute(
                select(CommitFinding).where(CommitFinding.commit_analysis_id.in_(commit_ids))
            )
            for f in findings_result.scalars().all():
                findings_map.setdefault(f.commit_analysis_id, []).append(f)

        commit_list = []
        for c in commits:
            findings = findings_map.get(c.id, [])
            commit_list.append({
                "commit_hash": c.commit_hash,
                "message": c.message,
                "commit_ts": c.commit_ts.isoformat() if c.commit_ts else None,
                "additions": c.additions,
                "deletions": c.deletions,
                "changed_files": c.changed_files,
                "risk_level": c.risk_level,
                "status": c.status,
                "findings_count": len(findings),
                "findings": [
                    {
                        "id": f.id,
                        "file_path": f.file_path,
                        "line_number": f.line_number,
                        "severity": f.severity,
                        "category": f.category,
                        "description": f.description,
                        "suggestion": f.suggestion,
                    }
                    for f in findings
                ],
            })

        return {"commits": commit_list, "total": total}

    @staticmethod
    def _score_to_grade(score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 75:
            return "B"
        if score >= 60:
            return "C"
        if score >= 40:
            return "D"
        return "F"
