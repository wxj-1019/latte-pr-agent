"""Tests for logging configuration and security filters."""

import logging
import pytest

from logging_config import (
    SensitiveDataFilter,
    RequestIdFilter,
    setup_logging,
    request_id_var,
)


class TestSetupLogging:
    def test_setup_logging_applies_level(self):
        setup_logging("DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_setup_logging_info_blocks_debug(self, caplog):
        setup_logging("INFO")
        logger = logging.getLogger("test_info_blocks_debug")
        with caplog.at_level(logging.INFO):
            logger.debug("this should not appear")
            logger.info("this should appear")
        assert "this should not appear" not in caplog.text
        assert "this should appear" in caplog.text

    def test_setup_logging_warning_blocks_info(self, caplog):
        setup_logging("WARNING")
        logger = logging.getLogger("test_warning_blocks_info")
        with caplog.at_level(logging.WARNING):
            logger.info("this should not appear")
            logger.warning("this should appear")
        assert "this should not appear" not in caplog.text
        assert "this should appear" in caplog.text

    def test_invalid_level_defaults_to_info(self):
        setup_logging("INVALID")
        assert logging.getLogger().level == logging.INFO


class TestSensitiveDataFilter:
    @pytest.fixture
    def filter_instance(self):
        return SensitiveDataFilter()

    @pytest.fixture
    def make_record(self):
        def _make(msg: str, args: tuple = ()) -> logging.LogRecord:
            return logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg=msg, args=args, exc_info=None,
            )
        return _make

    def test_redacts_database_url(self, filter_instance, make_record):
        record = make_record("Connecting to postgresql+asyncpg://user:pass@db:5432/code_review")
        assert filter_instance.filter(record)
        assert "postgresql+asyncpg://***" in record.msg
        assert "user:pass" not in record.msg

    def test_redacts_redis_url(self, filter_instance, make_record):
        record = make_record("Broker redis://redis:secret@localhost:6379/0")
        assert filter_instance.filter(record)
        assert "redis://***" in record.msg
        assert "secret" not in record.msg

    def test_redacts_openai_api_key(self, filter_instance, make_record):
        record = make_record("Using key sk-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz")
        assert filter_instance.filter(record)
        assert "***" in record.msg
        assert "sk-abc" not in record.msg

    def test_redacts_github_token(self, filter_instance, make_record):
        record = make_record("Authorization: token ghp_abcdefghijklmnopqrstuvwxyz01")
        assert filter_instance.filter(record)
        assert "***" in record.msg
        assert "ghp_" not in record.msg

    def test_redacts_gitlab_token(self, filter_instance, make_record):
        record = make_record("Token glpat-abcdefghijklmnop1234")
        assert filter_instance.filter(record)
        assert "***" in record.msg
        assert "glpat-" not in record.msg

    def test_redacts_bearer_auth_header(self, filter_instance, make_record):
        record = make_record("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        assert filter_instance.filter(record)
        assert "***" in record.msg
        assert "eyJhbG" not in record.msg

    def test_preserves_normal_message(self, filter_instance, make_record):
        record = make_record("Review 123: completed successfully")
        assert filter_instance.filter(record)
        assert record.msg == "Review 123: completed successfully"


class TestRequestIdFilter:
    @pytest.fixture
    def filter_instance(self):
        return RequestIdFilter()

    @pytest.fixture
    def make_record(self):
        def _make(msg: str) -> logging.LogRecord:
            return logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg=msg, args=(), exc_info=None,
            )
        return _make

    def test_injects_request_id(self, filter_instance, make_record):
        token = request_id_var.set("req-abc-123")
        try:
            record = make_record("test message")
            assert filter_instance.filter(record)
            assert getattr(record, "request_id") == "req-abc-123"
        finally:
            request_id_var.reset(token)

    def test_defaults_to_empty_string(self, filter_instance, make_record):
        # Ensure no leftover context from previous tests
        record = make_record("test message")
        assert filter_instance.filter(record)
        assert getattr(record, "request_id") == ""
