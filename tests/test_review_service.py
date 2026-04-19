import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from models import Review
from services.review_service import run_review, _run_review_core, _create_provider


def _make_mock_session():
    """Create a mock AsyncSession whose begin() returns a usable async CM."""
    session = MagicMock(spec=AsyncSession)

    begin_cm = MagicMock()
    begin_cm.__aenter__ = AsyncMock(return_value=None)
    begin_cm.__aexit__ = AsyncMock(return_value=None)
    session.begin = MagicMock(return_value=begin_cm)
    return session


class MockAsyncContextManager:
    """Replacement for MagicMock when used as an async context manager object.
    MagicMock dynamically creates class-level __aenter__/__aexit__ which
    shadow any instance-level overrides, so we use a plain class instead."""

    def __init__(self, enter_result):
        self._enter_result = enter_result

    async def __aenter__(self):
        return self._enter_result

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


class TestCreateProvider:
    """Tests for _create_provider()"""

    def test_create_provider_github(self):
        review = MagicMock()
        review.platform = "github"
        review.repo_id = "owner/repo"
        review.pr_number = 42

        with patch("services.review_service.GitProviderFactory") as mock_factory:
            mock_factory.from_pr_info = MagicMock(return_value="github_provider")
            with patch("services.review_service.settings") as mock_settings:
                mock_settings.github_token = MagicMock()
                mock_settings.github_token.get_secret_value.return_value = "gh_token"

                provider = _create_provider(review)

                assert provider == "github_provider"
                mock_factory.from_pr_info.assert_called_once_with(
                    platform="github",
                    repo_id="owner/repo",
                    pr_number=42,
                    token="gh_token",
                )

    def test_create_provider_gitlab(self):
        review = MagicMock()
        review.platform = "gitlab"
        review.repo_id = "group/project"
        review.pr_number = 7

        with patch("services.review_service.GitProviderFactory") as mock_factory:
            mock_factory.from_pr_info = MagicMock(return_value="gitlab_provider")
            with patch("services.review_service.settings") as mock_settings:
                mock_settings.gitlab_token = MagicMock()
                mock_settings.gitlab_token.get_secret_value.return_value = "gl_token"
                mock_settings.gitlab_url = "https://gitlab.example.com"

                provider = _create_provider(review)

                assert provider == "gitlab_provider"
                mock_factory.from_pr_info.assert_called_once_with(
                    platform="gitlab",
                    repo_id="group/project",
                    pr_number=7,
                    token="gl_token",
                    gitlab_url="https://gitlab.example.com",
                )


