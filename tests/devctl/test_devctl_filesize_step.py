"""The file-size step: source files stay within the line cap unless excepted."""

from __future__ import annotations

from typing import Any, cast

from check_workspace import Workspace
from devctl.check.filesize import LINE_CAP, FileSizeStep
from devctl.check.steps import StepResult


def run(workspace: Workspace, exceptions: str = "", **project: object) -> StepResult:
    workspace.write(".rapid-ship/kit.lock", 'kit_version = "0.2.0"\nstack = "python"\n')
    workspace.write(".rapid-ship/exceptions.toml", exceptions)
    return FileSizeStep().run(workspace.context(**cast("dict[str, Any]", project)))


FILE_SIZE = (
    '[[exception]]\nid = "EX-1"\npath = "src/app/big.py"\nrule = "file-size"\n'
    'reason = "Generated parser"\nremove_when = "The parser is generated at build time"\n'
)


def test_file_over_the_cap_fails(workspace: Workspace) -> None:
    workspace.write("src/app/big.py", "x = 1\n" * (LINE_CAP + 1))
    workspace.write("src/app/ok.py", "x = 1\n" * LINE_CAP)
    workspace.write("tests/test_long.py", "x = 1\n" * (LINE_CAP + 1))

    assert run(workspace).details == (
        "src/app/big.py: 501 lines exceeds the 500-line cap; "
        "split the file or add a file-size exception",
    )


def test_file_size_exception_allows_the_file(workspace: Workspace) -> None:
    workspace.write("src/app/big.py", "x = 1\n" * (LINE_CAP + 1))

    assert run(workspace, FILE_SIZE).status == "passed"


def test_exception_for_a_file_under_the_cap_is_stale(workspace: Workspace) -> None:
    workspace.write("src/app/big.py", "x = 1\n")

    assert run(workspace, FILE_SIZE).details == (
        "EX-1: src/app/big.py is within the 500-line cap or gone; delete this file-size exception",
    )


def test_no_source_roots_is_not_applicable(workspace: Workspace) -> None:
    assert run(workspace, source_roots=()).status == "not_applicable"


def over_cap() -> str:
    return "x = 1\n" * (LINE_CAP + 1)


def test_python_stack_counts_only_python_source(workspace: Workspace) -> None:
    workspace.write("src/app/data.json", over_cap())
    workspace.write("src/app/types.pyi", over_cap())

    assert run(workspace).details == (
        "src/app/types.pyi: 501 lines exceeds the 500-line cap; "
        "split the file or add a file-size exception",
    )


def test_agnostic_stack_counts_every_text_file(workspace: Workspace) -> None:
    workspace.write("src/app/data.json", over_cap())

    assert run(workspace, stack="agnostic").details == (
        "src/app/data.json: 501 lines exceeds the 500-line cap; "
        "split the file or add a file-size exception",
    )


def test_kit_file_is_skipped_unless_the_project_owns_it(workspace: Workspace) -> None:
    workspace.write("src/app/vendored.py", over_cap())
    workspace.write(".rapid-ship/exceptions.toml", "")
    workspace.write(
        ".rapid-ship/kit.lock",
        'kit_version = "0.2.0"\nstack = "python"\n\n[[file]]\n'
        'path = "src/app/vendored.py"\nkind = "managed"\nsha256 = "' + "a" * 64 + '"\n',
    )

    managed = FileSizeStep().run(workspace.context())
    owned = FileSizeStep().run(workspace.context(excluded=("src/app/vendored.py",)))

    assert managed.status == "passed"
    assert owned.details == (
        "src/app/vendored.py: 501 lines exceeds the 500-line cap; "
        "split the file or add a file-size exception",
    )


def test_symlinks_and_files_that_are_not_utf8_are_skipped(workspace: Workspace) -> None:
    workspace.write("docs/big.py", over_cap())
    (workspace.root / "src/app").mkdir(parents=True)
    (workspace.root / "src/app/alias.py").symlink_to("../../docs/big.py")
    (workspace.root / "src/app/blob.py").write_bytes(b"\xff\n" * (LINE_CAP + 1))

    assert run(workspace).status == "passed"


def test_details_are_sorted_by_path(workspace: Workspace) -> None:
    workspace.write("src/app/z.py", over_cap())
    workspace.write("src/app/a.py", over_cap())
    workspace.write("src/app/m.py", "x = 1\n")
    stale = FILE_SIZE.replace("EX-1", "EX-2").replace("src/app/big.py", "src/app/m.py")

    assert [line.split(":")[0] for line in run(workspace, stale).details] == [
        "src/app/a.py",
        "EX-2",
        "src/app/z.py",
    ]


def test_missing_kit_lock_blocks_the_step(workspace: Workspace) -> None:
    workspace.write(".rapid-ship/exceptions.toml", "")

    result = FileSizeStep().run(workspace.context())

    assert result.status == "blocked"
    assert result.details == (".rapid-ship/kit.lock: missing; run rapid-ship init",)
