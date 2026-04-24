from typing import Callable, Dict

from anthropic import AsyncAnthropic
import json_repair

from config import settings
from llm.base import LLMProvider
from llm.prompts import REVIEW_SYSTEM_PROMPT


def _anthropic_key() -> str:
    return settings.anthropic_api_key.get_secret_value()


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, _get_api_key: Callable[[], str] = _anthropic_key):
        self.client = AsyncAnthropic(
            api_key=api_key or _get_api_key()
        )
        self._get_api_key = _get_api_key

    def _refresh_api_key(self) -> None:
        self.client.api_key = self._get_api_key()

    async def generate_text(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        self._refresh_api_key()
        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=REVIEW_SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text

    async def review(self, prompt: str, model: str = "claude-3-5-sonnet-20241022", system_prompt: str | None = None) -> Dict:
        self._refresh_api_key()
        response = await self.client.messages.create(
            model=model,
            max_tokens=4000,
            system=system_prompt or REVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        # Extract ```json ... ``` block if present
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json_repair.loads(raw)
