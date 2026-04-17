from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from webhooks.router import router as webhook_router
from feedback.router import router as feedback_router
from prompts.router import router as prompts_router
from reviews.router import router as reviews_router
from configs.router import router as configs_router
from stats.router import router as stats_router
from models import get_db, Review


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Latte PR Agent",
    description="Enterprise AI Code Review System",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
