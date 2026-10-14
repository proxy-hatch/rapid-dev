"""The Python stack: its check steps, how pytest names tests and which suppressions it carries."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Iterator, Sequence

from devctl.check.steps import CommandStep

# rapid_ship/kit/adopt.py copies these patterns, comment_rules, marker_rules, _codes and
# _dotted, because rapid-ship cannot import devctl. tests/devctl/test_devctl_adopt_rules.py
# fails when the copies differ.
_NOQA = re.compile(
    r"#\s*(?:(?:ruff|flake8)\s*:\s*)?noqa\b"
    r"(?::\s*(?P<codes>[A-Za-z]+[0-9]+(?:[\s,]+[A-Za-z]+[0-9]+)*))?",
    re.IGNORECASE,
)
_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore\b(?:\[(?P<codes>[^\]]*)\])?")
_MYPY = re.compile(r"#\s*mypy:\s*(?P<setting>ignore-errors|disable-error-code)")
_NO_COVER = re.compile(r"#\s*pragma:\s*no\s+cover", re.IGNORECASE)
_SKIP_MARKS = frozenset({"skip", "skipif", "xfail"})
_SKIP_CALLS = frozenset({"skip", "xfail", "importorskip"})

# `uv run` exits 2 when the project does not install the tool, so a missing tool is blocked, not
# failed. --locked stops a stale lock instead of rewriting it. lint-imports also exits 1 for its
# own errors. pytest exits 5 when it collects no tests.
FORMAT = CommandStep("format", "fast", ("uv", "run", "--locked", "ruff", "format", "--check", "."))
LINT = CommandStep(
    "lint", "fast", ("uv", "run", "--locked", "ruff", "check", "--output-format", "concise", ".")
)
TYPES = CommandStep("types", "full", ("uv", "run", "--locked", "mypy"))
CONTRACTS = CommandStep("contracts", "full", ("uv", "run", "--locked", "lint-imports"))
TESTS = CommandStep(
    "tests", "full", ("uv", "run", "--locked", "pytest"), failed_codes=frozenset({1, 5})
)


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


def comments(source: str) -> dict[int, str]:
    """Comment text by line. Source that does not tokenize falls back to text after '#'."""
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        return {t.start[0]: t.string for t in tokens if t.type == tokenize.COMMENT}
    except (tokenize.TokenError, SyntaxError):
        lines = enumerate(source.splitlines(), start=1)
        return {number: line[line.index("#") :] for number, line in lines if "#" in line}


def comment_rules(comment: str) -> list[str]:
    rules = [_codes(m.group("codes"), upper=True) or "noqa" for m in _NOQA.finditer(comment)]
    rules += [_codes(m.group("codes")) or "type-ignore" for m in _TYPE_IGNORE.finditer(comment)]
    rules += [f"mypy:{m.group('setting')}" for m in _MYPY.finditer(comment)]
    rules += ["no-cover" for _ in _NO_COVER.finditer(comment)]
    return rules


def _codes(text: str | None, *, upper: bool = False) -> str:
    parts = [part for part in re.split(r"[\s,]+", text or "") if part]
    return ",".join(sorted(part.upper() if upper else part for part in parts))


def marker_rules(source: str) -> list[tuple[int, str]]:
    """The (line, rule) of each skip or xfail marker and call in the syntax tree."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _SKIP_MARKS:
            if _dotted(node.value) in ("pytest.mark", "mark"):
                found.append((node.lineno, node.attr))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _SKIP_CALLS
            and _dotted(node.func.value) == "pytest"
        ):
            found.append((node.lineno, node.func.attr))
    return found


def autouse_fixtures(source: str) -> list[tuple[str, int]]:
    """The (name, decorator line) of each fixture declared with autouse=True."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [
        (node.name, decorator.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        for decorator in node.decorator_list
        if _is_autouse_fixture(decorator)
    ]


def _is_autouse_fixture(decorator: ast.expr) -> bool:
    if not isinstance(decorator, ast.Call) or _dotted(decorator.func) not in (
        "pytest.fixture",
        "fixture",
    ):
        return False
    return any(
        keyword.arg == "autouse"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in decorator.keywords
    )


def _dotted(node: ast.expr) -> str:
    """'pytest.mark' for that attribute chain; '' for anything that is not a plain chain."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else ""
    return ""
