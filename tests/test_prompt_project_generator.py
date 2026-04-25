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

    prompt = gen._build_structured_prompt(features, config, historical, {})

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

    prompt = gen._build_structured_prompt({}, {}, {}, {})
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

        v1 = await gen._next_version(42, "org/repo")
        assert v1 == "org-repo-v1"

        session.add(
            PromptExperiment(version="org-repo-v1", prompt_text="test", repo_id="org/repo")
        )
        await session.commit()

        v2 = await gen._next_version(42, "org/repo")
        assert v2 == "org-repo-v2"

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


def test_scan_code_context():
    """测试代码上下文扫描能正确识别目录结构、API 模式和代码风格。"""
    import os as _os
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    repo_path = _os.path.normpath("/fake/repo")
    pkg_path = _os.path.join(repo_path, "package.json")
    main_path = _os.path.join(repo_path, "main.py")

    with patch("os.walk") as mock_walk, \
         patch("os.path.getsize", return_value=1024), \
         patch.object(gen, "_read_file_head") as mock_read, \
         patch.object(gen, "_scan_api_patterns") as mock_scan_api, \
         patch.object(gen, "_detect_code_style") as mock_detect_style:

        mock_walk.return_value = [
            (repo_path, ["src", ".git"], ["main.py", "package.json", ".env"]),
            (_os.path.join(repo_path, "src"), ["api", "models"], ["app.py"]),
            (_os.path.join(repo_path, "src", "api"), [], ["routes.py"]),
            (_os.path.join(repo_path, "src", "models"), [], ["user.py"]),
        ]
        mock_read.side_effect = lambda path, max_lines: {
            pkg_path: '{"dependencies": {"fastapi": "^0.100"}}',
            main_path: "from fastapi import FastAPI\napp = FastAPI()",
        }.get(path)

        ctx = gen._scan_code_context(repo_path)

        assert len(ctx["directory_tree"]) > 0
        assert "package.json" in ctx["config_summary"]
        assert "main.py" in [s["file"] for s in ctx["code_samples"]]
        mock_detect_style.assert_called_once()


def test_build_structured_prompt_with_code_context():
    """测试带有 code_context 的结构化 Prompt 构建。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    features = {
        "dominant_language": "Python",
        "framework": "FastAPI",
        "dominant_commit_type": "feat",
        "key_paths": ["src", "api"],
        "code_context": {
            "directory_tree": ["src/", "  api/", "    routes.py", "  models/", "    user.py"],
            "config_summary": {"pyproject.toml": "[tool.poetry.dependencies]\nfastapi = \"^0.100\""},
            "code_samples": [
                {"file": "src/main.py", "role": "entry", "content": "from fastapi import FastAPI\napp = FastAPI()"},
            ],
            "api_patterns": ["src/api/routes.py: GET /users", "src/models/user.py: Pydantic BaseModel"],
            "import_style": "absolute (from X import Y)",
            "naming_convention": "snake_case",
        },
    }
    config = {"critical_paths": [], "custom_rules": []}
    historical = {}

    prompt = gen._build_structured_prompt(features, config, historical, {})

    assert "项目目录结构快照" in prompt
    assert "src/" in prompt
    assert "关键配置摘要" in prompt
    assert "pyproject.toml" in prompt
    assert "识别的 API / 模型模式" in prompt
    assert "GET /users" in prompt
    assert "Pydantic BaseModel" in prompt
    assert "代码风格" in prompt
    assert "snake_case" in prompt
    assert "代表性代码片段" in prompt
    assert "src/main.py" in prompt
    assert "FastAPI" in prompt
    assert "JSON" in prompt


def test_fingerprint_includes_code_context():
    """测试指纹计算包含 code_context 的关键特征。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    features_with_ctx = {
        "static": {
            "dominant_language": "Python",
            "framework": "FastAPI",
            "commit_patterns": {"feat": 5},
            "key_paths": ["src"],
            "code_context": {
                "api_patterns": ["src/api.py: GET /users"],
                "code_samples": [{"file": "src/main.py"}],
                "import_style": "absolute",
                "naming_convention": "snake_case",
                "directory_tree": ["src/"],
            },
        },
        "config": {"critical_paths": [], "custom_rules": []},
        "historical": {"historical_categories": {}, "total_findings": 0},
    }

    features_without_ctx = {
        "static": {
            "dominant_language": "Python",
            "framework": "FastAPI",
            "commit_patterns": {"feat": 5},
            "key_paths": ["src"],
            "code_context": {},
        },
        "config": {"critical_paths": [], "custom_rules": []},
        "historical": {"historical_categories": {}, "total_findings": 0},
    }

    fp1 = gen._compute_fingerprint(features_with_ctx)
    fp2 = gen._compute_fingerprint(features_without_ctx)

    assert fp1 != fp2
    assert len(fp1) == 16
    assert len(fp2) == 16

    # 相同特征应产生相同指纹
    fp3 = gen._compute_fingerprint(features_with_ctx)
    assert fp1 == fp3


