import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db, Review, ReviewFinding
from repositories import ReviewRepository, FindingRepository
from utils.timezone import format_iso_beijing

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _serialize_review(review):
    return {
        "id": review.id,
        "org_id": review.org_id,
        "platform": review.platform,
        "repo_id": review.repo_id,
        "pr_number": review.pr_number,
        "pr_title": review.pr_title,
        "pr_author": review.pr_author,
        "base_branch": review.base_branch,
        "head_branch": review.head_branch,
        "head_sha": review.head_sha,
        "status": review.status,
        "risk_level": review.risk_level,
        "trigger_type": review.trigger_type,
        "review_mode": review.review_mode,
        "prompt_version": review.prompt_version,
        "diff_stats": review.diff_stats,
        "created_at": format_iso_beijing(review.created_at),
        "completed_at": format_iso_beijing(review.completed_at),
        "pr_files": [_serialize_pr_file(f) for f in (review.pr_files or [])],
    }


def _serialize_pr_file(pr_file):
    return {
        "id": pr_file.id,
        "review_id": pr_file.review_id,
        "file_path": pr_file.file_path,
        "change_type": pr_file.change_type,
        "additions": pr_file.additions,
        "deletions": pr_file.deletions,
        "diff_content": pr_file.diff_content,
    }


def _serialize_finding(finding):
    return {
        "id": finding.id,
        "review_id": finding.review_id,
        "file_path": finding.file_path,
        "line_number": finding.line_number,
        "category": finding.category,
        "severity": finding.severity,
        "description": finding.description,
        "suggestion": finding.suggestion,
        "confidence": float(finding.confidence) if finding.confidence is not None else None,
        "affected_files": finding.affected_files,
        "ai_model": finding.ai_model,
        "raw_response": finding.raw_response,
        "created_at": format_iso_beijing(finding.created_at),
    }


VALID_STATUSES = {"pending", "running", "completed", "failed", "skipped"}
VALID_RISKS = {"low", "medium", "high", "critical"}
MAX_REPO_FILTER_LEN = 100
DEFAULT_PAGE_SIZE = 20


@router.get("")
async def list_reviews(
    status: Optional[str] = None,
    repo: Optional[str] = None,
    risk: Optional[str] = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    db: AsyncSession = Depends(get_db),
):
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {', '.join(VALID_STATUSES)}")
    if risk and risk not in VALID_RISKS:
        raise HTTPException(status_code=400, detail=f"Invalid risk. Allowed: {', '.join(VALID_RISKS)}")

    safe_repo = None
    if repo:
        safe_repo = "".join(c for c in repo if c.isalnum() or c in "/-._")
        if len(safe_repo) > MAX_REPO_FILTER_LEN:
            raise HTTPException(status_code=400, detail=f"repo filter too long (max {MAX_REPO_FILTER_LEN})")
        if not safe_repo:
            safe_repo = None

    review_repo = ReviewRepository(db)
    total = await review_repo.count_all(status=status, repo_filter=safe_repo, risk=risk)
    offset = (max(1, page) - 1) * page_size
    reviews = await review_repo.list_all(
        status=status,
        repo_filter=safe_repo,
        risk=risk,
        limit=page_size,
        offset=offset,
    )
    data = [_serialize_review(r) for r in reviews]

    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/stream")
async def review_stream(db: AsyncSession = Depends(get_db)):
    async def event_generator():
        known: dict[int, str] = {}
        first_loop = True
        while True:
            await asyncio.sleep(3)
            result = await db.execute(select(Review.id, Review.status))
            current = {row[0]: row[1] for row in result.all()}
            updates = []
            for rid, status in current.items():
                if not first_loop and known.get(rid) != status:
                    # count findings for richer updates
                    cnt_result = await db.execute(
                        select(func.count()).select_from(ReviewFinding).where(ReviewFinding.review_id == rid)
                    )
                    findings_count = cnt_result.scalar() or 0
                    updates.append({
                        "review_id": rid,
                        "status": status,
                        "timestamp": format_iso_beijing(datetime.utcnow()),
                        "findings_count": findings_count,
                    })
            known = current
            first_loop = False
            for up in updates:
                yield f"data: {json.dumps(up)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{review_id}")
async def get_review(review_id: int, db: AsyncSession = Depends(get_db)):
    review_repo = ReviewRepository(db)
    review = await review_repo.get_by_id(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return _serialize_review(review)


@router.get("/{review_id}/findings")
async def get_review_findings(review_id: int, db: AsyncSession = Depends(get_db)):
    finding_repo = FindingRepository(db)
    findings = await finding_repo.get_by_review(review_id)
    return [_serialize_finding(f) for f in findings]
