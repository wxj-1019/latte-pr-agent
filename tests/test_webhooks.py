import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from webhooks.verifier import WebhookVerifier
from webhooks.parser import WebhookParser
from webhooks.rate_limiter import RateLimiter


# ==================== Verifier Tests ====================

def test_verify_github_valid():
    payload = b'{"action":"opened"}'
    secret = "mysecret"
    expected_sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert WebhookVerifier.verify_github(payload, expected_sig, secret) is True


def test_verify_github_invalid():
    payload = b'{"action":"opened"}'
    assert WebhookVerifier.verify_github(payload, "sha256=invalid", "mysecret") is False


def test_verify_github_missing_signature():
    assert WebhookVerifier.verify_github(b"payload", "", "secret") is False


@pytest.mark.asyncio
async def test_github_webhook_missing_signature(client_with_db: TestClient):
    response = client_with_db.post(
        "/webhook/github",
        content=b'{}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401
    assert "Missing" in response.json()["detail"]


def test_verify_gitlab_valid():
    assert WebhookVerifier.verify_gitlab("token123", "token123") is True


def test_verify_gitlab_invalid():
    assert WebhookVerifier.verify_gitlab("token123", "token456") is False


# ==================== Parser Tests ====================

def test_parse_github():
    payload = {
        "action": "opened",
        "repository": {"full_name": "owner/repo"},
        "pull_request": {
            "number": 42,
            "title": "Test PR",
            "user": {"login": "testuser"},
            "head": {"sha": "abc123", "ref": "feature"},
            "base": {"ref": "main"},
            "changed_files": 3,
        },
    }
    parsed = WebhookParser.parse_github(payload)
    assert parsed["repo_id"] == "owner/repo"
    assert parsed["pr_number"] == 42
    assert parsed["head_sha"] == "abc123"
    assert parsed["changed_files"] == 3


def test_parse_gitlab():
    payload = {
        "object_kind": "merge_request",
        "object_attributes": {
            "iid": 7,
            "title": "Test MR",
            "author_id": 99,
            "source_branch": "feature",
            "target_branch": "main",
            "action": "open",
            "last_commit": {"id": "def456"},
            "changes_count": 5,
        },
        "project": {"id": 123, "name": "myproject"},
    }
    parsed = WebhookParser.parse_gitlab(payload)
    assert parsed["repo_id"] == "123"
    assert parsed["pr_number"] == 7
    assert parsed["head_sha"] == "def456"
    assert parsed["changed_files"] == 5


# ==================== Rate Limiter Tests ====================

def test_rate_limiter_normal_pr():
    allowed, msg = RateLimiter.check_pr_size(10)
    assert allowed is True
    assert msg == ""


def test_rate_limiter_oversize_files():
    allowed, msg = RateLimiter.check_pr_size(501)
    assert allowed is False
    assert "500" in msg


def test_rate_limiter_oversize_diff():
    big_diff = "x" * (51 * 1024 * 1024)
    allowed, msg = RateLimiter.check_pr_size(10, diff_content=big_diff)
    assert allowed is False
    assert "50MB" in msg


# ==================== Router Tests ====================

def _github_signature(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_github_webhook_invalid_signature(client_with_db: TestClient):
    from config import settings
    settings.github_webhook_secret = "test-secret"
    body = json.dumps({"action": "opened"}).encode()
    response = client_with_db.post(
        "/webhook/github",
        content=body,
        headers={
            "X-Hub-Signature-256": "sha256=bad",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_github_webhook_ignored_event(client_with_db: TestClient):
    from config import settings
    settings.github_webhook_secret = "test-secret"
    payload = {"action": "closed", "repository": {"full_name": "o/r"}, "pull_request": {"number": 1}}
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = _github_signature(body, settings.github_webhook_secret)
    response = client_with_db.post(
        "/webhook/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Event ignored"


@pytest.mark.asyncio
async def test_github_webhook_oversize_pr(client_with_db: TestClient):
    from config import settings
    settings.github_webhook_secret = "test-secret"
    payload = {
        "action": "opened",
        "repository": {"full_name": "o/r"},
        "pull_request": {"number": 1, "changed_files": 501},
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = _github_signature(body, settings.github_webhook_secret)
    response = client_with_db.post(
        "/webhook/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "skipped" in data["message"] or "500" in data["message"]
    assert "review_id" in data


@pytest.mark.asyncio
async def test_github_webhook_success(client_with_db: TestClient):
    from config import settings
    from unittest.mock import patch
    settings.github_webhook_secret = "test-secret"
    payload = {
        "action": "opened",
        "repository": {"full_name": "o/r"},
        "pull_request": {
            "number": 1,
            "title": "Test",
            "user": {"login": "u"},
            "head": {"sha": "sha1"},
            "changed_files": 2,
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = _github_signature(body, settings.github_webhook_secret)
    with patch("webhooks.router.run_review"):
        response = client_with_db.post(
            "/webhook/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Review queued"
    assert isinstance(data["review_id"], int)


@pytest.mark.asyncio
async def test_gitlab_webhook_invalid_token(client_with_db: TestClient):
    from config import settings
    settings.gitlab_webhook_secret = "test-secret"
    response = client_with_db.post(
        "/webhook/gitlab",
        json={},
        headers={"X-Gitlab-Token": "bad"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_gitlab_webhook_success(client_with_db: TestClient):
    from config import settings
    from unittest.mock import patch
    settings.gitlab_webhook_secret = "test-secret"
    payload = {
        "object_attributes": {
            "iid": 3,
            "title": "MR Test",
            "author_id": 10,
            "action": "open",
            "last_commit": {"id": "sha2"},
            "changes_count": 1,
        },
        "project": {"id": 99},
    }
    with patch("webhooks.router.run_review"):
        response = client_with_db.post(
            "/webhook/gitlab",
            json=payload,
            headers={"X-Gitlab-Token": settings.gitlab_webhook_secret},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Review queued"
    assert isinstance(data["review_id"], int)
