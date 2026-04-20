from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


class Base(AsyncAttrs, DeclarativeBase):
    type_annotation_map = {
        dict: JSON,
        list: JSON,
    }


async_engine = create_async_engine(
    settings.database_url.get_secret_value(),
    echo=settings.app_env == "development",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)
AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


def recreate_engine():
    global async_engine, AsyncSessionLocal
    async_engine = create_async_engine(
        settings.database_url.get_secret_value(),
        echo=settings.app_env == "development",
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
