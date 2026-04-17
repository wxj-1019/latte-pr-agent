import asyncio
import logging
from typing import List, Optional

from providers import GitProvider
from repositories import FindingRepository
from feedback.formatter import FeedbackFormatter
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ReviewPublisher:
    """发布审查评论到 Git 平台"""

    def __init__(self, session: AsyncSession, provider: GitProvider):
        self.session = session
        self.provider = provider
        self.formatter = FeedbackFormatter()

    async def publish(self, review_id: int) -> None:
        findings = await FindingRepository(self.session).get_by_review(review_id)
        logger.info("Publishing review %s: %d findings", review_id, len(findings))
        semaphore = asyncio.Semaphore(5)
        success = 0

        async def _publish_one(finding) -> None:
            nonlocal success
            raw = finding.raw_response or {}
            formatted = self.formatter.format(
                {
                    "severity": finding.severity,
                    "description": finding.description,
                    "evidence": raw.get("evidence", ""),
                    "reasoning": raw.get("reasoning", ""),
                    "suggestion": finding.suggestion,
                }
            )
            async with semaphore:
                try:
                    await self.provider.publish_review_comment(
                        file=finding.file_path,
                        line=finding.line_number or 1,
                        comment=formatted,
                    )
                    success += 1
                except Exception:
                    logger.exception(
                        "Failed to publish comment for finding %s (%s:%s)",
                        finding.id, finding.file_path, finding.line_number,
                    )

        await asyncio.gather(*[_publish_one(f) for f in findings], return_exceptions=True)
        logger.info("Review %s: published %d/%d comments", review_id, success, len(findings))

    async def set_status(self, status: str, description: str) -> None:
        logger.info("Setting status check: status=%s description=%s", status, description)
        await self.provider.set_status_check(status, description)
