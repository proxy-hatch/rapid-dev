"""rapid-ship init: create-only, all-or-nothing writes and the Kit commit, in scratch repositories
(offline)."""

import errno
import os
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

import pytest

from rapid_ship.files import create_file
from rapid_ship.kit import init as init_module
from rapid_ship.kit import lock as lock_module
from rapid_ship.kit.init import init_repository
from rapid_ship.kit.lock import LOCK_PATH, Lock, file_sha256, read_lock
from rapid_ship.kit.templates import KitError, KitRefusal, installed_version

INIT_BRANCH = "rapid-ship/init"


def files_in(root: Path) -> list[str]:
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if ".git" not in p.relative_to(root).parts
    )


def test_init_writes_every_template_and_records_the_lock(
    git_repo: Path, make_templates: Callable[..., Path], kit_variables: dict[str, str]
) -> None:
    templates = make_templates()

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=templates
    )

    assert result.conflicts == ()
    assert result.skipped == ()
    assert set(result.created) == {
        ".agents/skills/rs-demo/SKILL.md",
        ".claude/skills/rs-demo",
        ".github/CODEOWNERS",
        ".rapid-ship/project.toml",
        "AGENTS.md",
        "devctl",
        "pyproject.toml",
        "src/demo_app/__init__.py",
        "tools/devctl/devctl/cli.py",
        LOCK_PATH,
    }
    assert (git_repo / ".claude/skills/rs-demo").readlink() == Path("../../.agents/skills/rs-demo")
    assert os.access(git_repo / "devctl", os.X_OK)
    assert (git_repo / ".github/CODEOWNERS").read_text() == "* @octo\n"
    lock = read_lock(git_repo)
    entries = {entry.path: entry for entry in lock.entries}
    assert entries["devctl"].sha256 == file_sha256((templates / "common/devctl").read_bytes())
    assert entries["AGENTS.md"].template_sha256 == file_sha256(b"# demo-app\n")
    assert (lock.stack, dict(lock.variables)) == ("python", kit_variables)


def test_existing_seeded_files_are_skipped_and_still_locked(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
) -> None:
    (git_repo / "AGENTS.md").write_text("# Ours\n")
    commit_all(git_repo)

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert result.skipped == ("AGENTS.md",)
    assert (git_repo / "AGENTS.md").read_text() == "# Ours\n"
    assert {e.path: e.kind for e in read_lock(git_repo).entries}["AGENTS.md"] == "seeded"


@pytest.mark.parametrize("target", ["README.md", "missing.md", "../outside.md"])
def test_a_seeded_file_that_is_a_symlink_is_skipped(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
    target: str,
) -> None:
    (git_repo / "README.md").write_text("# Ours\n")
    (git_repo / "AGENTS.md").symlink_to(target)
    commit_all(git_repo)

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert (result.conflicts, result.skipped) == ((), ("AGENTS.md",))
    assert (git_repo / "AGENTS.md").readlink() == Path(target)
    assert (git_repo / "README.md").read_text() == "# Ours\n"
    assert not (git_repo.parent / "outside.md").exists()
    assert {e.path: e.kind for e in read_lock(git_repo).entries}["AGENTS.md"] == "seeded"


def test_an_existing_python_project_gets_no_new_project_seeds(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
) -> None:
    (git_repo / "pyproject.toml").write_text('[project]\nname = "ours"\n')
    commit_all(git_repo)

    result = init_repository(
        git_repo, stack=None, variables=kit_variables, templates_root=make_templates()
    )

    assert result.stack == "python"
    assert not (git_repo / "src").exists()
    assert (git_repo / "pyproject.toml").read_text() == '[project]\nname = "ours"\n'
    assert {"pyproject.toml", "src/demo_app/__init__.py"}.isdisjoint(
        e.path for e in read_lock(git_repo).entries
    )


def link_github_outside(root: Path) -> None:
    outside = root.parent / "outside"
    outside.mkdir()
    (root / ".github").symlink_to(outside)


@pytest.mark.parametrize(
    ("arrange", "conflict"),
    [
        (lambda root: (root / "devctl").write_text("ours\n"), "devctl: exists"),
        (
            lambda root: (root / "devctl").symlink_to("missing-target"),
            "devctl: devctl is a symlink",
        ),
        (
            lambda root: (root / "tools").write_text("a file\n"),
            "tools/devctl/devctl/cli.py: tools is not a directory",
        ),
        (
            lambda root: (root / ".gitignore").write_text("tools/\n"),
            "tools/devctl/devctl/cli.py: ignored by git",
        ),
        (link_github_outside, ".github/CODEOWNERS: .github is a symlink"),
    ],
)
def test_init_writes_nothing_on_any_conflict(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
    run_git: Callable[..., str],
    arrange: Callable[[Path], object],
    conflict: str,
) -> None:
    arrange(git_repo)
    commit_all(git_repo)
    before = files_in(git_repo)

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert result.created == ()
    assert any(item.startswith(conflict) for item in result.conflicts)
    assert files_in(git_repo) == before
    assert run_git(git_repo, "branch", "--list", INIT_BRANCH) == ""
    outside = git_repo.parent / "outside"
    assert not outside.exists() or list(outside.iterdir()) == []