# ------------------------------------------------------------------
# 知识图谱集成测试
# ------------------------------------------------------------------

def test_infer_architecture_layer():
    """测试架构层推断。"""
    assert ProjectPromptGenerator._infer_architecture_layer("src/controllers/user.py") == "controller"
    assert ProjectPromptGenerator._infer_architecture_layer("src/services/order.py") == "service"
    assert ProjectPromptGenerator._infer_architecture_layer("src/models/db.py") == "data"
    assert ProjectPromptGenerator._infer_architecture_layer("src/middleware/auth.py") == "middleware"
    assert ProjectPromptGenerator._infer_architecture_layer("src/utils/helper.py") == "utility"
    assert ProjectPromptGenerator._infer_architecture_layer("tests/test_user.py") == "test"
    assert ProjectPromptGenerator._infer_architecture_layer("config/settings.py") == "config"
    assert ProjectPromptGenerator._infer_architecture_layer("src/main.py") == "other"
    # Windows path
    assert ProjectPromptGenerator._infer_architecture_layer("src\\handlers\\api.py") == "controller"


@pytest.mark.asyncio
async def test_collect_graph_features():
    """测试从知识图谱采集项目特征。"""
    session = MagicMock()

    # Mock entity type counts
    entity_result = MagicMock()
    entity_result.all.return_value = [("function", 42), ("class", 10), ("interface", 3)]

    # Mock relation type counts
    rel_result = MagicMock()
    rel_result.all.return_value = [("calls", 120), ("inherits", 8), ("decorates", 5)]

    # Mock top entities (in_degree)
    top_ent_result = MagicMock()
    top_ent_result.all.return_value = [
        (1, "UserService", "class", "src/services/user.py", 15),
        (2, "get_user", "function", "src/services/user.py", 8),
    ]

    # Mock architecture layers
    layer_result = MagicMock()
    layer_result.all.return_value = [
        ("src/services/user.py", 4),      # 3 functions + 1 class
        ("src/controllers/user.py", 2),   # 2 functions
    ]

    # Mock circular dependency
    cycle_result = MagicMock()
    cycle_result.scalar.return_value = 1

    # Mock god classes
    god_result = MagicMock()
    god_result.all.return_value = [
        ("OrderManager", "src/services/order.py", 25),
    ]

    # Queries are executed in fixed order in _collect_graph_features
    session.execute = AsyncMock(side_effect=[
        entity_result,   # 1. entity type counts
        rel_result,      # 2. relation type counts
        top_ent_result,  # 3. top entities
        layer_result,    # 4. architecture layers
        cycle_result,    # 5. circular dependency
        god_result,      # 6. god classes
    ])

    gen = ProjectPromptGenerator(session)
    result = await gen._collect_graph_features("repo-123", "default")

    assert result["entity_type_counts"] == {"function": 42, "class": 10, "interface": 3}
    assert result["relation_type_counts"] == {"calls": 120, "inherits": 8, "decorates": 5}
    assert len(result["top_entities"]) == 2
    assert result["top_entities"][0]["name"] == "UserService"
    assert result["top_entities"][0]["in_degree"] == 15
    assert "service" in result["architecture_layers"]
    assert "controller" in result["architecture_layers"]
    assert result["has_circular_dependency"] is True
    assert len(result["god_class_candidates"]) == 1
    assert result["god_class_candidates"][0]["name"] == "OrderManager"


@pytest.mark.asyncio
async def test_collect_graph_features_empty():
    """测试无图谱数据时的 graceful fallback。"""
    session = MagicMock()
    empty_result = MagicMock()
    empty_result.all.return_value = []
    empty_result.scalar.return_value = 0
    session.execute = AsyncMock(return_value=empty_result)

    gen = ProjectPromptGenerator(session)
    result = await gen._collect_graph_features("empty-repo", "default")

    assert result["entity_type_counts"] == {}
    assert result["relation_type_counts"] == {}
    assert result["top_entities"] == []
    assert result["architecture_layers"] == {}
    assert result["has_circular_dependency"] is False
    assert result["god_class_candidates"] == []


