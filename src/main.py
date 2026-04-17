from contextlib import asynccontextmanager
import logging
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from logging_config import setup_logging, request_id_var
from rate_limit import limiter
from webhooks.router import router as webhook_router
from feedback.router import router as feedback_router
from prompts.router import router as prompts_router
from reviews.router import router as reviews_router
from configs.router import router as configs_router
from stats.router import router as stats_router
from models import get_db, Review

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    logger.info("Latte PR Agent startup complete [env=%s]", settings.app_env)
    yield
    logger.info("Latte PR Agent shutting down")


_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

if "*" in _cors_origins:
    if settings.app_env == "production":
        raise RuntimeError(
            "CORS_ORIGINS cannot be '*' in production when allow_credentials=True. "
            "Set CORS_ORIGINS to an explicit domain whitelist."
        )
    logger.warning("CORS_ORIGINS='*' with credentials; expanding to common dev origins")
    _cors_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

_docs_url = "/docs" if settings.app_env != "production" else None
_redoc_url = "/redoc" if settings.app_env != "production" else None
_openapi_url = "/openapi.json" if settings.app_env != "production" else None

app = FastAPI(
    title="Latte PR Agent",
    description="Enterprise AI Code Review System",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)


app.include_router(webhook_router)
app.include_router(feedback_router)
app.include_router(prompts_router)
app.include_router(reviews_router)
app.include_router(configs_router)
app.include_router(stats_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "env": settings.app_env}


@app.get("/repos", tags=["repos"])
async def list_repos(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Review.repo_id).where(Review.platform != "direct").distinct()
    )
    repos = [row[0] for row in result.all() if row[0]]
    return {"repos": repos}
