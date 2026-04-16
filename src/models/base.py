from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import settings


class Base(AsyncAttrs, DeclarativeBase):
    type_annotation_map = {
        dict: JSON,
        list: JSON,
    }


async_engine = create_async_engine(settings.database_url, echo=settings.app_env == "development")
AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
