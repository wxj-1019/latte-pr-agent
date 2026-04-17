from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from config.project_config import ProjectConfigService

router = APIRouter(prefix="/configs", tags=["configs"])


class ConfigUpdateRequest(BaseModel):
    config_json: dict


class ConfigResponse(BaseModel):
    repo_id: str
    platform: str = "github"
    config_json: dict
    updated_at: Optional[str] = None


@router.get("/{repo_id:path}")
async def get_config(repo_id: str, db: AsyncSession = Depends(get_db)):
    service = ProjectConfigService(db)
    config = await service.get_config(platform="github", repo_id=repo_id)
    if not config:
        return {
            "repo_id": repo_id,
            "platform": "github",
            "config_json": {},
        }
    return {**config, "repo_id": repo_id}


@router.put("/{repo_id:path}")
async def update_config(repo_id: str, body: ConfigUpdateRequest, db: AsyncSession = Depends(get_db)):
    service = ProjectConfigService(db)
    try:
        result = await service.upsert_config(platform="github", repo_id=repo_id, config_json=body.config_json)
        await db.commit()
        return {
            "repo_id": repo_id,
            "platform": "github",
            "config_json": result.config_json,
            "updated_at": result.updated_at,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
