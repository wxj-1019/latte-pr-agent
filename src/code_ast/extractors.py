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


@dataclass
class CallInfo:
    caller_name: str
    callee_name: str
    start_line: int


@dataclass
class InheritanceInfo:
    class_name: str
    base_name: str
    start_line: int


@dataclass
class DecoratorInfo:
    target_name: str
    decorator_name: str
    start_line: int
    target_type: str  # function, class, method


# ==================== Call Extraction ====================

def _extract_python_calls(root: Node, local_functions: List[str], local_classes: List[str]) -> List[CallInfo]:
    calls = []
    for call_node in _walk(root, "call"):
        func_node = _find_child(call_node, "function")
        if not func_node:
            continue
        callee = ""
        if func_node.type == "identifier":
            callee = _node_text(func_node)
        elif func_node.type == "attribute":
            parts = []
            obj = _find_child(func_node, "object")
            attr = _find_child(func_node, "attribute")
            if obj:
                parts.append(_node_text(obj))
            if attr:
                parts.append(_node_text(attr))
            callee = ".".join(parts)
        if callee:
            # Determine caller context by walking up to nearest function/class
            caller = "<module>"
            parent = call_node.parent
            while parent:
                if parent.type in ("function_definition", "method_definition"):
                    name_node = _find_child(parent, "identifier")
                    if name_node:
                        caller = _node_text(name_node)
                    break
                elif parent.type == "class_definition":
                    name_node = _find_child(parent, "identifier")
                    if name_node:
                        caller = _node_text(name_node)
                    break
                parent = parent.parent
            calls.append(CallInfo(caller_name=caller, callee_name=callee, start_line=call_node.start_point[0] + 1))
    return calls


def _extract_java_calls(root: Node, local_functions: List[str], local_classes: List[str]) -> List[CallInfo]:
    calls = []
    for call_node in _walk(root, "method_invocation"):
        name_node = _find_child(call_node, "identifier")
        callee = _node_text(name_node)
        obj_node = _find_child(call_node, "field_access")
        if obj_node:
            obj = _node_text(obj_node)
            callee = f"{obj}.{callee}"
        if callee:
            caller = "<module>"
            parent = call_node.parent
            while parent:
                if parent.type == "method_declaration":
                    name_node = _find_child(parent, "identifier")
                    if name_node:
                        caller = _node_text(name_node)
                    break
                elif parent.type == "class_declaration":
                    name_node = _find_child(parent, "identifier")
                    if name_node:
                        caller = _node_text(name_node)
                    break
                parent = parent.parent
            calls.append(CallInfo(caller_name=caller, callee_name=callee, start_line=call_node.start_point[0] + 1))
    return calls


def _extract_go_calls(root: Node, local_functions: List[str], local_classes: List[str]) -> List[CallInfo]:
    calls = []
    for call_node in _walk(root, "call_expression"):
        func_node = _find_child(call_node, "function")
        callee = ""
        if func_node:
            if func_node.type == "identifier":
                callee = _node_text(func_node)
            elif func_node.type == "selector_expression":
                operand = _find_child(func_node, "operand")
                field = _find_child(func_node, "field")
                parts = []
                if operand:
                    parts.append(_node_text(operand))
                if field:
                    parts.append(_node_text(field))
                callee = ".".join(parts)
        if callee:
            caller = "<module>"
            parent = call_node.parent
            while parent:
                if parent.type == "function_declaration":
                    name_node = _find_child(parent, "identifier")
                    if name_node:
                        caller = _node_text(name_node)
                    break
                elif parent.type == "method_declaration":
                    name_node = _find_child(parent, "identifier")
                    if name_node:
                        caller = _node_text(name_node)
                    break
                parent = parent.parent
            calls.append(CallInfo(caller_name=caller, callee_name=callee, start_line=call_node.start_point[0] + 1))
    return calls


