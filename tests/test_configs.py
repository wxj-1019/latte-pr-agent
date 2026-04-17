import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture
def mock_config_service():
    with patch("configs.router.ProjectConfigService") as MockService:
        instance = MockService.return_value
        yield instance


@pytest.mark.asyncio
async def test_get_config_empty(async_client_with_db, mock_config_service):
    mock_config_service.get_config = AsyncMock(return_value=None)

    response = await async_client_with_db.get("/configs/org/new-repo")
    assert response.status_code == 200
    data = response.json()
    assert data["repo_id"] == "org/new-repo"
    assert data["config_json"] == {}


@pytest.mark.asyncio
async def test_get_config_existing(async_client_with_db, mock_config_service):
    mock_config_service.get_config = AsyncMock(return_value={
        "config_json": {"review_config": {"language": "python"}},
        "platform": "github",
    })

    response = await async_client_with_db.get("/configs/org/repo")
    assert response.status_code == 200
    data = response.json()
    assert data["config_json"]["review_config"]["language"] == "python"


@pytest.mark.asyncio
async def test_update_config(async_client_with_db, mock_config_service):
    mock_result = MagicMock()
    mock_result.config_json = {"review_config": {"language": "python"}}
    mock_result.updated_at = "2026-04-18T00:00:00"
    mock_config_service.upsert_config = AsyncMock(return_value=mock_result)

    response = await async_client_with_db.put(
        "/configs/org/test-repo",
        json={"config_json": {"review_config": {"language": "python"}}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["repo_id"] == "org/test-repo"
    assert data["config_json"]["review_config"]["language"] == "python"


@pytest.mark.asyncio
async def test_update_config_missing_body(async_client_with_db):
    response = await async_client_with_db.put(
        "/configs/org/test-repo",
        json={},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_config_invalid_body(async_client_with_db):
    response = await async_client_with_db.put(
        "/configs/org/test-repo",
        json={"config_json": "not a dict"},
    )
    assert response.status_code == 422
