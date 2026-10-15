"""Removed tests: identity across files, declarations, and unit or behavioural class."""

from __future__ import annotations

import pytest

from check_workspace import Workspace, gate_settings
from devctl.check.diff import Change, DiffStep, changed_files, glob_match, removed_tests
from devctl.check.steps import StepResult

EVIDENCE = "## Evidence\n\n~~~\n$ make test\nok\n~~~\n\nNot covered: x\n\n"
# A passed or failed result ends with this note: these workspaces have no CODEOWNERS file.
NO_CODEOWNERS = "no CODEOWNERS file; Protected paths are not listed"


def run(workspace: Workspace, base: str, body: str | None = None, **gate: object) -> StepResult:
    return DiffStep().run(workspace.context(base=base, pr_body=body, gate=gate_settings(**gate)))


def test_moved_test_is_not_removed() -> None:
    assert (
        removed_tests({"tests/test_a.py": (["test_x"], []), "tests/test_b.py": ([], ["test_x"])})
        == []
    )


def test_name_in_another_file_does_not_hide_a_removal() -> None:
    assert removed_tests({"tests/test_a.py": (["test_x", "test_y"], ["test_y"])}) == [
        "tests/test_a.py::test_x"
    ]
    assert removed_tests(
        {"tests/test_a.py": (["test_x"], []), "tests/test_b.py": (["test_x"], ["test_x"])}
    ) == ["tests/test_a.py::test_x"]


def test_undeclared_removal_fails_and_names_its_class(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "def test_create(): pass\ndef test_delete(): pass\n")
    workspace.write("tests/unit/test_math.py", "def test_add(): pass\n")
    base = workspace.commit()
    workspace.write("tests/test_api.py", "def test_create(): pass\n")
    workspace.write("tests/unit/test_math.py", "\n")

    result = run(workspace, base, EVIDENCE)

    assert result.status == "failed"
    assert result.details[:2] == (
        "removed unit test tests/unit/test_math.py::test_add: "
        "declare it under 'Removed tests:' in the PR's Evidence section",
        "removed behavioural test tests/test_api.py::test_delete: "
        "declare it under 'Removed tests:' in the PR's Evidence section",
    )


def test_declared_removal_passes_and_flight_waits_for_the_owner(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "class TestApi:\n    def test_delete(self): pass\n")
    base = workspace.commit()
    workspace.write("tests/test_api.py", "class TestApi:\n    pass\n")
    body = (
        EVIDENCE + "Removed tests:\n- tests/test_api.py::TestApi::test_delete: endpoint removed\n"
    )

    walk = run(workspace, base, body)
    flight = run(workspace, base, body, mode="flight")
    flight_off = run(
        workspace, base, body, mode="flight", owner_approves_behavioural_test_removal=False
    )

    assert walk.status == flight.status == flight_off.status == "passed"
    assert walk.details[0] == (
        "removed behavioural test tests/test_api.py::TestApi::test_delete: "
        "declared (endpoint removed)"
    )
    assert flight.details[0].endswith("; in Flight this waits for the owner's approval")
    assert flight_off.details[0] == walk.details[0]


def test_test_moved_to_an_untracked_file_is_not_removed(workspace: Workspace) -> None:
    workspace.write("tests/test_old.py", "def test_kept(): pass\n")
    base = workspace.commit()
    (workspace.root / "tests/test_old.py").unlink()
    workspace.write("tests/test_new.py", "def test_kept(): pass\n")

    assert run(workspace, base, EVIDENCE).status == "passed"


def test_removal_without_a_pr_body_explains_how_to_check_locally(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "def test_delete(): pass\n")
    base = workspace.commit()
    workspace.write("tests/test_api.py", "\n")

    result = run(workspace, base)

    assert result.details[0].endswith("(pass --pr-body <file> to check a body locally)")


def test_test_file_that_stops_parsing_fails(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "def test_delete(): pass\n")
    base = workspace.commit()
    workspace.write("tests/test_api.py", "def test_delete(:\n")

    assert (
        run(workspace, base, EVIDENCE)
        .details[0]
        .startswith("tests/test_api.py: cannot parse the tests at head")
    )


