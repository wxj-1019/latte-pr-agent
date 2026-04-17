"""
时区处理工具
统一使用北京时间 (UTC+8)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional


# 北京时间时区 (UTC+8)
BEIJING_TIMEZONE = timezone(timedelta(hours=8))


def beijing_now() -> datetime:
    """
    获取当前北京时间

    Returns:
        datetime: 当前北京时间（带时区信息）
    """
    return datetime.now(BEIJING_TIMEZONE)


def utc_to_beijing(utc_dt: datetime) -> datetime:
    """
    将UTC时间转换为北京时间

    Args:
        utc_dt: UTC时间（可以带时区或不带时区）

    Returns:
        datetime: 北京时间（带时区信息）
    """
    if utc_dt.tzinfo is None:
        # 如果输入时间没有时区信息，假设为UTC
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    # 转换为北京时间
    return utc_dt.astimezone(BEIJING_TIMEZONE)


def beijing_to_utc(beijing_dt: datetime) -> datetime:
    """
    将北京时间转换为UTC时间

    Args:
        beijing_dt: 北京时间（可以带时区或不带时区）

    Returns:
        datetime: UTC时间（带时区信息）
    """
    if beijing_dt.tzinfo is None:
        # 如果输入时间没有时区信息，假设为北京时间
        beijing_dt = beijing_dt.replace(tzinfo=BEIJING_TIMEZONE)

    # 转换为UTC
    return beijing_dt.astimezone(timezone.utc)


def format_beijing_time(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化时间为北京时间的字符串

    Args:
        dt: 时间对象
        format_str: 格式化字符串

    Returns:
        str: 格式化后的北京时间字符串
    """
    if dt.tzinfo is None:
        # 如果没有时区信息，假设为UTC并转换为北京时间
        dt = utc_to_beijing(dt)
    else:
        # 有时区信息，转换为北京时间
        dt = dt.astimezone(BEIJING_TIMEZONE)

    return dt.strftime(format_str)


def parse_beijing_time(time_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    解析字符串为北京时间

    Args:
        time_str: 时间字符串
        format_str: 格式化字符串

    Returns:
        datetime: 北京时间（带时区信息）
    """
    # 解析为naive datetime
    naive_dt = datetime.strptime(time_str, format_str)
    # 添加北京时区
    return naive_dt.replace(tzinfo=BEIJING_TIMEZONE)


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
    dt1_beijing = utc_to_beijing(dt1) if dt1.tzinfo is None else dt1.astimezone(BEIJING_TIMEZONE)
    dt2_beijing = utc_to_beijing(dt2) if dt2.tzinfo is None else dt2.astimezone(BEIJING_TIMEZONE)

    return dt1_beijing.date() == dt2_beijing.date()


def get_beijing_start_of_day(dt: Optional[datetime] = None) -> datetime:
    """
    获取北京时间的当天开始时间（00:00:00）

    Args:
        dt: 参考时间，默认为当前时间

    Returns:
        datetime: 当天开始时间（带北京时区）
    """
    if dt is None:
        dt = beijing_now()
    else:
        dt = utc_to_beijing(dt) if dt.tzinfo is None else dt.astimezone(BEIJING_TIMEZONE)

    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def get_beijing_end_of_day(dt: Optional[datetime] = None) -> datetime:
    """
    获取北京时间的当天结束时间（23:59:59.999999）

    Args:
        dt: 参考时间，默认为当前时间

    Returns:
        datetime: 当天结束时间（带北京时区）
    """
    if dt is None:
        dt = beijing_now()
    else:
        dt = utc_to_beijing(dt) if dt.tzinfo is None else dt.astimezone(BEIJING_TIMEZONE)

    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)