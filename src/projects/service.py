import logging
import os
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.project_repo import ProjectRepo

logger = logging.getLogger(__name__)


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

        repos_base = getattr(settings, "repos_base_path", "/repos")
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
        if project.local_path and os.path.isdir(project.local_path):
            import shutil
            shutil.rmtree(project.local_path, ignore_errors=True)
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
