import logging
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from rag.embedder import EmbeddingClient

logger = logging.getLogger(__name__)


class SemanticCodeSearch:
    """基于向量相似度的语义代码搜索。"""

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

    async def search(
        self,
        repo_id: str,
        query: str,
        entity_type: Optional[str] = None,
        top_k: int = 10,
        org_id: str = "default",
    ) -> List[Dict]:
        """语义搜索代码实体，返回最相关的实体列表（含邻居信息）。"""
        try:
            query_embedding = await self._get_embedder().embed(query)
        except Exception as exc:
            logger.warning("Embedding generation failed for query '%s': %s", query, exc)
            return []

        sql = text("""
            SELECT
                ce.id,
                ce.name,
                ce.entity_type,
                ce.file_path,
                ce.start_line,
                ce.signature,
                ce.meta_json,
                1 - (cee.embedding <=> :embedding::vector) as similarity
            FROM code_entities ce
            JOIN code_entity_embeddings cee ON ce.id = cee.entity_id
            WHERE ce.repo_id = :repo_id
              AND ce.org_id = :org_id
              AND (:entity_type IS NULL OR ce.entity_type = :entity_type)
            ORDER BY cee.embedding <=> :embedding::vector
            LIMIT :top_k
        """)
        result = await self.session.execute(
            sql,
            {
                "embedding": query_embedding,
                "repo_id": repo_id,
                "org_id": org_id,
                "entity_type": entity_type,
                "top_k": top_k,
            },
        )
        rows = [dict(r) for r in result.mappings()]

        # 补充邻居信息
        for row in rows:
            row["neighbors"] = await self._get_neighbors(
                repo_id, row["id"], limit=3, org_id=org_id
            )

        return rows

    async def _get_neighbors(
        self,
        repo_id: str,
        entity_id: int,
        limit: int = 3,
        org_id: str = "default",
    ) -> List[Dict]:
        """获取实体的直接邻居（调用/被调用、继承等）。"""
        sql = text("""
            SELECT
                ce.id,
                ce.name,
                ce.entity_type,
                ce.file_path,
                cr.relation_type
            FROM code_relationships cr
            JOIN code_entities ce ON
                (ce.id = cr.target_entity_id AND cr.source_entity_id = :entity_id)
                OR (ce.id = cr.source_entity_id AND cr.target_entity_id = :entity_id)
            WHERE cr.repo_id = :repo_id
              AND cr.org_id = :org_id
            LIMIT :limit
        """)
        result = await self.session.execute(
            sql,
            {
                "entity_id": entity_id,
                "repo_id": repo_id,
                "org_id": org_id,
                "limit": limit,
            },
        )
        return [dict(r) for r in result.mappings()]
