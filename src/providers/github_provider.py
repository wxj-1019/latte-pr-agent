from typing import Optional

import httpx
from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository

from providers.base import GitProvider


class GitHubProvider(GitProvider):
    def __init__(self, token: str, repo: str, pr_number: int):
        self.token = token
        self.repo_name = repo
        self.pr_number = pr_number
        self.client = Github(token)
        self.repo: Repository = self.client.get_repo(repo)
        self.pr: PullRequest = self.repo.get_pull(pr_number)

    async def publish_review_comment(self, file: str, line: int, comment: str) -> None:
        self.pr.create_review_comment(
            body=comment,
            commit_id=self.pr.head.sha,
            path=file,
            line=line,
        )

    async def publish_inline_suggestion(
        self, file: str, line: int, suggestion: str
    ) -> None:
        body = f"```suggestion\n{suggestion}\n```"
        self.pr.create_review_comment(
            body=body,
            commit_id=self.pr.head.sha,
            path=file,
            line=line,
        )

    async def set_status_check(
        self, status: str, description: str, context: str = "ai-code-review"
    ) -> None:
        state = status
        self.repo.get_commit(self.pr.head.sha).create_status(
            state=state,
            description=description,
            context=context,
        )

    async def get_diff_content(self) -> str:
        async with httpx.AsyncClient() as http:
            response = await http.get(
                f"https://api.github.com/repos/{self.repo_name}/pulls/{self.pr_number}",
                headers={
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github.v3.diff",
                },
            )
            response.raise_for_status()
            return response.text

    async def get_pr_info(self) -> dict:
        return {
            "number": self.pr.number,
            "title": self.pr.title,
            "author": self.pr.user.login if self.pr.user else None,
            "head_sha": self.pr.head.sha,
            "base_branch": self.pr.base.ref,
            "head_branch": self.pr.head.ref,
        }
