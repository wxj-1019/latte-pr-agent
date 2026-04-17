from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from prompts.registry import PromptRegistry
from prompts.optimizer import AutoPromptOptimizer

router = APIRouter(prefix="/prompts", tags=["prompts"])


class SavePromptRequest(BaseModel):
    version: str
    text: str
    metadata: dict | None = None


class OptimizeRequest(BaseModel):
    base_version: str = "v1"
    new_version: str = "v2"
    min_samples: int = 10


@router.get("/versions")
async def list_versions(db: AsyncSession = Depends(get_db)) -> list:
    registry = PromptRegistry(db)
    await registry.load_from_db()
    return await registry.list_versions_enriched()


@router.get("/versions/{version}")
async def get_version(version: str, db: AsyncSession = Depends(get_db)) -> dict:
    registry = PromptRegistry(db)
    await registry.load_from_db()
    pv = registry.get(version)
    if not pv:
        raise HTTPException(status_code=404, detail="Version not found")
    return {
        "version": pv.version,
        "text": pv.text,
        "metadata": pv.metadata,
    }


@router.post("/versions")
async def save_version(
    req: SavePromptRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    registry = PromptRegistry(db)
    await registry.save_version(req.version, req.text, req.metadata)
    return {"message": "Saved", "version": req.version}


@router.post("/optimize")
async def optimize_prompt(
    req: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    optimizer = AutoPromptOptimizer(db)
    result = await optimizer.analyze_and_optimize(
        base_version=req.base_version,
        new_version=req.new_version,
        min_samples=req.min_samples,
    )
    return result
