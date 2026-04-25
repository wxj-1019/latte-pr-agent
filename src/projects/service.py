import logging
import os
import shutil
import stat
import sys
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.project_repo import ProjectRepo
from models.commit_analysis import CommitAnalysis
from models.commit_finding import CommitFinding

logger = logging.getLogger(__name__)


def _remove_readonly(func, path, excinfo):
    """Windows 下 shutil.rmtree 遇到只读文件时的回调，先修改为可写再删除。"""
    if sys.platform == "win32":
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass


def _is_safe_path(base_path: str, target_path: str) -> bool:
    """检查 target_path 是否在 base_path 之下，防止路径遍历。"""
    abs_base = os.path.abspath(base_path)
    abs_target = os.path.abspath(target_path)
    return abs_target.startswith(abs_base + os.sep) or abs_target == abs_base


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_project(
        self, platform: str, repo_id: str, repo_url: str, branch: str = "main", org_id: str = "default"
    ) -> ProjectRepo:
        result = await self.session.execute(
            select(ProjectRepo).where(
                ProjectRepo.org_id == org_id,
                ProjectRepo.platform == platform,
                ProjectRepo.repo_id == repo_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        repos_base = settings.repos_base_path
        local_path = os.path.join(repos_base, org_id, repo_id.replace("/", "_"))

        project = ProjectRepo(
            org_id=org_id,
            platform=platform,
            repo_id=repo_id,
            repo_url=repo_url,
            branch=branch,
            local_path=local_path,
            status="cloning",
        )
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def list_projects(self, org_id: str = "default") -> List[ProjectRepo]:
        result = await self.session.execute(
            select(ProjectRepo)
            .where(ProjectRepo.org_id == org_id)
            .order_by(ProjectRepo.updated_at.desc())
        )
        projects = list(result.scalars().all())

        # 动态刷新每个项目的 commit/finding 统计（避免静态字段与实际数据不一致）
        if projects:
            project_ids = [p.id for p in projects]

            commit_counts = await self.session.execute(
                select(CommitAnalysis.project_id, func.count(CommitAnalysis.id))
                .where(CommitAnalysis.project_id.in_(project_ids))
                .group_by(CommitAnalysis.project_id)
            )
            commit_map = {pid: cnt for pid, cnt in commit_counts.all()}

            finding_counts = await self.session.execute(
                select(CommitAnalysis.project_id, func.count(CommitFinding.id))
                .join(CommitFinding, CommitFinding.commit_analysis_id == CommitAnalysis.id)
                .where(CommitAnalysis.project_id.in_(project_ids))
                .group_by(CommitAnalysis.project_id)
            )
            finding_map = {pid: cnt for pid, cnt in finding_counts.all()}

            for p in projects:
                # 先 expunge 再修改，避免 ORM 脏跟踪导致意外 flush 覆盖数据库
                self.session.expunge(p)
                p.total_commits = commit_map.get(p.id, 0)
                p.total_findings = finding_map.get(p.id, 0)

        return projects

    async def get_project(self, project_id: int) -> Optional[ProjectRepo]:
        result = await self.session.execute(select(ProjectRepo).where(ProjectRepo.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            commit_count = await self.session.execute(
                select(func.count(CommitAnalysis.id)).where(CommitAnalysis.project_id == project_id)
            )
            project.total_commits = commit_count.scalar() or 0

            finding_count = await self.session.execute(
                select(func.count(CommitFinding.id))
                .join(CommitFinding.analysis)
                .where(CommitAnalysis.project_id == project_id)
            )
            project.total_findings = finding_count.scalar() or 0
        return project

    async def delete_project(self, project_id: int) -> bool:
        project = await self.get_project(project_id)
        if not project:
            return False

        if project.local_path and isinstance(project.local_path, str):
            abs_local = os.path.abspath(project.local_path)
            abs_repos_base = os.path.abspath(settings.repos_base_path)

            if os.path.isdir(abs_local) and _is_safe_path(abs_repos_base, abs_local):
                try:
                    shutil.rmtree(abs_local, onexc=_remove_readonly)
                    logger.info("Deleted project directory: %s", abs_local)
                except Exception as exc:
                    logger.warning("Failed to delete project directory %s: %s", abs_local, exc)
            else:
                logger.warning(
                    "Skipped deleting directory %s: not under repos_base %s or does not exist",
                    abs_local, abs_repos_base,
                )

        await self.session.delete(project)
        await self.session.commit()
        return True

    async def update_status(self, project_id: int, status: str, error_message: Optional[str] = None) -> None:
        project = await self.get_project(project_id)
        if project:
            project.status = status
            if error_message is not None:
                project.error_message = error_message
            await self.session.commit()
