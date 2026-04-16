from dataclasses import dataclass
from typing import List, Optional

from tree_sitter import Node


@dataclass
class FunctionInfo:
    name: str
    signature: str
    start_line: int
    end_line: int
    return_type: str = ""


@dataclass
class ClassInfo:
    name: str
    bases: List[str]
    start_line: int
    end_line: int


@dataclass
class ImportInfo:
    module: str
    names: List[str]
    start_line: int


def _node_text(node: Optional[Node]) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode("utf-8", errors="replace")


def _find_child(node: Node, node_type: str) -> Optional[Node]:
    for child in node.children:
        if child.type == node_type:
            return child
    return None


def _find_children(node: Node, node_type: str) -> List[Node]:
    return [c for c in node.children if c.type == node_type]


def _walk(node: Node, target_type: str):
    """递归遍历所有子节点，返回匹配 target_type 的节点列表。"""
    results = []
    if node.type == target_type:
        results.append(node)
    for child in node.children:
        results.extend(_walk(child, target_type))
    return results


# ==================== Python ====================

def _extract_python_imports(node: Node) -> List[ImportInfo]:
    imports = []
    for child in node.children:
        if child.type == "import_statement":
            dotted = _find_child(child, "dotted_name")
            if dotted:
                module = _node_text(dotted)
                imports.append(ImportInfo(module=module, names=[], start_line=child.start_point[0] + 1))
        elif child.type == "import_from_statement":
            dotted_names = _find_children(child, "dotted_name")
            module = _node_text(dotted_names[0]) if dotted_names else ""
            names = [_node_text(d) for d in dotted_names[1:]]
            imports.append(ImportInfo(module=module, names=names, start_line=child.start_point[0] + 1))
    return imports


def _extract_python_functions(node: Node) -> List[FunctionInfo]:
    funcs = []
    for child in _walk(node, "function_definition"):
        name_node = _find_child(child, "identifier")
        params = _find_child(child, "parameters")
        return_type = ""
        seen_arrow = False
        for c in child.children:
            if c.type == "->":
                seen_arrow = True
            elif seen_arrow and c.type == "type":
                return_type = _node_text(c)
                break
        funcs.append(FunctionInfo(
            name=_node_text(name_node),
            signature=_node_text(params),
            start_line=child.start_point[0] + 1,
            end_line=child.end_point[0] + 1,
            return_type=return_type,
        ))
    return funcs


def _extract_python_classes(node: Node) -> List[ClassInfo]:
    classes = []
    for child in _walk(node, "class_definition"):
        name_node = _find_child(child, "identifier")
        arg_list = _find_child(child, "argument_list")
        bases = []
        if arg_list:
            for c in arg_list.children:
                if c.type in ("identifier", "attribute"):
                    bases.append(_node_text(c))
        classes.append(ClassInfo(
            name=_node_text(name_node),
            bases=bases,
            start_line=child.start_point[0] + 1,
            end_line=child.end_point[0] + 1,
        ))
    return classes


# ==================== Java ====================

def _extract_java_imports(node: Node) -> List[ImportInfo]:
    imports = []
    for child in node.children:
        if child.type == "import_declaration":
            target = _find_child(child, "scoped_identifier") or _find_child(child, "identifier")
            if target:
                imports.append(ImportInfo(
                    module=_node_text(target),
                    names=[],
                    start_line=child.start_point[0] + 1,
                ))
    return imports


def _extract_java_functions(node: Node) -> List[FunctionInfo]:
    funcs = []
    for child in _walk(node, "method_declaration"):
        name_node = _find_child(child, "identifier")
        params = _find_child(child, "formal_parameters")
        return_type = ""
        found_name = False
        for c in reversed(child.children):
            if c == name_node:
                found_name = True
                continue
            if found_name and c.type not in ("modifiers", ";"):
                return_type = _node_text(c)
                break
        funcs.append(FunctionInfo(
            name=_node_text(name_node),
            signature=_node_text(params),
            start_line=child.start_point[0] + 1,
            end_line=child.end_point[0] + 1,
            return_type=return_type,
        ))
    return funcs


def _extract_java_classes(node: Node) -> List[ClassInfo]:
    classes = []
    for child in _walk(node, "class_declaration"):
        name_node = _find_child(child, "identifier")
        bases = []
        for c in child.children:
            if c.type in ("superclass", "interfaces"):
                for sub in c.children:
                    if sub.type in ("type_identifier", "scoped_type_identifier"):
                        bases.append(_node_text(sub))
        classes.append(ClassInfo(
            name=_node_text(name_node),
            bases=bases,
            start_line=child.start_point[0] + 1,
            end_line=child.end_point[0] + 1,
        ))
    return classes


# ==================== Go ====================

