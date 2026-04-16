from abc import ABC, abstractmethod
from typing import Dict


class LLMProvider(ABC):
    """统一 LLM 提供商接口"""

    @abstractmethod
    async def review(self, prompt: str, model: str) -> Dict:
        pass
