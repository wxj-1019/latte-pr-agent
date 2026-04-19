import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from config.project_config import CrossServiceConfig, DownstreamService
from context.cross_service import CrossServiceAnalyzer


class TestAnalyze:
    """Tests for CrossServiceAnalyzer.analyze()"""

    @pytest.fixture
    def config_with_downstream(self):
        return CrossServiceConfig(
            enabled=True,
            downstream_repos=[
                DownstreamService(repo_id="owner/repo1", platform="github"),
                DownstreamService(repo_id="owner/repo2", platform="gitlab"),
            ],
        )

    @pytest.fixture
    def config_disabled(self):
        return CrossServiceConfig(enabled=False)

    @pytest.fixture
    def config_no_downstream(self):
        return CrossServiceConfig(enabled=True)

    @pytest.mark.asyncio
    async def test_analyze_disabled_returns_none(self, config_disabled):
        analyzer = CrossServiceAnalyzer(config_disabled)
        result = await analyzer.analyze([{"function": "foo"}])
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_no_downstream_returns_none(self, config_no_downstream):
        analyzer = CrossServiceAnalyzer(config_no_downstream)
        result = await analyzer.analyze([{"function": "foo"}])
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_no_api_changes_returns_none(self, config_with_downstream):
        analyzer = CrossServiceAnalyzer(config_with_downstream)
        result = await analyzer.analyze([])
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_no_identifiers_returns_none(self, config_with_downstream):
        analyzer = CrossServiceAnalyzer(config_with_downstream)
        result = await analyzer.analyze([{"file": "x.py"}])  # no "function" key
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_high_impact(self, config_with_downstream):
        analyzer = CrossServiceAnalyzer(config_with_downstream)
        with patch.object(analyzer, "_search_github", new_callable=AsyncMock) as mock_gh, \
             patch.object(analyzer, "_search_gitlab", new_callable=AsyncMock) as mock_gl:
            mock_gh.return_value = {"matches": [{"identifier": "foo", "count": 3}], "total_count": 3}
            mock_gl.return_value = {"matches": [{"identifier": "bar", "count": 2}], "total_count": 2}

            result = await analyzer.analyze([{"function": "foo"}, {"function": "bar"}])

        assert result is not None
        assert result["impact_level"] == "high"
        assert result["affected_services_count"] == 2
        assert result["downstream_services_count"] == 2
        assert len(result["details"]) == 2

    @pytest.mark.asyncio
    async def test_analyze_medium_impact(self, config_with_downstream):
        analyzer = CrossServiceAnalyzer(config_with_downstream)
        with patch.object(analyzer, "_search_github", new_callable=AsyncMock) as mock_gh, \
             patch.object(analyzer, "_search_gitlab", new_callable=AsyncMock) as mock_gl:
            mock_gh.return_value = {"matches": [{"identifier": "foo", "count": 1}], "total_count": 1}
            mock_gl.return_value = {"matches": [], "total_count": 0}

            result = await analyzer.analyze([{"function": "foo"}])

        assert result is not None
        assert result["impact_level"] == "medium"
        assert result["affected_services_count"] == 1

    @pytest.mark.asyncio
    async def test_analyze_low_impact(self, config_with_downstream):
        analyzer = CrossServiceAnalyzer(config_with_downstream)
        with patch.object(analyzer, "_search_github", new_callable=AsyncMock) as mock_gh, \
             patch.object(analyzer, "_search_gitlab", new_callable=AsyncMock) as mock_gl:
            mock_gh.return_value = {"matches": [], "total_count": 0}
            mock_gl.return_value = {"matches": [], "total_count": 0}

            result = await analyzer.analyze([{"function": "foo"}])

        assert result is not None
        assert result["impact_level"] == "low"
        assert result["affected_services_count"] == 0


class TestSearchDownstream:
    """Tests for _search_downstream dispatch"""

    @pytest.fixture
    def analyzer(self):
        config = CrossServiceConfig(enabled=True)
        return CrossServiceAnalyzer(config)

    @pytest.mark.asyncio
    async def test_search_downstream_github(self, analyzer):
        with patch.object(analyzer, "_search_github", new_callable=AsyncMock) as mock_gh:
            mock_gh.return_value = {"matches": ["x"], "total_count": 1}
            result = await analyzer._search_downstream("o/r", "github", ["foo"])
            assert result["total_count"] == 1
            mock_gh.assert_awaited_once_with("o/r", ["foo"])

    @pytest.mark.asyncio
    async def test_search_downstream_gitlab(self, analyzer):
        with patch.object(analyzer, "_search_gitlab", new_callable=AsyncMock) as mock_gl:
            mock_gl.return_value = {"matches": ["x"], "total_count": 1}
            result = await analyzer._search_downstream("o/r", "gitlab", ["foo"])
            assert result["total_count"] == 1
            mock_gl.assert_awaited_once_with("o/r", ["foo"])

    @pytest.mark.asyncio
    async def test_search_downstream_unknown_platform(self, analyzer):
        result = await analyzer._search_downstream("o/r", "bitbucket", ["foo"])
        assert result == {"matches": [], "total_count": 0}


