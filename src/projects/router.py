import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from projects.schemas import AddProjectRequest, ProjectListResponse, ProjectResponse, SyncResponse
from projects.service import ProjectService
from projects.progress import AnalysisProgressTracker

router = APIRouter(prefix="/projects", tags=["projects"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ProjectResponse, status_code=201)
async def add_project(
    body: AddProjectRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    if body.platform not in ("github", "gitlab"):
        raise HTTPException(status_code=400, detail="platform must be 'github' or 'gitlab'")
    svc = ProjectService(db)
    try:
        project = await svc.add_project(
            platform=body.platform,
            repo_id=body.repo_id,
            repo_url=body.repo_url,
            branch=body.branch,
            org_id=body.org_id,
        )
    except Exception as exc:
        logger.exception("Failed to add project %s/%s", body.platform, body.repo_id)
        raise HTTPException(status_code=500, detail=f"添加项目失败: {exc}")
    if project.status == "cloning":
        from tasks import _do_clone
        background_tasks.add_task(_do_clone, project.id)
    return project


@router.get("", response_model=ProjectListResponse)
async def list_projects(org_id: str = "default", db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    projects = await svc.list_projects(org_id)
    return ProjectListResponse(projects=projects, total=len(projects))


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    deleted = await svc.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"id": project_id, "status": "deleted"}


async def _git_cmd(cwd: str, args: list[str], timeout: int = 60) -> str:
    t0 = time.monotonic()
    if sys.platform == "win32":
        loop = asyncio.get_running_loop()
        def _run() -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git", *args],
                cwd=cwd,
                capture_output=True,
                timeout=timeout,
            )
        proc = await loop.run_in_executor(None, _run)
        if proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', errors='replace')}")
        stdout = proc.stdout.decode("utf-8", errors="replace")
    else:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {stderr.decode('utf-8', errors='replace')}")
        stdout = stdout_b.decode("utf-8", errors="replace")
    elapsed = time.monotonic() - t0
    logger.info("Git command [git %s] in %s completed in %.2fs", ' '.join(args), cwd, elapsed)
    return stdout


@router.post("/{project_id}/sync", response_model=SyncResponse)
async def sync_project(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    svc = ProjectService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    background_tasks.add_task(
        _do_sync, project_id, project.local_path, project.branch, project.repo_url
    )
    return SyncResponse(id=project.id, status="syncing", new_commits=0)


async def _do_sync(
    project_id: int,
    local_path: str,
    branch: str,
    repo_url: str,
) -> None:
    """后台执行仓库同步，并实时报告进度。"""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from models.base import async_engine
    from sqlalchemy import select
    from models.project_repo import ProjectRepo
    from commits.scanner import GitLogScanner
    from commits.service import CommitService

    AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

    await AnalysisProgressTracker.start(project_id, "sync")

    try:
        new_commits = 0

        if local_path and os.path.isdir(os.path.join(local_path, ".git")):
            await AnalysisProgressTracker.update(
                project_id, step="fetching", progress=10, total=100,
                message="正在 fetch 远程仓库...",
            )
            await _git_cmd(local_path, ["fetch", "origin"], timeout=60)

            await AnalysisProgressTracker.update(
                project_id, step="checking_updates", progress=30, total=100,
                message="检查更新中...",
            )
            result = await _git_cmd(
                local_path,
                ["log", f"HEAD..origin/{branch}", "--oneline"],
                timeout=30,
            )
            ahead_count = len([line for line in result.strip().split("\n") if line])

            await AnalysisProgressTracker.update(
                project_id, step="pulling", progress=50, total=100,
                message=f"发现 {ahead_count} 个新提交，正在 pull...",
            )
            await _git_cmd(local_path, ["pull", "origin", branch], timeout=60)
        else:
            await AnalysisProgressTracker.update(
                project_id, step="cloning", progress=20, total=100,
                message="本地仓库不存在，正在 clone...",
            )
            # 如果目标路径已存在但不是 git 仓库（如上次 clone 中断留下的残目录），先清理
            abs_local_path = os.path.abspath(local_path)
            if local_path and os.path.exists(abs_local_path):
                if os.path.isdir(abs_local_path):
                    shutil.rmtree(abs_local_path)
                else:
                    os.remove(abs_local_path)
            os.makedirs(os.path.dirname(abs_local_path), exist_ok=True)
            await _git_cmd(
                os.path.dirname(abs_local_path),
                ["clone", repo_url, os.path.basename(abs_local_path)],
                timeout=300,
            )
            detected = await _git_cmd(
                local_path,
                ["rev-parse", "--abbrev-ref", "HEAD"],
                timeout=10,
            )
            detected_branch = detected.strip()
            if detected_branch and detected_branch != branch:
                logger.info(
                    "Project %s: detected default branch '%s' (was '%s')",
                    project_id, detected_branch, branch,
                )
                branch = detected_branch
                async with AsyncSessionLocal() as session:
                    proj = (await session.execute(
                        select(ProjectRepo).where(ProjectRepo.id == project_id)
                    )).scalar_one_or_none()
                    if proj:
                        proj.branch = detected_branch
                        await session.commit()
            await AnalysisProgressTracker.update(
                project_id, step="clone_done", progress=60, total=100,
                message="克隆完成",
            )

        # 同步完成后自动扫描提交
        await AnalysisProgressTracker.update(
            project_id, step="scanning", progress=70, total=100,
            message="同步完成，开始扫描提交...",
        )

        scanner = GitLogScanner(local_path)
        commits = await scanner.get_commit_list(branch=branch, max_count=50)
        logger.info("Project %s: sync scanned %s commits", project_id, len(commits))

        async with AsyncSessionLocal() as session:
            commit_svc = CommitService(session)
            saved = await commit_svc.save_commits(project_id, commits)
            logger.info("Project %s: sync saved %s new commits", project_id, saved)

            if commits:
                project_result = await session.execute(
                    select(ProjectRepo).where(ProjectRepo.id == project_id)
                )
                project = project_result.scalar_one_or_none()
                if project:
                    project.last_analyzed_sha = commits[0].hash
                    project.total_commits += saved
                    project.status = "ready"
                    await session.commit()

                # 同步后自适应进化项目专属 Prompt（失败不影响主流程）
                try:
                    from prompts.project_prompt_generator import ProjectPromptGenerator
                    gen = ProjectPromptGenerator(session)
                    await gen.generate(project, force=False)
                except Exception as exc:
                    logger.warning("Project %s: auto prompt generation failed on sync: %s", project_id, exc)

            new_commits = saved

        await AnalysisProgressTracker.complete(
            project_id,
            result={"new_commits": new_commits},
        )
        logger.info("Project %s: sync completed, new_commits=%d", project_id, new_commits)

    except Exception as exc:
        logger.exception("Sync failed for project %s: %s", project_id, exc)
        await AnalysisProgressTracker.fail(project_id, str(exc))
        # 尝试更新项目状态为 error
        try:
            async with AsyncSessionLocal() as session:
                project_result = await session.execute(
                    select(ProjectRepo).where(ProjectRepo.id == project_id)
                )
                project = project_result.scalar_one_or_none()
                if project:
                    project.status = "error"
                    project.error_message = str(exc)[:500]
                    await session.commit()
        except Exception:
            logger.exception("Failed to update project error status for project %s", project_id)


@router.get("/{project_id}/stream")
async def project_analysis_stream(project_id: int):
    """SSE 端点：推送项目分析实时进度。"""
    async def event_generator():
        known: dict = {}
        while True:
            await asyncio.sleep(2)
            try:
                current = await AnalysisProgressTracker.get(project_id)
            except Exception:
                logger.warning("SSE: failed to get progress for project %s", project_id, exc_info=True)
                await asyncio.sleep(5)
                continue

            if current and current != known:
                known = current.copy()
                yield f"data: {json.dumps(current, ensure_ascii=False)}\n\n"

            if current and current.get("status") in ("completed", "failed"):
                # 再推送一次最终状态，然后清理
                await asyncio.sleep(1)
                await AnalysisProgressTracker.clear(project_id)
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
