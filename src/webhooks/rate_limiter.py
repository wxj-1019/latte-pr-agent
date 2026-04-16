from typing import Tuple


class RateLimiter:
    """超大 PR 熔断与基础限流逻辑"""

    OVERSIZE_THRESHOLD = {
        "max_files": 500,
        "max_diff_mb": 50,
    }

    @classmethod
    def check_pr_size(cls, changed_files: int, diff_size_mb: float = 0) -> Tuple[bool, str]:
        if changed_files > cls.OVERSIZE_THRESHOLD["max_files"]:
            return (
                False,
                f"PR 文件数超过 {cls.OVERSIZE_THRESHOLD['max_files']}，仅执行静态扫描，请联系管理员处理",
            )
        if diff_size_mb > cls.OVERSIZE_THRESHOLD["max_diff_mb"]:
            return (
                False,
                f"PR diff 大小超过 {cls.OVERSIZE_THRESHOLD['max_diff_mb']}MB，仅执行静态扫描，请联系管理员处理",
            )
        return True, ""
