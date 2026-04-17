import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_list_versions(async_client_with_db):
    response = await async_client_with_db.get("/prompts/versions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_version_v1(async_client_with_db):
    response = await async_client_with_db.get("/prompts/versions/v1")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "v1"
    assert "text" in data


@pytest.mark.asyncio
async def test_get_version_not_found(async_client_with_db):
    response = await async_client_with_db.get("/prompts/versions/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_prompt_registry_default():
    from prompts.registry import PromptRegistry
    registry = PromptRegistry(session=None)
    assert "v1" in registry.list_versions()
    assert registry.get_text("v1") is not None


@pytest.mark.asyncio
async def test_prompt_registry_get_missing():
    from prompts.registry import PromptRegistry
    registry = PromptRegistry(session=None)
    text = registry.get_text("nonexistent")
    assert text == registry.get_text("v1")


@pytest.mark.asyncio
async def test_experiment_assignment_deterministic():
    from prompts.registry import PromptRegistry
    registry = PromptRegistry(session=None)
    registry._versions["v2"] = registry._versions.get("v1") or MagicMock()
    result = await registry.get_experiment_assignment("org/repo-a")
    result2 = await registry.get_experiment_assignment("org/repo-a")
    assert result == result2


@pytest.mark.asyncio
async def test_experiment_assignment_no_session():
    from prompts.registry import PromptRegistry
    registry = PromptRegistry(session=None)
    result = await registry.get_experiment_assignment("any/repo")
    assert result == "v1"
