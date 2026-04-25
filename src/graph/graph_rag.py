import logging
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from rag.embedder import EmbeddingClient

logger = logging.getLogger(__name__)


class GraphRAGRetriever:
    """GraphRAG：结合向量检索 + 图遍历的代码上下文检索器。"""

    def __init__(
        self,
        session: AsyncSession,
        embedder: Optional[EmbeddingClient] = None,
    ):
        self.session = session
        self._embedder = embedder

    def _get_embedder(self) -> EmbeddingClient:
        if self._embedder is None:
            self._embedder = EmbeddingClient()
        return self._embedder

    async def retrieve(
        self,
        repo_id: str,
        query: str,
        changed_files: Optional[List[str]] = None,
        depth: int = 2,
        top_k: int = 10,
        org_id: str = "default",
    ) -> List[Dict]:
        """检索与查询和变更文件相关的代码上下文。

        策略：
        1. 向量检索：找到语义相关的代码实体（种子）
        2. 变更感知：从变更文件获取直接影响实体（种子）
        3. 图扩展：从种子出发，沿边遍历 depth 层
        4. 去重排序
        """
        changed_files = changed_files or []
        seed_ids: List[int] = []

        # Step 1: 向量检索种子实体
        try:
            vector_seeds = await self._vector_search(repo_id, query, top_k=5, org_id=org_id)
            seed_ids.extend(vector_seeds)
        except Exception as exc:
            logger.warning("GraphRAG vector search failed: %s", exc)

        # Step 2: 从变更文件获取种子实体
        if changed_files:
            changed_entities = await self._get_changed_entities(repo_id, changed_files, org_id=org_id)
            seed_ids.extend(changed_entities)

        seed_ids = list(set(seed_ids))
        if not seed_ids:
            return []

        # Step 3: 图遍历扩展
        expanded = await self._graph_expand(repo_id, seed_ids, depth=depth, org_id=org_id)

        # Step 4: 排序（种子实体优先，然后按深度）
        expanded.sort(key=lambda x: (0 if x["id"] in seed_ids else 1, x.get("depth", 99)))

        return expanded[:top_k]

    async def _vector_search(
        self,
        repo_id: str,
        query: str,
        top_k: int = 5,
        org_id: str = "default",
    ) -> List[int]:
        """基于向量相似度搜索获取种子实体 ID。"""
        query_embedding = await self._get_embedder().embed(query)

        sql = text("""
            SELECT ce.id
            FROM code_entities ce
            JOIN code_entity_embeddings cee ON ce.id = cee.entity_id
            WHERE ce.repo_id = :repo_id
              AND ce.org_id = :org_id
            ORDER BY cee.embedding <=> :embedding::vector
            LIMIT :top_k
        """)
        result = await self.session.execute(
            sql,
            {
                "embedding": query_embedding,
                "repo_id": repo_id,
                "org_id": org_id,
                "top_k": top_k,
            },
        )
        return [row["id"] for row in result.mappings()]

    async def _get_changed_entities(
        self,
        repo_id: str,
        changed_files: List[str],
        org_id: str = "default",
    ) -> List[int]:
        """从变更文件列表获取相关实体 ID。"""
        if not changed_files:
            return []
        # SQLite 不支持 ANY 数组函数，使用 IN 占位符
        dialect = self.session.bind.dialect.name if self.session.bind else "postgresql"
        if dialect == "sqlite":
            placeholders = ",".join([f":f{i}" for i in range(len(changed_files))])
            sql = text(f"""
                SELECT id FROM code_entities
                WHERE repo_id = :repo_id
                  AND org_id = :org_id
                  AND file_path IN ({placeholders})
                LIMIT 20
            """)
            params = {"repo_id": repo_id, "org_id": org_id}
            for i, f in enumerate(changed_files):
                params[f"f{i}"] = f
        else:
            sql = text("""
                SELECT id FROM code_entities
                WHERE repo_id = :repo_id
                  AND org_id = :org_id
                  AND file_path = ANY(:changed_files)
                LIMIT 20
            """)
            params = {
                "repo_id": repo_id,
                "org_id": org_id,
                "changed_files": changed_files,
            }
        result = await self.session.execute(sql, params)
        return [row["id"] for row in result.mappings()]

    async def _graph_expand(
        self,
        repo_id: str,
        seed_ids: List[int],
        depth: int = 2,
        org_id: str = "default",
    ) -> List[Dict]:
        """从种子实体出发，沿图边遍历扩展。使用 PostgreSQL 递归 CTE。
        SQLite 回退：仅返回种子实体（不支持递归 CTE + 数组操作）。"""
        if not seed_ids:
            return []

        dialect = self.session.bind.dialect.name if self.session.bind else "postgresql"
        if dialect == "sqlite":
            # SQLite fallback: return seeds + direct neighbors only
            placeholders = ",".join([f":s{i}" for i in range(len(seed_ids))])
            sql = text(f"""
                SELECT
                    ce.id,
                    ce.name,
                    ce.entity_type,
                    ce.file_path,
                    ce.signature,
                    ce.start_line,
                    ce.meta_json,
                    0 AS depth
                FROM code_entities ce
                WHERE ce.id IN ({placeholders})
                  AND ce.repo_id = :repo_id
                  AND ce.org_id = :org_id
                UNION
                SELECT
                    ce.id,
                    ce.name,
                    ce.entity_type,
                    ce.file_path,
                    ce.signature,
                    ce.start_line,
                    ce.meta_json,
                    1 AS depth
                FROM code_relationships cr
                JOIN code_entities ce ON
                    (ce.id = cr.target_entity_id AND cr.source_entity_id IN ({placeholders}))
                    OR (ce.id = cr.source_entity_id AND cr.target_entity_id IN ({placeholders}))
                WHERE cr.repo_id = :repo_id
                  AND cr.org_id = :org_id
            """)
            params: Dict = {"repo_id": repo_id, "org_id": org_id}
            for i, sid in enumerate(seed_ids):
                params[f"s{i}"] = sid
            result = await self.session.execute(sql, params)
            rows = [dict(r) for r in result.mappings()]
            # deduplicate
            seen = set()
            deduped = []
            for row in rows:
                if row["id"] not in seen:
                    seen.add(row["id"])
                    deduped.append(row)
            rows = deduped
        else:
            sql = text("""
                WITH RECURSIVE graph_search AS (
                    SELECT
                        ce.id,
                        ce.name,
                        ce.entity_type,
                        ce.file_path,
                        ce.signature,
                        ce.start_line,
                        ce.meta_json,
                        0 AS depth,
                        ARRAY[ce.id] AS path
                    FROM code_entities ce
                    WHERE ce.id = ANY(:seed_ids)
                      AND ce.repo_id = :repo_id
                      AND ce.org_id = :org_id

                    UNION

                    SELECT
                        ce.id,
                        ce.name,
                        ce.entity_type,
                        ce.file_path,
                        ce.signature,
                        ce.start_line,
                        ce.meta_json,
                        gs.depth + 1,
                        gs.path || ce.id
                    FROM graph_search gs
                    JOIN code_relationships cr ON
                        (cr.source_entity_id = gs.id OR cr.target_entity_id = gs.id)
                    JOIN code_entities ce ON
                        (ce.id = cr.target_entity_id AND cr.source_entity_id = gs.id)
                        OR (ce.id = cr.source_entity_id AND cr.target_entity_id = gs.id)
                    WHERE gs.depth < :max_depth
                      AND ce.repo_id = :repo_id
                      AND ce.org_id = :org_id
                      AND NOT ce.id = ANY(gs.path)
                )
                SELECT DISTINCT ON (id)
                    id, name, entity_type, file_path, signature, start_line, meta_json, depth
                FROM graph_search
                ORDER BY id, depth
            """)
            result = await self.session.execute(
                sql,
                {
                    "seed_ids": seed_ids,
                    "repo_id": repo_id,
                    "org_id": org_id,
                    "max_depth": depth,
                },
            )
            rows = [dict(r) for r in result.mappings()]

        for row in rows:
            if row.get("meta_json") is None:
                row["meta_json"] = {}
        return rows
