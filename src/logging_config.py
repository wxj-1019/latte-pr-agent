import json
import logging
import os
import re
import sys
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class SensitiveDataFilter(logging.Filter):
    _PATTERNS = [
        (r"(postgresql\+asyncpg://|postgresql://|redis://)[^\s'\"]+", r"\1***"),
        (r"\b(sk-[a-zA-Z0-9]{20,})\b", r"***"),
        (
            r"\b([a-zA-Z0-9_-]*(?:api[_-]?key|token|secret|password)[a-zA-Z0-9_-]*)\s*[=:]\s*[^\s&'\"]+",
            r"\1=***",
        ),
        (r"\b(ghp_[a-zA-Z0-9]{36})\b", r"***"),
        (r"\b(glpat-[a-zA-Z0-9\-]{20,})\b", r"***"),
        (r"(Authorization[\s:=]+(?:[Bb]earer\s+|[Tt]oken\s+))[^\s'\"]+", r"\1***"),
    ]

    def _redact(self, text: str) -> str:
        for pattern, repl in self._PATTERNS:
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if not isinstance(record.msg, str):
            return True
        record.msg = self._redact(record.msg)
        if record.args:
            safe_args = tuple(
                self._redact(a) if isinstance(a, str) else a for a in record.args
            )
            try:
                record.msg = record.msg % safe_args
            except (TypeError, ValueError):
                record.args = safe_args
            else:
                record.args = ()
        return True


class ColoredFormatter(logging.Formatter):
    _COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[1;35m",
    }
    _RESET = "\033[0m"
    _DIM = "\033[2m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelname, self._RESET)
        record.levelname_colored = f"{color}{record.levelname:8s}{self._RESET}"
        record.name_dimmed = f"{self._DIM}{record.name}{self._RESET}"
        return super().format(record)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "req_id": getattr(record, "request_id", ""),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exc_type"] = record.exc_info[0].__name__
            log_entry["exc_msg"] = str(record.exc_info[1])
        if hasattr(record, "http_method"):
            log_entry["method"] = record.http_method
        if hasattr(record, "http_path"):
            log_entry["path"] = record.http_path
        if hasattr(record, "http_status"):
            log_entry["status"] = record.http_status
        if hasattr(record, "http_duration_ms"):
            log_entry["duration_ms"] = round(record.http_duration_ms, 1)
        return json.dumps(log_entry, ensure_ascii=False)


_PLAIN_FMT = "%(asctime)s [%(levelname)-8s] [req:%(request_id)s] %(name)s: %(message)s"
_COLORED_FMT = "%(asctime)s [%(levelname_colored)s] [req:%(request_id)s] %(name_dimmed)s: %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_SHARED_FILTERS = [RequestIdFilter(), SensitiveDataFilter()]


def _configure_handler(handler: logging.Handler, log_format: str) -> None:
    for f in _SHARED_FILTERS:
        if not any(isinstance(x, type(f)) for x in handler.filters):
            handler.addFilter(f)
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    elif (
        hasattr(handler, "stream")
        and hasattr(handler.stream, "isatty")
        and handler.stream.isatty()
    ):
        handler.setFormatter(ColoredFormatter(fmt=_COLORED_FMT, datefmt=_DATE_FMT))
    else:
        handler.setFormatter(logging.Formatter(fmt=_PLAIN_FMT, datefmt=_DATE_FMT))


def setup_logging(
    log_level: str = "INFO",
    log_format: Optional[str] = None,
    log_file: Optional[str] = None,
) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    fmt = log_format or os.getenv("LOG_FORMAT", "text").lower()

    root = logging.getLogger()
    root.setLevel(level)

    for handler in root.handlers[:]:
        _configure_handler(handler, fmt)

    if not root.handlers:
        if log_file:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            handler: logging.Handler = RotatingFileHandler(
                str(path),
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
        else:
            handler = logging.StreamHandler(sys.stdout)
        _configure_handler(handler, fmt)
        root.addHandler(handler)

    for name in ("uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def setup_celery_logging(log_level: str = "INFO") -> None:
    setup_logging(log_level=log_level)


def log_request(
    method: str,
    path: str,
    status_code: int,
    duration: float,
    request_id: str = "",
) -> None:
    logger = logging.getLogger("latte.access")
    if not logger.handlers:
        logger.propagate = True
    record = logger.makeRecord(
        name="latte.access",
        level=logging.INFO,
        fn="",
        lno=0,
        msg="%s %s -> %s (%.1fms)",
        args=(method, path, status_code, duration * 1000),
        exc_info=None,
    )
    record.http_method = method
    record.http_path = path
    record.http_status = status_code
    record.http_duration_ms = duration * 1000
    record.request_id = request_id
    logger.handle(record)
