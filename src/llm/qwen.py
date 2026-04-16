import asyncio
import json
import os
from typing import Dict

from openai import AsyncOpenAI
import json_repair

from llm.base import LLMProvider
from llm.prompts import REVIEW_SYSTEM_PROMPT


class QwenProvider(LLMProvider):
    """阿里云通义千问 (Qwen) 模型适配器，基于 OpenAI 兼容接口。"""

    def __init__(self, api_key: str | None = None):
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("QWEN_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    async def review(self, prompt: str, model: str = "qwen-coder-plus-latest", system_prompt: str | None = None) -> Dict:
        return await self._call_with_retry(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt or REVIEW_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=4000,
        )

    async def _call_with_retry(self, **kwargs) -> Dict:
        model = kwargs.pop("model")
        prompt = kwargs.pop("prompt")
        system_prompt = kwargs.pop("system_prompt")
        raw = ""
        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
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
