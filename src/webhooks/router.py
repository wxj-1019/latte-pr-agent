from fastapi import APIRouter, Depends, Header, HTTPException, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import get_db
from repositories import ReviewRepository
from webhooks.verifier import WebhookVerifier
from webhooks.parser import WebhookParser
from webhooks.rate_limiter import RateLimiter
from services.review_service import run_review

router = APIRouter(prefix="/webhook", tags=["webhooks"])


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> dict:
    payload_bytes = await request.body()
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

    background_tasks.add_task(run_review, review.id)
    return {"message": "Review queued", "review_id": review.id}


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

    background_tasks.add_task(run_review, review.id)
    return {"message": "Review queued", "review_id": review.id}