class TestSearchGitHub:
    """Tests for _search_github"""

    @pytest.fixture
    def analyzer(self):
        config = CrossServiceConfig(enabled=True)
        return CrossServiceAnalyzer(config)

    @pytest.mark.asyncio
    async def test_search_github_no_token(self, analyzer):
        with patch("context.cross_service.settings") as mock_settings:
            mock_settings.github_token = MagicMock()
            mock_settings.github_token.get_secret_value.return_value = ""
            result = await analyzer._search_github("o/r", ["foo"])
            assert result == {"matches": [], "total_count": 0}

    @pytest.mark.asyncio
    async def test_search_github_success(self, analyzer):
        with patch("context.cross_service.settings") as mock_settings:
            mock_settings.github_token = MagicMock()
            mock_settings.github_token.get_secret_value.return_value = "gh_token"

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "total_count": 2,
                "items": [{"path": "src/a.py"}, {"path": "src/b.py"}],
            }

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await analyzer._search_github("o/r", ["foo"])

            assert result["total_count"] == 2
            assert len(result["matches"]) == 1
            assert result["matches"][0]["identifier"] == "foo"
            assert result["matches"][0]["count"] == 2
            assert result["matches"][0]["files"] == ["src/a.py", "src/b.py"]

    @pytest.mark.asyncio
    async def test_search_github_api_error(self, analyzer):
        with patch("context.cross_service.settings") as mock_settings:
            mock_settings.github_token = MagicMock()
            mock_settings.github_token.get_secret_value.return_value = "gh_token"

            mock_response = MagicMock()
            mock_response.status_code = 403

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await analyzer._search_github("o/r", ["foo"])

            assert result == {"matches": [], "total_count": 0}

    @pytest.mark.asyncio
    async def test_search_github_exception(self, analyzer):
        with patch("context.cross_service.settings") as mock_settings:
            mock_settings.github_token = MagicMock()
            mock_settings.github_token.get_secret_value.return_value = "gh_token"

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=ConnectionError("network down"))

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await analyzer._search_github("o/r", ["foo"])

            assert result == {"matches": [], "total_count": 0}


class TestSearchGitLab:
    """Tests for _search_gitlab"""

    @pytest.fixture
    def analyzer(self):
        config = CrossServiceConfig(enabled=True)
        return CrossServiceAnalyzer(config)

    @pytest.mark.asyncio
    async def test_search_gitlab_no_token(self, analyzer):
        with patch("context.cross_service.settings") as mock_settings:
            mock_settings.gitlab_token = MagicMock()
            mock_settings.gitlab_token.get_secret_value.return_value = ""
            mock_settings.gitlab_url = "https://gitlab.com"
            result = await analyzer._search_gitlab("o/r", ["foo"])
            assert result == {"matches": [], "total_count": 0}

    @pytest.mark.asyncio
    async def test_search_gitlab_success(self, analyzer):
        with patch("context.cross_service.settings") as mock_settings:
            mock_settings.gitlab_token = MagicMock()
            mock_settings.gitlab_token.get_secret_value.return_value = "gl_token"
            mock_settings.gitlab_url = "https://gitlab.com"

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {"path": "src/a.py"},
                {"path": "src/b.py"},
            ]

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await analyzer._search_gitlab("o/r", ["foo"])

            assert result["total_count"] == 2
            assert len(result["matches"]) == 1
            assert result["matches"][0]["identifier"] == "foo"
            assert result["matches"][0]["count"] == 2
            assert result["matches"][0]["files"] == ["src/a.py", "src/b.py"]

    @pytest.mark.asyncio
    async def test_search_gitlab_api_error(self, analyzer):
        with patch("context.cross_service.settings") as mock_settings:
            mock_settings.gitlab_token = MagicMock()
            mock_settings.gitlab_token.get_secret_value.return_value = "gl_token"
            mock_settings.gitlab_url = "https://gitlab.com"

            mock_response = MagicMock()
            mock_response.status_code = 401

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await analyzer._search_gitlab("o/r", ["foo"])

            assert result == {"matches": [], "total_count": 0}
