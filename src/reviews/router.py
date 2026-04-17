from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
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
MAX_REPO_FILTER_LEN = 100


@router.get("")
async def list_reviews(
    status: Optional[str] = None,
    repo: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    review_repo = ReviewRepository(db)
    reviews = await review_repo.list_all()
    data = [_serialize_review(r) for r in reviews]

    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {', '.join(VALID_STATUSES)}")
        data = [r for r in data if r["status"] == status]

    if repo:
        safe_repo = "".join(c for c in repo if c.isalnum() or c in "/-._")
        if len(safe_repo) > MAX_REPO_FILTER_LEN:
            raise HTTPException(status_code=400, detail=f"repo filter too long (max {MAX_REPO_FILTER_LEN})")
        if safe_repo:
            data = [r for r in data if safe_repo in r["repo_id"]]

    return data


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