def _extract_ts_calls(root: Node, local_functions: List[str], local_classes: List[str]) -> List[CallInfo]:
    calls = []
    for call_node in _walk(root, "call_expression"):
        func_node = _find_child(call_node, "function")
        callee = ""
        if func_node:
            if func_node.type == "identifier":
                callee = _node_text(func_node)
            elif func_node.type == "member_expression":
                obj = _find_child(func_node, "object")
                prop = _find_child(func_node, "property")
                parts = []
                if obj:
                    parts.append(_node_text(obj))
                if prop:
                    parts.append(_node_text(prop))
                callee = ".".join(parts)
        if callee:
            caller = "<module>"
            parent = call_node.parent
            while parent:
                if parent.type in ("function_declaration", "method_definition", "arrow_function"):
                    name_node = _find_child(parent, "identifier")
                    if name_node:
                        caller = _node_text(name_node)
                    break
                elif parent.type == "class_declaration":
                    name_node = _find_child(parent, "type_identifier")
                    if name_node:
                        caller = _node_text(name_node)
                    break
                parent = parent.parent
            calls.append(CallInfo(caller_name=caller, callee_name=callee, start_line=call_node.start_point[0] + 1))
    return calls


# ==================== Inheritance Extraction ====================

def _extract_python_inheritance(root: Node) -> List[InheritanceInfo]:
    result = []
    for cls in _walk(root, "class_definition"):
        name_node = _find_child(cls, "identifier")
        class_name = _node_text(name_node)
        arg_list = _find_child(cls, "argument_list")
        if arg_list:
            for c in arg_list.children:
                if c.type in ("identifier", "attribute"):
                    result.append(InheritanceInfo(class_name=class_name, base_name=_node_text(c), start_line=cls.start_point[0] + 1))
        # Also check decorators that might indicate mixin/ABC registration
    return result


def _extract_java_inheritance(root: Node) -> List[InheritanceInfo]:
    result = []
    for cls in _walk(root, "class_declaration"):
        name_node = _find_child(cls, "identifier")
        class_name = _node_text(name_node)
        for c in cls.children:
            if c.type in ("superclass", "interfaces"):
                for sub in c.children:
                    if sub.type in ("type_identifier", "scoped_type_identifier"):
                        result.append(InheritanceInfo(class_name=class_name, base_name=_node_text(sub), start_line=cls.start_point[0] + 1))
    return result


def _extract_go_inheritance(root: Node) -> List[InheritanceInfo]:
    # Go uses implicit interface implementation; explicit embedding via struct fields
    result = []
    for type_spec in _walk(root, "type_spec"):
        name_node = _find_child(type_spec, "type_identifier")
        type_name = _node_text(name_node)
        struct_type = _find_child(type_spec, "struct_type")
        if struct_type:
            for field in _walk(struct_type, "field_declaration"):
                type_node = _find_child(field, "type_identifier")
                if type_node:
                    result.append(InheritanceInfo(class_name=type_name, base_name=_node_text(type_node), start_line=field.start_point[0] + 1))
    return result


def _extract_ts_inheritance(root: Node) -> List[InheritanceInfo]:
    result = []
    for cls in _walk(root, "class_declaration"):
        name_node = _find_child(cls, "type_identifier")
        class_name = _node_text(name_node)
        heritage = _find_child(cls, "class_heritage")
        if heritage:
            for clause in heritage.children:
                if clause.type in ("extends_clause", "implements_clause"):
                    for c in clause.children:
                        if c.type in ("type_identifier", "member_expression", "identifier"):
                            result.append(InheritanceInfo(class_name=class_name, base_name=_node_text(c), start_line=cls.start_point[0] + 1))
    return result


# ==================== Decorator / Annotation Extraction ====================

