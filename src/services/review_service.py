from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from engine import ReviewEngine, ReviewCache
from llm import ReviewRouter
from models import async_engine
from providers import GitProviderFactory
from repositories import ReviewRepository
from feedback.publisher import ReviewPublisher


async def run_review(review_id: int) -> None:
    """Background task: execute full review pipeline."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        review_repo = ReviewRepository(session)
        review = await review_repo.get_by_id(review_id)
        if not review:
            return

        await review_repo.update_status(review_id, "running")

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

            # Build LLM router
            router = ReviewRouter(config={
                "primary_model": "deepseek-chat",
                "enable_reasoner_review": settings.enable_reasoner_review,
            })

            # Build cache
            cache = ReviewCache()

            # Run engine
            engine = ReviewEngine(session, router, cache)
            result = await engine.run(
                review_id=review_id,
                pr_diff=diff_content,
                pr_size_tokens=len(diff_content) // 2,
            )

            # Publish feedback
            publisher = ReviewPublisher(session, provider)
            await publisher.publish(review_id)

            # Set status check
            risk_level = result.get("risk_level", "low")
            if risk_level == "high":
                await publisher.set_status("failure", "Critical issues found")
            else:
                await publisher.set_status("success", f"Review completed. Risk: {risk_level}")

            await review_repo.update_status(review_id, "completed")
        except Exception:
            await review_repo.update_status(review_id, "failed")
            raise
