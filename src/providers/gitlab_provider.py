from typing import Optional

import gitlab
from gitlab.v4.objects import ProjectMergeRequest

from providers.base import GitProvider


class GitLabProvider(GitProvider):
    def __init__(
        self, token: str, project_id: int, mr_iid: int, gitlab_url: str
    ):
        self.gl = gitlab.Gitlab(gitlab_url, private_token=token)
        self.project = self.gl.projects.get(project_id)
        self.mr: ProjectMergeRequest = self.project.mergerequests.get(mr_iid)

    async def publish_review_comment(self, file: str, line: int, comment: str) -> None:
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

    async def publish_inline_suggestion(
        self, file: str, line: int, suggestion: str
    ) -> None:
        # GitLab Code Suggestion 格式
        body = f"```suggestion:-0+0\n{suggestion}\n```"
        await self.publish_review_comment(file, line, body)

    async def set_status_check(
        self, status: str, description: str, context: str = "ai-code-review"
    ) -> None:
        # GitLab Commit Status API
        # Map failure -> failed for GitLab
        gitlab_state = status if status != "failure" else "failed"
        self.project.commits.get(self.mr.sha).statuses.create(
            {
                "state": gitlab_state,
                "target_url": "",
                "description": description,
                "context": context,
            }
        )

    async def get_diff_content(self) -> str:
        # 获取 MR changes 的 diff
        changes = self.mr.changes()
        diffs = []
        for change in changes.get("changes", []):
            diffs.append(change.get("diff", ""))
        return "\n".join(diffs)

    async def get_pr_info(self) -> dict:
        return {
            "number": self.mr.iid,
            "title": self.mr.title,
            "author": self.mr.author.get("username") if self.mr.author else None,
            "head_sha": self.mr.sha,
            "base_branch": self.mr.target_branch,
            "head_branch": self.mr.source_branch,
        }
