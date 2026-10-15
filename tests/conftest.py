"""Shared offline fixtures: small Kit template trees and scratch git repositories."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

from check_workspace import Workspace, new_workspace
from devctl.process import run_process

KIT_TOML = """\
seeded = [".github/CODEOWNERS", ".rapid-ship/project.toml", "AGENTS.md"]
new_project = ["pyproject.toml", "src/__package__/__init__.py"]
executable = ["devctl"]
optional_skills = ["rs-extra"]
variables = ["owner", "package", "project_name", "repository"]
"""

TEMPLATE_FILES = {
    "kit.toml": KIT_TOML,
    "common/devctl": "#!/bin/sh\necho devctl\n",
    "common/tools/devctl/devctl/cli.py": "one\ntwo\nthree\nfour\nfive\n",
    "common/AGENTS.md": "# {{project_name}}\n",
    "common/.github/CODEOWNERS": "* @{{owner}}\n",
    "common/.agents/skills/rs-demo/SKILL.md": "demo\n",
    "common/.agents/skills/rs-extra/SKILL.md": "extra\n",
    "python/.rapid-ship/project.toml": 'stack = "python"\n\n[kit]\noptional = []\n',
    "agnostic/.rapid-ship/project.toml": 'stack = "agnostic"\n\n[kit]\noptional = []\n',
    "python/pyproject.toml": '[project]\nname = "{{project_name}}"\n',
    "python/src/__package__/__init__.py": '"""{{package}}."""\n',
}


@pytest.fixture
def kit_variables() -> dict[str, str]:
    return {
        "project_name": "demo-app",
        "package": "demo_app",
        "owner": "octo",
        "repository": "octo/demo-app",
    }


@pytest.fixture
def make_templates(tmp_path: Path) -> Callable[..., Path]:
    """Write a template tree under tmp_path/name. changes add or replace files; None removes one."""

    def make(name: str = "templates", changes: Mapping[str, str | None] | None = None) -> Path:
        root = tmp_path / name
        for relative, content in {**TEMPLATE_FILES, **(changes or {})}.items():
            if content is not None:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        return root

    return make


def _git(root: Path, *args: str) -> str:
    result = run_process(["git", *args], root, 60)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout


@pytest.fixture
def run_git() -> Callable[..., str]:
    return _git


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """An empty repository on main. Its commits need no signing and run no hooks."""
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    settings = {
        "user.name": "Test",
        "user.email": "test@example.invalid",
        "commit.gpgsign": "false",
        "core.hooksPath": "/dev/null",
    }
    for key, value in settings.items():
        _git(root, "config", key, value)
    return root


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """A git repository for devctl check tests."""
    return new_workspace(tmp_path / "repo")


@pytest.fixture
def commit_all() -> Callable[..., None]:
    def commit(root: Path, message: str = "Commit") -> None:
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "--allow-empty", "-m", message)

    return commit


@pytest.fixture
def write_kit_settings() -> Callable[..., None]:
    """Replace root/.rapid-ship/project.toml with a Python one holding these [kit] lists."""

    def write(root: Path, *, optional: Sequence[str] = (), exclude: Sequence[str] = ()) -> None:
        path = root / ".rapid-ship/project.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        kit = f"optional = {json.dumps(list(optional))}\nexclude = {json.dumps(list(exclude))}\n"
        path.write_text(
            f'stack = "python"\n\n[kit]\n{kit}'
        )  # a JSON list of strings is a TOML array

    return write


@pytest.fixture
def vendored(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
) -> Path:
    """The fixture Kit, vendored and committed in git_repo by init. Returns its template root.

    test_kit_cli.py overrides it with a version that runs the rapid-ship command.
    """
    from rapid_ship.kit.init import init_repository

    old = make_templates("old")
    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=old)
    return old
