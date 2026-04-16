import logging
import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config import settings
from context.builder import PRDiff
from engine import ReviewEngine, ReviewCache
from llm import ResilientReviewRouter
from models import async_engine
from providers import GitProviderFactory
from repositories import ReviewRepository
from feedback.publisher import ReviewPublisher

logger = logging.getLogger(__name__)


async def run_review(review_id: int) -> None:
    """Background task: execute full review pipeline."""
    AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        review_repo = ReviewRepository(session)
        review = await review_repo.get_by_id(review_id)
        if not review:
            logger.warning(f"Review {review_id} not found, skipping background task")
            return

        await review_repo.update_status(review_id, "running")
        provider = None

        try:
            # Create provider to fetch diff
            if review.platform == "github":
                provider = GitProviderFactory.from_pr_info(
                    platform="github",
                    repo_id=review.repo_id,
                    pr_number=review.pr_number,
                    token=settings.github_token,
                )
            else:
                provider = GitProviderFactory.from_pr_info(
                    platform="gitlab",
                    repo_id=review.repo_id,
                    pr_number=review.pr_number,
                    token=settings.gitlab_token,
                    gitlab_url=settings.gitlab_url,
                )

            diff_content = await provider.get_diff_content()
            logger.info(f"Review {review_id}: fetched diff ({len(diff_content)} chars)")

            # Infer changed files from diff for static analysis
            pr_diff_obj = PRDiff(content=diff_content)
            changed_files = pr_diff_obj.get_changed_files()

            # Infer local repo path (if cloned locally)
            repos_base = os.getenv("REPOS_BASE_PATH", "")
            repo_path = None
            if repos_base:
                repo_path = os.path.join(repos_base, review.repo_id.replace("/", "_"))
                if not os.path.isdir(repo_path):
                    repo_path = None

            # Build resilient LLM router with fallback chain
            router = ResilientReviewRouter(config={
                "primary": "deepseek-chat",
                "enable_reasoner_review": settings.enable_reasoner_review,
                "fallback_chain": ["deepseek-reasoner", "claude-3-5-sonnet"],
            })

            # Build cache
            cache = ReviewCache()

            # Run engine with optional static analysis
            engine = ReviewEngine(session, router, cache, enable_static_analysis=True)
            result = await engine.run(
                review_id=review_id,
                pr_diff=diff_content,
                pr_size_tokens=len(diff_content) // 2,
                repo_path=repo_path,
                changed_files=changed_files,
            )

            # Publish feedback
            if provider:
                publisher = ReviewPublisher(session, provider)
                await publisher.publish(review_id)

                # Set status check
                risk_level = result.get("risk_level", "low")
                if result.get("degraded"):
                    await publisher.set_status("success", "Review degraded: static analysis only")
                elif risk_level == "high":
                    await publisher.set_status("failure", "Critical issues found")
                else:
                    await publisher.set_status("success", f"Review completed. Risk: {risk_level}")

            await review_repo.update_status(review_id, "completed")
            logger.info(f"Review {review_id}: completed successfully")
        except Exception as exc:
            logger.exception(f"Review {review_id}: failed with error: {exc}")
            await review_repo.update_status(review_id, "failed")
            # Try to notify PR with failure status if provider was created
            if provider:
                try:
                    publisher = ReviewPublisher(session, provider)
                    await publisher.set_status("failure", "AI review failed due to internal error")
                except Exception:
                    logger.exception(f"Review {review_id}: failed to publish error status")
            raise
