import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from prompts.registry import PromptRegistry
from prompts.optimizer import AutoPromptOptimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompts", tags=["prompts"])


class SavePromptRequest(BaseModel):
    version: str
    text: str
    metadata: dict | None = None


class OptimizeRequest(BaseModel):
    base_version: str = "v1"
    new_version: str = "v2"
    min_samples: int = 10


def _fallback_versions(registry: PromptRegistry) -> list:
    return [
        {
            "id": idx + 1,
            "version": v,
            "is_active": True,
            "is_baseline": v == "v1",
            "ab_ratio": 0.5,
            "accuracy": 0.88,
            "repo_count": 0,
            "content": registry.get_text(v)[:200],
            "created_at": "2026-04-18T00:00:00+08:00",
        }
        for idx, v in enumerate(registry.list_versions())
    ]


@router.get("/versions")
async def list_versions(db: AsyncSession = Depends(get_db)) -> list:
    registry = PromptRegistry(db)
    try:
        await registry.load_from_db()
        return await registry.list_versions_enriched()
    except (OSError, ConnectionError):
        logger.warning("Failed to load prompts from DB, returning defaults", exc_info=True)
        return _fallback_versions(registry)


@router.get("/versions/{version}")
async def get_version(version: str, db: AsyncSession = Depends(get_db)) -> dict:
    registry = PromptRegistry(db)
    try:
        await registry.load_from_db()
    except (OSError, ConnectionError):
        logger.warning("Failed to load prompts from DB", exc_info=True)
    pv = registry.get(version)
    if not pv:
        raise HTTPException(status_code=404, detail="Prompt 版本不存在")
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
    try:
        registry = PromptRegistry(db)
        await registry.save_version(req.version, req.text, req.metadata)
        return {"message": "已保存", "version": req.version}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save prompt version %s: %s", req.version, exc)
        raise HTTPException(status_code=500, detail=f"保存 Prompt 失败: {exc}")


@router.post("")
async def save_version_alias(
    req: SavePromptRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await save_version(req, db)


@router.post("/optimize")
async def optimize_prompt(
    req: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        optimizer = AutoPromptOptimizer(db)
        result = await optimizer.analyze_and_optimize(
            base_version=req.base_version,
            new_version=req.new_version,
            min_samples=req.min_samples,
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to optimize prompt: %s", exc)
        raise HTTPException(status_code=500, detail=f"优化 Prompt 失败: {exc}")


@router.delete("/versions/{version}")
async def delete_version(version: str, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        if version == "v1":
            raise HTTPException(status_code=400, detail="不允许删除默认版本 v1")
        registry = PromptRegistry(db)
        await registry.load_from_db()
        deleted = await registry.delete_version(version)
        if not deleted:
            raise HTTPException(status_code=404, detail="Prompt 版本不存在")
        return {"message": f"已删除版本 {version}", "version": version}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete prompt version %s: %s", version, exc)
        raise HTTPException(status_code=500, detail=f"删除 Prompt 版本失败: {exc}")


@router.post("/generate-for-project/{project_id}")
async def generate_project_prompt(
    project_id: int,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        from models.project_repo import ProjectRepo
        from sqlalchemy import select
        from prompts.project_prompt_generator import ProjectPromptGenerator

        result = await db.execute(select(ProjectRepo).where(ProjectRepo.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        generator = ProjectPromptGenerator(db)
        version = await generator.generate(project, force=force)
        if not version:
            # 可能是不满足进化条件而跳过
            return {"message": "已是最新版本，无需重新生成", "version": None}
        return {"message": "已生成", "version": version}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to generate project prompt for project %s: %s", project_id, exc)
        raise HTTPException(status_code=500, detail=f"生成项目 Prompt 失败: {exc}")
