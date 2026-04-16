from abc import ABC, abstractmethod
from typing import Optional


class GitProvider(ABC):
    """统一 Git 平台接口，支持发布评论、行内建议、设置状态检查、获取 diff 内容。"""

    @abstractmethod
    async def publish_review_comment(self, file: str, line: int, comment: str) -> None:
        """发布行级审查评论"""
        pass

    @abstractmethod
    async def publish_inline_suggestion(
        self, file: str, line: int, suggestion: str
    ) -> None:
        """发布可直接应用的代码建议"""
        pass

    @abstractmethod
    async def set_status_check(
        self, status: str, description: str, context: str = "ai-code-review"
    ) -> None:
        """设置状态检查，status 应为 pending/success/failure"""
        pass

    @abstractmethod
    async def get_diff_content(self) -> str:
        """获取 PR/MR 的 diff 内容"""
        pass

    @abstractmethod
    async def get_pr_info(self) -> dict:
        """获取 PR/MR 的基础信息"""
        pass
