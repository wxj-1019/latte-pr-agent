import subprocess
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from context.builder import PRDiff, ProjectContextBuilder
from graph.builder import DependencyGraphBuilder


@pytest.mark.asyncio
async def test_phase2_end_to_end_context(async_db_session: AsyncSession, tmp_path):
    """
    构造临时 Python 项目，建立依赖图后模拟 PR diff，
    验证 ProjectContextBuilder 能返回真实的 upstream/downstream 和 API 变更检测。
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()

    # 创建跨文件 import 的 Python 项目
    (repo / "src" / "utils.py").write_text("def helper(x):\n    return x + 1\n")
    (repo / "src" / "app.py").write_text("from utils import helper\n\ndef main():\n    return helper(1)\n")

    # 初始化 git 仓库并提交
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)

    # 构建依赖图
    graph_builder = DependencyGraphBuilder(async_db_session)
    await graph_builder.build(str(repo), repo_id="test/repo")

    # 模拟修改 utils.py 函数签名的 PR diff
    diff = (
        "diff --git a/src/utils.py b/src/utils.py\n"
        "--- a/src/utils.py\n+++ b/src/utils.py\n"
        "@@ -1 +1 @@\n"
        "-def helper(x):\n+def helper(x, y=0):\n"
    )

    # 通过 build_context 获取完整项目上下文
    # 提供 file_content_map 以启用 APIDetector（精确检测 breaking change）
    builder = ProjectContextBuilder(
        db_session=async_db_session,
        repo_id="test/repo",
        file_content_map={
            "src/utils.py": {
                "before": b"def helper(x):\n    return x + 1\n",
                "after": b"def helper(x, y=0):\n    return x + y + 1\n",
            }
        },
    )
    context = await builder.build_context(PRDiff(content=diff))

    # 断言依赖图包含真实的 upstream（谁依赖了 utils.py）
    dg = context["dependency_graph"]
    assert "src/utils.py" in dg["upstream"]
    upstream_files = dg["upstream"]["src/utils.py"]
    assert "src/app.py" in upstream_files, f"Expected src/app.py in upstream, got {upstream_files}"

    # 断言 API 变更检测到签名修改且标记为 breaking
    api = context["api_contracts"]
    assert api["breaking_count"] >= 1, f"Expected breaking_count >= 1, got {api['breaking_count']}"
    assert any(
        change["function"] == "helper" and change["breaking_change"]
        for change in api["api_changes"]
    ), f"Expected helper breaking change, got {api['api_changes']}"