def test_build_structured_prompt_with_graph():
    """测试 Prompt 正确注入知识图谱上下文。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    features = {"dominant_language": "Python", "framework": "FastAPI", "dominant_commit_type": "feat"}
    config = {"critical_paths": [], "custom_rules": []}
    historical = {}
    graph = {
        "entity_type_counts": {"function": 50, "class": 12},
        "relation_type_counts": {"calls": 200},
        "architecture_layers": {
            "controller": {"entity_count": 8, "types": {"function": 6, "class": 2}},
            "service": {"entity_count": 15, "types": {"function": 10, "class": 5}},
        },
        "top_entities": [
            {"name": "UserService", "type": "class", "file": "src/services/user.py", "in_degree": 20},
        ],
        "god_class_candidates": [
            {"name": "OrderManager", "file": "src/services/order.py", "in_degree": 30},
        ],
        "has_circular_dependency": True,
    }

    prompt = gen._build_structured_prompt(features, config, historical, graph)

    assert "知识图谱架构分析" in prompt
    assert "function(50)" in prompt
    assert "controller(8)" in prompt
    assert "UserService" in prompt
    assert "入度: 20" in prompt
    assert "OrderManager" in prompt
    assert "检测到循环依赖" in prompt


def test_should_evolve_graph_changes():
    """测试图谱变化触发 Prompt 进化。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    current_features = {
        "static": {},
        "config": {},
        "historical": {},
        "graph": {
            "entity_type_counts": {"function": 50, "class": 12},
            "architecture_layers": {"controller": {}, "service": {}},
            "god_class_candidates": [{"name": "A"}],
        },
    }

    # 实体类型变化
    last_metadata = {
        "feature_fingerprint": "old",
        "graph": {
            "entity_type_counts": {"function": 50},  # 缺少 class
            "architecture_layers": {"controller": {}, "service": {}},
            "god_class_candidates": [{"name": "A"}],
        },
    }
    should, reason = gen._should_evolve("new", last_metadata, current_features)
    assert should is True
    assert "实体类型分布变化" in reason

    # 架构分层变化
    last_metadata2 = {
        "feature_fingerprint": "old",
        "graph": {
            "entity_type_counts": {"function": 50, "class": 12},
            "architecture_layers": {"controller": {}},  # 缺少 service
            "god_class_candidates": [{"name": "A"}],
        },
    }
    should2, reason2 = gen._should_evolve("new", last_metadata2, current_features)
    assert should2 is True
    assert "架构分层变化" in reason2

    # God Class 数量变化
    last_metadata3 = {
        "feature_fingerprint": "old",
        "graph": {
            "entity_type_counts": {"function": 50, "class": 12},
            "architecture_layers": {"controller": {}, "service": {}},
            "god_class_candidates": [],  # 空
        },
    }
    should3, reason3 = gen._should_evolve("new", last_metadata3, current_features)
    assert should3 is True
    assert "God Class 数量变化" in reason3


def test_fingerprint_includes_graph():
    """测试指纹计算包含图谱特征。"""
    session = MagicMock()
    gen = ProjectPromptGenerator(session)

    features_with_graph = {
        "static": {"dominant_language": "Python", "framework": "FastAPI", "commit_patterns": {"feat": 5}, "key_paths": ["src"]},
        "config": {"critical_paths": [], "custom_rules": []},
        "historical": {"historical_categories": {}, "total_findings": 0},
        "graph": {
            "entity_type_counts": {"function": 50},
            "relation_type_counts": {"calls": 100},
            "top_entities": [{"name": "A", "in_degree": 10}],
            "architecture_layers": {"service": {"entity_count": 5}},
        },
    }

    features_without_graph = {
        "static": {"dominant_language": "Python", "framework": "FastAPI", "commit_patterns": {"feat": 5}, "key_paths": ["src"]},
        "config": {"critical_paths": [], "custom_rules": []},
        "historical": {"historical_categories": {}, "total_findings": 0},
        "graph": {},
    }

    fp1 = gen._compute_fingerprint(features_with_graph)
    fp2 = gen._compute_fingerprint(features_without_graph)

    assert fp1 != fp2
    assert len(fp1) == 16
