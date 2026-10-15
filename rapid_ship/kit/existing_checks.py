"""The checks a repository already has, which rapid-ship init lists for rs-setup to combine with
devctl's: tool settings, git hooks and workflows.

It only reads. It opens a few files and asks git for two paths, and runs no project code and no
hook. A file it cannot read is listed as "<path> (unreadable)" so that init still succeeds.
"""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rapid_ship.kit.git import hooks_setup
from rapid_ship.kit.templates import KitError

# The file is the configuration, so its presence counts.
_SETTINGS_FILES = (
    "ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    ".mypy.ini",
    "pytest.ini",
    ".flake8",
    ".pylintrc",
    ".isort.cfg",
)
_HOOK_FILES = (".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml")
# These files serve many tools, so they count only with a section of a check. pytest reads
# [tool:pytest] in setup.cfg and [pytest] in tox.ini.
_SHARED_FILES = ("setup.cfg", "tox.ini")
_TOOL_SECTIONS = frozenset({"mypy", "flake8", "tool:pytest", "pytest", "isort"})
_SECTION = re.compile(r"^\[([^\]]+)\]", re.MULTILINE)  # at the start of a line, not indented
_PYPROJECT_TABLES = (
    ("tool", "ruff"),
    ("tool", "mypy"),
    ("tool", "pytest"),  # [tool.pytest.ini_options], and pytest 9's native [tool.pytest]
    ("tool", "black"),
    ("tool", "isort"),
    ("tool", "pylint"),
)
_WORKFLOWS = ".github/workflows"
_HOOKS_OFF = "/dev/null"  # a hooks path that turns hooks off, as the Kit commands do


def find_existing_checks(root: Path) -> tuple[str, ...]:
    """The tool settings, hooks and workflows in root, as sorted paths relative to root.

    A path outside root, such as the hooks of a linked worktree, is absolute. A directory ends in
    a slash. Call it before init writes anything: it lists what the repository had.
    """
    found = [*_settings(root), *_hooks(root), *_workflows(root)]
    return tuple(sorted(found))


def _settings(root: Path) -> list[str]:
    found = [name for name in _SETTINGS_FILES if (root / name).is_file()]
    for name in _SHARED_FILES:
        found += _read(root, name, _has_tool_section)
    return found + _read(root, "pyproject.toml", _has_tool_table)


def _read(root: Path, name: str, in_use: Callable[[str], bool]) -> list[str]:
    """[name] when the file exists and in_use says so of its text, "name (unreadable)" when it
    cannot be read or parsed, else nothing."""
    path = root / name
    if not path.is_file():
        return []
    try:
        used = in_use(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, RecursionError):
        return [f"{name} (unreadable)"]
    return [name] if used else []


def _has_tool_section(text: str) -> bool:
    return any(match[1] in _TOOL_SECTIONS for match in _SECTION.finditer(text))


def _has_tool_table(text: str) -> bool:
    document = tomllib.loads(text)
    for keys in _PYPROJECT_TABLES:
        node: Any = document
        for key in keys:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, dict):
            return True
    return False


def _hooks(root: Path) -> list[str]:
    found = [name for name in _HOOK_FILES if (root / name).is_file()]
    if (root / ".husky").is_dir():
        found.append(".husky/")
    try:
        configured, directory = hooks_setup(root)
    except KitError:
        return [*found, "git hooks (unreadable)"]
    if configured and configured != _HOOKS_OFF:
        found.append(f"{configured} (core.hooksPath)")
    if not directory.is_dir():  # git's default directory may not exist; /dev/null is no directory
        return found
    try:
        # Git runs a hook only when it is executable, and the .sample files are examples.
        hooks = [
            path
            for path in directory.iterdir()
            if not path.name.endswith(".sample") and path.is_file() and os.access(path, os.X_OK)
        ]
    except OSError:
        return [*found, f"{_display(root, directory)} (unreadable)"]
    return found + [_display(root, path) for path in hooks]


def _display(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _workflows(root: Path) -> list[str]:
    try:
        names = [
            path.name
            for path in (root / _WORKFLOWS).iterdir()
            if path.suffix in (".yml", ".yaml") and path.is_file()
        ]
    except (FileNotFoundError, NotADirectoryError):
        return []
    except OSError:
        return [f"{_WORKFLOWS} (unreadable)"]
    return [f"{_WORKFLOWS}/{name}" for name in names]
