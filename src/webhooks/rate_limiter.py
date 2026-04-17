import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """超大 PR 熔断与基础限流逻辑"""

    OVERSIZE_THRESHOLD = {
        "max_files": 500,
        "max_diff_mb": 50,
    }

    @classmethod
    def check_pr_size(cls, changed_files: int, diff_content: str = "") -> Tuple[bool, str]:
        diff_size_mb = len(diff_content.encode("utf-8")) / (1024 * 1024) if diff_content else 0

        if changed_files > cls.OVERSIZE_THRESHOLD["max_files"]:
            logger.warning(
                "PR size limit exceeded: changed_files=%d (max=%d)",
                changed_files, cls.OVERSIZE_THRESHOLD["max_files"]
            )
            return (
                False,
                f"PR 文件数超过 {cls.OVERSIZE_THRESHOLD['max_files']}，仅执行静态扫描，请联系管理员处理",
            )
        if diff_size_mb > cls.OVERSIZE_THRESHOLD["max_diff_mb"]:
            logger.warning(
                "PR size limit exceeded: diff_size_mb=%.2f (max=%d)",
                diff_size_mb, cls.OVERSIZE_THRESHOLD["max_diff_mb"]
            )
            return (
                False,
                f"PR diff 大小超过 {cls.OVERSIZE_THRESHOLD['max_diff_mb']}MB，仅执行静态扫描，请联系管理员处理",
            )
        return True, ""
