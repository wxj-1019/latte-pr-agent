import pytest

from config.project_config import ReviewConfig, CustomRule
from engine.rule_engine import RuleEngine


def test_rule_engine_ignore_patterns():
    config = ReviewConfig(ignore_patterns=["*.test.py", "tests/**/*", "*.md"])
    engine = RuleEngine(config)
    files = ["src/app.py", "src/app.test.py", "tests/test_app.py", "README.md"]
    filtered = engine.filter_ignored_files(files)
    assert filtered == ["src/app.py"]


def test_rule_engine_critical_path():
    config = ReviewConfig(critical_paths=["src/core/", "src/payment/"])
    engine = RuleEngine(config)
    findings = engine.analyze(
        ["src/core/utils.py", "src/app.py"],
        diff_content="",
    )
    assert len(findings) == 1
    assert findings[0]["file"] == "src/core/utils.py"
    assert findings[0]["rule_id"] == "critical_path"


def test_rule_engine_forbidden_regex():
    config = ReviewConfig(
        custom_rules=[
            CustomRule(
                name="No Direct DB Call in Controller",
                pattern="controllers/*.py",
                forbidden=r"from models import.*raw_sql",
                message="控制器层禁止直接调用数据库",
                severity="high",
            )
        ]
    )
    engine = RuleEngine(config)
    diff = (
        "diff --git a/controllers/user.py b/controllers/user.py\n"
        "--- a/controllers/user.py\n+++ b/controllers/user.py\n"
        "@@ -10 +10 @@\n"
        "-from services import user_service\n+from models import db_raw_sql\n"
    )
    findings = engine.analyze(["controllers/user.py"], diff)
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert "控制器层禁止直接调用数据库" in findings[0]["description"]
    assert findings[0]["rule_id"] == "No Direct DB Call in Controller"


def test_rule_engine_forbidden_regex_on_added_lines():
    config = ReviewConfig(
        custom_rules=[
            CustomRule(
                name="Sensitive Data Logging",
                pattern="*.py",
                forbidden=r"logger\.(info|debug).*(password|token|secret)",
                message="禁止在日志中输出敏感信息",
                severity="critical",
            )
        ]
    )
    engine = RuleEngine(config)
    diff = (
        "diff --git a/src/auth.py b/src/auth.py\n"
        "--- a/src/auth.py\n+++ b/src/auth.py\n"
        "@@ -20 +20 @@\n"
        "-pass\n+logger.info(f\"user token: {token}\")\n"
    )
    findings = engine.analyze(["src/auth.py"], diff)
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"


def test_rule_engine_no_match_when_pattern_mismatched():
    config = ReviewConfig(
        custom_rules=[
            CustomRule(
                name="API Version Compatibility",
                pattern="api/v\\d+/.*\\.py",
                check="backward_compatible",
                message="API 变更必须保持向后兼容",
                severity="critical",
            )
        ]
    )
    engine = RuleEngine(config)
    findings = engine.analyze(["src/app.py"], "")
    assert len(findings) == 0


def test_rule_engine_ignored_files_not_checked():
    config = ReviewConfig(
        ignore_patterns=["tests/**/*"],
        custom_rules=[
            CustomRule(
                name="No print in production",
                pattern="*.py",
                forbidden=r"print\(",
                message="禁止直接 print",
                severity="warning",
            )
        ],
    )
    engine = RuleEngine(config)
    diff = (
        "diff --git a/tests/test_app.py b/tests/test_app.py\n"
        "--- a/tests/test_app.py\n+++ b/tests/test_app.py\n"
        "@@ -1 +1 @@\n"
        "-pass\n+print('hello')\n"
    )
    findings = engine.analyze(["tests/test_app.py"], diff)
    assert len(findings) == 0
