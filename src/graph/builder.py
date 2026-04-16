import os
from pathlib import Path
from typing import List, Set, Tuple

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from code_ast import TreeSitterParser, ImportExtractor
from models import FileDependency


EXTENSION_TO_LANG = {
    ".py": "python",
    ".java": "java",
    ".go": "go",
    ".ts": "typescript",
    ".tsx": "typescript",
}


class DependencyGraphBuilder:
    """扫描仓库，基于 AST 提取 import 关系，构建文件依赖图。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def build(self, repo_path: str, repo_id: str, org_id: str = "default") -> None:
        """扫描整个仓库并写入 file_dependencies 表。"""
        repo_root = Path(repo_path).resolve()
        deps: Set[Tuple[str, str]] = set()

        for file_path in repo_root.rglob("*"):
            if not file_path.is_file():
                continue
            lang = EXTENSION_TO_LANG.get(file_path.suffix)
            if not lang:
                continue

            try:
                source = file_path.read_bytes()
            except Exception:
                continue

            parser = TreeSitterParser(lang)
            tree = parser.parse(source)
            if not tree:
                continue

            extractor = ImportExtractor(lang)
            imports = extractor.extract(tree.root_node)

            rel_file = str(file_path.relative_to(repo_root)).replace("\\", "/")
            for imp in imports:
                resolved = _resolve_import(imp.module, lang, repo_root, file_path.parent)
                for target in resolved:
                    target_rel = str(Path(target).relative_to(repo_root)).replace("\\", "/")
                    deps.add((rel_file, target_rel))

        # 清空旧数据（同一仓库）
        await self.session.execute(
            delete(FileDependency).where(
                FileDependency.repo_id == repo_id,
                FileDependency.org_id == org_id,
            )
        )

        # 批量写入
        if deps:
            records = [
                FileDependency(
                    org_id=org_id,
                    repo_id=repo_id,
                    downstream_file=down,
                    upstream_file=up,
                    relation_type="import",
                )
                for down, up in deps
            ]
            self.session.add_all(records)
            await self.session.commit()


def _resolve_import(module: str, lang: str, repo_root: Path, current_dir: Path) -> List[str]:
    """将 import 模块路径解析为可能的本地文件路径列表。"""
    if not module:
        return []

    candidates = []

    # 相对路径（TypeScript / Python relative imports）
    if module.startswith(".") or module.startswith(".."):
        target = current_dir / module
        candidates.extend(_try_extensions(target, lang))
        return [str(c) for c in candidates if c.exists()]

    # 将模块点号替换为路径分隔符
    parts = module.replace(".", "/")

    # 优先从当前文件目录查找（模拟包内 import）
    target_local = current_dir / parts
    candidates.extend(_try_extensions(target_local, lang))

    # 再从仓库根目录查找
    target_root = repo_root / parts
    candidates.extend(_try_extensions(target_root, lang))

    # 去重并保持顺序
    seen = set()
    results = []
    for c in candidates:
        if c not in seen and c.exists():
            seen.add(c)
            results.append(str(c))
    return results


def _try_extensions(path: Path, lang: str) -> List[Path]:
    """尝试常见扩展名和 index/__init__ 文件。"""
    candidates = []
    exts = {
        "python": [".py", "/__init__.py"],
        "java": [".java"],
        "go": [".go"],
        "typescript": [".ts", ".tsx", "/index.ts", "/index.tsx"],
    }.get(lang, [""])

    for ext in exts:
        if ext.startswith("/"):
            candidates.append(path / ext.lstrip("/"))
        else:
            candidates.append(Path(str(path) + ext))
    return candidates