def _extract_go_imports(node: Node) -> List[ImportInfo]:
    imports = []
    for child in node.children:
        if child.type == "import_declaration":
            for spec in _find_children(child, "import_spec"):
                lit = _find_child(spec, "interpreted_string_literal")
                if lit:
                    content = _find_child(lit, "interpreted_string_literal_content")
                    module = _node_text(content) if content else _node_text(lit).strip('"')
                    imports.append(ImportInfo(module=module, names=[], start_line=child.start_point[0] + 1))
            spec_list = _find_child(child, "import_spec_list")
            if spec_list:
                for spec in _find_children(spec_list, "import_spec"):
                    lit = _find_child(spec, "interpreted_string_literal")
                    if lit:
                        content = _find_child(lit, "interpreted_string_literal_content")
                        module = _node_text(content) if content else _node_text(lit).strip('"')
                        imports.append(ImportInfo(module=module, names=[], start_line=child.start_point[0] + 1))
    return imports


def _extract_go_functions(node: Node) -> List[FunctionInfo]:
    funcs = []
    for child in _walk(node, "function_declaration"):
        name_node = _find_child(child, "identifier")
        params = _find_child(child, "parameter_list")
        return_type = ""
        found_params = False
        for c in child.children:
            if c == params:
                found_params = True
                continue
            if found_params and c.type in ("type_identifier", "qualified_type", "slice_type", "map_type", "pointer_type"):
                return_type = _node_text(c)
                break
        funcs.append(FunctionInfo(
            name=_node_text(name_node),
            signature=_node_text(params),
            start_line=child.start_point[0] + 1,
            end_line=child.end_point[0] + 1,
            return_type=return_type,
        ))
    return funcs


def _extract_go_classes(node: Node) -> List[ClassInfo]:
    return []


# ==================== TypeScript ====================

def _extract_ts_imports(node: Node) -> List[ImportInfo]:
    imports = []
    for child in node.children:
        if child.type == "import_statement":
            source = _find_child(child, "string")
            module = _node_text(source).strip('"').strip("'") if source else ""
            names = []
            clause = _find_child(child, "import_clause")
            if clause:
                for c in clause.children:
                    if c.type == "named_imports":
                        for spec in _find_children(c, "import_specifier"):
                            id_node = _find_child(spec, "identifier")
                            if id_node:
                                names.append(_node_text(id_node))
                    elif c.type == "identifier":
                        names.append(_node_text(c))
            imports.append(ImportInfo(module=module, names=names, start_line=child.start_point[0] + 1))
    return imports


def _extract_ts_functions(node: Node) -> List[FunctionInfo]:
    funcs = []
    for child in _walk(node, "function_declaration"):
        name_node = _find_child(child, "identifier")
        params = _find_child(child, "formal_parameters")
        return_type = ""
        type_anno = _find_child(child, "type_annotation")
        if type_anno:
            return_type = _node_text(type_anno).lstrip(": ")
        funcs.append(FunctionInfo(
            name=_node_text(name_node),
            signature=_node_text(params),
            start_line=child.start_point[0] + 1,
            end_line=child.end_point[0] + 1,
            return_type=return_type,
        ))
    return funcs


def _extract_ts_classes(node: Node) -> List[ClassInfo]:
    classes = []
    for child in _walk(node, "class_declaration"):
        name_node = _find_child(child, "type_identifier")
        bases = []
        heritage = _find_child(child, "class_heritage")
        if heritage:
            for clause in heritage.children:
                if clause.type in ("extends_clause", "implements_clause"):
                    for c in clause.children:
                        if c.type in ("type_identifier", "member_expression", "identifier"):
                            bases.append(_node_text(c))
                elif clause.type in ("type_identifier", "member_expression", "identifier"):
                    bases.append(_node_text(clause))
        classes.append(ClassInfo(
            name=_node_text(name_node),
            bases=bases,
            start_line=child.start_point[0] + 1,
            end_line=child.end_point[0] + 1,
        ))
    return classes


# ==================== Public Extractors ====================

class ImportExtractor:
    def __init__(self, language: str):
        self.language = language.lower()

    def extract(self, root: Node) -> List[ImportInfo]:
        if self.language in ("python",):
            return _extract_python_imports(root)
        if self.language in ("java",):
            return _extract_java_imports(root)
        if self.language in ("go",):
            return _extract_go_imports(root)
        if self.language in ("typescript", "ts"):
            return _extract_ts_imports(root)
        return []


class FunctionExtractor:
    def __init__(self, language: str):
        self.language = language.lower()

    def extract_functions(self, root: Node) -> List[FunctionInfo]:
        if self.language in ("python",):
            return _extract_python_functions(root)
        if self.language in ("java",):
            return _extract_java_functions(root)
        if self.language in ("go",):
            return _extract_go_functions(root)
        if self.language in ("typescript", "ts"):
            return _extract_ts_functions(root)
        return []

    def extract_classes(self, root: Node) -> List[ClassInfo]:
        if self.language in ("python",):
            return _extract_python_classes(root)
        if self.language in ("java",):
            return _extract_java_classes(root)
        if self.language in ("go",):
            return _extract_go_classes(root)
        if self.language in ("typescript", "ts"):
            return _extract_ts_classes(root)
        return []
