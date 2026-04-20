import logging
import os
import subprocess

from celery import Celery

from config import settings
from services.review_service import run_review

logger = logging.getLogger(__name__)

celery_app = Celery(
    "latte_pr_agent",
    broker=settings.redis_url.get_secret_value(),
    backend=settings.redis_url.get_secret_value(),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=300,
)


@celery_app.task(bind=True, max_retries=2)
def run_review_task(self, review_id: int) -> None:
    """Celery task wrapper for run_review."""
    import asyncio
    from models.base import recreate_engine
    try:
        recreate_engine()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_review(review_id))
        finally:
            loop.close()
    except (OSError, ConnectionError, TimeoutError) as exc:
        logger.exception("Celery task failed for review %s: %s", review_id, exc)
        raise self.retry(exc=exc, countdown=10)


def get_celery_task():
    """Return the Celery task function for dispatching."""
    return run_review_task


@celery_app.task(bind=True, max_retries=1)
def clone_project_task(self, project_id: int) -> None:
    import asyncio
    from models.base import recreate_engine

    recreate_engine()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_do_clone(project_id))
    finally:
        loop.close()


async def _do_clone(project_id: int) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from models.base import async_engine
    from models.project_repo import ProjectRepo
    from sqlalchemy import select

    AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ProjectRepo).where(ProjectRepo.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return

        try:
            os.makedirs(os.path.dirname(project.local_path), exist_ok=True)
            subprocess.run(
                ["git", "clone", "--branch", project.branch, project.repo_url, project.local_path],
                capture_output=True,
                text=True,
                timeout=300,
            )
            project.status = "ready"
            await session.commit()
        except Exception as exc:
            project.status = "error"
            project.error_message = str(exc)
            await session.commit()
