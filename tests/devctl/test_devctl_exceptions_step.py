"""The exceptions step: each suppression has exactly one listed, current exception."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_workspace import Workspace
from devctl.check.exceptions import ExceptionsStep, normal_rule, scan
from devctl.check.steps import StepResult

ENTRY = """
[[exception]]
id = "{id}"
path = "{path}"
rule = "{rule}"
reason = "Runs the build tool with fixed arguments"
remove_when = "The build tool has a Python API"
"""
KIT_FILE_LOCK = (
    'kit_version = "0.2.0"\nstack = "python"\n\n[[file]]\n'
    'path = "tools/devctl/devctl/run.py"\nkind = "managed"\nsha256 = "' + "a" * 64 + '"\n'
)


def setup(workspace: Workspace, source: str, *entries: tuple[str, str, str]) -> StepResult:
    workspace.write(".rapid-ship/kit.lock", 'kit_version = "0.2.0"\nstack = "python"\n')
    workspace.write("src/app/run.py", source)
    text = "".join(ENTRY.format(id=i, path=p, rule=r) for i, p, r in entries)
    workspace.write(".rapid-ship/exceptions.toml", text)
    return ExceptionsStep().run(workspace.context())


def test_marked_suppression_with_entry_passes(workspace: Workspace) -> None:
    result = setup(
        workspace,
        "import subprocess\nsubprocess.run(['make'])  # noqa: S603  # rs-exception: EX-1\n",
        ("EX-1", "src/app/run.py", "S603"),
    )

    assert result.status == "passed", result.details


def test_unmarked_suppression_fails(workspace: Workspace) -> None:
    result = setup(workspace, "x = 1  # type: ignore[assignment]\n")

    assert result.details == (
        "src/app/run.py:1: suppression assignment needs '# rs-exception: EX-<n>' "
        "and an entry in .rapid-ship/exceptions.toml",
    )


def test_stale_entry_fails(workspace: Workspace) -> None:
    result = setup(workspace, "x = 1\n", ("EX-1", "src/app/run.py", "S603"))

    assert result.details == ("EX-1 is stale: no suppression carries it; delete the entry",)


def test_id_used_twice_fails(workspace: Workspace) -> None:
    result = setup(
        workspace,
        "a = 1  # noqa: E501  # rs-exception: EX-1\nb = 2  # noqa: E501  # rs-exception: EX-1\n",
        ("EX-1", "src/app/run.py", "E501"),
    )

    assert "EX-1 is used on 2 lines; each ID is used once" in result.details


def test_marker_for_another_path_or_rule_fails(workspace: Workspace) -> None:
    result = setup(
        workspace,
        "a = 1  # noqa: E501  # rs-exception: EX-1\nb = 2  # noqa: E501  # rs-exception: EX-2\n",
        ("EX-1", "src/app/other.py", "E501"),
        ("EX-2", "src/app/run.py", "S603"),
    )

    assert "src/app/run.py:1: EX-1 names src/app/other.py, not this file" in result.details
    assert (
        "src/app/run.py:2: EX-2 is for rule S603, which is not suppressed on this line"
        in result.details
    )


def test_unknown_id_fails(workspace: Workspace) -> None:
    result = setup(workspace, "a = 1  # noqa: E501  # rs-exception: EX-9\n")

    assert "src/app/run.py:1: EX-9 is not in .rapid-ship/exceptions.toml" in result.details


def test_invalid_exceptions_file_blocks_the_step(workspace: Workspace) -> None:
    # Plan 2's load_exceptions rejects blank fields, malformed IDs and repeated IDs.
    result = setup(
        workspace, "x = 1\n", ("EX-1", "src/app/run.py", "E501"), ("EX-1", "src/app/run.py", "S603")
    )

    assert result.status == "blocked"
    assert "EX-1" in result.details[0]


def test_skip_markers_and_calls_are_suppressions(workspace: Workspace) -> None:
    result = setup(
        workspace,
        "import pytest\n"
        "@pytest.mark.skipif(True, reason='x')\n"
        "def test_a():\n"
        "    pytest.skip('later')\n",
    )

    assert [d.split(":")[1] for d in result.details] == ["2", "4"]


def test_a_byte_order_mark_does_not_hide_a_skip_marker(workspace: Workspace) -> None:
    workspace.write(".rapid-ship/kit.lock", 'kit_version = "0.2.0"\nstack = "python"\n')
    workspace.write_with_bom(
        "src/app/run.py", "import pytest\n@pytest.mark.skip(reason='x')\ndef test_a(): pass\n"
    )
    workspace.write(".rapid-ship/exceptions.toml", "")

    result = ExceptionsStep().run(workspace.context())

    assert [d.split(":")[1] for d in result.details] == ["2"]


def test_strings_and_kit_files_are_not_suppressions(workspace: Workspace) -> None:
    workspace.write("tools/devctl/devctl/run.py", "x = 1  # noqa: E501\n")
    workspace.write(".rapid-ship/kit.lock", KIT_FILE_LOCK)
    workspace.write("src/app/run.py", "TEXT = '# noqa: E501'\n")
    workspace.write("docs/notes.md", "Write `# noqa: S603  # rs-exception: EX-<n>`.\n")
    workspace.write(".rapid-ship/exceptions.toml", "")

    assert ExceptionsStep().run(workspace.context()).status == "passed"


def test_a_kit_file_under_kit_exclude_is_scanned(workspace: Workspace) -> None:
    # [kit] exclude lists tools/devctl, so the project owns the file and its suppressions.
    workspace.write("tools/devctl/devctl/run.py", "x = 1  # noqa: E501\n")
    workspace.write(".rapid-ship/kit.lock", KIT_FILE_LOCK)
    workspace.write(".rapid-ship/exceptions.toml", "")

    result = ExceptionsStep().run(workspace.context(excluded=("tools/devctl",)))

    assert result.details == (
        "tools/devctl/devctl/run.py:1: suppression E501 needs '# rs-exception: EX-<n>' "
        "and an entry in .rapid-ship/exceptions.toml",
    )


def test_workflow_ignore_comment_needs_an_exception(workspace: Workspace) -> None:
    workspace.write(
        ".github/workflows/ci.yml", "permissions: {}  # zizmor: ignore[excessive-permissions]\n"
    )

    result = setup(workspace, "x = 1\n")

    assert result.details == (
        ".github/workflows/ci.yml:1: suppression zizmor:excessive-permissions needs "
        "'# rs-exception: EX-<n>' and an entry in .rapid-ship/exceptions.toml",
    )


def test_workflow_ignore_with_several_names_matches_its_entry(workspace: Workspace) -> None:
    workspace.write(
        ".github/workflows/ci.yml",
        "permissions: write-all  # zizmor: ignore[excessive-permissions, artipacked]"
        "  # rs-exception: EX-1\n",
    )

    result = setup(
        workspace,
        "x = 1\n",
        ("EX-1", ".github/workflows/ci.yml", "zizmor:artipacked,excessive-permissions"),
    )

    assert result.status == "passed", result.details


@pytest.mark.parametrize(
    ("rule", "normal"),
    [
        ("S607, S603", "S603,S607"),
        ("zizmor:excessive-permissions,artipacked", "zizmor:artipacked,excessive-permissions"),
        ("zizmor: unpinned-uses, artipacked", "zizmor:artipacked,unpinned-uses"),
        ("mypy:disable-error-code", "mypy:disable-error-code"),
        ("arg-type,call-arg", "arg-type,call-arg"),
        ("file-size", "file-size"),
    ],
)
def test_normal_rule_sorts_the_names_after_a_tool_prefix(rule: str, normal: str) -> None:
    assert normal_rule(rule) == normal


def test_marked_autouse_fixture_is_validated_unmarked_one_is_left_to_diff(
    workspace: Workspace,
) -> None:
    workspace.write(
        "tests/conftest.py",
        "import pytest\n"
        "@pytest.fixture(autouse=True)  # rs-exception: EX-1\n"
        "def fake_clock(): pass\n"
        "@pytest.fixture(autouse=True)\n"
        "def other(): pass\n",
    )

    result = setup(workspace, "x = 1\n", ("EX-1", "tests/conftest.py", "autouse"))

    assert result.status == "passed", result.details


# The gitleaks line is split so that documents quoting this test hold no allow comment.
EVERY_PYTHON_SUPPRESSION = (
    "# ruff: noqa: e501\n"
    "# flake8: noqa\n"
    '# mypy: disable-error-code="arg-type"\n'
    "import pytest\n"
    "from pytest import mark\n"
    "yaml = pytest.importorskip('yaml')  # noqa: f401\n"
    "pytestmark = mark.xfail\n"
    "x = f()  # type: ignore[call-arg, arg-type]  # noqa: E501, F821\n"
    "KEY = 'k'  # gitleaks" + ":allow  # NOQA\n"
    "TEXT = '# noqa: E501  # type: ignore'\n"
    "y = g()  # type: ignore\n"
    "@pytest.mark.skipif(\n"
    "    True, reason='r'\n"
    ")\n"
    "def test_a() -> None:  # pragma: no cover\n"
    "    pytest.skip('later')\n"
    "    pytest.xfail('known')  # mypy: ignore-errors\n"
)


def test_each_python_suppression_names_its_rule(tmp_path: Path) -> None:
    (tmp_path / "test_all.py").write_text(EVERY_PYTHON_SUPPRESSION)

    lines = scan(tmp_path, ["test_all.py"], frozenset(), "python")

    assert {line.number: list(line.rules) for line in lines} == {
        1: ["E501"],
        2: ["noqa"],
        3: ["mypy:disable-error-code"],
        6: ["F401", "importorskip"],
        7: ["xfail"],
        8: ["E501,F821", "arg-type,call-arg"],
        9: ["noqa", "gitleaks"],
        11: ["type-ignore"],
        12: ["skipif"],
        15: ["no-cover"],
        16: ["skip"],
        17: ["mypy:ignore-errors", "xfail"],
    }


def test_the_agnostic_stack_reads_only_text_rules(workspace: Workspace) -> None:
    workspace.write(".rapid-ship/kit.lock", 'kit_version = "0.2.0"\nstack = "agnostic"\n')
    workspace.write(".rapid-ship/exceptions.toml", "")
    workspace.write("src/run.py", "x = 1  # noqa: E501\n")
    workspace.write("notes.txt", "token  # gitleaks" + ":allow\n")

    result = ExceptionsStep().run(workspace.context(stack="agnostic"))

    assert result.details == (
        "notes.txt:1: suppression gitleaks needs '# rs-exception: EX-<n>' "
        "and an entry in .rapid-ship/exceptions.toml",
    )


def test_a_marker_on_a_python_line_without_a_suppression_fails(workspace: Workspace) -> None:
    result = setup(workspace, "x = 1  # rs-exception: EX-1\n", ("EX-1", "src/app/run.py", "S603"))

    assert result.details == (
        "src/app/run.py:1: EX-1 is for rule S603, which is not suppressed on this line",
    )


def test_symlinks_and_files_that_are_not_utf8_are_not_scanned(workspace: Workspace) -> None:
    workspace.write(".rapid-ship/kit.lock", 'kit_version = "0.2.0"\nstack = "python"\n')
    workspace.write(".rapid-ship/exceptions.toml", "")
    (workspace.root.parent / "outside.py").write_text("x = 1  # noqa: E501\n")
    (workspace.root / "alias.py").symlink_to("../outside.py")
    (workspace.root / "latin1.py").write_bytes(b"x = 1  # noqa: E501 \xe9\n")

    assert ExceptionsStep().run(workspace.context()).status == "passed"


def test_a_missing_kit_lock_blocks_the_step(workspace: Workspace) -> None:
    workspace.write(".rapid-ship/exceptions.toml", "")

    result = ExceptionsStep().run(workspace.context())

    assert result.status == "blocked"
    assert result.details == (".rapid-ship/kit.lock: missing; run rapid-ship init",)
