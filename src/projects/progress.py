import json
import logging
from datetime import datetime, timezone
from typing import Optional

from engine.cache import get_redis_client

logger = logging.getLogger(__name__)


class AnalysisProgressTracker:
    """使用 Redis 存储项目分析进度，供 SSE 轮询读取。

    Redis 键格式: project:{project_id}:analysis_progress
    TTL: 1 小时（防止死键堆积）
    """

    KEY_PREFIX = "project:{project_id}:analysis_progress"
    TTL_SECONDS = 3600

    @classmethod
    def _make_key(cls, project_id: int) -> str:
        return cls.KEY_PREFIX.format(project_id=project_id)

    @classmethod
    async def start(cls, project_id: int, operation: str) -> None:
        """标记分析任务开始。"""
        redis = await get_redis_client()
        payload = {
            "project_id": project_id,
            "operation": operation,
            "status": "running",
            "step": "started",
            "progress": 0,
            "total": 0,
            "message": f"开始{cls._operation_name(operation)}...",
            "timestamp": _now_iso(),
        }
        await redis.setex(
            cls._make_key(project_id),
            cls.TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False),
        )
        logger.info("Project %s: %s started", project_id, operation)

    @classmethod
    async def update(
        cls,
        project_id: int,
        step: str,
        progress: int,
        total: int,
        message: str,
    ) -> None:
        """更新分析进度。"""
        redis = await get_redis_client()
        key = cls._make_key(project_id)
        existing = await redis.get(key)
        payload = json.loads(existing) if existing else {}
        payload.update(
            {
                "status": "running",
                "step": step,
                "progress": progress,
                "total": total,
                "message": message,
                "timestamp": _now_iso(),
            }
        )
        await redis.setex(
            key,
            cls.TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False),
        )
        logger.info("Project %s: [%s] %s (%s/%s)", project_id, step, message, progress, total)

    @classmethod
    async def complete(cls, project_id: int, result: Optional[dict] = None) -> None:
        """标记分析任务完成。"""
        redis = await get_redis_client()
        key = cls._make_key(project_id)
        existing = await redis.get(key)
        payload = json.loads(existing) if existing else {}
        payload.update(
            {
                "status": "completed",
                "step": "finished",
                "progress": 100,
                "total": 100,
                "message": f"{cls._operation_name(payload.get('operation', '分析'))}完成",
                "result": result or {},
                "timestamp": _now_iso(),
            }
        )
        await redis.setex(
            key,
            cls.TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False),
        )
        logger.info("Project %s: analysis completed, result=%s", project_id, result)

    @classmethod
    async def fail(cls, project_id: int, error: str) -> None:
        """标记分析任务失败。"""
        redis = await get_redis_client()
        key = cls._make_key(project_id)
        existing = await redis.get(key)
        payload = json.loads(existing) if existing else {}
        payload.update(
            {
                "status": "failed",
                "step": "error",
                "message": f"分析失败: {error}",
                "error": error,
                "timestamp": _now_iso(),
            }
        )
        await redis.setex(
            key,
            cls.TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False),
        )
        logger.error("Project %s: analysis failed: %s", project_id, error)

    @classmethod
    async def get(cls, project_id: int) -> Optional[dict]:
        """从 Redis 读取当前进度。"""
        redis = await get_redis_client()
        raw = await redis.get(cls._make_key(project_id))
        if raw:
            return json.loads(raw)
        return None

    @classmethod
    async def clear(cls, project_id: int) -> None:
        """删除 Redis 键。"""
        redis = await get_redis_client()
        await redis.delete(cls._make_key(project_id))

    @staticmethod
    def _operation_name(operation: str) -> str:
        mapping = {"clone": "克隆", "sync": "同步", "scan": "扫描提交"}
        return mapping.get(operation, "分析")


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。"""
    return datetime.now(timezone.utc).isoformat()
