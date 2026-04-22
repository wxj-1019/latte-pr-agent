import asyncio
import logging
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from commits.service import CommitService
from projects.progress import AnalysisProgressTracker


class ProjectNotFoundException(HTTPException):
    def __init__(self, project_id: int):
        super().__init__(status_code=404, detail=f"Project {project_id} not found")


router = APIRouter(prefix="/projects/{project_id}", tags=["commits"])
logger = logging.getLogger(__name__)


@router.post("/scan")
async def scan_commits(
    project_id: int,
    background_tasks: BackgroundTasks,
    max_commits: int = Query(default=50, ge=1, le=500),
    since: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)

    if not project.local_path or not os.path.isdir(os.path.join(project.local_path, ".git")):
        raise HTTPException(status_code=400, detail="Project repository not cloned yet")

    background_tasks.add_task(
        _do_scan, project_id, project.local_path, project.branch, max_commits, since, project.last_analyzed_sha
    )
    return {"project_id": project_id, "status": "started", "operation": "scan"}


async def _do_scan(
    project_id: int,
    local_path: str,
    branch: str,
    max_commits: int,
    since: Optional[str],
    after_sha: Optional[str],
) -> None:
    """后台执行提交扫描，并实时报告进度。"""
    from commits.scanner import GitLogScanner
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from models.base import async_engine

    AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

    await AnalysisProgressTracker.start(project_id, "scan")

    try:
        scanner = GitLogScanner(local_path)

        async def _on_progress(step: str, progress: int, total: int) -> None:
            await AnalysisProgressTracker.update(
                project_id,
                step=step,
                progress=progress,
                total=total,
                message=f"{'解析' if step == 'parsing_git_log' else '保存'}提交中... ({progress}/{total})",
            )

        await AnalysisProgressTracker.update(
            project_id,
            step="fetching_git_log",
            progress=0,
            total=max_commits,
            message="正在获取 git 日志...",
        )

        commits = await scanner.get_commit_list(
            branch=branch,
            max_count=max_commits,
            since=since,
            after_sha=after_sha,
            progress_callback=_on_progress,
        )

        await AnalysisProgressTracker.update(
            project_id,
            step="saving_commits",
            progress=0,
            total=len(commits),
            message=f"正在保存 {len(commits)} 条提交到数据库...",
        )

        async with AsyncSessionLocal() as session:
            commit_svc = CommitService(session)
            saved = await commit_svc.save_commits(project_id, commits, progress_callback=_on_progress)

            if commits:
                from sqlalchemy import select
                from models.project_repo import ProjectRepo
                project_result = await session.execute(
                    select(ProjectRepo).where(ProjectRepo.id == project_id)
                )
                project = project_result.scalar_one_or_none()
                if project:
                    project.last_analyzed_sha = commits[0].hash
                    project.total_commits += saved
                    await session.commit()

        await AnalysisProgressTracker.complete(
            project_id,
            result={"scanned": len(commits), "saved": saved},
        )
        logger.info("Project %s: scan completed, scanned=%d saved=%d", project_id, len(commits), saved)

    except Exception as exc:
        logger.exception("Scan failed for project %s: %s", project_id, exc)
        await AnalysisProgressTracker.fail(project_id, str(exc))


@router.get("/commits")
async def list_commits(
    project_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    risk_level: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.list_commits(project_id, page, page_size, risk_level)


@router.get("/commits/{commit_hash}")
async def get_commit(project_id: int, commit_hash: str, db: AsyncSession = Depends(get_db)):
    svc = CommitService(db)
    commit = await svc.get_commit(project_id, commit_hash)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    findings = await svc.get_commit_findings(commit.id)
    return {
        "commit_hash": commit.commit_hash,
        "parent_hash": commit.parent_hash,
        "author_name": commit.author_name,
        "author_email": commit.author_email,
        "message": commit.message,
        "commit_ts": commit.commit_ts,
        "additions": commit.additions,
        "deletions": commit.deletions,
        "changed_files": commit.changed_files,
        "diff_content": commit.diff_content,
        "summary": commit.summary,
        "risk_level": commit.risk_level,
        "ai_model": commit.ai_model,
        "status": commit.status,
        "findings": [
            {
                "id": f.id,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "severity": f.severity,
                "category": f.category,
                "description": f.description,
                "suggestion": f.suggestion,
                "confidence": f.confidence,
                "evidence": f.evidence,
                "reasoning": f.reasoning,
            }
            for f in findings
        ],
    }


@router.get("/findings")
async def list_findings(
    project_id: int,
    severity: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_project_findings(project_id, severity, page)


@router.get("/stats")
async def project_stats(project_id: int, db: AsyncSession = Depends(get_db)):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_project_stats(project_id)


@router.get("/contributors")
async def contributor_analysis(project_id: int, db: AsyncSession = Depends(get_db)):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_contributor_analysis(project_id)


@router.get("/contributors/{author_email:path}")
async def contributor_detail(project_id: int, author_email: str, db: AsyncSession = Depends(get_db)):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_contributor_detail(project_id, author_email)
