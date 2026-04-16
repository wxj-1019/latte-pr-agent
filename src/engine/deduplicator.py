from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ReviewFinding


class CommentDeduplicator:
    """基于 review_id 和文件路径+行号的评论去重器"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def should_comment(
        self, review_id: int, file_path: str, line_number: int
    ) -> bool:
        """若同一 review 周期内已针对相同位置发布过评论，跳过"""
        result = await self.session.execute(
            select(ReviewFinding).where(
                ReviewFinding.review_id == review_id,
                ReviewFinding.file_path == file_path,
                ReviewFinding.line_number == line_number,
            )
        )
        existing = result.scalar_one_or_none()
        return existing is None
