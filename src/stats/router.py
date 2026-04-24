from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from stats.service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)) -> dict:
    service = StatsService(db)
    return await service.get_dashboard_summary()


@router.get("/metrics")
async def get_combined_metrics(
    repo_id: str = Query(..., description="仓库 ID，如 owner/repo"),
    range: str = Query("7d", description="时间范围: 7d, 30d, 90d"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """综合指标端点：合并 PR review 和 commit analysis 数据。

    返回前端指标页面所需的全部数据：
    - PR 审查指标（总数、发现项、误报率、置信度）
    - Commit 分析指标（提交数、已分析数、发现项）
    - 合并后的 category_distribution
    - 每日审查量折线图数据
    """
    service = StatsService(db)
    return await service.get_combined_metrics(repo_id, range=range)
