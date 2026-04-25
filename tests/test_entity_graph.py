import pytest
from fastapi.testclient import TestClient

from main import app
from models import Base, get_db
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def client_with_entity_db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


class TestEntityGraphAPI:
    def test_get_entity_graph_empty(self, client_with_entity_db):
        # 需要先创建项目，但实体图谱 API 在没有项目时返回 404
        # 这里仅测试接口可访问性（需要先添加项目）
        client = client_with_entity_db
        # 添加项目
        resp = client.post(
            "/projects",
            json={ 
                "platform": "github",
                "repo_url": "https://github.com/test/repo",
                "repo_id": "test/repo",
                "branch": "main",
            },
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        # 获取实体图谱（空）
        resp = client.get(f"/projects/{project_id}/entity-graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert data["nodes"] == []
        assert data["edges"] == []

    def test_build_entity_graph_not_cloned(self, client_with_entity_db):
        client = client_with_entity_db
        resp = client.post(
            "/projects",
            json={
                "platform": "github",
                "repo_url": "https://github.com/test/repo2",
                "repo_id": "test/repo2",
                "branch": "main",
            },
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        resp = client.post(f"/projects/{project_id}/entity-graph/build")
        assert resp.status_code == 400
        assert "not cloned" in resp.json()["detail"]

    def test_code_search_empty(self, client_with_entity_db):
        client = client_with_entity_db
        resp = client.post(
            "/projects",
            json={
                "platform": "github",
                "repo_url": "https://github.com/test/repo3",
                "repo_id": "test/repo3",
                "branch": "main",
            },
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        resp = client.get(f"/projects/{project_id}/code-search?q=auth")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "auth"
        assert data["results"] == []

    def test_graph_rag_retrieve_empty(self, client_with_entity_db):
        client = client_with_entity_db
        resp = client.post(
            "/projects",
            json={
                "platform": "github",
                "repo_url": "https://github.com/test/repo4",
                "repo_id": "test/repo4",
                "branch": "main",
            },
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        resp = client.post(
            f"/projects/{project_id}/graph-rag/retrieve",
            json={"query": "test query", "changed_files": ["src/main.py"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test query"
        assert data["results"] == []


class TestDiffParser:
    def test_extract_changed_files_from_diff(self):
        from commits.router import _extract_changed_files_from_diff

        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "index abc..def 100644\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1,5 +1,5 @@\n"
            " def main():\n"
            "-    pass\n"
            "+    return 42\n"
            "diff --git a/lib/utils.py b/lib/utils.py\n"
            "index 123..456 100644\n"
        )
        files = _extract_changed_files_from_diff(diff)
        assert files == ["src/main.py", "lib/utils.py"]

    def test_extract_changed_files_empty(self):
        from commits.router import _extract_changed_files_from_diff

        assert _extract_changed_files_from_diff("") == []
        assert _extract_changed_files_from_diff("random text without diff headers") == []
