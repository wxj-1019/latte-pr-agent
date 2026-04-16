import logging
import re
import subprocess
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from rag.embedder import EmbeddingClient
from rag.repository import BugKnowledgeRepository

logger = logging.getLogger(__name__)


class BugKnowledgeBuilder:
    """扫描 Git 历史，提取 Bug 修复记录并构建 RAG 知识库。"""

    def __init__(
        self,
        session: AsyncSession,
        embedder: Optional[EmbeddingClient] = None,
    ):
        self.session = session
        self.embedder = embedder or EmbeddingClient()

    async def scan_from_git_history(
        self,
        repo_path: str,
        org_id: str,
        repo_id: str,
        max_commits: int = 100,
    ) -> int:
        """扫描指定仓库的 Git 历史，过滤 Bug 修复类 Commit，生成 Embedding 并入库。

        返回成功插入的记录数。
        """
        commits = self._get_bug_commits(repo_path, max_commits=max_commits)
        if not commits:
            logger.info(f"No bug-fix commits found in {repo_path}")
            return 0

        inserted = 0
        for commit_hash, message in commits:
            if self._should_skip_commit(message):
                continue

            diff = self._get_commit_diff(repo_path, commit_hash)
            if not diff:
                continue

            # 截断过长的 diff，避免 embedding token 超限
            truncated_diff = diff[:8000]
            content_for_embed = f"{message}\n\n{truncated_diff}"

            try:
                embedding = await self.embedder.embed(content_for_embed)
            except Exception as exc:
                logger.warning(f"Failed to generate embedding for {commit_hash}: {exc}")
                continue

            await BugKnowledgeRepository.insert(
                session=self.session,
                org_id=org_id,
                repo_id=repo_id,
                bug_pattern=truncated_diff,
                embedding=embedding,
                severity=self._infer_severity(message),
                fix_commit=commit_hash,
                fix_description=message,
            )
            inserted += 1

        await self.session.commit()
        logger.info(f"Inserted {inserted} bug knowledge records for {repo_id}")
        return inserted

    def _get_bug_commits(self, repo_path: str, max_commits: int = 100) -> List[tuple]:
        """获取最近 N 条 commit 的 hash 与 message。"""
        try:
            output = subprocess.run(
                [
                    "git", "-C", repo_path, "log",
                    f"-{max_commits}",
                    "--pretty=format:%H|%s",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.warning(f"git log failed: {exc}")
            return []

        commits = []
        for line in output.stdout.strip().splitlines():
            if "|" in line:
                commit_hash, message = line.split("|", 1)
                commits.append((commit_hash, message))
        return commits

    def _should_skip_commit(self, message: str) -> bool:
        """过滤非 Bug 修复类或低质量的 commit。"""
        lower = message.lower()
        # 必须包含 bug/fix/patch/hotfix 关键词
        if not re.search(r"\b(bug|fix|patch|hotfix)\b", lower):
            return True
        # 排除纯文档、测试、revert、merge
        skip_keywords = ["docs:", "doc:", "test:", "tests:", "revert", "merge", "bump version"]
        if any(kw in lower for kw in skip_keywords):
            return True
        return False

    def _get_commit_diff(self, repo_path: str, commit_hash: str) -> str:
        try:
            output = subprocess.run(
                ["git", "-C", repo_path, "show", "--no-color", commit_hash],
                capture_output=True,
                text=True,
                check=True,
            )
            return output.stdout
        except subprocess.CalledProcessError as exc:
            logger.warning(f"git show failed for {commit_hash}: {exc}")
            return ""

    def _infer_severity(self, message: str) -> Optional[str]:
        lower = message.lower()
        if any(kw in lower for kw in ["critical", "security", "vulnerability", "cve"]):
            return "critical"
        if any(kw in lower for kw in ["memory leak", "deadlock", "race condition", "null pointer", "npe"]):
            return "high"
        if any(kw in lower for kw in ["exception", "crash", "error", "broken"]):
            return "medium"
        return "low"
