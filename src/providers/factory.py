from typing import Optional

from providers.base import GitProvider
from providers.github_provider import GitHubProvider
from providers.gitlab_provider import GitLabProvider


class GitProviderFactory:
    @staticmethod
    def from_webhook_payload(
        platform: str, payload: dict, token: str, gitlab_url: Optional[str] = None
    ) -> GitProvider:
        if platform == "github":
            repo = payload.get("repository", {}).get("full_name")
            pr_number = payload.get("pull_request", {}).get("number")
            if not repo or not pr_number:
                raise ValueError("Invalid GitHub webhook payload: missing repo or pr_number")
            return GitHubProvider(token=token, repo=repo, pr_number=pr_number)

        if platform == "gitlab":
            project_id = payload.get("project", {}).get("id")
            mr_iid = payload.get("object_attributes", {}).get("iid")
            if not project_id or not mr_iid:
                raise ValueError("Invalid GitLab webhook payload: missing project_id or mr_iid")
            return GitLabProvider(
                token=token,
                project_id=project_id,
                mr_iid=mr_iid,
                gitlab_url=gitlab_url or "https://gitlab.com",
            )

        raise ValueError(f"Unsupported platform: {platform}")

    @staticmethod
    def from_pr_info(
        platform: str,
        repo_id: str,
        pr_number: int,
        token: str,
        gitlab_url: Optional[str] = None,
    ) -> GitProvider:
        if platform == "github":
            return GitHubProvider(token=token, repo=repo_id, pr_number=pr_number)
        if platform == "gitlab":
            return GitLabProvider(
                token=token,
                project_id=int(repo_id),
                mr_iid=pr_number,
                gitlab_url=gitlab_url or "https://gitlab.com",
            )
        raise ValueError(f"Unsupported platform: {platform}")
