"""
时区处理工具
统一使用北京时间 (UTC+8) 进行存储和处理。
所有用于数据库存储的 datetime 均为 naive datetime（逻辑上表示北京时间）。
"""

from datetime import datetime, timezone, timedelta
from typing import Optional


# 北京时间时区 (UTC+8)
BEIJING_TIMEZONE = timezone(timedelta(hours=8))


def _as_naive_beijing(dt: datetime) -> datetime:
    """将任意 datetime 转换为 naive 北京时间（去掉 tzinfo）。"""
    if dt.tzinfo is None:
        # 假设已经是北京时间（存储约定）
        return dt
    return dt.astimezone(BEIJING_TIMEZONE).replace(tzinfo=None)


def beijing_now() -> datetime:
    """
    获取当前北京时间（naive datetime，用于数据库兼容）

    Returns:
        datetime: 当前北京时间（不带时区信息）
    """
    return datetime.now(BEIJING_TIMEZONE).replace(tzinfo=None)


def utc_to_beijing(utc_dt: datetime) -> datetime:
    """
    将 UTC 时间转换为北京时间（naive）

    Args:
        utc_dt: UTC 时间（可以带时区或不带时区）

    Returns:
        datetime: 北京时间（naive）
    """
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(BEIJING_TIMEZONE).replace(tzinfo=None)


def beijing_to_utc(beijing_dt: datetime) -> datetime:
    """
    将北京时间转换为 UTC 时间（naive）

    Args:
        beijing_dt: 北京时间（可以带时区或不带时区）

    Returns:
        datetime: UTC 时间（naive）
    """
    if beijing_dt.tzinfo is None:
        beijing_dt = beijing_dt.replace(tzinfo=BEIJING_TIMEZONE)
    return beijing_dt.astimezone(timezone.utc).replace(tzinfo=None)


def format_beijing_time(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化时间为北京时间的字符串

    Args:
        dt: 时间对象
        format_str: 格式化字符串

    Returns:
        str: 格式化后的北京时间字符串
    """
    dt = _as_naive_beijing(dt)
    return dt.strftime(format_str)


def parse_beijing_time(time_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    解析字符串为北京时间（naive）

    Args:
        time_str: 时间字符串
        format_str: 格式化字符串

    Returns:
        datetime: 北京时间（naive）
    """
    naive_dt = datetime.strptime(time_str, format_str)
    return naive_dt


def format_iso_beijing(dt: Optional[datetime]) -> Optional[str]:
    """
    将 datetime 格式化为带北京时区偏移的 ISO 8601 字符串（供前端正确解析）。
    """
    if dt is None:
        return None
    return _as_naive_beijing(dt).replace(tzinfo=BEIJING_TIMEZONE).isoformat()


def get_beijing_date() -> str:
    """
    获取当前北京日期 (YYYY-MM-DD)

    Returns:
        str: 当前北京日期
    """
    return beijing_now().strftime("%Y-%m-%d")


def get_beijing_datetime() -> str:
    """
    获取当前北京日期时间 (YYYY-MM-DD HH:MM:SS)

    Returns:
        str: 当前北京日期时间
    """
    return beijing_now().strftime("%Y-%m-%d %H:%M:%S")


def is_same_day_in_beijing(dt1: datetime, dt2: datetime) -> bool:
    """
    判断两个时间在北京时区下是否为同一天

    Args:
        dt1: 第一个时间
        dt2: 第二个时间

    Returns:
        bool: 是否为同一天
    """
    return _as_naive_beijing(dt1).date() == _as_naive_beijing(dt2).date()


def get_beijing_start_of_day(dt: Optional[datetime] = None) -> datetime:
    """
    获取北京时间的当天开始时间（00:00:00）

    Args:
        dt: 参考时间，默认为当前时间

    Returns:
        datetime: 当天开始时间（naive 北京时间）
    """
    dt = beijing_now() if dt is None else _as_naive_beijing(dt)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def get_beijing_end_of_day(dt: Optional[datetime] = None) -> datetime:
    """
    获取北京时间的当天结束时间（23:59:59.999999）

    Args:
        dt: 参考时间，默认为当前时间

    Returns:
        datetime: 当天结束时间（naive 北京时间）
    """
    dt = beijing_now() if dt is None else _as_naive_beijing(dt)
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
