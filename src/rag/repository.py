from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class BugKnowledgeRepository:
    """基于 PostgreSQL pgvector 的历史 Bug 知识库仓库。"""

    @staticmethod
    async def insert(
        session: AsyncSession,
        org_id: str,
        repo_id: str,
        bug_pattern: str,
        embedding: List[float],
        file_path: Optional[str] = None,
        severity: Optional[str] = None,
        fix_commit: Optional[str] = None,
        fix_description: Optional[str] = None,
    ) -> None:
        sql = text("""
            INSERT INTO bug_knowledge (
                org_id, repo_id, file_path, bug_pattern, severity,
                fix_commit, fix_description, embedding
            ) VALUES (
                :org_id, :repo_id, :file_path, :bug_pattern, :severity,
                :fix_commit, :fix_description, :embedding::vector
            )
        """)
        await session.execute(
            sql,
            {
                "org_id": org_id,
                "repo_id": repo_id,
                "file_path": file_path,
                "bug_pattern": bug_pattern,
                "severity": severity,
                "fix_commit": fix_commit,
                "fix_description": fix_description,
                "embedding": embedding,
            },
        )

    @staticmethod
    async def search_similar(
        session: AsyncSession,
        embedding: List[float],
        repo_id: str,
        limit: int = 3,
        min_similarity: float = 0.75,
        org_id: str = "default",
    ) -> List[Dict]:
        """使用 <=>（余弦距离）检索相似记录，并过滤相似度阈值。

        注意：pgvector 中 <=> 返回的是余弦距离（1 - 余弦相似度），
        因此 similarity = 1 - distance。
        """
        sql = text("""
            SELECT
                id,
                file_path,
                bug_pattern,
                severity,
                fix_commit,
                fix_description,
                1 - (embedding <=> :embedding::vector) AS similarity
            FROM bug_knowledge
            WHERE repo_id = :repo_id
              AND org_id = :org_id
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """)
        result = await session.execute(
            sql,
            {
                "embedding": embedding,
                "repo_id": repo_id,
                "org_id": org_id,
                "limit": limit,
            },
        )
        rows = result.mappings().all()
        return [
            {
                "id": row["id"],
                "file_path": row["file_path"],
                "bug_pattern": row["bug_pattern"],
                "severity": row["severity"],
                "fix_commit": row["fix_commit"],
                "fix_description": row["fix_description"],
                "similarity": row["similarity"],
            }
            for row in rows
            if row["similarity"] is not None and row["similarity"] >= min_similarity
        ]
