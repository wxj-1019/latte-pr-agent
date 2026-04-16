from typing import Optional

from tree_sitter import Tree

from code_ast.languages import get_parser


class TreeSitterParser:
    """封装 Tree-sitter 解析器，支持多语言。"""

    def __init__(self, language: str):
        self.language = language
        self._parser = get_parser(language)

    def parse(self, source: bytes) -> Optional[Tree]:
        try:
            return self._parser.parse(source)
        except Exception:
            return None
