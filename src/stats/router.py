from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from stats.service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)) -> dict:
    service = StatsService(db)
    return await service.get_dashboard_summary()
