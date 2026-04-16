from fastapi import APIRouter, Depends, Header, HTTPException, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import get_db
from repositories import ReviewRepository
from webhooks.verifier import WebhookVerifier
from webhooks.parser import WebhookParser
from webhooks.rate_limiter import RateLimiter
from services.review_service import run_review
from tasks import get_celery_task

router = APIRouter(prefix="/webhook", tags=["webhooks"])


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> dict:
    payload_bytes = await request.body()
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing webhook signature")
    if not WebhookVerifier.verify_github(
        payload_bytes, x_hub_signature_256, settings.github_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    parsed = WebhookParser.parse_github(payload)

    action = parsed.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return {"message": "Event ignored", "action": action}

    allowed, msg = RateLimiter.check_pr_size(parsed.get("changed_files", 0))
    if not allowed:
        # Still create a review record but mark as skipped
        review = await ReviewRepository(db).create(
            platform="github",
            repo_id=parsed["repo_id"],
            pr_number=parsed["pr_number"],
            pr_title=parsed.get("pr_title"),
            pr_author=parsed.get("pr_author"),
            head_sha=parsed.get("head_sha"),
            status="skipped",
            trigger_type=f"pull_request.{action}",
        )
        return {"message": msg, "review_id": review.id}

    review = await ReviewRepository(db).create(
        platform="github",
        repo_id=parsed["repo_id"],
        pr_number=parsed["pr_number"],
        pr_title=parsed.get("pr_title"),
        pr_author=parsed.get("pr_author"),
        head_sha=parsed.get("head_sha"),
        status="pending",
        trigger_type=f"pull_request.{action}",
    )

    _dispatch_review(background_tasks, review.id)
    return {"message": "Review queued", "review_id": review.id}


def _dispatch_review(background_tasks: BackgroundTasks, review_id: int) -> None:
    """优先使用 Celery，失败则回退到 FastAPI BackgroundTasks。"""
    try:
        task = get_celery_task()
        task.delay(review_id)
    except Exception as exc:
        # Fallback for environments without Celery/Redis available
        import logging
        logging.getLogger(__name__).warning(
            f"Celery dispatch failed ({exc}), falling back to BackgroundTasks"
        )
        background_tasks.add_task(run_review, review_id)


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_gitlab_token: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not WebhookVerifier.verify_gitlab(
        x_gitlab_token, settings.gitlab_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    payload = await request.json()
    parsed = WebhookParser.parse_gitlab(payload)

    action = parsed.get("action")
    if action not in ("open", "update", "reopen"):
        return {"message": "Event ignored", "action": action}

    allowed, msg = RateLimiter.check_pr_size(parsed.get("changed_files", 0))
    if not allowed:
        review = await ReviewRepository(db).create(
            platform="gitlab",
            repo_id=parsed["repo_id"],
            pr_number=parsed["pr_number"],
            pr_title=parsed.get("pr_title"),
            pr_author=str(parsed.get("pr_author")),
            head_sha=parsed.get("head_sha"),
            status="skipped",
            trigger_type=f"merge_request.{action}",
        )
        return {"message": msg, "review_id": review.id}

    review = await ReviewRepository(db).create(
        platform="gitlab",
        repo_id=parsed["repo_id"],
        pr_number=parsed["pr_number"],
        pr_title=parsed.get("pr_title"),
        pr_author=str(parsed.get("pr_author")),
        head_sha=parsed.get("head_sha"),
        status="pending",
        trigger_type=f"merge_request.{action}",
    )

    _dispatch_review(background_tasks, review.id)
    return {"message": "Review queued", "review_id": review.id}
