import pytest
from unittest.mock import patch

from models.system_settings import SystemSettings
from services.settings_service import (
    get_setting,
    set_setting,
    get_all_settings,
    get_effective_settings,
    apply_db_settings,
    SETTINGS_SCHEMA,
)
from utils.crypto import encrypt_value, decrypt_value


class TestCrypto:
    """Tests for Fernet encryption utilities."""

    def test_encrypt_decrypt_roundtrip(self):
        plain = "my-secret-token-123"
        cipher = encrypt_value(plain)
        assert cipher != plain
        assert decrypt_value(cipher) == plain

    def test_encrypt_empty_returns_empty(self):
        assert encrypt_value("") == ""

    def test_decrypt_empty_returns_none(self):
        assert decrypt_value("") is None

    def test_decrypt_garbage_returns_none(self):
        assert decrypt_value("not-a-valid-cipher") is None


class TestSettingsService:
    """Tests for settings CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_setting_missing(self, async_db_session):
        val = await get_setting(async_db_session, "nonexistent_key")
        assert val is None

    @pytest.mark.asyncio
    async def test_set_and_get_setting(self, async_db_session):
        await set_setting(async_db_session, "github_token", "gh_test_token")

        val = await get_setting(async_db_session, "github_token")
        assert val == "gh_test_token"

    @pytest.mark.asyncio
    async def test_set_setting_updates_existing(self, async_db_session):
        await set_setting(async_db_session, "github_token", "old_token")
        await async_db_session.flush()

        await set_setting(async_db_session, "github_token", "new_token")

        val = await get_setting(async_db_session, "github_token")
        assert val == "new_token"

    @pytest.mark.asyncio
    async def test_set_setting_unknown_key_raises(self, async_db_session):
        with pytest.raises(ValueError, match="Unknown setting key"):
            await set_setting(async_db_session, "unknown_key", "value")

    @pytest.mark.asyncio
    async def test_get_all_settings_includes_schema_keys(self, async_db_session):
        settings = await get_all_settings(async_db_session)
        for key in SETTINGS_SCHEMA:
            assert key in settings
            assert "has_value" in settings[key]
            assert "description" in settings[key]

    @pytest.mark.asyncio
    async def test_get_all_settings_secrets_hidden(self, async_db_session):
        await set_setting(async_db_session, "github_token", "secret")

        settings = await get_all_settings(async_db_session)
        # Secret values should not be returned in plaintext
        assert settings["github_token"]["value"] is None
        assert settings["github_token"]["has_value"] is True

    @pytest.mark.asyncio
    async def test_get_all_settings_non_secret_visible(self, async_db_session):
        await set_setting(async_db_session, "gitlab_url", "https://gitlab.example.com")

        settings = await get_all_settings(async_db_session)
        assert settings["gitlab_url"]["value"] == "https://gitlab.example.com"

    @pytest.mark.asyncio
    async def test_get_effective_settings_prefers_db(self, async_db_session):
        await set_setting(async_db_session, "github_token", "db_token")

        effective = await get_effective_settings(async_db_session)
        assert effective["github_token"] == "db_token"

    @pytest.mark.asyncio
    async def test_get_effective_settings_falls_back_to_env(self, async_db_session):
        effective = await get_effective_settings(async_db_session)
        # When DB has no value, should fall back to .env (empty string in tests)
        assert isinstance(effective["github_token"], str)

    @pytest.mark.asyncio
    async def test_apply_db_settings_updates_global(self, async_db_session):
        from config import settings

        original = settings.github_token.get_secret_value()
        await set_setting(async_db_session, "github_token", "applied_token")

        await apply_db_settings(async_db_session)
        assert settings.github_token.get_secret_value() == "applied_token"

        # Restore original
        settings.github_token = original


class TestSettingsAPI:
    """Tests for settings REST endpoints."""

    @pytest.mark.asyncio
    async def test_list_settings(self, async_client_with_db):
        resp = await async_client_with_db.get("/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data

    @pytest.mark.asyncio
    async def test_batch_update_settings(self, async_client_with_db):
        resp = await async_client_with_db.put(
            "/settings",
            json={"settings": [{"key": "github_token", "value": "gh_api_test"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["status"] == "ok"

        # Verify persisted
        resp2 = await async_client_with_db.get("/settings")
        cats = resp2.json()["categories"]
        platform_items = cats.get("platform", [])
        github_item = next((i for i in platform_items if i["key"] == "github_token"), None)
        assert github_item is not None
        assert github_item["has_value"] is True

    @pytest.mark.asyncio
    async def test_batch_update_unknown_key(self, async_client_with_db):
        resp = await async_client_with_db.put(
            "/settings",
            json={"settings": [{"key": "unknown_key", "value": "x"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["status"] == "error"

    @pytest.mark.asyncio
    async def test_update_single_setting(self, async_client_with_db):
        resp = await async_client_with_db.put(
            "/settings/gitlab_url",
            json={"key": "gitlab_url", "value": "https://gitlab.corp.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_update_single_setting_unknown_key(self, async_client_with_db):
        resp = await async_client_with_db.put(
            "/settings/unknown",
            json={"key": "unknown", "value": "x"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_admin_key_blocks_when_set(self, async_client_with_db):
        with patch("config.settings.admin_api_key", "secret123"):
            resp = await async_client_with_db.get("/settings")
            assert resp.status_code == 403

            resp2 = await async_client_with_db.get(
                "/settings", headers={"X-API-Key": "secret123"}
            )
            assert resp2.status_code == 200
