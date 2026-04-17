from abc import ABC, abstractmethod
from typing import Dict


class LLMProvider(ABC):
    """统一 LLM 提供商接口"""

    @abstractmethod
    async def review(self, prompt: str, model: str, system_prompt: str | None = None) -> Dict:
        pass

    @abstractmethod
    async def generate_text(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """通用文本生成接口，不强制 JSON 输出，返回原始文本。"""
        pass
