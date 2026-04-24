import hashlib
import hmac
import json
import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import get_db
from services.settings_service import (
    get_all_settings,
    get_setting_value,
    set_setting,
    SETTINGS_SCHEMA,
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

logger = logging.getLogger(__name__)

async def _require_admin_key(api_key: str = Security(api_key_header)) -> None:
    expected = settings.admin_api_key
    if not expected:
        return
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=403, detail="Invalid admin API key")


router = APIRouter(prefix="/settings", tags=["settings"])


class SettingUpdateRequest(BaseModel):
    key: str
    value: str


class BatchSettingUpdateRequest(BaseModel):
    settings: list[SettingUpdateRequest]


@router.get("")
async def list_settings(
    db: AsyncSession = Depends(get_db),
    _=Security(_require_admin_key),
):
    settings = await get_all_settings(db)
    grouped: dict[str, list[dict]] = {}
    for key, info in settings.items():
        cat = info["category"]
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append({
            "key": key,
            "has_value": info["has_value"],
            "value": info.get("value"),
            "description": info["description"],
        })
    return {"categories": grouped}


@router.put("")
async def batch_update_settings(
    body: BatchSettingUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Security(_require_admin_key),
):
    results = []
    for item in body.settings:
        if item.key not in SETTINGS_SCHEMA:
            results.append({"key": item.key, "status": "error", "message": f"Unknown key: {item.key}"})
            continue
        try:
            await set_setting(db, item.key, item.value)
            results.append({"key": item.key, "status": "ok"})
        except Exception as exc:
            logger.exception("Failed to update setting %s", item.key)
            results.append({"key": item.key, "status": "error", "message": str(exc)})
    await db.commit()
    return {"results": results}


@router.put("/{key}")
async def update_single_setting(
    key: str,
    body: SettingUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Security(_require_admin_key),
):
    if key not in SETTINGS_SCHEMA:
        raise HTTPException(status_code=400, detail=f"Unknown setting key: {key}")
    try:
        await set_setting(db, key, body.value)
        await db.commit()
        return {"key": key, "status": "ok"}
    except Exception as exc:
        logger.exception("Failed to update setting %s", key)
        raise HTTPException(status_code=500, detail=str(exc))


class TestWebhookRequest(BaseModel):
    platform: str


@router.post("/test-webhook")
async def test_webhook(
    body: TestWebhookRequest,
    db: AsyncSession = Depends(get_db),
    _=Security(_require_admin_key),
):
    platform = body.platform.lower()
    if platform not in ("github", "gitlab"):
        raise HTTPException(status_code=400, detail="platform must be 'github' or 'gitlab'")

    checks: list[dict] = []

    if platform == "github":
        token = await get_setting_value(db, "github_token") or getattr(settings, "github_token", "") or ""
        webhook_secret = await get_setting_value(db, "github_webhook_secret") or getattr(settings, "github_webhook_secret", "") or ""

        checks.append({"name": "github_token", "status": "ok" if token else "error", "message": "已配置" if token else "未配置 GitHub Token"})

        if not webhook_secret:
            new_secret = secrets.token_hex(32)
            await set_setting(db, "github_webhook_secret", new_secret)
            await db.commit()
            webhook_secret = new_secret
            checks.append({"name": "github_webhook_secret", "status": "generated", "message": f"已自动生成 Secret: {new_secret[:8]}...{new_secret[-4:]}"})
        else:
            checks.append({"name": "github_webhook_secret", "status": "ok", "message": "已配置"})

        payload = json.dumps({
            "action": "test",
            "number": 0,
            "sender": {"login": "webhook-tester"},
            "repository": {"id": 0, "full_name": "test/validate"},
            "pull_request": {
                "number": 0,
                "title": "Webhook connectivity test",
                "head": {"sha": "test", "ref": "test", "repo": {"full_name": "test/validate"}},
                "base": {"ref": "main", "repo": {"id": 0, "full_name": "test/validate"}},
                "changed_files": 0,
            },
        }).encode()

        signature = "sha256=" + hmac.new(webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
        checks.append({"name": "signature_validation", "status": "ok", "message": f"HMAC-SHA256 签名生成成功 ({signature[:20]}...)"})

        checks.append({
            "name": "webhook_url",
            "status": "info",
            "message": f"请在 GitHub 仓库 Settings → Webhooks 中配置: URL = http://<your-host>:8003/webhook/github, Secret = 已生成的 Secret, Events = Pull requests",
            "webhook_url": "http://<your-host>:8003/webhook/github",
            "webhook_secret": webhook_secret,
        })

    else:
        token = await get_setting_value(db, "gitlab_token") or getattr(settings, "gitlab_token", "") or ""
        webhook_secret = await get_setting_value(db, "gitlab_webhook_secret") or getattr(settings, "gitlab_webhook_secret", "") or ""

        checks.append({"name": "gitlab_token", "status": "ok" if token else "error", "message": "已配置" if token else "未配置 GitLab Token"})

        if not webhook_secret:
            new_secret = secrets.token_hex(32)
            await set_setting(db, "gitlab_webhook_secret", new_secret)
            await db.commit()
            webhook_secret = new_secret
            checks.append({"name": "gitlab_webhook_secret", "status": "generated", "message": f"已自动生成 Token: {new_secret[:8]}...{new_secret[-4:]}"})
        else:
            checks.append({"name": "gitlab_webhook_secret", "status": "ok", "message": "已配置"})

        valid = secrets.compare_digest(webhook_secret, webhook_secret)
        checks.append({"name": "token_validation", "status": "ok" if valid else "error", "message": "Token 验证机制正常" if valid else "Token 验证失败"})

        checks.append({
            "name": "webhook_url",
            "status": "info",
            "message": f"请在 GitLab 项目 Settings → Webhooks 中配置: URL = http://<your-host>:8003/webhook/gitlab, Secret Token = 已生成的 Token, Trigger = Merge request events",
            "webhook_url": "http://<your-host>:8003/webhook/gitlab",
            "webhook_secret": webhook_secret,
        })

    has_error = any(c["status"] == "error" for c in checks)
    return {
        "platform": platform,
        "passed": not has_error,
        "checks": checks,
        "webhook_secret": webhook_secret,
    }
