import asyncio
import hashlib
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from engine import ReviewEngine, ReviewCache
from llm import ResilientReviewRouter
from models import get_db, Review, ReviewFinding
from rate_limit import limiter
from repositories import ReviewRepository, FindingRepository
from utils.timezone import format_iso_beijing

logger = logging.getLogger(__name__)

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
        raise HTTPException(status_code=400, detail=f"状态参数无效，可选值: {', '.join(VALID_STATUSES)}")
    if risk and risk not in VALID_RISKS:
        raise HTTPException(status_code=400, detail=f"风险等级参数无效，可选值: {', '.join(VALID_RISKS)}")

    safe_repo = None
    if repo:
        safe_repo = "".join(c for c in repo if c.isalnum() or c in "/-._")
        if len(safe_repo) > MAX_REPO_FILTER_LEN:
            raise HTTPException(status_code=400, detail=f"仓库过滤字符串过长（最大 {MAX_REPO_FILTER_LEN} 字符）")
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
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 5
        while True:
            await asyncio.sleep(3)
            try:
                result = await db.execute(select(Review.id, Review.status))
                current = {row[0]: row[1] for row in result.all()}
                consecutive_errors = 0
            except Exception:
                consecutive_errors += 1
                logger.warning("SSE: DB query failed (%d/%d)", consecutive_errors, MAX_CONSECUTIVE_ERRORS, exc_info=True)
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error("SSE: too many consecutive DB errors, shutting down stream")
                    break
                await asyncio.sleep(10)
                continue
            updates = []
            for rid, status in current.items():
                if not first_loop and known.get(rid) != status:
                    try:
                        cnt_result = await db.execute(
                            select(func.count()).select_from(ReviewFinding).where(ReviewFinding.review_id == rid)
                        )
                        findings_count = cnt_result.scalar() or 0
                    except Exception:
                        findings_count = 0
                    updates.append({
                        "review_id": rid,
                        "status": status,
                        "timestamp": format_iso_beijing(datetime.now(timezone.utc)),
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
        raise HTTPException(status_code=404, detail="审查记录不存在")
    return _serialize_review(review)


@router.get("/{review_id}/findings")
async def get_review_findings(review_id: int, db: AsyncSession = Depends(get_db)):
    finding_repo = FindingRepository(db)
    findings = await finding_repo.get_by_review(review_id)
    return [_serialize_finding(f) for f in findings]


class AnalyzeRequest(BaseModel):
    filename: str
    content: str
    language: str = "python"
    repo_id: str = "direct/default"


def _build_single_file_diff(filename: str, content: str) -> str:
    safe_filename = filename.replace("\n", "").replace("\r", "")
    lines = content.splitlines()
    body = "".join(f"+{line}\n" for line in lines)
    content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:7]
    return (
        f"diff --git a/{safe_filename} b/{safe_filename}\n"
        f"new file mode 100644\n"
        f"index 0000000..{content_hash}\n"
        f"--- /dev/null\n"
        f"+++ b/{safe_filename}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
        f"{body}"
    )


@router.post("/analyze")
@limiter.limit("10/minute")
async def analyze_code(request: Request, req: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    review_repo = ReviewRepository(db)

    # Sanitize filename to prevent diff injection and path traversal
    import os
    safe_filename = os.path.basename(req.filename.replace("\n", "").replace("\r", ""))
    if not safe_filename or safe_filename in (".", ".."):
        safe_filename = "untitled.txt"

    # Generate synthetic identifiers with timestamp to avoid unique-constraint collisions on re-analyze
    ts = str(int(time.time()))
    content_hash = hashlib.sha256(req.content.encode("utf-8")).hexdigest()
    # head_sha is capped at 40 chars in the DB schema
    synthetic_sha = f"{content_hash[:32]}-{ts[-7:]}"
    pr_number = -(abs(hash(f"{req.content}:{ts}")) % (10**9))

    lines_count = len(req.content.splitlines())
    diff_stats = {safe_filename: {"additions": lines_count, "deletions": 0, "changes": lines_count}}

    # Create synthetic review and mark running in a single transaction
    async with db.begin():
        review = await review_repo.create(
            platform="direct",
            repo_id=req.repo_id,
            pr_number=pr_number,
            head_sha=synthetic_sha,
            pr_title=f"直接分析: {safe_filename}",
            status="pending",
            diff_stats=diff_stats,
        )
        review_id = review.id
        await review_repo.update_status(review_id, "running")

    diff_content = _build_single_file_diff(safe_filename, req.content)
    changed_files = [safe_filename]

    # Optional local repo path for static analysis / config
    repo_path = None
    repos_base = os.getenv("REPOS_BASE_PATH", "")
    if repos_base and not req.repo_id.startswith("direct/"):
        candidate = os.path.join(repos_base, req.repo_id.replace("/", "_"))
        if os.path.isdir(candidate):
            repo_path = candidate

    # If no local repo, write to a temporary directory so Semgrep can still run
    tmpdir = None
    if repo_path is None:
        tmpdir = tempfile.TemporaryDirectory()
        repo_path = tmpdir.name
        file_path = os.path.join(repo_path, safe_filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(req.content)

    try:
        # Build router & engine
        llm_router = ResilientReviewRouter(config={
            "primary_model": "deepseek-chat",
            "enable_reasoner_review": getattr(settings, "enable_reasoner_review", False),
            "fallback_chain": ["deepseek-reasoner", "claude-3-5-sonnet"],
        })
        try:
            cache = ReviewCache()
        except Exception:
            logger.warning("Redis unavailable, running analysis without cache")
            cache = None
        engine = ReviewEngine(
            session=db,
            router=llm_router,
            cache=cache,
            prompt_version="v1",
            enable_static_analysis=True,
            repo_id=req.repo_id,
            project_config=None,
        )

        async with db.begin():
            result = await engine.run(
                review_id=review_id,
                pr_diff=diff_content,
                pr_size_tokens=len(req.content) // 2,
                repo_path=repo_path,
                changed_files=changed_files,
            )

        # Compute quality gate risk level for response
        from feedback.quality_gate import QualityGate
        gate = QualityGate(result.get("issues", []), None)
        gate_result = gate.assess()
        risk_level = gate_result["risk_level"]

        findings = await FindingRepository(db).get_by_review(review_id)
        return {
            "review_id": review_id,
            "status": "completed",
            "summary": result.get("summary", ""),
            "risk_level": risk_level,
            "findings": [_serialize_finding(f) for f in findings],
        }
    except Exception as exc:
        try:
            async with db.begin():
                await review_repo.update_status(review_id, "failed")
        except Exception:
            logger.exception("Failed to update failed status for review_id=%s", review_id)
        logger.exception("Analyze failed for review_id=%s", review_id)
        raise HTTPException(status_code=500, detail="分析失败，请稍后重试")
    finally:
        if tmpdir is not None:
            tmpdir.cleanup()
