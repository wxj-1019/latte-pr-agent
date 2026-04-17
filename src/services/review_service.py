import logging
import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config import settings
from config.project_config import ProjectConfigService
from context.builder import PRDiff
from engine import ReviewEngine, ReviewCache
from graph.builder import DependencyGraphBuilder
from llm import ResilientReviewRouter
from models import async_engine
from providers import GitProviderFactory
from repositories import ReviewRepository
from feedback.publisher import ReviewPublisher
from feedback.quality_gate import QualityGate
from prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


async def run_review(review_id: int) -> None:
    """Background task: execute full review pipeline."""
    AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        review_repo = ReviewRepository(session)
        review = await review_repo.get_by_id(review_id)
        if not review:
            logger.warning("Review %s not found, skipping background task", review_id)
            return

        provider = None

        try:
            async with session.begin():
                await review_repo.update_status(review_id, "running")
                # Create provider to fetch diff
                if review.platform == "github":
                    provider = GitProviderFactory.from_pr_info(
                        platform="github",
                        repo_id=review.repo_id,
                        pr_number=review.pr_number,
                        token=settings.github_token.get_secret_value(),
                    )
                else:
                    provider = GitProviderFactory.from_pr_info(
                        platform="gitlab",
                        repo_id=review.repo_id,
                        pr_number=review.pr_number,
                        token=settings.gitlab_token.get_secret_value(),
                        gitlab_url=settings.gitlab_url,
                    )

                diff_content = await provider.get_diff_content()
                logger.info("Review %s: fetched diff (%s chars)", review_id, len(diff_content))

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

                # Load and cache project config
                project_config = None
                if repo_path:
                    try:
                        config_service = ProjectConfigService(session)
                        project_config = await config_service.load_and_cache(
                            repo_path, review.platform, review.repo_id, org_id=review.org_id
                        )
                        logger.info("Review %s: project config loaded", review_id)
                    except Exception as exc:
                        logger.warning("Review %s: project config load failed: %s", review_id, exc, exc_info=True)

                # Incremental dependency graph update
                if repo_path:
                    try:
                        graph_builder = DependencyGraphBuilder(session)
                        await graph_builder.build(repo_path, review.repo_id, org_id=review.org_id)
                        logger.info("Review %s: dependency graph updated", review_id)
                    except Exception as exc:
                        logger.warning("Review %s: dependency graph build failed: %s", review_id, exc, exc_info=True)

                # Determine prompt version via A/B experiment registry
                prompt_registry = PromptRegistry(session)
                await prompt_registry.load_from_db()
                prompt_version = await prompt_registry.get_experiment_assignment(review.repo_id)

                # Build resilient LLM router with fallback chain
                router = ResilientReviewRouter(config={
                    "primary_model": "deepseek-chat",
                    "enable_reasoner_review": settings.enable_reasoner_review,
                    "fallback_chain": ["deepseek-reasoner", "claude-3-5-sonnet"],
                })

                # Build cache
                cache = ReviewCache()

                # Run engine with optional static analysis
                engine = ReviewEngine(
                    session, router, cache,
                    prompt_version=prompt_version,
                    enable_static_analysis=True,
                    repo_id=review.repo_id,
                    project_config=project_config,
                )
                result = await engine.run(
                    review_id=review_id,
                    pr_diff=diff_content,
                    pr_size_tokens=len(diff_content) // 2,
                    repo_path=repo_path,
                    changed_files=changed_files,
                )

                # Quality gate assessment (always compute risk level)
                gate = QualityGate(result.get("issues", []), project_config)
                gate_result = gate.assess()
                final_risk_level = gate_result["risk_level"]

                # Publish feedback
                if provider:
                    publisher = ReviewPublisher(session, provider)
                    await publisher.publish(review_id)

                    if result.get("degraded"):
                        await publisher.set_status("success", "Review degraded: static analysis only")
                    else:
                        await publisher.set_status(gate_result["status"], gate_result["description"])

                await review_repo.update_status(review_id, "completed", risk_level=final_risk_level if not result.get("degraded") else None)
            logger.info("Review %s: completed successfully", review_id)
        except Exception as exc:
            logger.exception("Review %s: failed with error: %s", review_id, exc)
            try:
                async with session.begin():
                    await review_repo.update_status(review_id, "failed")
            except Exception:
                logger.exception("Review %s: failed to update failed status", review_id)
            # Try to notify PR with failure status if provider was created
            if provider:
                try:
                    publisher = ReviewPublisher(session, provider)
                    await publisher.set_status("failure", "AI review failed due to internal error")
                except Exception:
                    logger.exception("Review %s: failed to publish error status", review_id)
            raise
