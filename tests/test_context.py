import pytest

from context.builder import PRDiff, ProjectContextBuilder


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


def test_project_context_builder_basic():
    diff = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-import os\n+import sys\n"
        "@@ -10 +10 @@\n-def old_func(x):\n+def new_func(x, y):\n"
    )
    builder = ProjectContextBuilder()
    context = builder.build_context(PRDiff(content=diff))

    assert "pr_diff" in context
    assert len(context["file_changes"]) == 1
    assert context["file_changes"][0]["file"] == "src/app.py"
    assert "dependency_graph" in context
    assert "api_contracts" in context
    assert context["api_contracts"]["breaking_count"] == 1
    assert context["similar_bugs"] == []
    assert context["cross_service_impact"] is None


def test_project_context_builder_no_api_change():
    diff = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n+++ b/src/app.py\n@@ -5 +5 @@\n-print('hello')\n+print('world')\n"
    )
    builder = ProjectContextBuilder()
    context = builder.build_context(PRDiff(content=diff))
    assert context["api_contracts"]["breaking_count"] == 0
    assert context["api_contracts"]["api_changes"] == []
