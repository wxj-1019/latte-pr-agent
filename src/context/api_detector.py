from typing import Dict, List

from code_ast import FunctionExtractor
from code_ast.parser import TreeSitterParser


class APIDetector:
    """基于 Tree-sitter AST 检测文件级别的 API 变更（新增、删除、签名修改）。"""

    def __init__(self, language: str):
        self.language = language
        self.extractor = FunctionExtractor(language)

    def detect_changes(self, before: bytes, after: bytes) -> List[Dict]:
        before_funcs = self._index_functions(before)
        after_funcs = self._index_functions(after)

        changes: List[Dict] = []

        # added or modified
        for name, after_info in after_funcs.items():
            before_info = before_funcs.get(name)
            if before_info is None:
                changes.append({
                    "function": name,
                    "type": "added",
                    "breaking_change": False,
                    "old_signature": None,
                    "new_signature": after_info.signature,
                })
            elif before_info.signature != after_info.signature or before_info.return_type != after_info.return_type:
                changes.append({
                    "function": name,
                    "type": "modified",
                    "breaking_change": True,
                    "old_signature": before_info.signature,
                    "new_signature": after_info.signature,
                })

        # removed
        for name, before_info in before_funcs.items():
            if name not in after_funcs:
                changes.append({
                    "function": name,
                    "type": "removed",
                    "breaking_change": True,
                    "old_signature": before_info.signature,
                    "new_signature": None,
                })

        return changes

    def _index_functions(self, content: bytes) -> Dict[str, object]:
        if not content:
            return {}
        parser = TreeSitterParser(self.language)
        tree = parser.parse(content)
        funcs = self.extractor.extract_functions(tree.root_node)
        return {f.name: f for f in funcs}
