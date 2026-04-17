import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from graph import DependencyGraphBuilder, CodeGraphRepository
from models import FileDependency


@pytest.mark.asyncio
async def test_dependency_graph_builder(async_db_session: AsyncSession, tmp_path):
    # Create a fake Python project
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("from utils import helper\n")
    (tmp_path / "src" / "utils.py").write_text("import os\n")
    (tmp_path / "src" / "app.py").write_text("from main import run\n")

    builder = DependencyGraphBuilder(async_db_session)
    await builder.build(str(tmp_path), repo_id="test-repo")

    result = await async_db_session.execute(
        __import__('sqlalchemy', fromlist=['select']).select(FileDependency)
    )
    deps = result.scalars().all()
    pairs = {(d.downstream_file, d.upstream_file) for d in deps}

    assert ("src/main.py", "src/utils.py") in pairs
    assert ("src/app.py", "src/main.py") in pairs
    # os is stdlib, should not be resolved to local file
    assert not any("os" in up for _, up in pairs)


@pytest.mark.asyncio
async def test_code_graph_get_callers(async_db_session: AsyncSession):
    deps = [
        FileDependency(org_id="default", repo_id="repo1", downstream_file="c.py", upstream_file="b.py"),
        FileDependency(org_id="default", repo_id="repo1", downstream_file="b.py", upstream_file="a.py"),
    ]
    async_db_session.add_all(deps)
    await async_db_session.flush()

    callers = await CodeGraphRepository.get_callers(async_db_session, "repo1", "a.py", depth=3)
    files = {c["file"] for c in callers}
    assert "b.py" in files
    assert "c.py" in files


@pytest.mark.asyncio
async def test_code_graph_get_dependencies(async_db_session: AsyncSession):
    deps = [
        FileDependency(org_id="default", repo_id="repo1", downstream_file="b.py", upstream_file="a.py"),
        FileDependency(org_id="default", repo_id="repo1", downstream_file="c.py", upstream_file="b.py"),
    ]
    async_db_session.add_all(deps)
    await async_db_session.flush()

    # b.py depends on a.py; c.py depends on b.py
    downstream = await CodeGraphRepository.get_dependencies(async_db_session, "repo1", "b.py", depth=3)
    files = {d["file"] for d in downstream}
    assert "a.py" in files

    downstream_c = await CodeGraphRepository.get_dependencies(async_db_session, "repo1", "c.py", depth=3)
    files_c = {d["file"] for d in downstream_c}
    assert "b.py" in files_c
    assert "a.py" in files_c


@pytest.mark.asyncio
async def test_code_graph_get_affected_files(async_db_session: AsyncSession):
    deps = [
        FileDependency(org_id="default", repo_id="repo1", downstream_file="b.py", upstream_file="a.py"),
        FileDependency(org_id="default", repo_id="repo1", downstream_file="c.py", upstream_file="b.py"),
    ]
    async_db_session.add_all(deps)
    await async_db_session.flush()

    result = await CodeGraphRepository.get_affected_files(
        async_db_session, "repo1", ["a.py"], depth=3
    )
    assert "a.py" in result
    # upstream = who calls me (affected by my change)
    assert any(d["file"] == "b.py" for d in result["a.py"]["upstream"])
    assert any(d["file"] == "c.py" for d in result["a.py"]["upstream"])
