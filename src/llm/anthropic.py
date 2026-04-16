import os
from typing import Dict

from anthropic import AsyncAnthropic
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


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None = None):
        self.client = AsyncAnthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

    async def review(self, prompt: str, model: str = "claude-3-5-sonnet-20241022") -> Dict:
        response = await self.client.messages.create(
            model=model,
            max_tokens=4000,
            system=REVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        # Extract ```json ... ``` block if present
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json_repair.loads(raw)
