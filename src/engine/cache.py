import hashlib
import json
from typing import Dict, Optional

import redis.asyncio as redis

from config import settings


class ReviewCache:
    """基于 diff hash 的审查结果缓存"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or redis.from_url(settings.redis_url)
        self.ttl_seconds = 3600  # 1 hour

    def _make_key(self, diff_content: str, prompt_version: str, model: str) -> str:
        content = f"{diff_content}|{prompt_version}|{model}"
        return f"review_cache:{hashlib.sha256(content.encode()).hexdigest()}"

    async def get(
        self, diff_content: str, prompt_version: str, model: str
    ) -> Optional[Dict]:
        key = self._make_key(diff_content, prompt_version, model)
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None

    async def set(
        self, diff_content: str, prompt_version: str, model: str, result: Dict
    ) -> None:
        key = self._make_key(diff_content, prompt_version, model)
        await self.redis.setex(key, self.ttl_seconds, json.dumps(result))
