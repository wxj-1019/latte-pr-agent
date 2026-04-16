import os
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from config.project_config import ProjectConfigLoader, ProjectConfigService, ReviewConfig
from models import ProjectConfig


def test_project_config_loader_uses_defaults_when_missing():
    config = ProjectConfigLoader.load("/nonexistent/path")
    assert config.language == "python"
    assert config.block_on_critical is True
    assert config.critical_paths == []


def test_project_config_loader_parses_yaml(tmp_path):
    yaml_content = """
review_config:
  language: go
  framework: gin
  critical_paths:
    - "src/core/"
  block_on_critical: false
  ai_model:
    primary: claude-3-5-sonnet
"""
    (tmp_path / ".review-config.yml").write_text(yaml_content, encoding="utf-8")
    config = ProjectConfigLoader.load(str(tmp_path))
    assert config.language == "go"
    assert config.framework == "gin"
    assert config.critical_paths == ["src/core/"]
    assert config.block_on_critical is False
    assert config.ai_model.primary == "claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_project_config_service_upsert_and_get(async_db_session: AsyncSession):
    service = ProjectConfigService(async_db_session)
    config = await service.upsert_config(
        platform="github",
        repo_id="o/r",
        config_json={"language": "java", "block_on_critical": True},
    )

    assert config is not None
    assert config.platform == "github"

    fetched = await service.get_config("github", "o/r")
    assert fetched["language"] == "java"
    assert fetched["block_on_critical"] is True


@pytest.mark.asyncio
async def test_project_config_service_load_and_cache(async_db_session: AsyncSession, tmp_path):
    yaml_content = """
review_config:
  language: typescript
  custom_rules:
    - name: No console
      pattern: "*.ts"
      forbidden: "console.log"
      severity: warning
"""
    (tmp_path / ".review-config.yml").write_text(yaml_content, encoding="utf-8")

    service = ProjectConfigService(async_db_session)
    review_config = await service.load_and_cache(str(tmp_path), "github", "o/r")

    assert review_config.language == "typescript"
    assert len(review_config.custom_rules) == 1

    fetched = await service.get_config("github", "o/r")
    assert fetched["language"] == "typescript"
