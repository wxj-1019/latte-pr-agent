import re
from typing import Dict, List, Optional


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
        # 简化：只要有 +def 和 -def 同名出现，即视为签名修改
        return True

    def is_breaking(self) -> bool:
        # 简化：参数减少、重命名等简单判断（可扩展）
        return self.is_remove and not self.is_add

    @property
    def old_signature(self) -> str:
        return f"def {self.function_name}({self.signature})"

    @property
    def new_signature(self) -> str:
        return f"def {self.function_name}({self.signature})"


class ProjectContextBuilder:
    """
    构建包含项目级上下文的审查 Prompt。
    当前为基础实现（MVP 增强版），后续可替换为 Tree-sitter + 递归 CTE 的完整版本。
    """

    def __init__(self, db_session=None, embedding_model=None):
        self.db = db_session
        self.embedding_model = embedding_model

    def build_context(self, pr_diff: PRDiff) -> Dict:
        return {
            "pr_diff": pr_diff.content,
            "file_changes": self._parse_file_changes(pr_diff),
            "dependency_graph": self._analyze_dependencies(pr_diff),
            "similar_bugs": self._retrieve_similar_bugs(pr_diff),
            "api_contracts": self._detect_api_changes(pr_diff),
            "cross_service_impact": None,  # Phase 3+ 启用
        }

    def _parse_file_changes(self, pr_diff: PRDiff) -> List[Dict]:
        files = []
        for f in pr_diff.get_changed_files():
            files.append({"file": f, "change_type": "modified"})
        return files

    def _analyze_dependencies(self, pr_diff: PRDiff) -> Dict:
        """
        简化版依赖分析：基于 import 语句的正则提取。
        后续升级为 Tree-sitter AST + PostgreSQL 递归 CTE。
        """
        changed_files = pr_diff.get_changed_files()
        upstream = {}
        downstream = {}
        imports = {}

        for file in changed_files:
            file_imports = self._extract_imports_from_diff(pr_diff.content, file)
            imports[file] = file_imports
            upstream[file] = file_imports
            downstream[file] = []

        # 简单的反向依赖推断：如果 A import B，则 B 的 downstream 包含 A
        for file, deps in imports.items():
            for dep in deps:
                for target in changed_files:
                    if self._module_matches_file(dep, target) and target != file:
                        downstream.setdefault(target, []).append(file)

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

    def _retrieve_similar_bugs(self, pr_diff: PRDiff) -> List[Dict]:
        """RAG 检索占位符，Phase 2 接入 pgvector"""
        return []

    def _detect_api_changes(self, pr_diff: PRDiff) -> Dict:
        """检测接口契约变更"""
        api_changes = []
        for change in pr_diff.get_function_changes():
            if change.is_signature_modified():
                api_changes.append({
                    "function": change.function_name,
                    "file": change.file_name,
                    "old_signature": change.old_signature,
                    "new_signature": change.new_signature,
                    "breaking_change": change.is_breaking(),
                    "affected_locations": 0,  # Phase 2 接入 CodeGraph 后计算
                    "affected_files": [],
                })

        return {
            "api_changes": api_changes,
            "breaking_count": len([a for a in api_changes if a["breaking_change"]]),
        }