def test_init_refuses_a_dirty_tree_an_existing_lock_or_a_non_repository(
    tmp_path: Path,
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
) -> None:
    templates = make_templates()
    (git_repo / "notes.txt").write_text("draft\n")
    with pytest.raises(KitRefusal, match="the work tree has changes"):
        init_repository(git_repo, stack="python", variables=kit_variables, templates_root=templates)
    assert files_in(git_repo) == ["notes.txt"]

    (git_repo / ".rapid-ship").mkdir()
    (git_repo / LOCK_PATH).write_text("")
    commit_all(git_repo)
    with pytest.raises(KitRefusal, match=r"kit\.lock exists"):
        init_repository(git_repo, stack="python", variables=kit_variables, templates_root=templates)

    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(KitRefusal, match="not inside a git work tree"):
        init_repository(plain, stack="python", variables=kit_variables, templates_root=templates)


def test_init_needs_a_stack_without_pyproject(
    git_repo: Path, make_templates: Callable[..., Path], kit_variables: dict[str, str]
) -> None:
    with pytest.raises(KitError, match="pass --stack python or --stack agnostic"):
        init_repository(
            git_repo, stack=None, variables=kit_variables, templates_root=make_templates()
        )


def test_the_stack_version_wins_on_init(
    git_repo: Path, make_templates: Callable[..., Path], kit_variables: dict[str, str]
) -> None:
    path = "tools/devctl/devctl/stack.py"
    templates = make_templates(changes={f"common/{path}": "common\n", f"python/{path}": "python\n"})

    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=templates)

    assert (git_repo / path).read_text() == "python\n"
    assert {e.path: e for e in read_lock(git_repo).entries}[path].sha256 == file_sha256(b"python\n")


def test_a_failed_write_removes_everything_init_created(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    real = create_file

    def failing(path: Path, content: bytes, *, executable: bool = False) -> None:
        calls.append(path)
        if len(calls) == 3:
            raise OSError("disk full")
        real(path, content, executable=executable)

    monkeypatch.setattr(init_module, "create_file", failing)

    with pytest.raises(KitError, match="disk full"):
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )
    assert files_in(git_repo) == []


def test_a_refused_symlink_stops_init_without_writing_a_copy(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Path.symlink_to also passes target_is_directory.
    def refuse(target: object, path: object, *rest: object) -> NoReturn:
        raise OSError(errno.EPERM, "Operation not permitted", str(path))

    monkeypatch.setattr(os, "symlink", refuse)

    with pytest.raises(
        KitError, match=r"Operation not permitted.*removed the files it had created"
    ):
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )
    assert files_in(git_repo) == []


@pytest.mark.parametrize("project_toml", [True, False])
def test_a_failed_lock_write_removes_everything_init_created(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    project_toml: bool,
) -> None:
    # Without a template under .rapid-ship, write_lock creates that directory itself.
    changes = {} if project_toml else {"python/.rapid-ship/project.toml": None}

    def failing(path: Path, content: bytes, *, mode: int = 0o600) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(lock_module, "atomic_replace", failing)

    with pytest.raises(KitError, match=r"read-only file system.*removed the files it had created"):
        init_repository(
            git_repo,
            stack="python",
            variables=kit_variables,
            templates_root=make_templates(changes=changes),
        )
    assert files_in(git_repo) == []


def test_a_lock_the_write_refuses_also_removes_everything_init_created(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(root: Path, lock: Lock) -> NoReturn:
        raise KitError(".rapid-ship/kit.lock: .rapid-ship is a symlink")

    monkeypatch.setattr(init_module, "write_lock", refuse)

    with pytest.raises(KitError, match=r"is a symlink.*removed the files it had created"):
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )
    assert files_in(git_repo) == []


# init commits the Kit on its own branch (spec section 3, init steps 5 to 8).


def test_init_commits_exactly_the_kit_on_its_own_branch(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
    run_git: Callable[..., str],
) -> None:
    (git_repo / ".gitignore").write_text("*.log\n")
    commit_all(git_repo, "Start")
    (git_repo / "debug.log").write_text("ignored, so the tree is clean\n")
    start = run_git(git_repo, "rev-parse", "HEAD").strip()

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert (result.branch, result.base) == (INIT_BRANCH, "main")
    assert run_git(git_repo, "branch", "--show-current").strip() == INIT_BRANCH
    assert result.commit == run_git(git_repo, "rev-parse", "HEAD").strip()
    assert run_git(git_repo, "rev-parse", "HEAD~1", "main").split() == [start, start]
    subject = run_git(git_repo, "log", "-1", "--format=%s").strip()
    assert subject == f"chore: vendor the rapid-ship Kit {installed_version()}"
    committed = run_git(git_repo, "show", "--name-only", "--format=", "HEAD").split()
    assert sorted(committed) == sorted(result.created)
    assert run_git(git_repo, "status", "--porcelain") == ""
    assert (git_repo / "debug.log").exists()