class TestRunReviewCore:
    """Tests for _run_review_core()"""

    @pytest.fixture
    def mock_review(self):
        review = MagicMock(spec=Review)
        review.id = 1
        review.platform = "github"
        review.repo_id = "owner/repo"
        review.pr_number = 123
        review.org_id = None
        return review

    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.get_diff_content = AsyncMock(return_value="diff content")
        return provider

    @pytest.mark.asyncio
    async def test_core_success(self, mock_review, mock_provider):
        session = _make_mock_session()
        with patch("services.review_service.ReviewRepository") as mock_repo_cls, \
             patch("services.review_service.PRDiff") as mock_pr_diff_cls, \
             patch("services.review_service.ProjectConfigService") as mock_config_cls, \
             patch("services.review_service.DependencyGraphBuilder") as mock_graph_cls, \
             patch("services.review_service.PromptRegistry") as mock_prompt_cls, \
             patch("services.review_service.ResilientReviewRouter") as mock_router_cls, \
             patch("services.review_service.ReviewCache") as mock_cache_cls, \
             patch("services.review_service.ReviewEngine") as mock_engine_cls, \
             patch("services.review_service.QualityGate") as mock_gate_cls, \
             patch("services.review_service.ReviewPublisher") as mock_publisher_cls, \
             patch("services.review_service.settings") as mock_settings:

            # Setup mocks
            mock_repo = MagicMock()
            mock_repo.update_status = AsyncMock(return_value=MagicMock())
            mock_repo_cls.return_value = mock_repo

            mock_pr_diff = MagicMock()
            mock_pr_diff.get_changed_files.return_value = ["src/main.py"]
            mock_pr_diff_cls.return_value = mock_pr_diff

            mock_config_service = MagicMock()
            mock_config_service.load_and_cache = AsyncMock(return_value={"language": "python"})
            mock_config_cls.return_value = mock_config_service

            mock_graph = MagicMock()
            mock_graph.build = AsyncMock()
            mock_graph_cls.return_value = mock_graph

            mock_prompt = MagicMock()
            mock_prompt.load_from_db = AsyncMock()
            mock_prompt.get_experiment_assignment = AsyncMock(return_value="v1.2.0")
            mock_prompt_cls.return_value = mock_prompt

            mock_router = MagicMock()
            mock_router_cls.return_value = mock_router

            mock_cache = AsyncMock()
            mock_cache_cls.create = AsyncMock(return_value=mock_cache)

            mock_engine = MagicMock()
            mock_engine.run = AsyncMock(return_value={
                "issues": [{"severity": "critical"}],
                "summary": "1 issue",
            })
            mock_engine_cls.return_value = mock_engine

            mock_gate = MagicMock()
            mock_gate.assess.return_value = {
                "status": "failure",
                "description": "Critical issue found",
                "risk_level": "high",
            }
            mock_gate_cls.return_value = mock_gate

            mock_publisher = MagicMock()
            mock_publisher.publish = AsyncMock()
            mock_publisher.set_status = AsyncMock()
            mock_publisher_cls.return_value = mock_publisher

            mock_settings.enable_reasoner_review = True

            # Execute
            await _run_review_core(session, mock_review, mock_provider)

            # Verify
            mock_repo.update_status.assert_any_await(mock_review.id, "running")
            mock_repo.update_status.assert_any_await(mock_review.id, "completed", risk_level="high")
            mock_engine.run.assert_awaited_once()
            mock_publisher.publish.assert_awaited_once_with(mock_review.id)
            mock_publisher.set_status.assert_awaited_once_with("failure", "Critical issue found")

    @pytest.mark.asyncio
    async def test_core_success_with_repo_path(self, mock_review, mock_provider):
        """Test that repo_path, config load, and graph build paths are exercised."""
        session = _make_mock_session()
        with patch.dict("os.environ", {"REPOS_BASE_PATH": "/tmp/repos"}), \
             patch("services.review_service.os.path.isdir", return_value=True), \
             patch("services.review_service.ReviewRepository") as mock_repo_cls, \
             patch("services.review_service.PRDiff") as mock_pr_diff_cls, \
             patch("services.review_service.ProjectConfigService") as mock_config_cls, \
             patch("services.review_service.DependencyGraphBuilder") as mock_graph_cls, \
             patch("services.review_service.PromptRegistry") as mock_prompt_cls, \
             patch("services.review_service.ResilientReviewRouter") as mock_router_cls, \
             patch("services.review_service.ReviewCache") as mock_cache_cls, \
             patch("services.review_service.ReviewEngine") as mock_engine_cls, \
             patch("services.review_service.QualityGate") as mock_gate_cls, \
             patch("services.review_service.ReviewPublisher") as mock_publisher_cls, \
             patch("services.review_service.settings") as mock_settings:

            mock_repo = MagicMock()
            mock_repo.update_status = AsyncMock(return_value=MagicMock())
            mock_repo_cls.return_value = mock_repo

            mock_pr_diff = MagicMock()
            mock_pr_diff.get_changed_files.return_value = ["src/main.py"]
            mock_pr_diff_cls.return_value = mock_pr_diff

            mock_config_service = MagicMock()
            mock_config_service.load_and_cache = AsyncMock(return_value={"language": "python"})
            mock_config_cls.return_value = mock_config_service

            mock_graph = MagicMock()
            mock_graph.build = AsyncMock()
            mock_graph_cls.return_value = mock_graph

            mock_prompt = MagicMock()
            mock_prompt.load_from_db = AsyncMock()
            mock_prompt.get_experiment_assignment = AsyncMock(return_value="v1.2.0")
            mock_prompt_cls.return_value = mock_prompt

            mock_router_cls.return_value = MagicMock()

            mock_cache = AsyncMock()
            mock_cache_cls.create = AsyncMock(return_value=mock_cache)

            mock_engine = MagicMock()
            mock_engine.run = AsyncMock(return_value={
                "issues": [],
                "summary": "ok",
            })
            mock_engine_cls.return_value = mock_engine

            mock_gate = MagicMock()
            mock_gate.assess.return_value = {
                "status": "success",
                "description": "OK",
                "risk_level": "low",
            }
            mock_gate_cls.return_value = mock_gate

            mock_publisher = MagicMock()
            mock_publisher.publish = AsyncMock()
            mock_publisher.set_status = AsyncMock()
            mock_publisher_cls.return_value = mock_publisher

            mock_settings.enable_reasoner_review = True

            await _run_review_core(session, mock_review, mock_provider)

            mock_config_cls.assert_called_once_with(session)
            mock_config_service.load_and_cache.assert_awaited_once()
            mock_graph_cls.assert_called_once_with(session)
            mock_graph.build.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_core_config_graph_failure(self, mock_review, mock_provider):
        """Test graceful handling when config load and graph build fail."""
        session = _make_mock_session()
        with patch.dict("os.environ", {"REPOS_BASE_PATH": "/tmp/repos"}), \
             patch("services.review_service.os.path.isdir", return_value=True), \
             patch("services.review_service.ReviewRepository") as mock_repo_cls, \
             patch("services.review_service.PRDiff") as mock_pr_diff_cls, \
             patch("services.review_service.ProjectConfigService") as mock_config_cls, \
             patch("services.review_service.DependencyGraphBuilder") as mock_graph_cls, \
             patch("services.review_service.PromptRegistry") as mock_prompt_cls, \
             patch("services.review_service.ResilientReviewRouter") as mock_router_cls, \
             patch("services.review_service.ReviewCache") as mock_cache_cls, \
             patch("services.review_service.ReviewEngine") as mock_engine_cls, \
             patch("services.review_service.QualityGate") as mock_gate_cls, \
             patch("services.review_service.ReviewPublisher") as mock_publisher_cls, \
             patch("services.review_service.settings") as mock_settings:

            mock_repo = MagicMock()
            mock_repo.update_status = AsyncMock(return_value=MagicMock())
            mock_repo_cls.return_value = mock_repo

            mock_pr_diff = MagicMock()
            mock_pr_diff.get_changed_files.return_value = []
            mock_pr_diff_cls.return_value = mock_pr_diff

            mock_config_service = MagicMock()
            mock_config_service.load_and_cache = AsyncMock(side_effect=RuntimeError("config fail"))
            mock_config_cls.return_value = mock_config_service

            mock_graph = MagicMock()
            mock_graph.build = AsyncMock(side_effect=RuntimeError("graph fail"))
            mock_graph_cls.return_value = mock_graph

            mock_prompt = MagicMock()
            mock_prompt.load_from_db = AsyncMock()
            mock_prompt.get_experiment_assignment = AsyncMock(return_value=None)
            mock_prompt_cls.return_value = mock_prompt

            mock_router_cls.return_value = MagicMock()

            mock_cache = AsyncMock()
            mock_cache_cls.create = AsyncMock(return_value=mock_cache)

            mock_engine = MagicMock()
            mock_engine.run = AsyncMock(return_value={
                "issues": [],
                "summary": "ok",
            })
            mock_engine_cls.return_value = mock_engine

            mock_gate = MagicMock()
            mock_gate.assess.return_value = {
                "status": "success",
                "description": "OK",
                "risk_level": "low",
            }
            mock_gate_cls.return_value = mock_gate

            mock_publisher = MagicMock()
            mock_publisher.publish = AsyncMock()
            mock_publisher.set_status = AsyncMock()
            mock_publisher_cls.return_value = mock_publisher

            mock_settings.enable_reasoner_review = False

            await _run_review_core(session, mock_review, mock_provider)

            mock_repo.update_status.assert_any_await(mock_review.id, "completed", risk_level="low")

    @pytest.mark.asyncio
    async def test_core_degraded(self, mock_review, mock_provider):
        session = _make_mock_session()
        with patch("services.review_service.ReviewRepository") as mock_repo_cls, \
             patch("services.review_service.PRDiff") as mock_pr_diff_cls, \
             patch("services.review_service.ProjectConfigService") as mock_config_cls, \
             patch("services.review_service.DependencyGraphBuilder") as mock_graph_cls, \
             patch("services.review_service.PromptRegistry") as mock_prompt_cls, \
             patch("services.review_service.ResilientReviewRouter") as mock_router_cls, \
             patch("services.review_service.ReviewCache") as mock_cache_cls, \
             patch("services.review_service.ReviewEngine") as mock_engine_cls, \
             patch("services.review_service.QualityGate") as mock_gate_cls, \
             patch("services.review_service.ReviewPublisher") as mock_publisher_cls, \
             patch("services.review_service.settings") as mock_settings:

            mock_repo = MagicMock()
            mock_repo.update_status = AsyncMock(return_value=MagicMock())
            mock_repo_cls.return_value = mock_repo

            mock_pr_diff = MagicMock()
            mock_pr_diff.get_changed_files.return_value = []
            mock_pr_diff_cls.return_value = mock_pr_diff

            mock_config_cls.return_value = MagicMock()
            mock_config_cls.return_value.load_and_cache = AsyncMock(return_value=None)

            mock_graph_cls.return_value = MagicMock()
            mock_graph_cls.return_value.build = AsyncMock()

            mock_prompt = MagicMock()
            mock_prompt.load_from_db = AsyncMock()
            mock_prompt.get_experiment_assignment = AsyncMock(return_value=None)
            mock_prompt_cls.return_value = mock_prompt

            mock_router_cls.return_value = MagicMock()

            mock_cache = AsyncMock()
            mock_cache_cls.create = AsyncMock(return_value=mock_cache)

            mock_engine = MagicMock()
            mock_engine.run = AsyncMock(return_value={
                "issues": [],
                "degraded": True,
            })
            mock_engine_cls.return_value = mock_engine

            mock_gate = MagicMock()
            mock_gate.assess.return_value = {
                "status": "success",
                "description": "OK",
                "risk_level": "low",
            }
            mock_gate_cls.return_value = mock_gate

            mock_publisher = MagicMock()
            mock_publisher.publish = AsyncMock()
            mock_publisher.set_status = AsyncMock()
            mock_publisher_cls.return_value = mock_publisher

            mock_settings.enable_reasoner_review = False

            await _run_review_core(session, mock_review, mock_provider)

            mock_repo.update_status.assert_any_await(mock_review.id, "completed", risk_level=None)
            mock_publisher.set_status.assert_awaited_once_with(
                "success", "审查已降级：仅展示静态分析结果"
            )


