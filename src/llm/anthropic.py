import os
from typing import Dict

from anthropic import AsyncAnthropic
import json_repair

from llm.base import LLMProvider
from llm.prompts import REVIEW_SYSTEM_PROMPT


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None = None):
        self.client = AsyncAnthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

    async def review(self, prompt: str, model: str = "claude-3-5-sonnet-20241022", system_prompt: str | None = None) -> Dict:
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
