import os

from llm.openai_compat import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com",
            default_model="deepseek-chat",
        )
