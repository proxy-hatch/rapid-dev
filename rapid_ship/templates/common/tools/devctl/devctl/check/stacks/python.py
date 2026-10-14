"""The Python stack: how pytest names tests. Task 9 adds the stack's check steps."""

from __future__ import annotations

import ast
from collections.abc import Iterator, Sequence


def is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def test_identities(source: str) -> list[str]:
    """Pytest's default names: test* functions, and test* methods in Test* classes."""
    return list(_tests(ast.parse(source).body, ""))


def _tests(body: Sequence[ast.stmt], prefix: str) -> Iterator[str]:
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            yield prefix + node.name
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            yield from _tests(node.body, f"{prefix}{node.name}::")
