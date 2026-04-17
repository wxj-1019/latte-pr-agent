"""Integration tests for the direct code analyze endpoint."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


def _make_provider_mock(mock_result):
    """Return a mock provider class that doesn't need API keys."""
    class MockProvider:
        async def review(self, prompt, model, system_prompt=None):
            return mock_result
    return MockProvider


class _FakeCache:
    async def get(self, *args, **kwargs):
        return None

    async def set(self, *args, **kwargs):
        pass


@pytest.fixture
def analyze_patches():
    """Patches LLM providers and Redis cache so analyze tests don't need real deps."""
    import contextlib

    def _apply(mock_result):
        stack = contextlib.ExitStack()
        stack.enter_context(
            patch.multiple(
                "llm.router",
                DeepSeekProvider=_make_provider_mock(mock_result),
                AnthropicProvider=_make_provider_mock(mock_result),
                QwenProvider=_make_provider_mock(mock_result),
            )
        )
        stack.enter_context(patch("reviews.router.ReviewCache", return_value=_FakeCache()))
        stack.enter_context(patch("engine.review_engine.ReviewCache", return_value=_FakeCache()))
        stack.enter_context(patch("engine.cache.ReviewCache", return_value=_FakeCache()))
        return stack
    return _apply


@pytest.mark.asyncio
class TestAnalyzeEndpoint:
    async def test_analyze_code_success(self, async_client_with_db, analyze_patches):
        mock_result = {
            "issues": [
                {
                    "file": "test.py",
                    "line": 2,
                    "severity": "warning",
                    "category": "style",
                    "description": "Missing type hints",
                    "suggestion": "Add type annotations",
                    "confidence": 0.85,
                }
            ],
            "summary": "Found 1 issue",
            "risk_level": "medium",
            "degraded": False,
        }

        with analyze_patches(mock_result):
            response = await async_client_with_db.post(
                "/reviews/analyze",
                json={
                    "filename": "test.py",
                    "content": "def hello():\n    pass\n",
                    "language": "python",
                    "repo_id": "direct/default",
                },
            )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "completed"
        assert data["risk_level"] == "medium"
        assert len(data["findings"]) == 1
        finding = data["findings"][0]
        assert finding["file_path"] == "test.py"
        assert finding["severity"] == "warning"
        assert finding["description"] == "Missing type hints"

    async def test_analyze_code_with_critical_issue(self, async_client_with_db, analyze_patches):
        mock_result = {
            "issues": [
                {
                    "file": "test.py",
                    "line": 1,
                    "severity": "critical",
                    "category": "security",
                    "description": "SQL injection",
                    "confidence": 0.95,
                }
            ],
            "summary": "Critical issue found",
            "risk_level": "high",
            "degraded": False,
        }

        with analyze_patches(mock_result):
            response = await async_client_with_db.post(
                "/reviews/analyze",
                json={
                    "filename": "test.py",
                    "content": "query = f'SELECT * FROM users WHERE id = {user_id}'",
                    "language": "python",
                    "repo_id": "direct/default",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] == "critical"
        assert len(data["findings"]) == 1
        assert data["findings"][0]["severity"] == "critical"

    async def test_analyze_empty_code(self, async_client_with_db, analyze_patches):
        mock_result = {"issues": [], "summary": "No issues", "risk_level": "low", "degraded": False}

        with analyze_patches(mock_result):
            response = await async_client_with_db.post(
                "/reviews/analyze",
                json={
                    "filename": "test.py",
                    "content": "   ",
                    "language": "python",
                    "repo_id": "direct/default",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["findings"] == []

    async def test_analyze_filename_sanitization(self, async_client_with_db, analyze_patches):
        mock_result = {"issues": [], "summary": "OK", "risk_level": "low", "degraded": False}

        with analyze_patches(mock_result):
            response = await async_client_with_db.post(
                "/reviews/analyze",
                json={
                    "filename": "../etc/passwd",
                    "content": "print('hello')",
                    "language": "python",
                    "repo_id": "direct/default",
                },
            )

        assert response.status_code == 200


@pytest.mark.asyncio
class TestReposEndpoint:
    async def test_list_repos_empty(self, async_client_with_db):
        response = await async_client_with_db.get("/repos")
        assert response.status_code == 200
        assert response.json() == {"repos": []}

    async def test_list_repos_excludes_direct(self, async_client_with_db, analyze_patches):
        mock_result = {"issues": [], "summary": "OK", "risk_level": "low", "degraded": False}
        with analyze_patches(mock_result):
            await async_client_with_db.post(
                "/reviews/analyze",
                json={
                    "filename": "test.py",
                    "content": "print('hello')",
                    "language": "python",
                    "repo_id": "direct/default",
                },
            )

        response = await async_client_with_db.get("/repos")
        assert response.status_code == 200
        # direct/default should be excluded
        assert "direct/default" not in response.json()["repos"]
