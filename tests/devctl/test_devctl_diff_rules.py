"""Tautologies, new autouse fixtures and the Protected-path listing."""

from __future__ import annotations

import pytest

from check_workspace import Workspace
from devctl.check.diff import DiffStep, codeowners_match, protected_patterns
from devctl.check.steps import StepResult

ALWAYS_TRUE = "is always true; assert on the behaviour instead"


def change(workspace: Workspace, path: str, before: str, after: str) -> StepResult:
    workspace.write(path, before)
    base = workspace.commit()
    workspace.write(path, after)
    return DiffStep().run(workspace.context(base=base))


@pytest.mark.parametrize(
    "after",
    [
        "def test_total():\n    assert True\n",
        "def test_total():\n    assert total(1) == total(1)\n",
        "class TestTotal:\n    def test_total(self):\n        self.assertEqual(x, x)\n",
    ],
)
def test_assertion_turned_into_a_tautology_fails(workspace: Workspace, after: str) -> None:
    result = change(
        workspace, "tests/test_total.py", "def test_total():\n    assert total(1) == 1\n", after
    )

    # The class-based case also renames the test, which the removed-test rule reports.
    [tautology] = [detail for detail in result.details if detail.endswith(ALWAYS_TRUE)]
    assert result.status == "failed"
    assert tautology.startswith("tests/test_total.py:")


def test_a_byte_order_mark_does_not_hide_a_tautology(workspace: Workspace) -> None:
    workspace.write_with_bom("tests/test_total.py", "def test_total():\n    assert total(1) == 1\n")
    base = workspace.commit()
    workspace.write_with_bom("tests/test_total.py", "def test_total():\n    assert True\n")

    result = DiffStep().run(workspace.context(base=base))

    assert result.status == "failed"
    assert result.details[0] == f"tests/test_total.py:2: assert True {ALWAYS_TRUE}"


def test_existing_tautology_is_not_reported(workspace: Workspace) -> None:
    source = "def test_placeholder():\n    assert True\n"

    assert change(workspace, "tests/test_p.py", source, source + "\n").status == "passed"


def test_new_autouse_fixture_needs_an_exception_marker(workspace: Workspace) -> None:
    before = "import pytest\n@pytest.fixture(autouse=True)\ndef old(): pass\n"
    after = before + "@pytest.fixture(autouse=True)\ndef fake_clock(): pass\n"

    result = change(workspace, "tests/conftest.py", before, after)

    assert result.status == "failed"
    assert result.details[0] == (
        "tests/conftest.py:4: new autouse fixture fake_clock needs an exception: add "
        "'# rs-exception: EX-<n>' on its decorator line and an entry with rule autouse"
    )


def test_a_byte_order_mark_does_not_hide_a_new_autouse_fixture(workspace: Workspace) -> None:
    workspace.write_with_bom("tests/conftest.py", "import pytest\n")
    base = workspace.commit()
    workspace.write_with_bom(
        "tests/conftest.py",
        "import pytest\n@pytest.fixture(autouse=True)\ndef fake_clock(): pass\n",
    )

    result = DiffStep().run(workspace.context(base=base))

    assert result.status == "failed"
    assert result.details[0].startswith("tests/conftest.py:2: new autouse fixture fake_clock ")


def test_marked_autouse_fixture_passes(workspace: Workspace) -> None:
    after = "import pytest\n@pytest.fixture(autouse=True)  # rs-exception: EX-4\ndef fake(): pass\n"

    assert change(workspace, "tests/conftest.py", "", after).status == "passed"


def test_protected_paths_are_listed_without_failing(workspace: Workspace) -> None:
    workspace.write(
        ".github/CODEOWNERS",
        "* @owner\n# Flight: uncomment below.\n# .github/ @owner\n# /pyproject.toml @owner\n",
    )

    result = change(workspace, ".github/workflows/ci.yml", "on: push\n", "on: [push]\n")

    assert result.status == "passed"
    assert result.details == ("protected: .github/workflows/ci.yml",)


@pytest.mark.parametrize(
    ("pattern", "path", "matches"),
    [
        (".github/", ".github/workflows/ci.yml", True),
        (".github/", "docs/.github/x", True),
        ("/pyproject.toml", "pyproject.toml", True),
        ("/pyproject.toml", "sub/pyproject.toml", False),
        # The seeded Python set lists Ruff's settings at any depth, the way Ruff reads them.
        ("/**/ruff.toml", "ruff.toml", True),
        ("/**/ruff.toml", "src/app/ruff.toml", True),
        ("/**/ruff.toml", "src/app/ruff.toml.orig", False),
        ("docs/patterns/", "docs/patterns/settings.md", True),
        ("*.toml", "a/b.toml", True),
        ("tools/devctl/", "tools/devctl", False),
    ],
)
def test_codeowners_patterns(pattern: str, path: str, matches: bool) -> None:
    assert codeowners_match(pattern, path) is matches


def test_added_copy_of_an_existing_tautology_is_reported_at_the_later_line(
    workspace: Workspace,
) -> None:
    before = "def test_a():\n    assert True\n"

    result = change(
        workspace, "tests/test_p.py", before, before + "\ndef test_b():\n    assert True\n"
    )

    assert result.details[0] == f"tests/test_p.py:5: assert True {ALWAYS_TRUE}"


def test_agnostic_stack_lists_only_protected_paths(workspace: Workspace) -> None:
    workspace.write("tests/test_p.py", "def test_a():\n    assert f()\n")
    base = workspace.commit()
    workspace.write("tests/test_p.py", "def test_a():\n    assert True\n")

    result = DiffStep().run(workspace.context(base=base, stack="agnostic"))

    assert result == StepResult(
        "diff", "passed", ("no CODEOWNERS file; Protected paths are not listed",)
    )


def test_protected_patterns_come_from_the_file_github_reads_first(workspace: Workspace) -> None:
    workspace.write("docs/CODEOWNERS", "/docs/ @docs-owner\n")
    workspace.write(
        "CODEOWNERS",
        "# Owners: see the handbook.\n* @owner\n/api/ dev@example.com @team/api\n#/db/ @owner\n",
    )

    assert protected_patterns(workspace.root) == ["/api/", "/db/"]


def test_codeowners_that_is_not_utf8_blocks(workspace: Workspace) -> None:
    (workspace.root / ".github").mkdir()
    (workspace.root / ".github/CODEOWNERS").write_bytes(b"/api/ @owner \xff\n")

    result = change(workspace, "api/x.py", "a = 1\n", "a = 2\n")

    assert result.status == "blocked"
    assert result.details[0].startswith(".github/CODEOWNERS is not UTF-8")
