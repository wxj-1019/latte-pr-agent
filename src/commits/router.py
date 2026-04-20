import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from commits.service import CommitService

router = APIRouter(prefix="/projects/{project_id}", tags=["commits"])
logger = logging.getLogger(__name__)


@router.post("/scan")
async def scan_commits(
    project_id: int,
    max_commits: int = Query(default=50, ge=1, le=500),
    since: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    svc = CommitService(db)
    project = await svc.get_project_or_raise(project_id)

    if not project.local_path or not os.path.isdir(os.path.join(project.local_path, ".git")):
        raise HTTPException(status_code=400, detail="Project repository not cloned yet")

    from commits.scanner import GitLogScanner
    scanner = GitLogScanner(project.local_path)
    commits = scanner.get_commit_list(
        branch=project.branch,
        max_count=max_commits,
        since=since,
        after_sha=project.last_analyzed_sha,
    )
    saved = await svc.save_commits(project_id, commits)

    if commits:
        project.last_analyzed_sha = commits[0].hash
        project.total_commits += saved
        await db.commit()

    return {"project_id": project_id, "scanned": len(commits), "saved": saved}


@router.get("/commits")
async def list_commits(
    project_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    risk_level: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    svc = CommitService(db)
    await svc.get_project_or_raise(project_id)
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
    await svc.get_project_or_raise(project_id)
    return await svc.get_project_findings(project_id, severity, page)


@router.get("/stats")
async def project_stats(project_id: int, db: AsyncSession = Depends(get_db)):
    svc = CommitService(db)
    await svc.get_project_or_raise(project_id)
    return await svc.get_project_stats(project_id)
