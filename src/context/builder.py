import re
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession


class PRDiff:
    """简化版 PRDiff 包装器"""

    def __init__(self, content: str, repo_id: str = ""):
        self.content = content
        self.repo_id = repo_id

    def get_changed_files(self) -> List[str]:
        files = []
        for line in self.content.splitlines():
            if line.startswith("diff --git "):
                parts = line.split()
                if len(parts) >= 4:
                    files.append(parts[2].replace("a/", ""))
        return files

    def get_function_changes(self) -> List["FunctionChange"]:
        """基于 diff 内容提取函数签名变更（简化版正则匹配）"""
        changes = []
        file_name = ""
        for line in self.content.splitlines():
            if line.startswith("diff --git "):
                parts = line.split()
                if len(parts) >= 4:
                    file_name = parts[3].replace("b/", "")
            # 匹配 Python 函数定义变更：+def func_name(...):
            match = re.match(r"^[+\-]def\s+(\w+)\s*\((.*?)\)", line)
            if match:
                func_name = match.group(1)
                signature = match.group(2)
                is_add = line.startswith("+")
                is_remove = line.startswith("-")
                changes.append(
                    FunctionChange(
                        function_name=func_name,
                        file_name=file_name,
                        signature=signature,
                        is_add=is_add,
                        is_remove=is_remove,
                    )
                )
        return changes


class FunctionChange:
    def __init__(self, function_name: str, file_name: str, signature: str, is_add: bool, is_remove: bool):
        self.function_name = function_name
        self.file_name = file_name
        self.signature = signature
        self.is_add = is_add
        self.is_remove = is_remove

    def is_signature_modified(self) -> bool:
        return self.is_add and self.is_remove

    def is_breaking(self) -> bool:
        if self.is_remove and not self.is_add:
            return True
        return False

    @property
    def old_signature(self) -> str:
        return f"def {self.function_name}({self.signature})"

    @property
    def new_signature(self) -> str:
        return f"def {self.function_name}({self.signature})"


