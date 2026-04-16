import asyncio
import json
import os
from typing import Dict

from openai import AsyncOpenAI
import json_repair

from llm.base import LLMProvider

REVIEW_SYSTEM_PROMPT = """You are an expert code reviewer. Analyze the provided code diff and respond with a JSON object containing a list of issues found.

Required JSON format:
{
  "issues": [
    {
      "file": "path/to/file",
      "line": 42,
      "severity": "critical|warning|info",
      "category": "security|logic|performance|architecture|style",
      "description": "Clear description of the issue",
      "suggestion": "How to fix it",
      "confidence": 0.95,
      "evidence": "the exact code snippet",
      "reasoning": "why this is an issue"
    }
  ],
  "summary": "brief summary",
  "risk_level": "low|medium|high"
}

Be concise and accurate. If no issues are found, return an empty issues array."""


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
            except (json.JSONDecodeError, Exception):
                if attempt == 2:
                    return {"error": "json_parse_failed", "raw": raw if "raw" in dir() else "", "issues": []}
                await asyncio.sleep(2 ** attempt)
