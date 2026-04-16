import pytest
from unittest.mock import AsyncMock, patch

from context.builder import PRDiff, ProjectContextBuilder, FunctionChange
from context.api_detector import APIDetector


def test_pr_diff_get_changed_files():
    diff = (
        "diff --git a/src/main.py b/src/main.py\n"
        "--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-old\n+new\n"
        "diff --git a/src/utils.py b/src/utils.py\n"
        "--- a/src/utils.py\n+++ b/src/utils.py\n@@ -2 +2 @@\n-bad\n+good\n"
    )
    pr_diff = PRDiff(content=diff)
    files = pr_diff.get_changed_files()
    assert files == ["src/main.py", "src/utils.py"]


def test_pr_diff_get_function_changes():
    diff = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n+++ b/src/app.py\n@@ -10 +10 @@\n-def old_func(x):\n+def new_func(x, y):\n"
    )
    pr_diff = PRDiff(content=diff)
    changes = pr_diff.get_function_changes()
    assert len(changes) == 2
    assert changes[0].function_name == "old_func"
    assert changes[1].function_name == "new_func"


@pytest.mark.asyncio
async def test_project_context_builder_basic():
    diff = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-import os\n+import sys\n"
        "@@ -10 +10 @@\n-def old_func(x):\n+def new_func(x, y):\n"
    )
    builder = ProjectContextBuilder()
    context = await builder.build_context(PRDiff(content=diff))

    assert "pr_diff" in context
    assert len(context["file_changes"]) == 1
    assert context["file_changes"][0]["file"] == "src/app.py"
    assert "dependency_graph" in context
    assert "api_contracts" in context
    assert context["api_contracts"]["breaking_count"] == 1
    assert context["similar_bugs"] == []
    assert context["cross_service_impact"] is None


@pytest.mark.asyncio
async def test_project_context_builder_no_api_change():
    diff = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n+++ b/src/app.py\n@@ -5 +5 @@\n-print('hello')\n+print('world')\n"
    )
    builder = ProjectContextBuilder()
    context = await builder.build_context(PRDiff(content=diff))
    assert context["api_contracts"]["breaking_count"] == 0
    assert context["api_contracts"]["api_changes"] == []


# ==================== Phase 2-3 新增测试 ====================

def test_function_change_signature_modified():
    add = FunctionChange("foo", "f.py", "x", is_add=True, is_remove=False)
    remove = FunctionChange("foo", "f.py", "x", is_add=False, is_remove=True)
    modify = FunctionChange("foo", "f.py", "x", is_add=True, is_remove=True)
    assert add.is_signature_modified() is False
    assert remove.is_signature_modified() is False
    assert modify.is_signature_modified() is True


def test_function_change_breaking():
    deleted = FunctionChange("foo", "f.py", "x", is_add=False, is_remove=True)
    added = FunctionChange("foo", "f.py", "x", is_add=True, is_remove=False)
    modified = FunctionChange("foo", "f.py", "x", is_add=True, is_remove=True)
    assert deleted.is_breaking() is True
    assert added.is_breaking() is False
    assert modified.is_breaking() is False


@pytest.mark.asyncio
async def test_project_context_builder_fallback_dependencies():
    diff = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-import os\n+import utils\n"
        "diff --git a/src/utils.py b/src/utils.py\n"
        "--- a/src/utils.py\n+++ b/src/utils.py\n@@ -1 +1 @@\n-pass\n+print(1)\n"
    )
    builder = ProjectContextBuilder()
    context = await builder.build_context(PRDiff(content=diff))
    dg = context["dependency_graph"]
    # app.py imports utils.py -> app.py downstream includes utils.py
    assert "utils" in dg["downstream"]["src/app.py"] or "src/utils.py" in dg["downstream"]["src/app.py"]
    # utils.py upstream includes app.py (reverse inference)
    assert "src/app.py" in dg["upstream"]["src/utils.py"]


def test_api_detector_detects_changes():
    before = b"def foo(x: int) -> str:\n    pass\ndef bar():\n    pass\n"
    after = b"def foo(x: int, y: str) -> str:\n    pass\ndef baz():\n    pass\n"
    detector = APIDetector("python")
    changes = detector.detect_changes(before, after)
    types = {c["function"]: c["type"] for c in changes}
    assert types.get("foo") == "modified"
    assert types.get("bar") == "removed"
    assert types.get("baz") == "added"
    breaking = {c["function"] for c in changes if c["breaking_change"]}
    assert breaking == {"foo", "bar"}


@pytest.mark.asyncio
async def test_project_context_builder_with_code_graph():
    diff = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-import os\n+import sys\n"
    )
    pr_diff = PRDiff(content=diff, repo_id="o/r")
    mock_session = AsyncMock()

    with patch("graph.repository.CodeGraphRepository.get_affected_files", new_callable=AsyncMock) as mock_affected:
        mock_affected.return_value = {
            "src/app.py": {
                "upstream": [{"file": "src/main.py", "depth": 1}],
                "downstream": [{"file": "src/test_app.py", "depth": 1}],
            }
        }
        builder = ProjectContextBuilder(db_session=mock_session, repo_id="o/r")
        context = await builder.build_context(pr_diff)

        assert context["dependency_graph"]["upstream"]["src/app.py"] == ["src/main.py"]
        assert context["dependency_graph"]["downstream"]["src/app.py"] == ["src/test_app.py"]
        mock_affected.assert_awaited_once_with(mock_session, "o/r", ["src/app.py"], depth=3)


@pytest.mark.asyncio
async def test_project_context_builder_precise_api_detection():
    diff = "diff --git a/src/app.py b/src/app.py\n"
    pr_diff = PRDiff(content=diff)
    before = b"def old_func(x):\n    pass\n"
    after = b"def new_func(x, y):\n    pass\n"
    builder = ProjectContextBuilder(
        file_content_map={
            "src/app.py": {"before": before, "after": after}
        }
    )
    context = await builder.build_context(pr_diff)
    changes = context["api_contracts"]["api_changes"]
    assert len(changes) == 2
    names = {c["function"] for c in changes}
    assert names == {"old_func", "new_func"}
    assert context["api_contracts"]["breaking_count"] == 1  # old_func removed
