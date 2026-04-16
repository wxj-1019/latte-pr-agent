import pytest

from code_ast import TreeSitterParser, FunctionExtractor, ImportExtractor, FunctionInfo, ClassInfo, ImportInfo


# ==================== Python ====================

PYTHON_CODE = b'''\
import os
from collections import OrderedDict
from typing import List, Dict

def foo(x: int, y: str) -> bool:
    return True

class Bar:
    pass

class Baz(Bar):
    def method(self) -> None:
        pass
'''


def test_python_imports():
    parser = TreeSitterParser("python")
    tree = parser.parse(PYTHON_CODE)
    assert tree is not None
    extractor = ImportExtractor("python")
    imports = extractor.extract(tree.root_node)
    modules = [i.module for i in imports]
    assert "os" in modules
    assert "collections" in modules
    assert "typing" in modules


def test_python_functions():
    parser = TreeSitterParser("python")
    tree = parser.parse(PYTHON_CODE)
    extractor = FunctionExtractor("python")
    funcs = extractor.extract_functions(tree.root_node)
    assert len(funcs) == 2
    foo = next(f for f in funcs if f.name == "foo")
    assert foo.signature == "(x: int, y: str)"
    assert foo.return_type == "bool"
    assert foo.start_line == 5

    method = next(f for f in funcs if f.name == "method")
    assert "self" in method.signature
    assert method.return_type == "None"


def test_python_classes():
    parser = TreeSitterParser("python")
    tree = parser.parse(PYTHON_CODE)
    extractor = FunctionExtractor("python")
    classes = extractor.extract_classes(tree.root_node)
    assert len(classes) == 2
    bar = next(c for c in classes if c.name == "Bar")
    assert bar.bases == []

    baz = next(c for c in classes if c.name == "Baz")
    assert baz.bases == ["Bar"]


# ==================== Java ====================

JAVA_CODE = b'''\
import java.util.List;

public class Foo {
    public int bar(String x) {
        return 1;
    }
}
'''


def test_java_imports():
    parser = TreeSitterParser("java")
    tree = parser.parse(JAVA_CODE)
    extractor = ImportExtractor("java")
    imports = extractor.extract(tree.root_node)
    assert len(imports) == 1
    assert imports[0].module == "java.util.List"


def test_java_functions():
    parser = TreeSitterParser("java")
    tree = parser.parse(JAVA_CODE)
    extractor = FunctionExtractor("java")
    funcs = extractor.extract_functions(tree.root_node)
    assert len(funcs) == 1
    assert funcs[0].name == "bar"
    assert funcs[0].signature == "(String x)"
    assert funcs[0].return_type == "int"


def test_java_classes():
    parser = TreeSitterParser("java")
    tree = parser.parse(JAVA_CODE)
    extractor = FunctionExtractor("java")
    classes = extractor.extract_classes(tree.root_node)
    assert len(classes) == 1
    assert classes[0].name == "Foo"


# ==================== Go ====================

GO_CODE = b'''\
package main

import "fmt"

func Add(a int, b int) int {
    return a + b
}
'''


def test_go_imports():
    parser = TreeSitterParser("go")
    tree = parser.parse(GO_CODE)
    extractor = ImportExtractor("go")
    imports = extractor.extract(tree.root_node)
    assert len(imports) == 1
    assert imports[0].module == "fmt"


def test_go_functions():
    parser = TreeSitterParser("go")
    tree = parser.parse(GO_CODE)
    extractor = FunctionExtractor("go")
    funcs = extractor.extract_functions(tree.root_node)
    assert len(funcs) == 1
    assert funcs[0].name == "Add"
    assert funcs[0].signature == "(a int, b int)"
    assert funcs[0].return_type == "int"


def test_go_classes():
    parser = TreeSitterParser("go")
    tree = parser.parse(GO_CODE)
    extractor = FunctionExtractor("go")
    classes = extractor.extract_classes(tree.root_node)
    assert classes == []


# ==================== TypeScript ====================

TS_CODE = b'''\
import { User } from "./user";

function greet(name: string): string {
    return "Hello " + name;
}

class MyClass extends BaseClass implements IInterface {
    method(): void {}
}
'''


def test_ts_imports():
    parser = TreeSitterParser("typescript")
    tree = parser.parse(TS_CODE)
    extractor = ImportExtractor("typescript")
    imports = extractor.extract(tree.root_node)
    assert len(imports) == 1
    assert imports[0].module == "./user"
    assert "User" in imports[0].names


def test_ts_functions():
    parser = TreeSitterParser("typescript")
    tree = parser.parse(TS_CODE)
    extractor = FunctionExtractor("typescript")
    funcs = extractor.extract_functions(tree.root_node)
    assert len(funcs) == 1
    assert funcs[0].name == "greet"
    assert funcs[0].signature == "(name: string)"
    assert funcs[0].return_type == "string"


def test_ts_classes():
    parser = TreeSitterParser("typescript")
    tree = parser.parse(TS_CODE)
    extractor = FunctionExtractor("typescript")
    classes = extractor.extract_classes(tree.root_node)
    assert len(classes) == 1
    assert classes[0].name == "MyClass"
    assert "BaseClass" in classes[0].bases
    assert "IInterface" in classes[0].bases


# ==================== Error Handling ====================

def test_python_syntax_error():
    bad_code = b'def foo(\n    pass\n'
    parser = TreeSitterParser("python")
    tree = parser.parse(bad_code)
    assert tree is not None  # tree-sitter 会尝试恢复解析
    extractor = FunctionExtractor("python")
    funcs = extractor.extract_functions(tree.root_node)
    # 语法错误时不应抛异常，但可能无法提取到完整函数
    # 这里只验证不抛异常即可


def test_unsupported_language():
    with pytest.raises(ValueError, match="Unsupported language"):
        TreeSitterParser("rust")