def test_init_from_a_detached_head_branches_at_that_commit(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
    run_git: Callable[..., str],
) -> None:
    commit_all(git_repo, "One")
    commit_all(git_repo, "Two")
    run_git(git_repo, "switch", "-q", "--detach", "HEAD~1")
    start = run_git(git_repo, "rev-parse", "HEAD").strip()

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert (result.branch, result.base) == (INIT_BRANCH, start)
    assert run_git(git_repo, "rev-parse", f"{INIT_BRANCH}~1").strip() == start
    assert run_git(git_repo, "branch", "--show-current").strip() == INIT_BRANCH


def test_init_without_commits_makes_the_first_commit_on_the_current_branch(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    run_git: Callable[..., str],
) -> None:
    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert (result.branch, result.base) == ("main", None)
    assert run_git(git_repo, "rev-list", "--count", "HEAD").strip() == "1"
    assert result.commit == run_git(git_repo, "rev-parse", "HEAD").strip()
    assert run_git(git_repo, "branch", "--list", INIT_BRANCH) == ""
    assert run_git(git_repo, "status", "--porcelain") == ""


def test_init_refuses_an_existing_init_branch_before_writing(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
    run_git: Callable[..., str],
) -> None:
    commit_all(git_repo)
    run_git(git_repo, "branch", INIT_BRANCH)

    with pytest.raises(KitRefusal, match=f"branch {INIT_BRANCH} exists"):
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )

    assert files_in(git_repo) == []
    assert run_git(git_repo, "branch", "--show-current").strip() == "main"


def test_a_dirty_tree_is_listed_up_to_20_paths_and_nothing_is_written(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
) -> None:
    (git_repo / "tracked.md").write_text("one\n")
    commit_all(git_repo)
    (git_repo / "tracked.md").write_text("two\n")
    names = [f"note{number:02}.md" for number in range(22)]
    for name in names:
        (git_repo / name).write_text("draft\n")

    with pytest.raises(KitRefusal) as refused:
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )

    lines = str(refused.value).splitlines()
    # git status lists tracked changes before untracked files.
    assert [line.strip() for line in lines if line.startswith("  ")] == [
        "tracked.md",
        *names[:19],
        "and 3 more",
    ]
    assert lines[0].startswith("the work tree has changes")
    assert "rs-setup" in lines[-1]
    assert "commit or stash" in lines[-1]
    assert files_in(git_repo) == sorted([*names, "tracked.md"])


@pytest.mark.parametrize("history", ["commits", "no commits"])
@pytest.mark.parametrize("cause", ["signing", "identity"])
def test_a_failed_commit_restores_the_starting_state(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
    run_git: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
    history: str,
    cause: str,
) -> None:
    if history == "commits":
        commit_all(git_repo, "Start")
    if cause == "signing":
        run_git(git_repo, "config", "commit.gpgsign", "true")
        run_git(git_repo, "config", "gpg.program", "false")
        expected = "gpg failed to sign"
    else:  # only this repository's configuration, which has no identity
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        for name in ("AUTHOR", "COMMITTER"):
            monkeypatch.delenv(f"GIT_{name}_NAME", raising=False)
            monkeypatch.delenv(f"GIT_{name}_EMAIL", raising=False)
        run_git(git_repo, "config", "--unset", "user.name")
        run_git(git_repo, "config", "--unset", "user.email")
        run_git(git_repo, "config", "user.useConfigOnly", "true")
        expected = "Author identity unknown"

    with pytest.raises(KitError) as stopped:
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )

    message = str(stopped.value)
    assert message.startswith("init stopped (git commit failed: ")
    assert expected in message
    assert files_in(git_repo) == []
    assert run_git(git_repo, "status", "--porcelain", "--untracked-files=all") == ""
    assert run_git(git_repo, "branch", "--show-current").strip() == "main"
    assert run_git(git_repo, "branch", "--list", "rapid-ship/*") == ""
    if history == "commits":
        assert message.endswith(f"back on main, {INIT_BRANCH} deleted")


def test_a_failed_write_on_the_init_branch_switches_back_and_deletes_it(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
    run_git: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit_all(git_repo, "Start")

    def refuse(target: object, path: object, *rest: object) -> NoReturn:
        raise OSError(errno.EPERM, "Operation not permitted", str(path))

    monkeypatch.setattr(os, "symlink", refuse)

    with pytest.raises(KitError, match=f"Operation not permitted.*back on main, {INIT_BRANCH}"):
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )
    assert files_in(git_repo) == []
    assert run_git(git_repo, "branch", "--show-current").strip() == "main"
    assert run_git(git_repo, "branch", "--list", "rapid-ship/*") == ""
