import logging

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import get_db
from services.settings_service import (
    get_all_settings,
    set_setting,
    SETTINGS_SCHEMA,
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

logger = logging.getLogger(__name__)

async def _require_admin_key(api_key: str = Security(api_key_header)) -> None:
    expected = settings.admin_api_key
    if expected and api_key != expected:
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
