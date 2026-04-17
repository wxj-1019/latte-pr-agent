import logging
import re
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    """Inject request_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()  # type: ignore[attr-defined]
        return True


class SensitiveDataFilter(logging.Filter):
    """Redact sensitive tokens, API keys, and connection URLs from log messages."""

    _PATTERNS = [
        # Database / Redis URLs with credentials
        (r"(postgresql\+asyncpg://|postgresql://|redis://)[^\s'\"]+", r"\1***"),
        # API keys (OpenAI, DeepSeek, Anthropic, Qwen)
        (r"\b(sk-[a-zA-Z0-9]{20,})\b", r"***"),
        (
            r"\b([a-zA-Z0-9_-]*(?:api[_-]?key|token|secret|password)[a-zA-Z0-9_-]*)\s*[=:]\s*[^\s&'\"]+",
            r"\1=***",
        ),
        # GitHub personal access token
        (r"\b(ghp_[a-zA-Z0-9]{36})\b", r"***"),
        # GitLab personal access token
        (r"\b(glpat-[a-zA-Z0-9\-]{20,})\b", r"***"),
        # Generic Bearer/Token auth headers
        (r"(Authorization[\s:=]+(?:[Bb]earer\s+|[Tt]oken\s+))[^\s'\"]+", r"\1***"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if not isinstance(record.msg, str):
            return True
        msg = record.msg
        for pattern, repl in self._PATTERNS:
            msg = re.sub(pattern, repl, msg, flags=re.IGNORECASE)
        record.msg = msg
        # Prevent double-interpolation by downstream formatters
        if record.args:
            try:
                msg = msg % record.args
            except (TypeError, ValueError):
                pass
            else:
                record.msg = msg
                record.args = ()
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logger with consistent formatting and security filters."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [req:%(request_id)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # If no handlers exist (e.g. in production), add our own.
    # If handlers already exist (e.g. pytest caplog, uvicorn), augment them.
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.addFilter(RequestIdFilter())
        handler.addFilter(SensitiveDataFilter())
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)
            if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
                handler.addFilter(RequestIdFilter())
            if not any(isinstance(f, SensitiveDataFilter) for f in handler.filters):
                handler.addFilter(SensitiveDataFilter())