@pytest.mark.parametrize(
    ("base_has_mark", "head_has_mark"), [(True, True), (True, False), (False, True)]
)
def test_a_byte_order_mark_does_not_hide_a_removed_test(
    workspace: Workspace, base_has_mark: bool, head_has_mark: bool
) -> None:
    before = "def test_get(): pass\ndef test_delete(): pass\n"
    after = "def test_get(): pass\n"
    (workspace.write_with_bom if base_has_mark else workspace.write)("tests/test_api.py", before)
    base = workspace.commit()
    (workspace.write_with_bom if head_has_mark else workspace.write)("tests/test_api.py", after)

    result = run(workspace, base, EVIDENCE)

    assert result.status == "failed"
    assert result.details == (
        "removed behavioural test tests/test_api.py::test_delete: "
        "declare it under 'Removed tests:' in the PR's Evidence section",
        NO_CODEOWNERS,
    )


def test_no_base_is_not_applicable(workspace: Workspace) -> None:
    assert DiffStep().run(workspace.context()).status == "not_applicable"


def test_changed_files_include_untracked_files(workspace: Workspace) -> None:
    workspace.write("kept.txt", "a\n")
    workspace.write("edited file.txt", "a\n")
    workspace.write("gone.txt", "a\n")
    workspace.write(".gitignore", "*.log\n")
    base = workspace.commit()
    workspace.write("edited file.txt", "b\n")
    (workspace.root / "gone.txt").unlink()
    workspace.write("new/added.txt", "a\n")
    workspace.write("debug.log", "a\n")

    changes = changed_files(workspace.context().repo, base)

    assert sorted(changes, key=lambda change: change.path) == [
        Change("edited file.txt", "M"),
        Change("gone.txt", "D"),
        Change("new/added.txt", "A"),
    ]


@pytest.mark.parametrize(
    ("pattern", "path", "matches"),
    [
        ("tests/unit/**", "tests/unit/a/test_x.py", True),
        ("tests/*/test_x.py", "tests/unit/test_x.py", True),
        ("tests/*/test_x.py", "tests/unit/a/test_x.py", False),
        ("**/unit/**", "tests/unit/test_x.py", True),
        ("**/unit/**", "unit/test_x.py", True),
        ("tests/test_?.py", "tests/test_x.py", True),
        ("tests/test_?.py", "tests/test_xy.py", False),
        ("tests/unit.py", "tests/unitxpy", False),
    ],
)
def test_glob_match(pattern: str, path: str, matches: bool) -> None:
    assert glob_match(pattern, path) is matches


def test_deleted_test_file_removes_its_tests(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "class TestApi:\n    def test_get(self): pass\n")
    base = workspace.commit()
    (workspace.root / "tests/test_api.py").unlink()

    assert run(workspace, base, EVIDENCE).details == (
        "removed behavioural test tests/test_api.py::TestApi::test_get: "
        "declare it under 'Removed tests:' in the PR's Evidence section",
        NO_CODEOWNERS,
    )


def test_base_that_did_not_parse_holds_no_tests(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "def test_delete(:\n")
    base = workspace.commit()
    workspace.write("tests/test_api.py", "def test_delete(): pass\n")

    assert run(workspace, base, EVIDENCE) == StepResult("diff", "passed", (NO_CODEOWNERS,))


def test_head_that_is_not_utf8_cannot_parse(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "def test_delete(): pass\n")
    base = workspace.commit()
    (workspace.root / "tests/test_api.py").write_bytes(b"def test_delete(): pass  # \xff\n")

    result = run(workspace, base, EVIDENCE)

    assert result.status == "failed"
    assert result.details[1:] == (NO_CODEOWNERS,)
    assert result.details[0].startswith("tests/test_api.py: cannot parse the tests at head")


def test_agnostic_stack_does_not_read_tests(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "def test_delete(): pass\n")
    base = workspace.commit()
    workspace.write("tests/test_api.py", "\n")

    context = workspace.context(base=base, stack="agnostic")

    assert DiffStep().run(context) == StepResult("diff", "passed", (NO_CODEOWNERS,))


def test_unknown_base_is_blocked(workspace: Workspace) -> None:
    workspace.commit()

    result = DiffStep().run(workspace.context(base="0" * 40))

    assert result.status == "blocked"
    assert result.details[0].startswith("git diff:")
