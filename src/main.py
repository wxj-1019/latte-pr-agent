from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import settings
from webhooks.router import router as webhook_router
from feedback.router import router as feedback_router
from prompts.router import router as prompts_router


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

app.include_router(webhook_router)
app.include_router(feedback_router)
app.include_router(prompts_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "env": settings.app_env}
