import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ReviewFinding

logger = logging.getLogger(__name__)


class CommentDeduplicator:
    """基于 review_id 和文件路径+行号的评论去重器"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._seen: set[tuple[int, str, int]] = set()
        self._preloaded: bool = False

    async def preload_existing(self, review_id: int) -> None:
        """批量加载 review 下已有的 finding，避免 N+1。"""
        result = await self.session.execute(
            select(ReviewFinding).where(ReviewFinding.review_id == review_id)
        )
        for finding in result.scalars().all():
            self._seen.add((finding.review_id, finding.file_path, finding.line_number))
        self._preloaded = True
        logger.debug("Preloaded %d existing findings for review %s", len(self._seen), review_id)

    async def should_comment(
        self, review_id: int, file_path: str, line_number: int
    ) -> bool:
        """若同一 review 周期内已针对相同位置发布过评论，跳过"""
        if self._preloaded:
            should = (review_id, file_path, line_number) not in self._seen
            if not should:
                logger.debug("Deduplicating: skipping duplicate at %s:%s", file_path, line_number)
            return should
        # fallback：未 preload 时保留原逻辑
        result = await self.session.execute(
            select(ReviewFinding).where(
                ReviewFinding.review_id == review_id,
                ReviewFinding.file_path == file_path,
                ReviewFinding.line_number == line_number,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            logger.debug("Deduplicating: skipping duplicate at %s:%s", file_path, line_number)
        return existing is None
