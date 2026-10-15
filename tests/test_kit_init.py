"""rapid-ship init: create-only, all-or-nothing writes into scratch repositories (offline)."""

import errno
import os
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

import pytest

from rapid_ship.files import create_file
from rapid_ship.kit import init as init_module
from rapid_ship.kit import lock as lock_module
from rapid_ship.kit.init import _github_repository_name, init_repository, resolve_variables
from rapid_ship.kit.lock import LOCK_PATH, Lock, file_sha256, read_lock
from rapid_ship.kit.templates import KitError, KitRefusal


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
    with pytest.raises(KitError, match="pass --stack python or --stack neutral"):
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


def test_variables_default_from_the_directory(tmp_path: Path) -> None:
    assert resolve_variables(tmp_path / "Rapid-Ship.app") == {
        "project_name": "Rapid-Ship.app",
        "package": "rapid_ship_app",
        "owner": "",
        "repository": "",
    }


@pytest.mark.parametrize(
    "options",
    [
        {"name": "my project"},
        {"package": "class"},
        {"package": "3d"},
        {"owner": "-octo"},
        {"owner": 'octo"x'},
        {"owner": "o" * 40},
        {"repository": "octo"},
        {"repository": "octo/demo\nx"},
        {"repository": "octo/."},
        {"repository": "octo/.."},
    ],
)
def test_invalid_variables_are_refused(tmp_path: Path, options: dict[str, str]) -> None:
    with pytest.raises(KitError):
        resolve_variables(tmp_path / "demo", **options)


def test_variables_default_from_a_relative_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "demo-app").mkdir()
    monkeypatch.chdir(tmp_path / "demo-app")

    assert resolve_variables(Path())["project_name"] == "demo-app"


def test_explicit_variables_replace_the_defaults(tmp_path: Path) -> None:
    variables = resolve_variables(
        tmp_path / "demo",
        name="my.app",
        package="my_pkg",
        owner="octo-cat",
        repository="octo-cat/my.app",
    )

    assert variables == {
        "project_name": "my.app",
        "package": "my_pkg",
        "owner": "octo-cat",
        "repository": "octo-cat/my.app",
    }


def test_an_invalid_value_is_named_with_its_option(tmp_path: Path) -> None:
    with pytest.raises(KitError, match="owner '-x' is not a GitHub login; check --owner"):
        resolve_variables(tmp_path / "demo", owner="-x")


@pytest.mark.parametrize(
    ("url", "name"),
    [
        ("git@github.com:octo/Widget.git", "Widget"),
        ("git@github.com:octo/widget", "widget"),
        ("github.com:octo/widget.git", "widget"),
        ("https://github.com/octo/widget", "widget"),
        ("https://github.com/octo/widget.git", "widget"),
        ("http://github.com/octo/widget.git", "widget"),
        ("https://octo@github.com/octo/widget", "widget"),
        ("https://x-access-token:SECRET@github.com/octo/widget.git", "widget"),
        ("ssh://git@github.com/octo/widget.git", "widget"),
        ("https://github.com/octo/widget/", "widget"),
        ("https://github.com/octo/widget.git/", "widget"),
        ("https://GitHub.COM/octo/widget.git", "widget"),
        ("git@github.com:octo/my.app.git", "my.app"),
        ("https://github.com/octo/_bad", "_bad"),
    ],
)
def test_a_github_remote_url_gives_its_repository_name(url: str, name: str) -> None:
    assert _github_repository_name(url) == name


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/octo/widget.git",
        "git@gitlab.com:octo/widget.git",
        "https://github.com.example.invalid/octo/widget.git",
        "https://github.com@example.invalid/octo/widget.git",
        "https://example.invalid/github.com/octo/widget.git",
        "https://github.com/octo",
        "https://github.com/octo/widget/extra",
        "https://github.com/octo/widget?token=SECRET",
        "https://github.com/octo/.git",
        "/srv/git/widget.git",
        "../widget",
        "",
    ],
)
def test_another_host_or_an_unparsable_url_gives_no_name(url: str) -> None:
    assert _github_repository_name(url) is None


