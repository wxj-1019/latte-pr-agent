from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from config.project_config import ProjectConfigService

router = APIRouter(prefix="/configs", tags=["configs"])


@router.get("/{repo_id}")
async def get_config(repo_id: str, db: AsyncSession = Depends(get_db)):
    service = ProjectConfigService(db)
    config = await service.get_config(platform="github", repo_id=repo_id)
    if not config:
        # Return empty config structure instead of 404
        return {
            "repo_id": repo_id,
            "platform": "github",
            "config_json": {},
        }
    return {**config, "repo_id": repo_id}


@router.put("/{repo_id}")
async def update_config(repo_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    service = ProjectConfigService(db)
    try:
        result = await service.upsert_config(platform="github", repo_id=repo_id, config_json=body)
        return {
            "repo_id": repo_id,
            "platform": "github",
            "config_json": result.config_json,
            "updated_at": result.updated_at,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
