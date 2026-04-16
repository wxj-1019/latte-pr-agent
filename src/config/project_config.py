import fnmatch
import logging
import os
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models import ProjectConfig

logger = logging.getLogger(__name__)


class ContextAnalysisConfig(BaseModel):
    enabled: bool = True
    dependency_depth: int = 2
    historical_bug_check: bool = True
    api_contract_detection: bool = True


class CustomRule(BaseModel):
    name: str
    pattern: str = "*"
    forbidden: Optional[str] = None
    check: Optional[str] = None
    message: str = ""
    severity: str = "warning"


class AIModelConfig(BaseModel):
    primary: str = "deepseek-chat"
    fallback: str = "deepseek-reasoner"
    enterprise_option: Optional[str] = "claude-3-5-sonnet"
    temperature: float = 0.1
    max_tokens: int = 4000


class DualModelVerificationConfig(BaseModel):
    enabled: bool = False
    trigger_on: List[str] = Field(default_factory=lambda: ["critical", "warning"])
    max_reasoner_context_tokens: int = 15000


class ReviewConfig(BaseModel):
    language: str = "python"
    framework: Optional[str] = None
    context_analysis: ContextAnalysisConfig = Field(default_factory=ContextAnalysisConfig)
    critical_paths: List[str] = Field(default_factory=list)
    ignore_patterns: List[str] = Field(default_factory=list)
    custom_rules: List[CustomRule] = Field(default_factory=list)
    ai_model: AIModelConfig = Field(default_factory=AIModelConfig)
    dual_model_verification: DualModelVerificationConfig = Field(default_factory=DualModelVerificationConfig)
    block_on_critical: bool = True

    @field_validator("critical_paths", "ignore_patterns", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        return v


class ProjectConfigLoader:
    """从本地仓库加载 .review-config.yml 并解析为 Pydantic 模型。"""

    DEFAULT_FILENAME = ".review-config.yml"

    @classmethod
    def load(cls, repo_path: str) -> ReviewConfig:
        filepath = os.path.join(repo_path, cls.DEFAULT_FILENAME)
        if not os.path.isfile(filepath):
            logger.info(f"No {cls.DEFAULT_FILENAME} found in {repo_path}, using defaults")
            return ReviewConfig()

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.warning(f"Failed to parse {filepath}: {exc}, using defaults")
            return ReviewConfig()

        review_data = data.get("review_config", {}) if isinstance(data, dict) else {}
        return ReviewConfig(**review_data)


class ProjectConfigService:
    """将项目配置缓存到 PostgreSQL，提供异步读写接口。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_config(self, platform: str, repo_id: str, org_id: str = "default") -> Optional[Dict]:
        result = await self.session.execute(
            select(ProjectConfig).where(
                ProjectConfig.platform == platform,
                ProjectConfig.repo_id == repo_id,
                ProjectConfig.org_id == org_id,
            )
        )
        config = result.scalar_one_or_none()
        return config.config_json if config else None

    async def upsert_config(
        self,
        platform: str,
        repo_id: str,
        config_json: Dict,
        org_id: str = "default",
    ) -> ProjectConfig:
        stmt = (
            pg_insert(ProjectConfig)
            .values(
                org_id=org_id,
                platform=platform,
                repo_id=repo_id,
                config_json=config_json,
            )
            .on_conflict_do_update(
                index_elements=["org_id", "platform", "repo_id"],
                set_={"config_json": config_json},
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

        result = await self.session.execute(
            select(ProjectConfig).where(
                ProjectConfig.platform == platform,
                ProjectConfig.repo_id == repo_id,
                ProjectConfig.org_id == org_id,
            )
        )
        return result.scalar_one()

    async def load_and_cache(
        self, repo_path: str, platform: str, repo_id: str, org_id: str = "default"
    ) -> ReviewConfig:
        review_config = ProjectConfigLoader.load(repo_path)
        await self.upsert_config(platform, repo_id, review_config.model_dump(), org_id)
        return review_config
