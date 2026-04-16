import asyncio
import json
import os
from typing import Dict

from openai import AsyncOpenAI
import json_repair

from llm.base import LLMProvider
from llm.prompts import REVIEW_SYSTEM_PROMPT


class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str | None = None):
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )

    async def review(self, prompt: str, model: str = "deepseek-chat") -> Dict:
        return await self._call_with_retry(
            model=model,
            prompt=prompt,
            temperature=0.1,
            max_tokens=4000,
        )

    async def _call_with_retry(self, **kwargs) -> Dict:
        model = kwargs.pop("model")
        prompt = kwargs.pop("prompt")
        raw = ""
        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    **kwargs,
                )
                raw = response.choices[0].message.content or ""
                return json_repair.loads(raw)
            except json.JSONDecodeError:
                if attempt == 2:
                    return {"error": "json_parse_failed", "raw": raw, "issues": []}
                await asyncio.sleep(2 ** attempt)
            except Exception:
                if attempt == 2:
                    return {"error": "api_call_failed", "raw": raw, "issues": []}
                await asyncio.sleep(2 ** attempt)
