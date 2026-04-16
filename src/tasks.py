import logging

from celery import Celery

from config import settings
from services.review_service import run_review

logger = logging.getLogger(__name__)

celery_app = Celery(
    "latte_pr_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes hard limit
    task_soft_time_limit=300,  # 5 minutes soft limit
)


@celery_app.task(bind=True, max_retries=2)
def run_review_task(self, review_id: int) -> None:
    """Celery task wrapper for run_review."""
    import asyncio
    try:
        asyncio.run(run_review(review_id))
    except Exception as exc:
        logger.exception(f"Celery task failed for review {review_id}: {exc}")
        raise self.retry(exc=exc, countdown=10)


def get_celery_task():
    """Return the Celery task function for dispatching."""
    return run_review_task
