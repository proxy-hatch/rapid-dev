"""The Python stack: its check steps, how pytest names tests and which suppressions it carries."""

from __future__ import annotations

import ast
import io
import json
import re
import tempfile
import tokenize
from collections.abc import Iterator, Sequence
from pathlib import Path

from devctl.check.steps import (
    CheckContext,
    CommandStep,
    StepResult,
    Tier,
    blocked,
    command_result,
    failed,
    output_tail,
    passed,
    run_tool,
)

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

# Spec section 5 names pip-audit because `uv audit` is still experimental (uv 0.13.1 says so) and
# uv 0.11.0 exits 0 with known vulnerabilities. uv 0.13.1 exits 1 for user errors too, so no
# exit code tells findings from errors. The step reads pip-audit's JSON report instead.
PIP_AUDIT = "pip-audit==2.10.1"


class AuditStep:
    """Audit the locked dependencies, all groups and extras, for known vulnerabilities."""

    name = "audit"
    tier: Tier = "full"

    def run(self, context: CheckContext) -> StepResult:
        with tempfile.TemporaryDirectory(prefix="devctl-audit-") as scratch:
            requirements = Path(scratch, "requirements.txt")
            report = Path(scratch, "audit.json")
            export = (
                *("uv", "export", "--locked", "--format", "requirements-txt"),
                *("--all-groups", "--all-extras", "--no-emit-project", "--no-emit-local"),
                *("--no-header", "--quiet"),
                *("--output-file", str(requirements)),
            )
            exported = run_tool(context.repo.root, export, 300)
            if exported is None or exported.timed_out or exported.returncode != 0:
                return command_result(self.name, export, exported, frozenset())
            audit = (
                *("uv", "tool", "run", "--from", PIP_AUDIT, "pip-audit"),
                *("--requirement", str(requirements)),
                *("--require-hashes", "--disable-pip", "--strict", "--progress-spinner", "off"),
                *("--format", "json", "--output", str(report)),
            )
            audited = run_tool(context.repo.root, audit, 600)
            if audited is None or audited.timed_out:
                return command_result(self.name, audit, audited, frozenset())
            vulnerabilities = _vulnerabilities(report)
            if vulnerabilities is None:
                return blocked(
                    self.name, "pip-audit wrote no readable report", *output_tail(audited)
                )
            if vulnerabilities:
                return failed(self.name, *vulnerabilities)
            if audited.returncode != 0:
                return blocked(
                    self.name,
                    f"pip-audit exited {audited.returncode}, but its report lists no vulnerability",
                    *output_tail(audited),
                )
            return passed(self.name)


def _vulnerabilities(report: Path) -> list[str] | None:
    """One line per distinct vulnerability in pip-audit's JSON report; None when unreadable.

    pip-audit 2.10.1 can list the same vulnerability twice. A shape this does not understand is
    None, never an empty list, so it cannot pass.
    """
    try:
        document = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    dependencies = document.get("dependencies") if isinstance(document, dict) else None
    if not isinstance(dependencies, list):
        return None
    lines: list[str] = []
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            return None
        found = dependency.get("vulns", [])  # A skipped dependency has no `vulns`.
        if not isinstance(found, list):
            return None
        for vulnerability in found:
            line = _vulnerability_line(dependency, vulnerability)
            if line is None:
                return None
            lines.append(line)
    return list(dict.fromkeys(lines))


def _vulnerability_line(dependency: dict[str, object], vulnerability: object) -> str | None:
    if not isinstance(vulnerability, dict):
        return None
    name, version = dependency.get("name"), dependency.get("version")
    identifier, fixes = vulnerability.get("id"), vulnerability.get("fix_versions", [])
    if not (isinstance(name, str) and isinstance(version, str) and isinstance(identifier, str)):
        return None
    if not isinstance(fixes, list) or not all(isinstance(fix, str) for fix in fixes):
        return None
    fixed = f"fixed in {', '.join(fixes)}" if fixes else "no fix yet"
    return f"{name} {version}: {identifier} ({fixed})"


def is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _parse(source: str) -> ast.Module:
    """Parse source. ast.parse rejects the UTF-8 byte-order mark that some editors write first."""
    return ast.parse(source.removeprefix("\ufeff"))


def test_identities(source: str) -> list[str]:
    """Pytest's default names: test* functions, and test* methods in Test* classes."""
    return list(_tests(_parse(source).body, ""))


def _tests(body: Sequence[ast.stmt], prefix: str) -> Iterator[str]:
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            yield prefix + node.name
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            yield from _tests(node.body, f"{prefix}{node.name}::")


_TRUTHY_CALLS = frozenset({"assertTrue", "assert_"})
_EQUAL_CALLS = frozenset(
    {"assertEqual", "assertEquals", "assertIs", "assertGreaterEqual", "assertLessEqual"}
)
_REFLEXIVE = (ast.Eq, ast.Is, ast.GtE, ast.LtE)


def tautologies(source: str) -> list[tuple[int, str]]:
    """Assertions that cannot fail; SyntaxError propagates."""
    return [
        (node.lineno, ast.unparse(node))
        for node in ast.walk(_parse(source))
        if isinstance(node, ast.Assert | ast.Call) and _tautological(node)
    ]


def _tautological(node: ast.Assert | ast.Call) -> bool:
    if isinstance(node, ast.Assert):
        return _always_true(node.test)
    return isinstance(node.func, ast.Attribute) and _tautological_call(node.func.attr, node.args)


def _tautological_call(name: str, args: list[ast.expr]) -> bool:
    if name in _TRUTHY_CALLS and args:
        return _truthy_constant(args[0])
    return name in _EQUAL_CALLS and len(args) >= 2 and _same(args[0], args[1])


def _always_true(test: ast.expr) -> bool:
    if _truthy_constant(test):
        return True
    return (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], _REFLEXIVE)
        and _same(test.left, test.comparators[0])
    )


def _truthy_constant(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and bool(node.value)


def _same(first: ast.expr, second: ast.expr) -> bool:
    return ast.dump(first) == ast.dump(second)


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
        tree = _parse(source)
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
        tree = _parse(source)
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