def test_variables_default_to_the_origin_repository_name(
    git_repo: Path, run_git: Callable[..., str]
) -> None:
    run_git(git_repo, "remote", "add", "origin", "git@github.com:octo/Widget.git")

    variables = resolve_variables(git_repo)

    assert variables["project_name"] == "Widget"
    assert variables["package"] == "widget"
    assert variables["repository"] == ""  # the name comes from origin; the repository is not set


def test_the_repository_option_beats_the_origin_remote(
    git_repo: Path, run_git: Callable[..., str]
) -> None:
    run_git(git_repo, "remote", "add", "origin", "https://github.com/octo/from-origin.git")

    variables = resolve_variables(git_repo, repository="octo/from-option")

    assert variables["project_name"] == "from-option"


def test_the_name_option_beats_the_repository_and_the_origin(
    git_repo: Path, run_git: Callable[..., str]
) -> None:
    run_git(git_repo, "remote", "add", "origin", "https://github.com/octo/from-origin.git")

    variables = resolve_variables(git_repo, name="mine", repository="octo/from-option")

    assert variables["project_name"] == "mine"


def test_a_remote_that_is_not_origin_does_not_name_the_project(
    git_repo: Path, run_git: Callable[..., str]
) -> None:
    run_git(git_repo, "remote", "add", "upstream", "https://github.com/octo/upstream-name.git")

    assert resolve_variables(git_repo)["project_name"] == "project"


def test_a_non_github_origin_falls_back_to_the_checkout_directory(
    git_repo: Path, run_git: Callable[..., str]
) -> None:
    run_git(git_repo, "remote", "add", "origin", "https://gitlab.com/octo/widget.git")

    assert resolve_variables(git_repo)["project_name"] == "project"


def test_a_repository_without_a_remote_uses_its_directory_name(git_repo: Path) -> None:
    assert resolve_variables(git_repo)["project_name"] == "project"


def test_a_linked_worktree_without_a_remote_uses_the_main_checkout_name(
    git_repo: Path, commit_all: Callable[..., None], run_git: Callable[..., str], tmp_path: Path
) -> None:
    commit_all(git_repo)
    linked = tmp_path / "random-worktree-name"
    run_git(git_repo, "worktree", "add", "-q", str(linked), "-b", "feature")

    assert resolve_variables(linked)["project_name"] == "project"


def test_a_linked_worktree_shares_the_origin_name(
    git_repo: Path, commit_all: Callable[..., None], run_git: Callable[..., str], tmp_path: Path
) -> None:
    run_git(git_repo, "remote", "add", "origin", "https://github.com/octo/Widget.git")
    commit_all(git_repo)
    linked = tmp_path / "random-worktree-name"
    run_git(git_repo, "worktree", "add", "-q", str(linked), "-b", "feature")

    assert resolve_variables(linked)["project_name"] == "Widget"


def test_an_invalid_origin_name_is_named_without_the_url_or_its_token(
    git_repo: Path, run_git: Callable[..., str]
) -> None:
    run_git(
        git_repo, "remote", "add", "origin", "https://x-access-token:SECRET@github.com/octo/_bad"
    )

    with pytest.raises(KitError, match="_bad") as raised:
        resolve_variables(git_repo)

    assert "SECRET" not in str(raised.value)
    assert "github.com" not in str(raised.value)


def test_a_repository_name_that_is_not_a_project_name_needs_the_name_option(tmp_path: Path) -> None:
    with pytest.raises(KitError, match=r"project name '\.github' .*check --name"):
        resolve_variables(tmp_path / "demo", repository="octo/.github")

    variables = resolve_variables(tmp_path / "demo", name="demo", repository="octo/.github")

    assert variables["repository"] == "octo/.github"
