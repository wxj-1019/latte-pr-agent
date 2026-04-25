import os
from typing import List

from openai import AsyncOpenAI

from config import settings


class EmbeddingClient:
    """封装文本 Embedding 生成服务（默认 OpenAI text-embedding-3-small，1536 维）。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        timeout: float = 30.0,
    ):
        self.model = model
        self.dimensions = dimensions
        self.client = AsyncOpenAI(
            api_key=api_key or settings.openai_api_key.get_secret_value() or os.getenv("OPENAI_API_KEY"),
            base_url=base_url,
            timeout=timeout,
        )

    async def embed(self, text: str) -> List[float]:
        result = await self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
        )
        return result.data[0].embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        result = await self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )
        return [item.embedding for item in result.data]
