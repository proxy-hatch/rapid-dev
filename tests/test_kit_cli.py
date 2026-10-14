"""The rapid-ship command line in scratch repositories (offline)."""

import functools
import json
import os
from importlib.metadata import PackageNotFoundError

import pytest

from rapid_ship.cli import main
from rapid_ship.kit.sync import sync_repository
from rapid_ship.kit.templates import installed_version


def test_init_status_and_sync_with_the_packaged_kit(git_repo, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)

    assert main(["init", "--stack", "neutral", "--owner", "octo"]) == 0
    out = capsys.readouterr().out
    assert "Next: commit these files on a branch, then run the rs-setup skill" in out
    assert "* @octo" in (git_repo / ".github/CODEOWNERS").read_text().splitlines()
    assert main(["status", "--strict"]) == 0
    capsys.readouterr()
    assert main(["status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["strict_ok"] is True
    assert main(["sync", "--in-place"]) == 0
    assert "Kit is current; nothing to sync." in capsys.readouterr().out


def test_init_skips_a_seeded_file_that_is_a_symlink(git_repo, commit_all, monkeypatch, capsys):
    # A common layout in agent repositories. init, status and sync never write or read it.
    (git_repo / "AGENTS.md").write_text("# Ours\n")
    (git_repo / "CLAUDE.md").symlink_to("AGENTS.md")
    commit_all(git_repo)
    monkeypatch.chdir(git_repo)

    assert main(["init", "--stack", "neutral", "--owner", "octo"]) == 0

    out = capsys.readouterr().out
    assert "Skipped existing seeded files; rs-setup merges them:\n  AGENTS.md\n  CLAUDE.md\n" in out
    commit_all(git_repo, "Add the Kit")
    assert main(["status", "--strict"]) == 0
    assert main(["sync", "--in-place"]) == 0
    assert os.readlink(git_repo / "CLAUDE.md") == "AGENTS.md"
    assert (git_repo / "AGENTS.md").read_text() == "# Ours\n"


def test_init_without_an_owner_leaves_the_walk_line_for_rs_setup(git_repo, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)

    assert main(["init", "--stack", "neutral"]) == 0

    assert "# * @<owner>" in (git_repo / ".github/CODEOWNERS").read_text().splitlines()
    assert "CODEOWNERS has no owner line yet; rs-setup writes it." in capsys.readouterr().out


@pytest.fixture
def fixture_kit(make_templates, monkeypatch):
    root = make_templates()
    monkeypatch.setattr("rapid_ship.kit.templates.packaged_templates", lambda: root)
    return root


def test_a_managed_conflict_exits_1_and_writes_nothing(
    git_repo, fixture_kit, commit_all, monkeypatch, capsys
):
    (git_repo / "devctl").write_text("ours\n")
    commit_all(git_repo)
    monkeypatch.chdir(git_repo)

    assert main(["init", "--stack", "python"]) == 1

    assert "devctl: exists" in capsys.readouterr().err
    assert not (git_repo / ".rapid-ship").exists()


def test_strict_status_fails_on_a_modified_managed_file(git_repo, fixture_kit, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)
    assert main(["init", "--stack", "python"]) == 0
    (git_repo / "devctl").write_text("changed\n")
    capsys.readouterr()

    assert main(["status"]) == 0
    assert main(["status", "--strict"]) == 1
    assert "modified          devctl" in capsys.readouterr().out


def test_strict_status_passes_with_an_excluded_modified_file(
    git_repo, fixture_kit, write_kit_settings, monkeypatch, capsys
):
    monkeypatch.chdir(git_repo)
    assert main(["init", "--stack", "python"]) == 0
    write_kit_settings(git_repo, exclude=["devctl"])
    (git_repo / "devctl").write_text("ours\n")
    capsys.readouterr()

    assert main(["status", "--strict"]) == 0
    assert "excluded          devctl" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("arrange", "argv", "code", "message"),
    [
        (
            lambda root: (root / "notes.txt").write_text("x\n"),
            ["init", "--stack", "neutral"],
            1,
            "the work tree has changes",
        ),
        (lambda root: None, ["status"], 2, "kit.lock is missing; run rapid-ship init"),
        (lambda root: None, ["init"], 2, "pass --stack python or --stack neutral"),
        (lambda root: None, ["init", "--stack", "neutral", "--owner=-x"], 2, "owner"),
    ],
)
def test_refusals_exit_1_and_errors_exit_2(
    git_repo, monkeypatch, capsys, arrange, argv, code, message
):
    arrange(git_repo)
    monkeypatch.chdir(git_repo)

    assert main(argv) == code
    assert message in capsys.readouterr().err


def test_outside_a_work_tree_exits_1(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert main(["status"]) == 1
    assert "not inside a git work tree" in capsys.readouterr().err


def test_a_command_is_required():
    with pytest.raises(SystemExit) as raised:
        main([])
    assert raised.value.code == 2


# The version comes from the installed package's metadata. A source run without it (for example
# PYTHONPATH=. python -m rapid_ship) must say so, not fail with a traceback.


@pytest.fixture
def no_package_metadata(monkeypatch):
    def missing(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr("importlib.metadata.version", missing)


@pytest.mark.parametrize("argv", [["--version"], ["init", "--stack", "neutral"]])
def test_missing_package_metadata_exits_2_and_writes_nothing(
    git_repo, monkeypatch, capsys, no_package_metadata, argv
):
    monkeypatch.chdir(git_repo)

    assert main(argv) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("rapid-ship: ") and "package metadata" in captured.err
    assert not (git_repo / ".rapid-ship").exists()


def test_help_does_not_need_the_package_metadata(
    tmp_path, monkeypatch, capsys, no_package_metadata
):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as raised:
        main(["--help"])

    assert raised.value.code == 0
    assert "usage: rapid-ship" in capsys.readouterr().out


# status and sync after the packaged templates change. Offline: the old release's templates and
# the pull request are fakes.

PULL_REQUEST = "https://github.com/octo/demo-app/pull/1"
CLI = "tools/devctl/devctl/cli.py"


@pytest.fixture
def vendored(git_repo, fixture_kit, commit_all, monkeypatch):
    """The fixture Kit, vendored and committed in git_repo. Returns the old template root."""
    monkeypatch.chdir(git_repo)
    assert main(["init", "--stack", "python"]) == 0
    commit_all(git_repo, "Add the Kit")
    return fixture_kit


@pytest.fixture
def release(vendored, make_templates, monkeypatch):
    """Install a newer Kit; changes edit its templates. sync's merge base is the old Kit."""

    def install(changes):
        new = make_templates("new", changes)
        monkeypatch.setattr("rapid_ship.kit.templates.packaged_templates", lambda: new)
        monkeypatch.setattr(
            "rapid_ship.cli.sync_repository",
            functools.partial(
                sync_repository,
                old_templates=lambda version: vendored,
                open_pull_request=lambda root, branch, base, title, body: PULL_REQUEST,
            ),
        )

    return install


def test_status_lists_what_differs_from_the_lock_and_the_release(
    vendored, git_repo, release, capsys
):
    (git_repo / CLI).write_text("local\n")
    release({"common/devctl": "#!/bin/sh\necho newer\n"})
    capsys.readouterr()

    assert main(["status", "--strict"]) == 1

    lines = capsys.readouterr().out.splitlines()
    version = installed_version()
    assert lines[0] == f"Kit {version} (installed rapid-ship {version}), stack python"
    assert f"modified          {CLI}" in lines
    assert "outdated          devctl" in lines
    assert lines[-1].endswith(" managed files unchanged.")


def test_status_json_reports_each_list_and_the_strict_verdict(vendored, git_repo, release, capsys):
    release({"common/devctl": "#!/bin/sh\necho newer\n"})
    capsys.readouterr()

    assert main(["status", "--json", "--strict"]) == 1

    report = json.loads(capsys.readouterr().out)
    assert set(report) == {
        "kit_version",
        "installed_version",
        "stack",
        "files",
        "outdated",
        "not_installed",
        "strict_ok",
    }
    assert report["stack"] == "python"
    assert (report["outdated"], report["strict_ok"]) == (["devctl"], False)
    assert {"path": "devctl", "kind": "managed", "state": "unchanged"} in report["files"]


def test_sync_in_place_replaces_an_unchanged_file(vendored, git_repo, release, capsys):
    release({"common/devctl": "#!/bin/sh\necho newer\n"})
    capsys.readouterr()

    assert main(["sync", "--in-place"]) == 0

    out = capsys.readouterr().out
    assert "Replaced with the new template:\n  devctl\n" in out
    assert out.endswith("Wrote the changes to the work tree.\n")
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho newer\n"


def test_sync_opens_a_pull_request_from_its_branch(vendored, git_repo, release, run_git, capsys):
    release({"common/devctl": "#!/bin/sh\necho newer\n"})
    capsys.readouterr()

    assert main(["sync"]) == 0

    branch = f"rapid-ship/kit-sync-{installed_version()}"
    assert capsys.readouterr().out.endswith(f"Opened {PULL_REQUEST} on {branch}.\n")
    assert run_git(git_repo, "branch", "--show-current").strip() == branch


def test_sync_lists_each_conflict_with_its_diff_and_the_ways_out(
    vendored, git_repo, release, capsys
):
    (git_repo / CLI).write_text("one\ntwo\nthree\nfour\nlocal five\n")
    release(
        {
            "common/devctl": "#!/bin/sh\necho newer\n",
            f"common/{CLI}": "one\ntwo\nthree\nfour\nFIVE\n",
        }
    )
    capsys.readouterr()

    assert main(["sync", "--in-place"]) == 1

    out = capsys.readouterr().out
    assert "Replaced with the new template:\n  devctl\n" in out
    assert f"Conflict: {CLI}: " in out
    assert "-five" in out and "+FIVE" in out
    assert "make the file equal the new template" in out and "`[kit] exclude`" in out
    assert out.endswith("Wrote the changes to the work tree.\n")


def test_a_sync_that_only_conflicts_says_nothing_was_written(vendored, git_repo, release, capsys):
    (git_repo / CLI).write_text("one\ntwo\nthree\nfour\nlocal five\n")
    release({f"common/{CLI}": "one\ntwo\nthree\nfour\nFIVE\n"})
    capsys.readouterr()

    assert main(["sync", "--in-place"]) == 1

    out = capsys.readouterr().out
    assert f"Conflict: {CLI}: " in out
    assert out.endswith("Nothing was written.\n")
    assert "Wrote the changes" not in out and "Opened" not in out
    assert (git_repo / CLI).read_text() == "one\ntwo\nthree\nfour\nlocal five\n"


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a file with mode 000")
@pytest.mark.parametrize("argv", [["status", "--strict"], ["sync", "--in-place"]])
def test_an_unreadable_managed_file_exits_2_without_a_traceback(vendored, git_repo, capsys, argv):
    unreadable = git_repo / CLI
    unreadable.chmod(0)
    capsys.readouterr()
    try:
        code = main(argv)
    finally:
        unreadable.chmod(0o644)

    assert code == 2
    err = capsys.readouterr().err
    assert err.startswith("rapid-ship: ") and "Permission denied" in err and CLI in err


def test_a_current_kit_still_lists_missing_files(vendored, git_repo, capsys):
    (git_repo / "devctl").unlink()
    capsys.readouterr()

    assert main(["sync", "--in-place"]) == 0

    out = capsys.readouterr().out
    assert out.splitlines()[0] == "Kit is current; nothing to sync."
    assert "  devctl\n" in out
    assert not (git_repo / "devctl").exists()
