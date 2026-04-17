import asyncio
import logging
from typing import Optional

import httpx
from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository

from providers.base import GitProvider

logger = logging.getLogger(__name__)


class GitHubProvider(GitProvider):
    def __init__(self, token: str, repo: str, pr_number: int):
        self.token = token
        self.repo_name = repo
        self.pr_number = pr_number
        self.client = Github(token)
        self.repo: Repository = self.client.get_repo(repo)
        self.pr: PullRequest = self.repo.get_pull(pr_number)

    async def publish_review_comment(self, file: str, line: int, comment: str) -> None:
        try:
            self.pr.create_review_comment(
                body=comment,
                commit_id=self.pr.head.sha,
                path=file,
                line=line,
            )
        except Exception as exc:
            logger.warning("Failed to publish GitHub review comment: %s", exc)

    async def publish_inline_suggestion(
        self, file: str, line: int, suggestion: str
    ) -> None:
        body = f"```suggestion\n{suggestion}\n```"
        try:
            self.pr.create_review_comment(
                body=body,
                commit_id=self.pr.head.sha,
                path=file,
                line=line,
            )
        except Exception as exc:
            logger.warning("Failed to publish GitHub inline suggestion: %s", exc)

    async def set_status_check(
        self, status: str, description: str, context: str = "ai-code-review"
    ) -> None:
        state = status
        try:
            self.repo.get_commit(self.pr.head.sha).create_status(
                state=state,
                description=description,
                context=context,
            )
        except Exception as exc:
            logger.warning("Failed to set GitHub status check: %s", exc)

    async def get_diff_content(self) -> str:
        async with httpx.AsyncClient(timeout=30.0) as http:
            for attempt in range(3):
                try:
                    response = await http.get(
                        f"https://api.github.com/repos/{self.repo_name}/pulls/{self.pr_number}",
                        headers={
                            "Authorization": f"token {self.token}",
                            "Accept": "application/vnd.github.v3.diff",
                        },
                    )
                    response.raise_for_status()
                    return response.text
                except httpx.HTTPStatusError as exc:
                    logger.warning("GitHub API HTTP error: %s", exc)
                    raise
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
        return ""

    async def get_pr_info(self) -> dict:
        return {
            "number": self.pr.number,
            "title": self.pr.title,
            "author": self.pr.user.login if self.pr.user else None,
            "head_sha": self.pr.head.sha,
            "base_branch": self.pr.base.ref,
            "head_branch": self.pr.head.ref,
        }
