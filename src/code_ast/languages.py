"""Tree-sitter language parser registry."""

from tree_sitter import Language, Parser


def _load_python():
    import tree_sitter_python as mod
    return Language(mod.language())


def _load_java():
    import tree_sitter_java as mod
    return Language(mod.language())


def _load_go():
    import tree_sitter_go as mod
    return Language(mod.language())


def _load_typescript():
    import tree_sitter_typescript as mod
    return Language(mod.language_typescript())


LANGUAGE_MAP = {
    "python": _load_python,
    "java": _load_java,
    "go": _load_go,
    "typescript": _load_typescript,
    "ts": _load_typescript,
}


def get_language(name: str) -> Language:
    loader = LANGUAGE_MAP.get(name.lower())
    if not loader:
        raise ValueError(f"Unsupported language: {name}")
    return loader()


def get_parser(name: str) -> Parser:
    return Parser(get_language(name))