def _extract_python_decorators(root: Node) -> List[DecoratorInfo]:
    result = []
    for target in _walk(root, "function_definition") + _walk(root, "class_definition"):
        target_type = "function" if target.type == "function_definition" else "class"
        name_node = _find_child(target, "identifier")
        target_name = _node_text(name_node)
        # Decorators appear as siblings before target in tree, but within tree_sitter Python grammar
        # decorators are child nodes of function_definition/class_definition
        for child in target.children:
            if child.type == "decorator":
                dec_name = ""
                dec_call = _find_child(child, "call")
                if dec_call:
                    func = _find_child(dec_call, "function")
                    if func:
                        dec_name = _node_text(func)
                else:
                    for c in child.children:
                        if c.type in ("identifier", "attribute"):
                            dec_name = _node_text(c)
                            break
                if dec_name:
                    result.append(DecoratorInfo(target_name=target_name, decorator_name=dec_name, start_line=child.start_point[0] + 1, target_type=target_type))
    return result


def _extract_java_decorators(root: Node) -> List[DecoratorInfo]:
    result = []
    for target in _walk(root, "class_declaration") + _walk(root, "method_declaration"):
        target_type = "class" if target.type == "class_declaration" else "method"
        name_node = _find_child(target, "identifier")
        target_name = _node_text(name_node)
        modifiers = _find_child(target, "modifiers")
        if modifiers:
            for ann in _walk(modifiers, "annotation"):
                name = _find_child(ann, "identifier")
                if not name:
                    scoped = _find_child(ann, "scoped_identifier")
                    if scoped:
                        name = _find_child(scoped, "identifier")
                dec_name = _node_text(name)
                if dec_name:
                    result.append(DecoratorInfo(target_name=target_name, decorator_name=dec_name, start_line=ann.start_point[0] + 1, target_type=target_type))
    return result


def _extract_go_decorators(root: Node) -> List[DecoratorInfo]:
    return []


def _extract_ts_decorators(root: Node) -> List[DecoratorInfo]:
    result = []
    for target in _walk(root, "class_declaration") + _walk(root, "function_declaration") + _walk(root, "method_definition"):
        target_type = "class" if target.type == "class_declaration" else "function"
        if target.type == "class_declaration":
            name_node = _find_child(target, "type_identifier")
        else:
            name_node = _find_child(target, "identifier")
        target_name = _node_text(name_node)
        for child in target.children:
            if child.type == "decorator":
                dec_call = _find_child(child, "call_expression")
                if dec_call:
                    func = _find_child(dec_call, "function")
                    if func:
                        dec_name = _node_text(func)
                    else:
                        dec_name = _node_text(child)
                else:
                    dec_name = _node_text(child)
                if dec_name:
                    result.append(DecoratorInfo(target_name=target_name, decorator_name=dec_name, start_line=child.start_point[0] + 1, target_type=target_type))
    return result


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


class CallExtractor:
    def __init__(self, language: str):
        self.language = language.lower()

    def extract(self, root: Node, local_functions: List[str] = None, local_classes: List[str] = None) -> List[CallInfo]:
        local_functions = local_functions or []
        local_classes = local_classes or []
        if self.language in ("python",):
            return _extract_python_calls(root, local_functions, local_classes)
        if self.language in ("java",):
            return _extract_java_calls(root, local_functions, local_classes)
        if self.language in ("go",):
            return _extract_go_calls(root, local_functions, local_classes)
        if self.language in ("typescript", "ts"):
            return _extract_ts_calls(root, local_functions, local_classes)
        return []


class InheritanceExtractor:
    def __init__(self, language: str):
        self.language = language.lower()

    def extract(self, root: Node) -> List[InheritanceInfo]:
        if self.language in ("python",):
            return _extract_python_inheritance(root)
        if self.language in ("java",):
            return _extract_java_inheritance(root)
        if self.language in ("go",):
            return _extract_go_inheritance(root)
        if self.language in ("typescript", "ts"):
            return _extract_ts_inheritance(root)
        return []


class DecoratorExtractor:
    def __init__(self, language: str):
        self.language = language.lower()

    def extract(self, root: Node) -> List[DecoratorInfo]:
        if self.language in ("python",):
            return _extract_python_decorators(root)
        if self.language in ("java",):
            return _extract_java_decorators(root)
        if self.language in ("go",):
            return _extract_go_decorators(root)
        if self.language in ("typescript", "ts"):
            return _extract_ts_decorators(root)
        return []