class ProjectContextBuilder:
    """
    构建包含项目级上下文的审查 Prompt。
    支持 CodeGraphRepository 做真实依赖分析，支持 APIDetector 做精确 API 变更检测，支持 RAGRetriever 做历史 Bug 检索。
    """

    def __init__(
        self,
        db_session: Optional[AsyncSession] = None,
        embedding_model=None,
        repo_id: str = "",
        file_content_map: Optional[Dict[str, Dict[str, bytes]]] = None,
        rag_retriever=None,
    ):
        self.db = db_session
        self.embedding_model = embedding_model
        self.repo_id = repo_id
        self.file_content_map = file_content_map or {}
        self.rag_retriever = rag_retriever

    async def build_context(self, pr_diff: PRDiff) -> Dict:
        return {
            "pr_diff": pr_diff.content,
            "file_changes": self._parse_file_changes(pr_diff),
            "dependency_graph": await self._analyze_dependencies(pr_diff),
            "similar_bugs": await self._retrieve_similar_bugs(pr_diff),
            "api_contracts": await self._detect_api_changes(pr_diff),
            "cross_service_impact": None,  # Phase 3+ 启用
        }

    def _parse_file_changes(self, pr_diff: PRDiff) -> List[Dict]:
        files = []
        for f in pr_diff.get_changed_files():
            files.append({"file": f, "change_type": "modified"})
        return files

    async def _analyze_dependencies(self, pr_diff: PRDiff) -> Dict:
        changed_files = pr_diff.get_changed_files()
        if self.db and self.repo_id:
            from graph.repository import CodeGraphRepository

            affected = await CodeGraphRepository.get_affected_files(
                self.db, self.repo_id, changed_files, depth=3
            )
            upstream = {
                f: [item["file"] for item in affected.get(f, {}).get("upstream", [])]
                for f in changed_files
            }
            downstream = {
                f: [item["file"] for item in affected.get(f, {}).get("downstream", [])]
                for f in changed_files
            }
            imports = {f: downstream[f] for f in changed_files}
            risk_score = self._calc_dependency_risk(upstream)
            return {
                "upstream": upstream,
                "downstream": downstream,
                "imports": imports,
                "risk_score": risk_score,
            }

        # Fallback: regex-based analysis from diff
        upstream = {}
        downstream = {}
        imports = {}

        for file in changed_files:
            file_imports = self._extract_imports_from_diff(pr_diff.content, file)
            imports[file] = file_imports
            downstream[file] = file_imports
            upstream[file] = []

        # 反向依赖推断：如果 A import B，则 A 的 downstream 包含 B，B 的 upstream 包含 A
        for file, deps in imports.items():
            for dep in deps:
                for target in changed_files:
                    if self._module_matches_file(dep, target) and target != file:
                        upstream.setdefault(target, []).append(file)

        return {
            "upstream": upstream,
            "downstream": downstream,
            "risk_score": self._calc_dependency_risk(upstream),
        }

    def _extract_imports_from_diff(self, diff_content: str, target_file: str) -> List[str]:
        """从 diff 中提取新增/修改的 import 语句"""
        imports = []
        in_target = False
        for line in diff_content.splitlines():
            if line.startswith("diff --git "):
                in_target = target_file in line
                continue
            if not in_target:
                continue
            # Python import 匹配
            match = re.match(r"^[+\-](?:from\s+(\S+)\s+import|import\s+(\S+))", line)
            if match:
                module = match.group(1) or match.group(2)
                if module:
                    imports.append(module)
        return list(set(imports))

    def _module_matches_file(self, module: str, file_path: str) -> bool:
        """简化匹配：将模块路径转换为文件路径进行比对"""
        module_path = module.replace(".", "/")
        return module_path in file_path or file_path.replace(".py", "").replace("/", ".") in module

    def _calc_dependency_risk(self, upstream: Dict[str, List[str]]) -> float:
        if not upstream:
            return 0.0
        total_deps = sum(len(v) for v in upstream.values())
        avg_deps = total_deps / len(upstream)
        return min(avg_deps / 5.0, 1.0)

    async def _retrieve_similar_bugs(self, pr_diff: PRDiff) -> List[Dict]:
        """RAG 检索相似历史 Bug。"""
        if self.db and self.repo_id and self.rag_retriever:
            try:
                return await self.rag_retriever.retrieve(
                    self.db, pr_diff.content, self.repo_id
                )
            except Exception:
                return []
        return []

    async def _detect_api_changes(self, pr_diff: PRDiff) -> Dict:
        """检测接口契约变更。优先使用 APIDetector（需要 file_content_map），否则回退到 diff 正则。"""
        changed_files = pr_diff.get_changed_files()
        api_changes = []

        # 1. Precise detection with file_content_map
        for file_path in changed_files:
            contents = self.file_content_map.get(file_path)
            if contents:
                lang = self._detect_language(file_path)
                if lang:
                    from context.api_detector import APIDetector

                    detector = APIDetector(lang)
                    for change in detector.detect_changes(
                        contents.get("before", b""), contents.get("after", b"")
                    ):
                        api_changes.append({
                            "function": change["function"],
                            "file": file_path,
                            "old_signature": change["old_signature"],
                            "new_signature": change["new_signature"],
                            "breaking_change": change["breaking_change"],
                            "change_type": change["type"],
                            "affected_locations": 0,
                            "affected_files": [],
                        })

        # 2. Fallback to diff regex for files not in content map
        if not api_changes and not self.file_content_map:
            for change in pr_diff.get_function_changes():
                api_changes.append({
                    "function": change.function_name,
                    "file": change.file_name,
                    "old_signature": change.old_signature,
                    "new_signature": change.new_signature,
                    "breaking_change": change.is_breaking(),
                    "change_type": "modified",
                    "affected_locations": 0,
                    "affected_files": [],
                })

        return {
            "api_changes": api_changes,
            "breaking_count": len([a for a in api_changes if a["breaking_change"]]),
        }

    def _detect_language(self, file_path: str) -> Optional[str]:
        if file_path.endswith(".py"):
            return "python"
        if file_path.endswith(".java"):
            return "java"
        if file_path.endswith(".go"):
            return "go"
        if file_path.endswith(".ts") or file_path.endswith(".tsx"):
            return "typescript"
        return None
