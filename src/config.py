from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/code_review"
    sync_database_url: str = "postgresql://postgres:postgres@localhost:5432/code_review"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # GitHub
    github_token: str = ""
    github_webhook_secret: str = ""

    # GitLab
    gitlab_token: str = ""
    gitlab_webhook_secret: str = ""
    gitlab_url: str = "https://gitlab.com"

    # LLM
    deepseek_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    max_concurrent_reviews: int = 20
    enable_reasoner_review: bool = False


settings = Settings()
