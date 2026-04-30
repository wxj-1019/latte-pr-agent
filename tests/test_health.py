from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    with patch("main._redis_client", new=AsyncMock()):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "env" in data
