import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from config.project_config import ProjectConfigService
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/configs", tags=["configs"])


class ConfigUpdateRequest(BaseModel):
    config_json: dict


class ConfigResponse(BaseModel):
    repo_id: str
    platform: str = "github"
    config_json: dict
    updated_at: Optional[str] = None


class VerifyRequest(BaseModel):
    repo_id: str
    platform: str = "github"


class VerifyCheckResult(BaseModel):
    name: str
    status: str
    message: str


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


@router.post("/verify")
async def verify_project_config(body: VerifyRequest):
    checks: list[VerifyCheckResult] = []

    # 1. Git platform token
    if body.platform == "github":
        token = settings.github_token.get_secret_value()
        if not token:
            checks.append(VerifyCheckResult(
                name="github_token", status="error",
                message="GitHub Token not configured. Please set GITHUB_TOKEN in .env",
            ))
        else:
            try:
                from github import Github
                client = Github(token)
                repo = client.get_repo(body.repo_id)
                checks.append(VerifyCheckResult(
                    name="github_token", status="ok",
                    message=f"Connected to {repo.full_name} ({repo.visibility})",
                ))
            except Exception as exc:
                checks.append(VerifyCheckResult(
                    name="github_token", status="error",
                    message=f"Cannot access repository: {exc}",
                ))
    elif body.platform == "gitlab":
        token = settings.gitlab_token.get_secret_value()
        if not token:
            checks.append(VerifyCheckResult(
                name="gitlab_token", status="error",
                message="GitLab Token not configured. Please set GITLAB_TOKEN in .env",
            ))
        else:
            try:
                import gitlab
                gl = gitlab.Gitlab(settings.gitlab_url, private_token=token)
                project = gl.projects.get(body.repo_id)
                checks.append(VerifyCheckResult(
                    name="gitlab_token", status="ok",
                    message=f"Connected to {project.path_with_namespace}",
                ))
            except Exception as exc:
                checks.append(VerifyCheckResult(
                    name="gitlab_token", status="error",
                    message=f"Cannot access project: {exc}",
                ))

    # 2. Webhook secret
    if body.platform == "github":
        secret = settings.github_webhook_secret
        if secret:
            checks.append(VerifyCheckResult(
                name="webhook_secret", status="ok",
                message="Webhook secret configured",
            ))
        else:
            checks.append(VerifyCheckResult(
                name="webhook_secret", status="warning",
                message="Webhook secret not set. Webhook verification will be skipped",
            ))
    elif body.platform == "gitlab":
        secret = settings.gitlab_webhook_secret
        if secret:
            checks.append(VerifyCheckResult(
                name="webhook_secret", status="ok",
                message="Webhook secret configured",
            ))
        else:
            checks.append(VerifyCheckResult(
                name="webhook_secret", status="warning",
                message="Webhook secret not set",
            ))

    # 3. LLM API Key
    llm_keys = {
        "deepseek": settings.deepseek_api_key.get_secret_value(),
        "anthropic": settings.anthropic_api_key.get_secret_value(),
        "openai": settings.openai_api_key.get_secret_value(),
        "qwen": settings.qwen_api_key.get_secret_value(),
    }
    available = [k for k, v in llm_keys.items() if v]
    if available:
        checks.append(VerifyCheckResult(
            name="llm_api_key", status="ok",
            message=f"Available models: {', '.join(available)}",
        ))
    else:
        checks.append(VerifyCheckResult(
            name="llm_api_key", status="error",
            message="No LLM API Key configured. Please set at least one of: DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, QWEN_API_KEY",
        ))

    # 4. Database connection
    try:
        from sqlalchemy import text
        from models.base import async_engine
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks.append(VerifyCheckResult(
            name="database", status="ok",
            message="Database connection successful",
        ))
    except Exception as exc:
        checks.append(VerifyCheckResult(
            name="database", status="error",
            message=f"Database connection failed: {exc}",
        ))

    # 5. Redis (optional)
    try:
        import redis.asyncio as aioredis
        redis_url = settings.redis_url.get_secret_value()
        r = aioredis.from_url(redis_url)
        await r.ping()
        await r.close()
        checks.append(VerifyCheckResult(
            name="redis", status="ok",
            message="Redis connection successful",
        ))
    except Exception:
        checks.append(VerifyCheckResult(
            name="redis", status="warning",
            message="Redis not available. Cache and queue features will be disabled",
        ))

    passed = all(c.status != "error" for c in checks)
    has_warning = any(c.status == "warning" for c in checks)

    return {
        "passed": passed,
        "has_warning": has_warning,
        "checks": [c.model_dump() for c in checks],
        "summary": "All checks passed" if passed and not has_warning
        else "Passed with warnings" if passed and has_warning
        else "Some checks failed",
    }
