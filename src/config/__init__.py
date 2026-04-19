from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: SecretStr = SecretStr("postgresql+asyncpg://postgres:postgres@localhost:5432/code_review")
    sync_database_url: SecretStr = SecretStr("postgresql://postgres:postgres@localhost:5432/code_review")

    # Redis
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")

    # GitHub
    github_token: SecretStr = SecretStr("")
    github_webhook_secret: str = ""

    # GitLab
    gitlab_token: SecretStr = SecretStr("")
    gitlab_webhook_secret: str = ""
    gitlab_url: str = "https://gitlab.com"

    # LLM
    deepseek_api_key: SecretStr = SecretStr("")
    anthropic_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    qwen_api_key: SecretStr = SecretStr("")

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    max_concurrent_reviews: int = 20
    enable_reasoner_review: bool = False
    cors_origins: str = "*"
    admin_api_key: str = ""


settings = Settings()
