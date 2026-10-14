"""rapid-ship init: create-only, all-or-nothing writes into scratch repositories (offline)."""

import errno
import os
from pathlib import Path

import pytest

from rapid_ship.kit import init as init_module
from rapid_ship.kit import lock as lock_module
from rapid_ship.kit.init import init_repository, resolve_variables
from rapid_ship.kit.lock import LOCK_PATH, file_sha256, read_lock
from rapid_ship.kit.templates import KitError, KitRefusal


def files_in(root):
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if ".git" not in p.relative_to(root).parts
    )


def test_init_writes_every_template_and_records_the_lock(git_repo, make_templates, kit_variables):
    templates = make_templates()

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=templates
    )

    assert result.conflicts == () and result.skipped == ()
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
    assert os.readlink(git_repo / ".claude/skills/rs-demo") == "../../.agents/skills/rs-demo"
    assert os.access(git_repo / "devctl", os.X_OK)
    assert (git_repo / ".github/CODEOWNERS").read_text() == "* @octo\n"
    lock = read_lock(git_repo)
    entries = {entry.path: entry for entry in lock.entries}
    assert entries["devctl"].sha256 == file_sha256((templates / "common/devctl").read_bytes())
    assert entries["AGENTS.md"].template_sha256 == file_sha256(b"# demo-app\n")
    assert (lock.stack, dict(lock.variables)) == ("python", kit_variables)


def test_existing_seeded_files_are_skipped_and_still_locked(
    git_repo, make_templates, kit_variables, commit_all
):
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
    git_repo, make_templates, kit_variables, commit_all, target
):
    (git_repo / "README.md").write_text("# Ours\n")
    (git_repo / "AGENTS.md").symlink_to(target)
    commit_all(git_repo)

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert (result.conflicts, result.skipped) == ((), ("AGENTS.md",))
    assert os.readlink(git_repo / "AGENTS.md") == target
    assert (git_repo / "README.md").read_text() == "# Ours\n"
    assert not (git_repo.parent / "outside.md").exists()
    assert {e.path: e.kind for e in read_lock(git_repo).entries}["AGENTS.md"] == "seeded"


def test_an_existing_python_project_gets_no_new_project_seeds(
    git_repo, make_templates, kit_variables, commit_all
):
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


def link_github_outside(root):
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
    git_repo, make_templates, kit_variables, commit_all, arrange, conflict
):
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
    tmp_path, git_repo, make_templates, kit_variables, commit_all
):
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


def test_init_needs_a_stack_without_pyproject(git_repo, make_templates, kit_variables):
    with pytest.raises(KitError, match="pass --stack python or --stack neutral"):
        init_repository(
            git_repo, stack=None, variables=kit_variables, templates_root=make_templates()
        )


def test_the_stack_version_wins_on_init(git_repo, make_templates, kit_variables):
    path = "tools/devctl/devctl/stack.py"
    templates = make_templates(changes={f"common/{path}": "common\n", f"python/{path}": "python\n"})

    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=templates)

    assert (git_repo / path).read_text() == "python\n"
    assert {e.path: e for e in read_lock(git_repo).entries}[path].sha256 == file_sha256(b"python\n")


def test_a_failed_write_removes_everything_init_created(
    git_repo, make_templates, kit_variables, monkeypatch
):
    calls = []
    real = init_module.create_file

    def failing(path, content, *, executable=False):
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
    git_repo, make_templates, kit_variables, monkeypatch
):
    def refuse(target, path, *rest):  # Path.symlink_to also passes target_is_directory
        raise OSError(errno.EPERM, "Operation not permitted", str(path))

    monkeypatch.setattr(init_module.os, "symlink", refuse)

    with pytest.raises(
        KitError, match=r"Operation not permitted.*removed the files it had created"
    ):
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )
    assert files_in(git_repo) == []


@pytest.mark.parametrize("project_toml", [True, False])
def test_a_failed_lock_write_removes_everything_init_created(
    git_repo, make_templates, kit_variables, monkeypatch, project_toml
):
    # Without a template under .rapid-ship, write_lock creates that directory itself.
    changes = {} if project_toml else {"python/.rapid-ship/project.toml": None}

    def failing(path, content, *, mode=0o600):
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
    git_repo, make_templates, kit_variables, monkeypatch
):
    def refuse(root, lock):
        raise KitError(".rapid-ship/kit.lock: .rapid-ship is a symlink")

    monkeypatch.setattr(init_module, "write_lock", refuse)

    with pytest.raises(KitError, match=r"is a symlink.*removed the files it had created"):
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )
    assert files_in(git_repo) == []


def test_variables_default_from_the_directory(tmp_path):
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
def test_invalid_variables_are_refused(tmp_path, options):
    with pytest.raises(KitError):
        resolve_variables(tmp_path / "demo", **options)


def test_variables_default_from_a_relative_root(tmp_path, monkeypatch):
    (tmp_path / "demo-app").mkdir()
    monkeypatch.chdir(tmp_path / "demo-app")

    assert resolve_variables(Path("."))["project_name"] == "demo-app"


def test_explicit_variables_replace_the_defaults(tmp_path):
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


def test_an_invalid_value_is_named_with_its_option(tmp_path):
    with pytest.raises(KitError, match="owner '-x' is not a GitHub login; check --owner"):
        resolve_variables(tmp_path / "demo", owner="-x")
