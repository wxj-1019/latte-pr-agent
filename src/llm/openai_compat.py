import asyncio
import json
from typing import Callable, Dict

from openai import AsyncOpenAI, AuthenticationError
import json_repair

from llm.base import LLMProvider
from llm.prompts import REVIEW_SYSTEM_PROMPT


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容接口的通用基类，适用于 DeepSeek、Qwen 等使用 OpenAI SDK 的提供商。

    ``_get_api_key`` 是一个可选的 callable，每次调用前会用它刷新 client.api_key，
    确保即使 provider 在 apply_db_settings 之前创建，调用时也能拿到数据库中的真实 key。
    """

    def __init__(self, api_key: str, base_url: str, default_model: str, _get_api_key: Callable[[], str] | None = None):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._default_model = default_model
        self._get_api_key = _get_api_key

    async def review(self, prompt: str, model: str | None = None, system_prompt: str | None = None) -> Dict:
        self._refresh_api_key()
        return await self._call_with_retry(
            model=model or self._default_model,
            prompt=prompt,
            system_prompt=system_prompt or REVIEW_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=4000,
        )

    async def generate_text(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        self._refresh_api_key()
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def _refresh_api_key(self) -> None:
        if self._get_api_key:
            self.client.api_key = self._get_api_key()

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
            except AuthenticationError:
                raise  # 认证错误不重试
            except json.JSONDecodeError:
                if attempt == 2:
                    return {"error": "json 解析失败", "raw": raw, "issues": []}
                await asyncio.sleep(2 ** attempt)
            except (OSError, ConnectionError, TimeoutError):
                if attempt == 2:
                    return {"error": "api 调用失败", "raw": raw, "issues": []}
                await asyncio.sleep(2 ** attempt)
        return {"error": "超过最大重试次数", "raw": raw, "issues": []}
