import os
from pathlib import Path

from pydantic import field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_env = os.getenv("APP_ENV", "development").lower()
_env_override = f".env.{_env}" if os.path.exists(f".env.{_env}") else None

_env_files = [".env"]
if _env_override:
    _env_files.append(_env_override)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files,
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
    log_format: str = "text"
    log_file: str = ""
    max_concurrent_reviews: int = 20
    enable_reasoner_review: bool = False
    cors_origins: str = "*"
    admin_api_key: str = ""
    repos_base_path: str = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.repos_base_path.strip():
            self.repos_base_path = self._default_repos_path()

    @staticmethod
    def _default_repos_path() -> str:
        home = Path.home()
        default = home / ".latte-pr-agent" / "repos"
        default.mkdir(parents=True, exist_ok=True)
        return str(default)

    def get_repos_base_path(self) -> str:
        raw = self.repos_base_path.strip()
        if raw:
            resolved = Path(raw).resolve()
            resolved.mkdir(parents=True, exist_ok=True)
            return str(resolved)
        return self._default_repos_path()

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_env(cls, v):
        if isinstance(v, str):
            return v.lower().strip()
        return v

    def get_cors_origins(self) -> list[str]:
        """根据环境自动推断 CORS origins。

        - 生产环境：必须显式配置，不能为 * 或空
        - 开发环境：未配置时自动展开为常见本地端口
        """
        raw = self.cors_origins.strip()
        if raw and raw != "*":
            return [o.strip() for o in raw.split(",") if o.strip()]

        if self.app_env == "production":
            raise RuntimeError(
                "生产环境必须显式配置 CORS_ORIGINS，"
                "例如：CORS_ORIGINS=https://your-domain.com"
            )

        # 开发环境默认值
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    def get_docs_urls(self) -> dict:
        """根据环境返回 API 文档配置。"""
        if self.app_env == "production":
            return {"docs_url": None, "redoc_url": None, "openapi_url": None}
        return {
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        }


settings = Settings()
