import os

from llm.openai_compat import OpenAICompatibleProvider


class QwenProvider(OpenAICompatibleProvider):

    def __init__(self, api_key: str | None = None):
        super().__init__(
            api_key=api_key or os.getenv("QWEN_API_KEY", ""),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            default_model="qwen-coder-plus-latest",
        )
