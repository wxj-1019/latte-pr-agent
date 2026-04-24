import logging
import os
import shutil
import stat
import sys
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.project_repo import ProjectRepo

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
        return list(result.scalars().all())

    async def get_project(self, project_id: int) -> Optional[ProjectRepo]:
        result = await self.session.execute(select(ProjectRepo).where(ProjectRepo.id == project_id))
        return result.scalar_one_or_none()

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
