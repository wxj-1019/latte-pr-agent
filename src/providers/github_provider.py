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
        self._client = Github(token)
        self._repo: Optional[Repository] = None
        self._pr: Optional[PullRequest] = None

    async def _get_repo(self) -> Repository:
        if self._repo is None:
            self._repo = await asyncio.to_thread(self._client.get_repo, self.repo_name)
        return self._repo

    async def _get_pr(self) -> PullRequest:
        if self._pr is None:
            repo = await self._get_repo()
            self._pr = await asyncio.to_thread(repo.get_pull, self.pr_number)
        return self._pr

    async def publish_review_comment(self, file: str, line: int, comment: str) -> None:
        try:
            pr = await self._get_pr()
            await asyncio.to_thread(
                pr.create_review_comment,
                body=comment,
                commit_id=pr.head.sha,
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
            pr = await self._get_pr()
            await asyncio.to_thread(
                pr.create_review_comment,
                body=body,
                commit_id=pr.head.sha,
                path=file,
                line=line,
            )
        except Exception as exc:
            logger.warning("Failed to publish GitHub inline suggestion: %s", exc)

    async def set_status_check(
        self, status: str, description: str, context: str = "ai-code-review"
    ) -> None:
        valid_states = {"pending", "success", "failure", "error"}
        state = status if status in valid_states else "pending"
        try:
            pr = await self._get_pr()
            commit = await asyncio.to_thread(self._repo.get_commit, pr.head.sha)
            await asyncio.to_thread(
                commit.create_status,
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
        pr = await self._get_pr()
        number = await asyncio.to_thread(lambda: pr.number)
        title = await asyncio.to_thread(lambda: pr.title)
        author = await asyncio.to_thread(lambda: pr.user.login if pr.user else None)
        head_sha = await asyncio.to_thread(lambda: pr.head.sha)
        base_ref = await asyncio.to_thread(lambda: pr.base.ref)
        head_ref = await asyncio.to_thread(lambda: pr.head.ref)
        return {
            "number": number,
            "title": title,
            "author": author,
            "head_sha": head_sha,
            "base_branch": base_ref,
            "head_branch": head_ref,
        }
