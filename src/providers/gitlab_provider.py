import asyncio
import logging
from functools import partial
from typing import Optional

import gitlab
from gitlab.v4.objects import ProjectMergeRequest

from providers.base import GitProvider

logger = logging.getLogger(__name__)


class GitLabProvider(GitProvider):
    def __init__(
        self, token: str, project_id: int, mr_iid: int, gitlab_url: str
    ):
        self.gl = gitlab.Gitlab(gitlab_url, private_token=token)
        self.project = self.gl.projects.get(project_id)
        self.mr: ProjectMergeRequest = self.project.mergerequests.get(mr_iid)

    def _sync_publish_review_comment(self, file: str, line: int, comment: str) -> None:
        self.mr.discussions.create(
            {
                "body": comment,
                "position": {
                    "base_sha": self.mr.diff_refs["base_sha"],
                    "head_sha": self.mr.diff_refs["head_sha"],
                    "start_sha": self.mr.diff_refs["start_sha"],
                    "position_type": "text",
                    "new_path": file,
                    "new_line": line,
                },
            }
        )

    async def publish_review_comment(self, file: str, line: int, comment: str) -> None:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, partial(self._sync_publish_review_comment, file, line, comment)
            )
        except Exception as exc:
            logger.warning("Failed to publish GitLab review comment: %s", exc)

    async def publish_inline_suggestion(
        self, file: str, line: int, suggestion: str
    ) -> None:
        body = f"```suggestion:-0+0\n{suggestion}\n```"
        await self.publish_review_comment(file, line, body)

    def _sync_set_status_check(
        self, status: str, description: str, context: str
    ) -> None:
        gitlab_state = status if status != "failure" else "failed"
        self.project.commits.get(self.mr.sha).statuses.create(
            {
                "state": gitlab_state,
                "target_url": "",
                "description": description,
                "context": context,
            }
        )

    async def set_status_check(
        self, status: str, description: str, context: str = "ai-code-review"
    ) -> None:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, partial(self._sync_set_status_check, status, description, context)
            )
        except Exception as exc:
            logger.warning("Failed to set GitLab status check: %s", exc)

    def _sync_get_diff_content(self) -> str:
        changes = self.mr.changes()
        diffs = []
        for change in changes.get("changes", []):
            diffs.append(change.get("diff", ""))
        return "\n".join(diffs)

    async def get_diff_content(self) -> str:
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._sync_get_diff_content
            )
        except Exception as exc:
            logger.warning("Failed to fetch GitLab diff content: %s", exc)
            raise

    def _sync_get_pr_info(self) -> dict:
        return {
            "number": self.mr.iid,
            "title": self.mr.title,
            "author": self.mr.author.get("username") if self.mr.author else None,
            "head_sha": self.mr.sha,
            "base_branch": self.mr.target_branch,
            "head_branch": self.mr.source_branch,
        }

    async def get_pr_info(self) -> dict:
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._sync_get_pr_info
            )
        except Exception as exc:
            logger.warning("Failed to fetch GitLab MR info: %s", exc)
            raise
