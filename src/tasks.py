import asyncio
import logging
import os
import shutil
import subprocess
import sys
import time

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
    from commits.scanner import GitLogScanner
    from commits.service import CommitService
    from projects.progress import AnalysisProgressTracker

    AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ProjectRepo).where(ProjectRepo.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            logger.warning("Clone task: project %s not found", project_id)
            return

        await AnalysisProgressTracker.start(project_id, "clone")
        logger.info("Starting clone for project %s: %s -> %s", project_id, project.repo_url, project.local_path)

        try:
            os.makedirs(os.path.dirname(project.local_path) if project.local_path else "/tmp/repos", exist_ok=True)
            abs_local_path = os.path.abspath(project.local_path) if project.local_path else ""
            if abs_local_path and os.path.isdir(os.path.join(abs_local_path, ".git")):
                logger.info("Repo already exists at %s, skipping clone", abs_local_path)
                await AnalysisProgressTracker.update(
                    project_id, step="skip_clone", progress=50, total=100,
                    message="仓库已存在，跳过克隆",
                )
            else:
                await AnalysisProgressTracker.update(
                    project_id, step="cloning", progress=20, total=100,
                    message="正在克隆仓库...",
                )
                # 清理已存在但非 git 仓库的残留目录
                if abs_local_path and os.path.exists(abs_local_path):
                    if os.path.isdir(abs_local_path):
                        shutil.rmtree(abs_local_path)
                    else:
                        os.remove(abs_local_path)
                t0 = time.monotonic()
                clone_cwd = os.path.dirname(abs_local_path) or "."
                clone_target = os.path.basename(abs_local_path)
                os.makedirs(clone_cwd, exist_ok=True)
                if sys.platform == "win32":
                    loop = asyncio.get_running_loop()
                    def _clone() -> subprocess.CompletedProcess:
                        return subprocess.run(
                            ["git", "clone", project.repo_url, clone_target],
                            capture_output=True,
                            timeout=300,
                            cwd=clone_cwd,
                        )
                    proc = await loop.run_in_executor(None, _clone)
                    if proc.returncode != 0:
                        raise RuntimeError(f"git clone failed: {proc.stderr.decode('utf-8', errors='replace')}")
                else:
                    proc = await asyncio.create_subprocess_exec(
                        "git", "clone", project.repo_url, clone_target,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=clone_cwd,
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
                    if proc.returncode != 0:
                        raise RuntimeError(f"git clone failed: {stderr.decode('utf-8', errors='replace')}")

                def _detect_branch() -> str:
                    r = subprocess.run(
                        ["git", "-C", abs_local_path, "rev-parse", "--abbrev-ref", "HEAD"],
                        capture_output=True, text=True, timeout=10,
                    )
                    return r.stdout.strip() if r.returncode == 0 else "main"

                if sys.platform == "win32":
                    detected_branch = await loop.run_in_executor(None, _detect_branch)
                else:
                    bp = await asyncio.create_subprocess_exec(
                        "git", "-C", abs_local_path, "rev-parse", "--abbrev-ref", "HEAD",
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    )
                    bo, _ = await asyncio.wait_for(bp.communicate(), timeout=10)
                    detected_branch = bo.decode().strip() if bp.returncode == 0 else "main"

                if detected_branch and detected_branch != project.branch:
                    logger.info("Detected default branch '%s' (configured: '%s'), updating", detected_branch, project.branch)
                    project.branch = detected_branch

                elapsed = time.monotonic() - t0
                logger.info("Clone succeeded for project %s in %.2fs", project_id, elapsed)
                await AnalysisProgressTracker.update(
                    project_id, step="clone_done", progress=60, total=100,
                    message=f"克隆完成，耗时 {elapsed:.1f}s",
                )

            # 克隆成功后自动扫描提交
            await AnalysisProgressTracker.update(
                project_id, step="scanning", progress=70, total=100,
                message="开始扫描提交...",
            )
            scanner = GitLogScanner(project.local_path)
            commits = await scanner.get_commit_list(branch=project.branch, max_count=50)
            logger.info("Project %s: scanned %s commits", project_id, len(commits))
            await AnalysisProgressTracker.update(
                project_id, step="saving", progress=85, total=100,
                message=f"扫描完成，正在保存 {len(commits)} 条提交...",
            )

            commit_svc = CommitService(session)
            saved = await commit_svc.save_commits(project_id, commits)
            logger.info("Project %s: saved %s new commits", project_id, saved)

            if commits:
                project.last_analyzed_sha = commits[0].hash
                project.total_commits = saved

            project.status = "ready"
            await session.commit()
            logger.info("Project %s: clone and scan completed", project_id)

            await AnalysisProgressTracker.complete(
                project_id,
                result={"scanned": len(commits), "saved": saved},
            )
        except Exception as exc:
            logger.exception("Clone failed for project %s: %s", project_id, exc)
            await AnalysisProgressTracker.fail(project_id, str(exc))
            project.status = "error"
            project.error_message = str(exc)
            await session.commit()
