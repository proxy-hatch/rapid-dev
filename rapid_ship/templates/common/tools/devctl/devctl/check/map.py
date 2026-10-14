"""The map step: guide links resolve, and every skill has its discovery alias."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from devctl.check.markdown import navigation_links
from devctl.check.steps import CheckContext, StepResult, Tier, blocked, failed, passed
from devctl.repo import RepoError
from devctl.settings import ProjectSettings


class MapStep:
    name = "map"
    tier: Tier = "fast"

    def run(self, context: CheckContext) -> StepResult:
        try:
            files = context.repo.files()
        except RepoError as error:
            return blocked(self.name, str(error))
        root = context.repo.root
        found = guides(root, files, context.project)
        errors = [*link_errors(root, files, found), *skill_alias_errors(root, files)]
        return failed(self.name, *errors) if errors else passed(self.name)


def guides(root: Path, files: Sequence[str], project: ProjectSettings) -> list[str]:
    """The AGENTS.md files among `files` that exist as files. `project` carries map settings."""
    return [
        path
        for path in files
        if PurePosixPath(path).name == "AGENTS.md" and (root / path).is_file()
    ]


def link_errors(root: Path, files: Sequence[str], found: Sequence[str]) -> list[str]:
    """Map rule 1: each local link in each guide reaches a file the checkout maintains."""
    maintained = set(files)
    maintained.update(parent.as_posix() for path in files for parent in PurePosixPath(path).parents)
    aliases = [root / path for path in files if (root / path).is_symlink()]
    errors: list[str] = []
    for guide in found:
        try:
            links = navigation_links((root / guide).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            errors.append(f"{guide}:{error}")
            continue
        for line, target in links:
            if problem := _link_error(root, guide, line, target, maintained, aliases):
                errors.append(problem)
    return errors


def _link_error(
    root: Path,
    guide: str,
    line: int,
    target: str,
    maintained: set[str],
    aliases: Sequence[Path],
) -> str | None:
    target = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])", r"\1", target)
    url = urlsplit(target)
    if url.scheme or url.netloc or not url.path:
        return None
    dependency = Path(os.path.normpath((root / guide).parent / unquote(url.path)))
    if not dependency.exists():
        return f"{guide}:{line}: missing target {target!r}; update the navigation link"
    relative = dependency.relative_to(root).as_posix() if dependency.is_relative_to(root) else None
    # Git records directory aliases, not their descendants. Both the navigation
    # path (or its alias) and the resolved destination must belong to the checkout.
    resolved, real_root = dependency.resolve(), root.resolve()
    if (
        (relative in maintained or any(dependency.is_relative_to(alias) for alias in aliases))
        and resolved.is_relative_to(real_root)
        and resolved.relative_to(real_root).as_posix() in maintained
    ):
        return None
    return (
        f"{guide}:{line}: target {target!r} is not maintained in this checkout; "
        "track its source or update the navigation link"
    )


def skill_alias_errors(root: Path, files: Sequence[str]) -> list[str]:
    """Map rule 7, alias half: each skill has a SKILL.md and a symlink in .claude/skills."""
    present = set(files)
    canonical = _skill_names(root, files, ".agents/skills")
    aliases = _skill_names(root, files, ".claude/skills")
    errors = [_canonical_error(root, name) for name in sorted(canonical)]
    errors += [_alias_error(root, present, name) for name in sorted(canonical)]
    errors += [
        f".claude/skills/{name}: no matching .agents/skills/{name} in Git; "
        "remove the alias or add the skill"
        for name in sorted(aliases - canonical)
    ]
    errors += [
        f"{path}: only skill links belong in .claude/skills; remove it"
        for path in _stray_files(root, files)
    ]
    return [error for error in errors if error]


def _skill_names(root: Path, files: Sequence[str], surface: str) -> set[str]:
    names: set[str] = set()
    for path in files:
        if path.startswith(f"{surface}/"):
            name = path[len(surface) + 1 :].split("/", 1)[0]
            entry = root / surface / name
            if entry.is_symlink() or entry.is_dir():  # files are not skills
                names.add(name)
    return names


def _stray_files(root: Path, files: Sequence[str]) -> list[str]:
    """Files directly under .claude/skills, such as a guide; rule 7 allows only skill links."""
    names = {path.split("/")[2] for path in files if path.startswith(".claude/skills/")}
    entries = {name: root / ".claude/skills" / name for name in names}
    return sorted(
        f".claude/skills/{name}"
        for name, entry in entries.items()
        if not entry.is_symlink() and not entry.is_dir()
    )


def _canonical_error(root: Path, name: str) -> str | None:
    entry = root / ".agents/skills" / name
    if entry.is_symlink() and (
        entry.readlink().is_absolute() or not entry.resolve().is_relative_to(root.resolve())
    ):
        return f".agents/skills/{name}: make it a relative symlink inside the repository"
    if not (entry / "SKILL.md").is_file():
        return f".agents/skills/{name}: missing SKILL.md"
    return None


def _alias_error(root: Path, present: set[str], name: str) -> str | None:
    relative = f".claude/skills/{name}"
    alias, canonical = root / relative, root / ".agents/skills" / name
    expected = f"../../.agents/skills/{name}"
    if relative in present and alias.is_symlink():
        resolved = alias.resolve()
        inside = resolved.is_relative_to(root.resolve())
        if not alias.readlink().is_absolute() and inside and resolved == canonical.resolve():
            return None
        return f"{relative}: make it a relative symlink to {expected}"
    if (
        alias.is_dir()
        and not alias.is_symlink()
        and any(p.startswith(f"{relative}/") for p in present)
    ):
        return (
            f"{relative}: a copy is not an alias; replace it with a relative symlink to {expected}"
        )
    return f"{relative}: add a relative symlink to {expected} and track it in Git"
