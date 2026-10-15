"""Each reference kind in spec section 5 resolves only when its target exists."""

from __future__ import annotations

import pytest

from check_workspace import Workspace
from devctl.check.references import resolve

PYPROJECT = """
[tool.ruff.lint]
select = ["E", "S"]
ignore = ["S101"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"os.environ".msg = "Read settings through app.settings"

[tool.importlinter]
root_packages = ["app"]

[[tool.importlinter.contracts]]
name = "layers"
type = "layers"
layers = ["app.api", "app.core"]

[tool.mypy]
files = ["src", "tests"]
exclude = ["^src/app/generated/"]
"""

TESTS = """
def test_top(): pass
class TestCore:
    def test_runs(self): pass
"""


@pytest.mark.parametrize(
    ("reference", "resolves"),
    [
        ("check:map", True),
        ("check:nope", False),
        ("ruff:S603", True),
        ("ruff:S101", False),
        ("ruff:F401", False),
        ("banned:os.environ", True),
        ("banned:os.getenv", False),
        ("contract:layers", True),
        ("contract:missing", False),
        ("type:src/app/core.py", True),
        ("type:src/app/generated/x.py", False),
        ("type:scripts/run.py", False),
        ("type:src/app/absent.py", False),
        ("test:tests/test_core.py::TestCore::test_runs", True),
        ("test:tests/test_core.py::test_top", True),
        ("test:tests/test_core.py::test_absent", False),
        ("nonsense", False),
        ("lint:E501", False),
    ],
)
def test_python_references(workspace: Workspace, reference: str, resolves: bool) -> None:
    workspace.write("pyproject.toml", PYPROJECT)
    workspace.write("src/app/core.py", "")
    workspace.write("src/app/generated/x.py", "")
    workspace.write("scripts/run.py", "")
    workspace.write("tests/test_core.py", TESTS)

    reason = resolve(reference, workspace.context())

    assert (reason is None) is resolves, reason
    if reason is not None:
        assert reference in reason


def test_python_only_kinds_do_not_resolve_for_the_agnostic_stack(workspace: Workspace) -> None:
    workspace.write("pyproject.toml", PYPROJECT)

    reason = resolve("ruff:S603", workspace.context(stack="agnostic"))

    assert reason == "ruff:S603: unknown reference kind ruff for the agnostic stack"


@pytest.mark.parametrize("reference", [":x", "check:", "test:tests/test_core.py", "test:::x"])
def test_incomplete_references_say_how_to_write_them(workspace: Workspace, reference: str) -> None:
    reason = resolve(reference, workspace.context())

    assert reason is not None
    assert reason.startswith(f"{reference}: write ")


def test_a_reference_cannot_leave_the_repository(workspace: Workspace) -> None:
    workspace.write("tests/test_core.py", TESTS)

    reason = resolve("test:../repo/tests/test_core.py::test_top", workspace.context())

    assert (
        reason
        == "test:../repo/tests/test_core.py::test_top: ../repo/tests/test_core.py is not a file"
    )


def test_a_test_file_that_does_not_parse_does_not_resolve(workspace: Workspace) -> None:
    workspace.write("tests/test_core.py", "def test_top(:\n")

    reason = resolve("test:tests/test_core.py::test_top", workspace.context())

    assert reason is not None
    assert "tests/test_core.py does not parse" in reason


@pytest.mark.parametrize(
    ("name", "resolves"), [("checks_run", True), ("checks", False), ("run", False)]
)
def test_agnostic_stack_matches_a_test_name_as_a_whole_word(
    workspace: Workspace, name: str, resolves: bool
) -> None:
    workspace.write("tests/run.sh", "checks_run() { :; }\n")

    reason = resolve(f"test:tests/run.sh::{name}", workspace.context(stack="agnostic"))

    assert (reason is None) is resolves, reason


def test_python_kinds_name_a_missing_or_invalid_pyproject(workspace: Workspace) -> None:
    context = workspace.context()
    assert resolve("ruff:F401", context) == "ruff:F401: pyproject.toml is missing"

    workspace.write("pyproject.toml", "[tool.ruff\n")
    reason = resolve("ruff:F401", context)

    assert reason is not None
    assert reason.startswith("ruff:F401: pyproject.toml: ")


def test_a_malformed_setting_is_named_not_raised(workspace: Workspace) -> None:
    workspace.write("pyproject.toml", '[tool.ruff.lint]\nselect = "E"\nignore = [1]\n')

    reason = resolve("ruff:E501", workspace.context())

    assert reason == "ruff:E501: [tool.ruff.lint] ignore must be a list of strings"


@pytest.mark.parametrize(
    ("settings", "reference", "resolves"),
    [
        ("", "F401", True),  # Ruff's default select is E4, E7, E9 and F
        ("", "E501", False),
        ("", "S603", False),
        ('extend-select = ["S"]', "S603", True),
        ('select = ["ALL"]', "S603", True),
        ('select = ["ALL"]\nignore = ["ALL"]', "S603", False),  # ignore wins a tie
        ('select = ["S"]\nextend-ignore = ["S6"]', "S603", False),
        ('select = ["S"]\nextend-ignore = ["S6"]', "S101", True),
        ('select = ["S6"]\nignore = ["S"]', "S603", True),  # the longer select prefix wins
    ],
)
def test_ruff_selection_follows_prefix_length(
    workspace: Workspace, settings: str, reference: str, resolves: bool
) -> None:
    workspace.write("pyproject.toml", f"[tool.ruff.lint]\n{settings}\n")

    assert (resolve(f"ruff:{reference}", workspace.context()) is None) is resolves


def test_ruff_falls_back_to_the_top_level_settings(workspace: Workspace) -> None:
    workspace.write("pyproject.toml", '[tool.ruff]\nselect = ["S"]\n')

    assert resolve("ruff:S603", workspace.context()) is None


@pytest.mark.parametrize(
    ("settings", "path", "resolves"),
    [
        ('files = "src, tests"', "tests/test_core.py", True),
        ('files = ["src"]\nexclude = "^src/app/gen,erated/"', "src/app/gen,erated/x.py", False),
        ('files = ["src"]\nexclude = "^src/app/gen,erated/"', "src/app/core.py", True),
        ('files = ["."]', "scripts/run.py", True),
        ('files = ["./src/"]', "src/app/core.py", True),
        ('files = ["src/app/core.py"]', "src/app/core.py", True),
        ('files = ["src/app/co"]', "src/app/core.py", False),  # a name prefix is not a directory
        ("", "src/app/core.py", False),  # mypy checks only what `files` names
    ],
)
def test_type_reference_follows_mypy_files_and_exclude(
    workspace: Workspace, settings: str, path: str, resolves: bool
) -> None:
    workspace.write("pyproject.toml", f"[tool.mypy]\n{settings}\n")
    for name in (
        "src/app/core.py",
        "src/app/gen,erated/x.py",
        "scripts/run.py",
        "tests/test_core.py",
    ):
        workspace.write(name, "")

    assert (resolve(f"type:{path}", workspace.context()) is None) is resolves


def test_an_invalid_mypy_exclude_is_named(workspace: Workspace) -> None:
    workspace.write("pyproject.toml", '[tool.mypy]\nfiles = ["src"]\nexclude = ["("]\n')
    workspace.write("src/app/core.py", "")

    reason = resolve("type:src/app/core.py", workspace.context())

    assert reason == "type:src/app/core.py: [tool.mypy] exclude '(' is not a regular expression"
