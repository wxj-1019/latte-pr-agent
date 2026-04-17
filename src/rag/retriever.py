import logging
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from rag.embedder import EmbeddingClient
from rag.repository import BugKnowledgeRepository

logger = logging.getLogger(__name__)


class RAGRetriever:
    """基于 PR diff 检索相似历史 Bug 的 RAG 检索器。"""

    def __init__(self, embedder: Optional[EmbeddingClient] = None):
        self.embedder = embedder or EmbeddingClient()

    async def retrieve(
        self,
        session: AsyncSession,
        pr_diff_text: str,
        repo_id: str,
        limit: int = 3,
        min_similarity: float = 0.75,
        org_id: str = "default",
    ) -> List[Dict]:
        """对 PR diff 生成 embedding，检索相似历史 Bug。"""
        logger.info("RAG retrieving for repo=%s limit=%d", repo_id, limit)
        truncated = pr_diff_text[:12000]
        embedding = await self.embedder.embed(truncated)
        results = await BugKnowledgeRepository.search_similar(
            session=session,
            embedding=embedding,
            repo_id=repo_id,
            limit=limit,
            min_similarity=min_similarity,
            org_id=org_id,
        )
        logger.info("RAG retrieved %d similar bugs for repo=%s", len(results), repo_id)
        return results
