from contextlib import asynccontextmanager
import logging
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from logging_config import setup_logging, request_id_var
from rate_limit import limiter
from webhooks.router import router as webhook_router
from feedback.router import router as feedback_router
from prompts.router import router as prompts_router
from reviews.router import router as reviews_router
from configs.router import router as configs_router
from stats.router import router as stats_router
from settings.router import router as settings_router
from projects.router import router as projects_router
from commits.router import router as commits_router
from models import get_db, Review

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    logger.info("Latte PR Agent startup complete [env=%s]", settings.app_env)
    yield
    logger.info("Latte PR Agent shutting down")


_cors_origins = settings.get_cors_origins()
_docs_url = settings.get_docs_urls()["docs_url"]
_redoc_url = settings.get_docs_urls()["redoc_url"]
_openapi_url = settings.get_docs_urls()["openapi_url"]

app = FastAPI(
    title="Latte PR Agent - AI 代码审查系统",
    description="企业级 AI 代码审查系统",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 X-Request-ID。"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)


# CORS 必须最后添加，确保它在 middleware 栈的最外层，
# 这样即使内部发生异常，CORS 头也能正确返回。
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器：确保 500 错误返回结构化 JSON 和 CORS 头。"""
    logger.exception("Unhandled exception: %s", exc)
    origin = request.headers.get("origin", "")
    headers: dict[str, str] = {}
    if origin in _cors_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    # 生产环境不暴露内部错误详情
    message = str(exc) if settings.app_env != "production" else "An unexpected error occurred"
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "message": message},
        headers=headers,
    )


app.include_router(webhook_router)
app.include_router(feedback_router)
app.include_router(prompts_router)
app.include_router(reviews_router)
app.include_router(configs_router)
app.include_router(stats_router)
app.include_router(settings_router)
app.include_router(projects_router)
app.include_router(commits_router)


@app.get("/health", tags=["health"])
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    health = {"status": "ok", "env": settings.app_env, "checks": {}}

    # Database check
    try:
        await db.execute(select(1))
        health["checks"]["database"] = "ok"
    except Exception as exc:
        logger.warning("Health check database failed: %s", exc)
        health["checks"]["database"] = "error"
        health["status"] = "degraded"

    # Redis check (async)
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(settings.redis_url.get_secret_value(), socket_connect_timeout=2)
        await redis_client.ping()
        await redis_client.aclose()
        health["checks"]["redis"] = "ok"
    except Exception as exc:
        logger.warning("Health check redis failed: %s", exc)
        health["checks"]["redis"] = "error"
        health["status"] = "degraded"

    return health


@app.get("/repos", tags=["repos"])
async def list_repos(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Review.repo_id).where(Review.platform != "direct").distinct()
    )
    repos = [row[0] for row in result.all() if row[0]]
    return {"repos": repos}
