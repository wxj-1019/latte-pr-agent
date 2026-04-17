from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


async def test_github_webhook_uses_celery_when_available(async_client_with_db):
    with patch("webhooks.router.get_celery_task") as mock_get_task:
        mock_task = MagicMock()
        mock_task.delay = MagicMock()
        mock_get_task.return_value = mock_task

        from config import settings
        settings.github_webhook_secret = "test-secret"
        import hashlib, hmac, json
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
        sig = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()

        response = await async_client_with_db.post(
            "/webhook/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        mock_task.delay.assert_called_once()


async def test_github_webhook_fallback_to_background_tasks_on_celery_error(async_client_with_db):
    with patch("webhooks.router.get_celery_task") as mock_get_task:
        mock_get_task.side_effect = ConnectionError("Redis down")

        from unittest.mock import patch as mock_patch
        with mock_patch("webhooks.router.run_review"):
            from config import settings
            settings.github_webhook_secret = "test-secret"
            import hashlib, hmac, json
            payload = {
                "action": "opened",
                "repository": {"full_name": "o/r"},
                "pull_request": {
                    "number": 2,
                    "title": "Test",
                    "user": {"login": "u"},
                    "head": {"sha": "sha2"},
                    "changed_files": 2,
                },
            }
            body = json.dumps(payload, separators=(",", ":")).encode()
            sig = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()

            response = await async_client_with_db.post(
                "/webhook/github",
                content=body,
                headers={
                    "X-Hub-Signature-256": sig,
                    "Content-Type": "application/json",
                },
            )

            assert response.status_code == 200
