from config import settings
from llm.openai_compat import OpenAICompatibleProvider


def _deepseek_key() -> str:
    return settings.deepseek_api_key.get_secret_value()


class DeepSeekProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or _deepseek_key(),
            base_url="https://api.deepseek.com",
            default_model="deepseek-chat",
            _get_api_key=_deepseek_key,
        )
