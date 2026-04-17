"""Tests for request_id middleware."""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestRequestIdMiddleware:
    def test_generates_request_id_when_absent(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0

    def test_preserves_provided_request_id(self, client):
        custom_id = "custom-req-id-12345"
        response = client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == custom_id

    def test_request_id_is_uuid_format_when_generated(self, client):
        response = client.get("/health")
        req_id = response.headers["X-Request-ID"]
        # UUID4 format: 8-4-4-4-12 hex digits
        parts = req_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12
