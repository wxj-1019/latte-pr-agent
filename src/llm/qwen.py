from config import settings
from llm.openai_compat import OpenAICompatibleProvider


def _qwen_key() -> str:
    return settings.qwen_api_key.get_secret_value()


class QwenProvider(OpenAICompatibleProvider):

    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or _qwen_key(),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            default_model="qwen-coder-plus-latest",
            _get_api_key=_qwen_key,
        )
