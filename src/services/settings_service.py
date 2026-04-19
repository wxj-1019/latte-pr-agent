import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.system_settings import SystemSettings
from utils.crypto import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)

SETTINGS_SCHEMA = {
    "github_token": {"category": "platform", "description": "GitHub Personal Access Token", "secret": True},
    "github_webhook_secret": {"category": "platform", "description": "GitHub Webhook Secret", "secret": True},
    "gitlab_token": {"category": "platform", "description": "GitLab Personal Access Token", "secret": True},
    "gitlab_webhook_secret": {"category": "platform", "description": "GitLab Webhook Secret", "secret": True},
    "gitlab_url": {"category": "platform", "description": "GitLab URL", "secret": False},
    "deepseek_api_key": {"category": "llm", "description": "DeepSeek API Key", "secret": True},
    "anthropic_api_key": {"category": "llm", "description": "Anthropic API Key", "secret": True},
    "openai_api_key": {"category": "llm", "description": "OpenAI API Key", "secret": True},
    "qwen_api_key": {"category": "llm", "description": "Qwen API Key", "secret": True},
}


async def get_setting(db: AsyncSession, key: str) -> Optional[str]:
    result = await db.execute(select(SystemSettings).where(SystemSettings.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return decrypt_value(row.encrypted_value)


async def get_all_settings(db: AsyncSession) -> dict:
    result = await db.execute(select(SystemSettings))
    rows = result.scalars().all()
    settings_map = {}
    for row in rows:
        schema = SETTINGS_SCHEMA.get(row.key, {"secret": True})
        if schema.get("secret", True):
            settings_map[row.key] = {
                "value": None,
                "has_value": bool(row.encrypted_value),
                "category": row.category,
                "description": row.description,
            }
        else:
            settings_map[row.key] = {
                "value": decrypt_value(row.encrypted_value),
                "has_value": bool(row.encrypted_value),
                "category": row.category,
                "description": row.description,
            }
    for key, schema in SETTINGS_SCHEMA.items():
        if key not in settings_map:
            settings_map[key] = {
                "value": None,
                "has_value": False,
                "category": schema["category"],
                "description": schema["description"],
            }
    return settings_map


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    if key not in SETTINGS_SCHEMA:
        raise ValueError(f"Unknown setting key: {key}")
    schema = SETTINGS_SCHEMA[key]
    encrypted = encrypt_value(value) if value else ""
    result = await db.execute(select(SystemSettings).where(SystemSettings.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        row = SystemSettings(
            key=key,
            encrypted_value=encrypted,
            category=schema["category"],
            description=schema["description"],
        )
        db.add(row)
    else:
        row.encrypted_value = encrypted
        row.category = schema["category"]
        row.description = schema["description"]
    await db.flush()
    logger.info("Setting '%s' updated (category=%s)", key, schema["category"])


async def resolve_setting(db: AsyncSession, key: str, env_fallback: str = "") -> str:
    db_value = await get_setting(db, key)
    if db_value is not None:
        return db_value
    return env_fallback


async def get_effective_settings(db: AsyncSession) -> dict:
    from config import settings

    keys_map = {
        "github_token": settings.github_token.get_secret_value(),
        "github_webhook_secret": settings.github_webhook_secret,
        "gitlab_token": settings.gitlab_token.get_secret_value(),
        "gitlab_webhook_secret": settings.gitlab_webhook_secret,
        "gitlab_url": settings.gitlab_url,
        "deepseek_api_key": settings.deepseek_api_key.get_secret_value(),
        "anthropic_api_key": settings.anthropic_api_key.get_secret_value(),
        "openai_api_key": settings.openai_api_key.get_secret_value(),
        "qwen_api_key": settings.qwen_api_key.get_secret_value(),
    }

    effective = {}
    for key, env_val in keys_map.items():
        db_val = await get_setting(db, key)
        effective[key] = db_val if db_val is not None else env_val
    return effective


async def apply_db_settings(db: AsyncSession) -> None:
    """Apply database overrides to the global settings object.

    Safe for Celery workers (separate processes).  When running inside
    the FastAPI process via BackgroundTasks, multiple concurrent tasks
    may briefly see each other's tokens, but the window is small and
    the impact is limited to the review pipeline.
    """
    from pydantic import SecretStr
    from config import settings

    effective = await get_effective_settings(db)
    for key, value in effective.items():
        if not value:
            continue
        if key in ("github_token", "gitlab_token", "deepseek_api_key",
                   "anthropic_api_key", "openai_api_key", "qwen_api_key"):
            setattr(settings, key, SecretStr(value))
        else:
            setattr(settings, key, value)
