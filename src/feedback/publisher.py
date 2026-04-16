from typing import List, Optional

from providers import GitProvider
from repositories import FindingRepository
from feedback.formatter import FeedbackFormatter
from sqlalchemy.ext.asyncio import AsyncSession


class ReviewPublisher:
    """发布审查评论到 Git 平台"""

    def __init__(self, session: AsyncSession, provider: GitProvider):
        self.session = session
        self.provider = provider
        self.formatter = FeedbackFormatter()

    async def publish(self, review_id: int) -> None:
        findings = await FindingRepository(self.session).get_by_review(review_id)
        for finding in findings:
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
            await self.provider.publish_review_comment(
                file=finding.file_path,
                line=finding.line_number or 1,
                comment=formatted,
            )

    async def set_status(self, status: str, description: str) -> None:
        await self.provider.set_status_check(status, description)
