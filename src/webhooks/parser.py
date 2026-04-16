from typing import Optional


class WebhookParser:
    """从 GitHub/GitLab Webhook payload 中提取关键字段"""

    @staticmethod
    def parse_github(payload: dict) -> dict:
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        return {
            "platform": "github",
            "repo_id": repo.get("full_name"),
            "pr_number": pr.get("number"),
            "pr_title": pr.get("title"),
            "pr_author": pr.get("user", {}).get("login"),
            "head_sha": pr.get("head", {}).get("sha"),
            "base_branch": pr.get("base", {}).get("ref"),
            "head_branch": pr.get("head", {}).get("ref"),
            "action": payload.get("action"),
            "changed_files": pr.get("changed_files", 0),
        }

    @staticmethod
    def parse_gitlab(payload: dict) -> dict:
        attrs = payload.get("object_attributes", {})
        project = payload.get("project", {})
        return {
            "platform": "gitlab",
            "repo_id": str(project.get("id")),
            "pr_number": attrs.get("iid"),
            "pr_title": attrs.get("title"),
            "pr_author": attrs.get("author_id"),
            "head_sha": attrs.get("last_commit", {}).get("id"),
            "base_branch": attrs.get("target_branch"),
            "head_branch": attrs.get("source_branch"),
            "action": attrs.get("action"),
            "changed_files": attrs.get("changes_count", 0),
        }
