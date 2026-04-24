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


def _env_values() -> dict:
    """Read current .env values so the settings page can show them as fallback."""
    from config import settings

    def _get(val):
        # Tests may use plain str instead of SecretStr
        return val.get_secret_value() if hasattr(val, "get_secret_value") else (val or "")

    return {
        "github_token": _get(settings.github_token),
        "github_webhook_secret": _get(settings.github_webhook_secret),
        "gitlab_token": _get(settings.gitlab_token),
        "gitlab_webhook_secret": _get(settings.gitlab_webhook_secret),
        "gitlab_url": _get(settings.gitlab_url),
        "deepseek_api_key": _get(settings.deepseek_api_key),
        "anthropic_api_key": _get(settings.anthropic_api_key),
        "openai_api_key": _get(settings.openai_api_key),
        "qwen_api_key": _get(settings.qwen_api_key),
    }


async def get_setting(db: AsyncSession, key: str) -> Optional[str]:
    result = await db.execute(select(SystemSettings).where(SystemSettings.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return decrypt_value(row.encrypted_value)


async def get_all_settings(db: AsyncSession) -> dict:
    """Return all settings for the admin UI.

    For non-secret keys the raw value is returned (DB overrides .env).
    For secret keys the raw value is hidden, but ``has_value`` reflects
    whether a value exists in DB *or* .env so the UI can show a placeholder.
    """
    env_values = _env_values()
    result = await db.execute(select(SystemSettings))
    rows = result.scalars().all()

    settings_map = {}
    for row in rows:
        schema = SETTINGS_SCHEMA.get(row.key, {"secret": True})
        is_secret = schema.get("secret", True)
        db_has_value = bool(row.encrypted_value)
        env_val = env_values.get(row.key, "")
        env_has_value = bool(env_val)

        if is_secret:
            settings_map[row.key] = {
                "value": None,
                "has_value": db_has_value or env_has_value,
                "category": schema["category"],
                "description": schema["description"],
            }
        else:
            settings_map[row.key] = {
                "value": decrypt_value(row.encrypted_value) if db_has_value else env_val,
                "has_value": db_has_value or env_has_value,
                "category": schema["category"],
                "description": schema["description"],
            }

    # Fill missing keys from schema with .env fallback
    for key, schema in SETTINGS_SCHEMA.items():
        if key not in settings_map:
            env_val = env_values.get(key, "")
            is_secret = schema.get("secret", True)
            settings_map[key] = {
                "value": None if is_secret else env_val,
                "has_value": bool(env_val),
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


async def get_setting_value(db: AsyncSession, key: str) -> Optional[str]:
    env_values = _env_values()
    db_val = await get_setting(db, key)
    if db_val is not None:
        return db_val
    return env_values.get(key) or None


async def get_effective_settings(db: AsyncSession) -> dict:
    env_values = _env_values()
    effective = {}
    for key, env_val in env_values.items():
        db_val = await get_setting(db, key)
        effective[key] = db_val if db_val is not None else env_val
    return effective


async def apply_db_settings(db: AsyncSession) -> None:
    """Apply database overrides to the global settings object and os.environ.

    Safe for Celery workers (separate processes).  When running inside
    the FastAPI process via BackgroundTasks, multiple concurrent tasks
    may briefly see each other's tokens, but the window is small and
    the impact is limited to the review pipeline.

    Both `settings.*` and `os.environ` are updated so that code reading
    from either source picks up the correct value.  The env var is only
    overwritten when a real database value exists — placeholder values
    from .env are never propagated.
    """
    import os

    from pydantic import SecretStr
    from config import settings

    effective = await get_effective_settings(db)
    for key, value in effective.items():
        if not value:
            continue
        if key in ("github_token", "gitlab_token", "deepseek_api_key",
                   "anthropic_api_key", "openai_api_key", "qwen_api_key"):
            setattr(settings, key, SecretStr(value))
            os.environ[key.upper()] = value
        else:
            setattr(settings, key, value)
