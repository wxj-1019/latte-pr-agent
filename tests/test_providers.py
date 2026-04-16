import pytest
from unittest.mock import MagicMock, patch

from providers import GitHubProvider, GitLabProvider, GitProviderFactory


# ==================== GitHub Provider Tests ====================

@pytest.fixture
def mock_github_pr():
    pr = MagicMock()
    pr.number = 42
    pr.title = "Test PR"
    pr.user.login = "testuser"
    pr.head.sha = "abc123"
    pr.head.ref = "feature-branch"
    pr.base.ref = "main"
    pr.url = "https://api.github.com/repos/owner/repo/pulls/42"
    return pr


@pytest.fixture
def mock_github_repo(mock_github_pr):
    repo = MagicMock()
    repo.get_pull.return_value = mock_github_pr
    repo.get_commit.return_value.create_status.return_value = None
    return repo


@pytest.fixture
def mock_github_client(mock_github_repo):
    client = MagicMock()
    client.get_repo.return_value = mock_github_repo
    return client


@pytest.mark.asyncio
async def test_github_provider_publish_comment(mock_github_client, mock_github_pr):
    with patch("providers.github_provider.Github", return_value=mock_github_client):
        provider = GitHubProvider(token="fake_token", repo="owner/repo", pr_number=42)
        await provider.publish_review_comment("src/main.py", 10, "This looks good")

    mock_github_pr.create_review_comment.assert_called_once_with(
        body="This looks good",
        commit_id="abc123",
        path="src/main.py",
        line=10,
    )


@pytest.mark.asyncio
async def test_github_provider_set_status_check(mock_github_client, mock_github_repo):
    with patch("providers.github_provider.Github", return_value=mock_github_client):
        provider = GitHubProvider(token="fake_token", repo="owner/repo", pr_number=42)
        await provider.set_status_check("success", "All checks passed")

    mock_github_repo.get_commit.assert_called_once_with("abc123")
    commit = mock_github_repo.get_commit.return_value
    commit.create_status.assert_called_once_with(
        state="success",
        description="All checks passed",
        context="ai-code-review",
    )


@pytest.mark.asyncio
async def test_github_provider_get_pr_info(mock_github_client):
    with patch("providers.github_provider.Github", return_value=mock_github_client):
        provider = GitHubProvider(token="fake_token", repo="owner/repo", pr_number=42)
        info = await provider.get_pr_info()

    assert info["number"] == 42
    assert info["title"] == "Test PR"
    assert info["author"] == "testuser"
    assert info["head_sha"] == "abc123"


# ==================== GitLab Provider Tests ====================

@pytest.fixture
def mock_gitlab_mr():
    mr = MagicMock()
    mr.iid = 7
    mr.title = "Test MR"
    mr.author = {"username": "testuser"}
    mr.sha = "def456"
    mr.target_branch = "main"
    mr.source_branch = "feature-branch"
    mr.diff_refs = {
        "base_sha": "base123",
        "head_sha": "head456",
        "start_sha": "start789",
    }
    mr.changes.return_value = {
        "changes": [
            {"diff": "@@ -1 +1 @@\n-old\n+new\n"},
        ]
    }
    return mr


@pytest.fixture
def mock_gitlab_project(mock_gitlab_mr):
    project = MagicMock()
    project.mergerequests.get.return_value = mock_gitlab_mr
    project.commits.get.return_value.statuses.create.return_value = None
    return project


@pytest.fixture
def mock_gitlab_client(mock_gitlab_project):
    client = MagicMock()
    client.projects.get.return_value = mock_gitlab_project
    return client


@pytest.mark.asyncio
async def test_gitlab_provider_publish_comment(mock_gitlab_client, mock_gitlab_mr):
    with patch("providers.gitlab_provider.gitlab.Gitlab", return_value=mock_gitlab_client):
        provider = GitLabProvider(
            token="fake_token", project_id=123, mr_iid=7, gitlab_url="https://gitlab.com"
        )
        await provider.publish_review_comment("src/app.py", 5, "Consider refactoring")

    mock_gitlab_mr.discussions.create.assert_called_once()
    call_args = mock_gitlab_mr.discussions.create.call_args[0][0]
    assert call_args["body"] == "Consider refactoring"
    assert call_args["position"]["new_path"] == "src/app.py"
    assert call_args["position"]["new_line"] == 5


@pytest.mark.asyncio
async def test_gitlab_provider_set_status_check(mock_gitlab_client, mock_gitlab_project):
    with patch("providers.gitlab_provider.gitlab.Gitlab", return_value=mock_gitlab_client):
        provider = GitLabProvider(
            token="fake_token", project_id=123, mr_iid=7, gitlab_url="https://gitlab.com"
        )
        await provider.set_status_check("failure", "Critical issues found")

    mock_gitlab_project.commits.get.assert_called_once_with("def456")
    commit = mock_gitlab_project.commits.get.return_value
    commit.statuses.create.assert_called_once_with(
        {
            "state": "failed",
            "target_url": "",
            "description": "Critical issues found",
            "context": "ai-code-review",
        }
    )


@pytest.mark.asyncio
async def test_gitlab_provider_get_diff_content(mock_gitlab_client, mock_gitlab_mr):
    with patch("providers.gitlab_provider.gitlab.Gitlab", return_value=mock_gitlab_client):
        provider = GitLabProvider(
            token="fake_token", project_id=123, mr_iid=7, gitlab_url="https://gitlab.com"
        )
        diff = await provider.get_diff_content()

    assert "@@ -1 +1 @@" in diff
    mock_gitlab_mr.changes.assert_called_once()


# ==================== Factory Tests ====================

def test_factory_github():
    payload = {
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"number": 42},
    }
    with patch("providers.factory.GitHubProvider") as MockGH:
        GitProviderFactory.from_webhook_payload("github", payload, "token123")
        MockGH.assert_called_once_with(token="token123", repo="owner/repo", pr_number=42)


def test_factory_gitlab():
    payload = {
        "project": {"id": 123},
        "object_attributes": {"iid": 7},
    }
    with patch("providers.factory.GitLabProvider") as MockGL:
        GitProviderFactory.from_webhook_payload("gitlab", payload, "token456")
        MockGL.assert_called_once_with(
            token="token456", project_id=123, mr_iid=7, gitlab_url="https://gitlab.com"
        )


def test_factory_invalid_platform():
    with pytest.raises(ValueError, match="Unsupported platform"):
        GitProviderFactory.from_webhook_payload("bitbucket", {}, "token")


def test_factory_missing_github_fields():
    with pytest.raises(ValueError, match="Invalid GitHub webhook payload"):
        GitProviderFactory.from_webhook_payload("github", {"repository": {}}, "token")


def test_factory_missing_gitlab_fields():
    with pytest.raises(ValueError, match="Invalid GitLab webhook payload"):
        GitProviderFactory.from_webhook_payload("gitlab", {"project": {}}, "token")
