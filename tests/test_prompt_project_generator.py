import os
from unittest.mock import MagicMock, patch, AsyncMock, mock_open

import pytest

from prompts.project_prompt_generator import ProjectPromptGenerator, DEFAULT_COMMIT_ANALYSIS_PROMPT
from prompts.registry import PromptRegistry
from models.project_repo import ProjectRepo
from models.prompt_experiment import PromptExperiment
from models.commit_analysis import CommitAnalysis
from models.commit_finding import CommitFinding


@pytest.mark.asyncio
async def test_detect_tech_stack_python():
    """测试 Python 项目技术栈识别。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    with patch("os.walk") as mock_walk:
        mock_walk.return_value = [
            ("/fake/repo", ["src"], ["requirements.txt", "README.md"]),
            ("/fake/repo/src", [], ["main.py"]),
        ]
        with patch("builtins.open", mock_open(read_data="fastapi>=0.100\nsqlalchemy\npytest")):
            stack = gen._detect_tech_stack("/fake/repo")

    assert stack["language"] == "Python"
    assert stack["framework"] == "FastAPI"
    assert stack["build_tool"] == "pip/setuptools"
    assert "src" in stack["key_paths"]


@pytest.mark.asyncio
async def test_detect_tech_stack_node():
    """测试 Node.js 项目技术栈识别。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    with patch("os.walk") as mock_walk:
        mock_walk.return_value = [
            ("/fake/repo", ["src"], ["package.json", "README.md"]),
            ("/fake/repo/src", [], ["App.tsx"]),
        ]
        with patch("builtins.open", mock_open(read_data='{"dependencies":{"react":"^18","next":"^14"}}')):
            stack = gen._detect_tech_stack("/fake/repo")

    assert stack["language"] == "TypeScript"
    assert stack["framework"] == "Next.js"
    assert stack["build_tool"] == "npm/yarn/pnpm"


@pytest.mark.asyncio
async def test_collect_project_config():
    """测试项目配置读取。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    project = MagicMock()
    project.config_json = {
        "review_config": {
            "critical_paths": ["src/payment", "src/auth"],
            "custom_rules": [{"name": "禁止直接调用 DB", "message": "控制器层不应直接访问数据库", "severity": "warning"}],
            "context_analysis": {"enabled": True},
        }
    }

    config = gen._collect_project_config(project)
    assert config["critical_paths"] == ["src/payment", "src/auth"]
    assert len(config["custom_rules"]) == 1
    assert config["context_analysis_enabled"] is True


@pytest.mark.asyncio
async def test_collect_historical_findings():
    """测试历史 Commit Finding 统计。"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        ca = CommitAnalysis(
            project_id=1, commit_hash="abc123", author_name="A", author_email="a@b.com",
            message="test", commit_ts=None, additions=1, deletions=0, changed_files=1, status="completed",
        )
        session.add(ca)
        await session.commit()

        session.add_all([
            CommitFinding(commit_analysis_id=ca.id, file_path="a.py", severity="warning", category="logic", description="d1"),
            CommitFinding(commit_analysis_id=ca.id, file_path="b.py", severity="critical", category="security", description="d2"),
            CommitFinding(commit_analysis_id=ca.id, file_path="c.py", severity="warning", category="logic", description="d3"),
        ])
        await session.commit()

        gen = ProjectPromptGenerator(session)
        hist = await gen._collect_historical_findings(1)

    assert hist["total_findings"] == 3
    assert hist["top_risk_category"] == "logic"
    assert hist["historical_categories"]["logic"] == 2
    assert hist["historical_categories"]["security"] == 1
    assert hist["historical_severity"]["warning"] == 2
    assert hist["historical_severity"]["critical"] == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_fingerprint_stable():
    """测试相同特征产生相同指纹。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    features = {
        "static": {"dominant_language": "Python", "framework": "FastAPI", "key_paths": ["src"], "commit_patterns": {"feat": 5, "fix": 2}},
        "config": {"critical_paths": ["src/core"], "custom_rules": []},
        "historical": {"historical_categories": {"logic": 3}, "top_risk_category": "logic"},
    }

    fp1 = gen._compute_fingerprint(features)
    fp2 = gen._compute_fingerprint(features)
    assert fp1 == fp2
    assert len(fp1) == 16


@pytest.mark.asyncio
async def test_fingerprint_changes_with_key_features():
    """测试关键特征变化导致指纹变化。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    base = {
        "static": {"dominant_language": "Python", "framework": "FastAPI", "key_paths": ["src"], "commit_patterns": {"feat": 5, "fix": 2}},
        "config": {"critical_paths": ["src/core"], "custom_rules": []},
        "historical": {"historical_categories": {"logic": 3}, "top_risk_category": "logic"},
    }

    fp_base = gen._compute_fingerprint(base)

    # 语言变化
    changed = {**base, "static": {**base["static"], "dominant_language": "Go", "framework": "Gin"}}
    fp_changed = gen._compute_fingerprint(changed)
    assert fp_changed != fp_base


@pytest.mark.asyncio
async def test_should_evolve_first_time():
    """测试首次生成时强制进化。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    should, reason = gen._should_evolve("abc", None, {})
    assert should is True
    assert "首次" in reason


@pytest.mark.asyncio
async def test_should_evolve_tech_stack_change():
    """测试技术栈变化触发进化。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    last_meta = {
        "feature_fingerprint": "old123",
        "dominant_language": "Python",
        "framework": "Flask",
        "commit_patterns": {"feat": 5, "fix": 2},
        "critical_paths": ["src"],
        "custom_rules": [],
        "top_risk_category": "logic",
        "total_findings": 10,
    }
    current = {
        "static": {"dominant_language": "Go", "framework": "Gin", "commit_patterns": {"feat": 5, "fix": 2}, "key_paths": ["src"]},
        "config": {"critical_paths": ["src"], "custom_rules": []},
        "historical": {"top_risk_category": "logic", "total_findings": 10, "historical_categories": {"logic": 3}},
    }

    should, reason = gen._should_evolve("new456", last_meta, current)
    assert should is True
    assert "技术栈" in reason


