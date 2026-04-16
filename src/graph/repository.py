from typing import List, Dict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CodeGraphRepository:
    """基于 PostgreSQL 递归 CTE 的代码图查询仓库。"""

    @staticmethod
    async def get_callers(
        session: AsyncSession,
        repo_id: str,
        file: str,
        depth: int = 3,
        org_id: str = "default",
    ) -> List[Dict]:
        """查询指定文件的上游调用者（哪些文件依赖它）。"""
        sql = text("""
            WITH RECURSIVE chain AS (
                SELECT downstream_file, upstream_file, 1 AS depth
                FROM file_dependencies
                WHERE upstream_file = :file
                  AND repo_id = :repo_id
                  AND org_id = :org_id
                UNION ALL
                SELECT fd.downstream_file, fd.upstream_file, c.depth + 1
                FROM file_dependencies fd
                JOIN chain c ON fd.upstream_file = c.downstream_file
                WHERE c.depth < :depth
                  AND fd.repo_id = :repo_id
                  AND fd.org_id = :org_id
            )
            SELECT downstream_file AS file, MIN(depth) AS depth
            FROM chain
            GROUP BY downstream_file
            ORDER BY MIN(depth)
        """)
        result = await session.execute(sql, {
            "file": file,
            "repo_id": repo_id,
            "depth": depth,
            "org_id": org_id,
        })
        return [{"file": row.file, "depth": row.depth} for row in result.mappings()]

    @staticmethod
    async def get_dependencies(
        session: AsyncSession,
        repo_id: str,
        file: str,
        depth: int = 3,
        org_id: str = "default",
    ) -> List[Dict]:
        """查询指定文件的下游依赖（它依赖哪些文件）。"""
        sql = text("""
            WITH RECURSIVE chain AS (
                SELECT downstream_file, upstream_file, 1 AS depth
                FROM file_dependencies
                WHERE downstream_file = :file
                  AND repo_id = :repo_id
                  AND org_id = :org_id
                UNION ALL
                SELECT fd.downstream_file, fd.upstream_file, c.depth + 1
                FROM file_dependencies fd
                JOIN chain c ON fd.downstream_file = c.upstream_file
                WHERE c.depth < :depth
                  AND fd.repo_id = :repo_id
                  AND fd.org_id = :org_id
            )
            SELECT upstream_file AS file, MIN(depth) AS depth
            FROM chain
            GROUP BY upstream_file
            ORDER BY MIN(depth)
        """)
        result = await session.execute(sql, {
            "file": file,
            "repo_id": repo_id,
            "depth": depth,
            "org_id": org_id,
        })
        return [{"file": row.file, "depth": row.depth} for row in result.mappings()]

    @staticmethod
    async def get_affected_files(
        session: AsyncSession,
        repo_id: str,
        changed_files: List[str],
        depth: int = 3,
        org_id: str = "default",
    ) -> Dict[str, List[Dict]]:
        """给定变更文件列表，返回每个文件的上游和下游影响面。"""
        result = {}
        for f in changed_files:
            result[f] = {
                "upstream": await CodeGraphRepository.get_callers(session, repo_id, f, depth, org_id),
                "downstream": await CodeGraphRepository.get_dependencies(session, repo_id, f, depth, org_id),
            }
        return result