class TestRunReview:
    """Tests for run_review() entry point"""

    @pytest.mark.asyncio
    async def test_run_review_not_found(self):
        session = _make_mock_session()
        with patch("services.review_service.async_sessionmaker") as mock_sessionmaker:
            factory = MagicMock()
            factory.return_value = MockAsyncContextManager(session)
            mock_sessionmaker.return_value = factory

            with patch("services.review_service.apply_db_settings") as mock_apply:
                with patch("services.review_service.ReviewRepository") as mock_repo_cls:
                    mock_repo = MagicMock()
                    mock_repo.get_by_id = AsyncMock(return_value=None)
                    mock_repo_cls.return_value = mock_repo

                    await run_review(999)

                    mock_apply.assert_awaited_once_with(session)
                    mock_repo.get_by_id.assert_awaited_once_with(999)

    @pytest.mark.asyncio
    async def test_run_review_network_error(self):
        review = MagicMock(spec=Review)
        review.id = 1
        review.platform = "github"
        review.repo_id = "owner/repo"
        review.pr_number = 1
        review.org_id = None

        session = _make_mock_session()
        with patch("services.review_service.async_sessionmaker") as mock_sessionmaker:
            factory = MagicMock()
            factory.return_value = MockAsyncContextManager(session)
            mock_sessionmaker.return_value = factory

            with patch("services.review_service.apply_db_settings"):
                with patch("services.review_service.ReviewRepository") as mock_repo_cls:
                    mock_repo = MagicMock()
                    mock_repo.get_by_id = AsyncMock(return_value=review)
                    mock_repo.update_status = AsyncMock(return_value=MagicMock())
                    mock_repo_cls.return_value = mock_repo

                    with patch("services.review_service._create_provider") as mock_create:
                        provider = MagicMock()
                        provider.get_diff_content = AsyncMock(side_effect=ConnectionError("timeout"))
                        mock_create.return_value = provider

                        with patch("services.review_service.ReviewPublisher") as mock_pub_cls:
                            mock_publisher = MagicMock()
                            mock_publisher.set_status = AsyncMock()
                            mock_pub_cls.return_value = mock_publisher

                            await run_review(1)

                            mock_repo.update_status.assert_any_await(1, "failed")
                            mock_publisher.set_status.assert_awaited_once_with(
                                "failure", "AI 审查因外部服务不可用失败"
                            )

    @pytest.mark.asyncio
    async def test_run_review_unexpected_error(self):
        review = MagicMock(spec=Review)
        review.id = 2
        review.platform = "github"
        review.repo_id = "owner/repo"
        review.pr_number = 1
        review.org_id = None

        session = _make_mock_session()
        with patch("services.review_service.async_sessionmaker") as mock_sessionmaker:
            factory = MagicMock()
            factory.return_value = MockAsyncContextManager(session)
            mock_sessionmaker.return_value = factory

            with patch("services.review_service.apply_db_settings"):
                with patch("services.review_service.ReviewRepository") as mock_repo_cls:
                    mock_repo = MagicMock()
                    mock_repo.get_by_id = AsyncMock(return_value=review)
                    mock_repo.update_status = AsyncMock(return_value=MagicMock())
                    mock_repo_cls.return_value = mock_repo

                    with patch("services.review_service._create_provider") as mock_create:
                        provider = MagicMock()
                        provider.get_diff_content = AsyncMock(side_effect=RuntimeError("bug"))
                        mock_create.return_value = provider

                        with patch("services.review_service.ReviewPublisher") as mock_pub_cls:
                            mock_publisher = MagicMock()
                            mock_publisher.set_status = AsyncMock()
                            mock_pub_cls.return_value = mock_publisher

                            with pytest.raises(RuntimeError, match="bug"):
                                await run_review(2)

                            mock_repo.update_status.assert_any_await(2, "failed")
                            mock_publisher.set_status.assert_awaited_once_with(
                                "failure", "AI 审查因内部错误失败"
                            )

    @pytest.mark.asyncio
    async def test_run_review_success(self):
        """Test the happy path through run_review entry point."""
        review = MagicMock(spec=Review)
        review.id = 4
        review.platform = "github"
        review.repo_id = "owner/repo"
        review.pr_number = 1
        review.org_id = None

        session = _make_mock_session()
        with patch("services.review_service.async_sessionmaker") as mock_sessionmaker:
            factory = MagicMock()
            factory.return_value = MockAsyncContextManager(session)
            mock_sessionmaker.return_value = factory

            with patch("services.review_service.apply_db_settings"):
                with patch("services.review_service.ReviewRepository") as mock_repo_cls:
                    mock_repo = MagicMock()
                    mock_repo.get_by_id = AsyncMock(return_value=review)
                    mock_repo.update_status = AsyncMock(return_value=MagicMock())
                    mock_repo_cls.return_value = mock_repo

                    with patch("services.review_service._create_provider") as mock_create:
                        provider = MagicMock()
                        provider.get_diff_content = AsyncMock(return_value="diff")
                        mock_create.return_value = provider

                        with patch("services.review_service._run_review_core") as mock_core:
                            mock_core.return_value = None
                            await run_review(4)

                            mock_core.assert_awaited_once_with(session, review, provider)

    @pytest.mark.asyncio
    async def test_run_review_timeout_error(self):
        """Test that asyncio.TimeoutError is handled as network error."""
        review = MagicMock(spec=Review)
        review.id = 3
        review.platform = "github"
        review.repo_id = "owner/repo"
        review.pr_number = 1
        review.org_id = None

        session = _make_mock_session()
        with patch("services.review_service.async_sessionmaker") as mock_sessionmaker:
            factory = MagicMock()
            factory.return_value = MockAsyncContextManager(session)
            mock_sessionmaker.return_value = factory

            with patch("services.review_service.apply_db_settings"):
                with patch("services.review_service.ReviewRepository") as mock_repo_cls:
                    mock_repo = MagicMock()
                    mock_repo.get_by_id = AsyncMock(return_value=review)
                    mock_repo.update_status = AsyncMock(return_value=MagicMock())
                    mock_repo_cls.return_value = mock_repo

                    with patch("services.review_service._create_provider") as mock_create:
                        provider = MagicMock()
                        provider.get_diff_content = AsyncMock(side_effect=asyncio.TimeoutError("timed out"))
                        mock_create.return_value = provider

                        with patch("services.review_service.ReviewPublisher") as mock_pub_cls:
                            mock_publisher = MagicMock()
                            mock_publisher.set_status = AsyncMock()
                            mock_pub_cls.return_value = mock_publisher

                            await run_review(3)

                            mock_repo.update_status.assert_any_await(3, "failed")
                            mock_publisher.set_status.assert_awaited_once_with(
                                "failure", "AI 审查因外部服务不可用失败"
                            )