@pytest.mark.asyncio
async def test_should_evolve_commit_type_shift():
    """测试 Commit 类型显著偏移触发进化。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    last_meta = {
        "feature_fingerprint": "old123",
        "dominant_language": "Python",
        "framework": "unknown",
        "commit_patterns": {"feat": 10, "fix": 0, "refactor": 0},
        "critical_paths": [],
        "custom_rules": [],
        "top_risk_category": "",
        "total_findings": 0,
    }
    current = {
        "static": {"dominant_language": "Python", "framework": "unknown", "commit_patterns": {"feat": 2, "fix": 8, "refactor": 0}, "key_paths": []},
        "config": {"critical_paths": [], "custom_rules": []},
        "historical": {"top_risk_category": "", "total_findings": 0, "historical_categories": {}},
    }

    should, reason = gen._should_evolve("new456", last_meta, current)
    assert should is True
    assert "fix" in reason


@pytest.mark.asyncio
async def test_should_not_evolve_minor_change():
    """测试微小变化不触发进化。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    last_meta = {
        "feature_fingerprint": "old123",
        "dominant_language": "Python",
        "framework": "unknown",
        "commit_patterns": {"feat": 5, "fix": 3, "refactor": 2},
        "critical_paths": [],
        "custom_rules": [],
        "top_risk_category": "logic",
        "total_findings": 10,
    }
    current = {
        "static": {"dominant_language": "Python", "framework": "unknown", "commit_patterns": {"feat": 5, "fix": 3, "refactor": 2}, "key_paths": []},
        "config": {"critical_paths": [], "custom_rules": []},
        "historical": {"top_risk_category": "logic", "total_findings": 10, "historical_categories": {"logic": 3}},
    }

    should, reason = gen._should_evolve("new456", last_meta, current)
    # 指纹不同但关键特征相同，应判定为不进化
    assert should is False
    assert "阈值" in reason or "未达" in reason


@pytest.mark.asyncio
async def test_build_structured_prompt():
    """测试结构化 Prompt 构建。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    features = {
        "dominant_language": "Python",
        "framework": "FastAPI",
        "dominant_commit_type": "feat",
        "key_paths": ["src", "api", "tests"],
    }
    config = {
        "critical_paths": ["src/core"],
        "custom_rules": [{"name": "规则A", "message": "不要直接调用 DB", "severity": "warning"}],
    }
    historical = {
        "top_risk_category": "logic",
        "historical_categories": {"logic": 5, "security": 2},
    }

    prompt = gen._build_structured_prompt(features, config, historical)

    assert "Python" in prompt
    assert "FastAPI" in prompt
    assert "feat" in prompt
    assert "src/core" in prompt
    assert "规则A" in prompt
    assert "logic" in prompt
    assert "JSON" in prompt
    assert "issues" in prompt
    assert "功能完整性" in prompt
    assert "回归风险" in prompt
    assert "Pydantic" in prompt


@pytest.mark.asyncio
async def test_build_structured_prompt_fallback_no_data():
    """测试无特征数据时的 fallback Prompt 构建。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    prompt = gen._build_structured_prompt({}, {}, {})
    assert "JSON" in prompt
    assert "issues" in prompt
    assert "功能完整性" in prompt
    assert "逻辑正确性" in prompt


@pytest.mark.asyncio
async def test_refiner_fallback_on_structure_loss():
    """测试 LLM 润色后丢失结构时的回退逻辑。"""
    session = MagicMock()
    provider = MagicMock()
    provider.generate_text = AsyncMock(return_value="一段没有 JSON 要求的普通文本")

    gen = ProjectPromptGenerator(session, provider=provider)
    base = "基础模板，包含 JSON 和 issues 要求"
    result = await gen._refine_prompt_with_llm(base, {}, {}, {})

    assert result == base


@pytest.mark.asyncio
async def test_next_version():
    """测试版本号递增逻辑。"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        gen = ProjectPromptGenerator(session)

        v1 = await gen._next_version(42)
        assert v1 == "project-42-v1"

        session.add(
            PromptExperiment(version="project-42-v1", prompt_text="test", repo_id="org/repo")
        )
        await session.commit()

        v2 = await gen._next_version(42)
        assert v2 == "project-42-v2"

    await engine.dispose()


@pytest.mark.asyncio
async def test_registry_get_project_prompt_text():
    """测试 PromptRegistry 能正确查询项目专属 Prompt。"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        registry = PromptRegistry(session)

        result = await registry.get_project_prompt_text("org/repo-a")
        assert result is None

        session.add(
            PromptExperiment(version="project-1-v1", prompt_text="old text", repo_id="org/repo-a")
        )
        session.add(
            PromptExperiment(version="project-1-v2", prompt_text="new text", repo_id="org/repo-a")
        )
        await session.commit()

        result = await registry.get_project_prompt_text("org/repo-a")
        assert result == "new text"

    await engine.dispose()


@pytest.mark.asyncio
async def test_generate_for_project_api(async_client_with_db):
    """测试手动触发生成项目 Prompt 的 API（404 场景）。"""
    resp = await async_client_with_db.post("/prompts/generate-for-project/99999")
    assert resp.status_code == 404
