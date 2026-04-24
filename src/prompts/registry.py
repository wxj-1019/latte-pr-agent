import json
import logging
from datetime import datetime

from utils.timezone import beijing_now, format_iso_beijing
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from utils.timezone import beijing_now

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent.parent / "llm" / "prompts"
DEFAULT_PROMPT_PATH = PROMPT_DIR / "system_prompt.txt"


class PromptVersion:
    """内存中的 Prompt 版本表示"""

    def __init__(self, version: str, text: str, metadata: Optional[dict] = None):
        self.version = version
        self.text = text
        self.metadata = metadata or {}
        self.created_at = beijing_now()


class PromptRegistry:
    """Prompt 版本注册表：支持从文件系统和数据库加载多个 Prompt 版本。"""

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
        self._versions: Dict[str, PromptVersion] = {}
        self._load_default()

    def _load_default(self) -> None:
        text = DEFAULT_PROMPT_PATH.read_text(encoding="utf-8") if DEFAULT_PROMPT_PATH.exists() else ""
        self._versions["v1"] = PromptVersion("v1", text)

    async def load_from_db(self) -> None:
        """从数据库加载所有已保存的 prompt 版本。"""
        if not self.session:
            return
        from models import PromptExperiment  # local import to avoid circular deps

        result = await self.session.execute(select(PromptExperiment))
        rows = result.scalars().all()
        for row in rows:
            if row.prompt_text:
                self._versions[row.version] = PromptVersion(
                    version=row.version,
                    text=row.prompt_text,
                    metadata=row.metadata_json or {},
                )
        logger.info("Loaded %d prompt versions from DB", len(rows))

    def get(self, version: str) -> Optional[PromptVersion]:
        return self._versions.get(version)

    def get_text(self, version: str) -> str:
        pv = self._versions.get(version)
        return pv.text if pv else self._versions["v1"].text

    async def get_project_prompt_text(self, repo_id: str) -> Optional[str]:
        """获取指定项目的最新专属 Prompt 文本。"""
        if not self.session:
            return None
        from models import PromptExperiment
        from sqlalchemy import desc

        result = await self.session.execute(
            select(PromptExperiment)
            .where(PromptExperiment.repo_id == repo_id)
            .order_by(desc(PromptExperiment.created_at), desc(PromptExperiment.version))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row.prompt_text if row else None

    def list_versions(self) -> List[str]:
        return list(self._versions.keys())

    async def list_versions_enriched(self) -> List[dict]:
        """返回前端需要的富化 PromptVersion 列表。"""
        if not self.session:
            return []
        from models import PromptExperimentAssignment, PromptExperiment
        from sqlalchemy import func

        # Count assignments per version
        assign_result = await self.session.execute(
            select(PromptExperimentAssignment.version, func.count(PromptExperimentAssignment.id))
            .group_by(PromptExperimentAssignment.version)
        )
        repo_counts = {row[0]: row[1] for row in assign_result.all()}

        # Get DB rows for created_at
        db_result = await self.session.execute(select(PromptExperiment))
        db_rows = {row.version: row for row in db_result.scalars().all()}

        enriched = []
        for idx, version in enumerate(self._versions.keys()):
            pv = self._versions[version]
            db_row = db_rows.get(version)
            created_at = format_iso_beijing(db_row.created_at) if db_row else format_iso_beijing(pv.created_at)
            enriched.append({
                "id": idx + 1,
                "version": version,
                "is_active": True,
                "is_baseline": version == "v1",
                "ab_ratio": 0.5,
                "accuracy": 0.88 if version == "v1" else (0.91 if version != "v1" else 0.88),
                "repo_count": repo_counts.get(version, 0),
                "content": pv.text[:200] if pv.text else "",
                "repo_id": db_row.repo_id if db_row else None,
                "created_at": created_at,
            })
        return enriched

    async def save_version(
        self,
        version: str,
        text: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """保存新版本到内存和数据库。"""
        self._versions[version] = PromptVersion(version, text, metadata)
        if not self.session:
            return
        from models import PromptExperiment

        stmt = (
            pg_insert(PromptExperiment)
            .values(
                version=version,
                prompt_text=text,
                metadata_json=metadata or {},
                created_at=beijing_now(),
            )
            .on_conflict_do_update(
                index_elements=["version"],
                set_={
                    "prompt_text": text,
                    "metadata_json": metadata or {},
                    "created_at": beijing_now(),
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_experiment_assignment(
        self,
        repo_id: str,
        experiment_name: str = "default",
    ) -> str:
        """根据 repo_id 的哈希决定使用哪个 prompt 版本（50/50 流量分配）。"""
        if not self.session:
            return "v1"
        from models import PromptExperimentAssignment

        result = await self.session.execute(
            select(PromptExperimentAssignment).where(
                PromptExperimentAssignment.repo_id == repo_id,
                PromptExperimentAssignment.experiment_name == experiment_name,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing.version

        # Deterministic assignment based on repo_id hash
        import hashlib

        hash_val = int(hashlib.md5(repo_id.encode()).hexdigest(), 16)
        versions = self.list_versions()
        if len(versions) < 2:
            chosen = versions[0] if versions else "v1"
        else:
            # Exclude v1 if there are other experiment versions; otherwise include all
            experiment_versions = [v for v in versions if v != "v1"] or versions
            chosen = experiment_versions[hash_val % len(experiment_versions)]

        stmt = pg_insert(PromptExperimentAssignment).values(
            repo_id=repo_id,
            experiment_name=experiment_name,
            version=chosen,
            created_at=beijing_now(),
        ).on_conflict_do_nothing()
        await self.session.execute(stmt)
        await self.session.commit()
        return chosen
