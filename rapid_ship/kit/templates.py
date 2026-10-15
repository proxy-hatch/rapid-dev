"""Kit templates: the manifest, rendering for one project, and the project's Kit settings."""

from __future__ import annotations

import importlib.metadata
import os
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Literal

from rapid_ship.files import UnsafePath, relative_parts, safe_path

Stack = Literal["python", "agnostic"]
Kind = Literal["managed", "seeded"]
STACKS: tuple[Stack, ...] = ("python", "agnostic")

PROJECT_SETTINGS = ".rapid-ship/project.toml"
_VARIABLE = re.compile(r"\{\{([a-z_]+)\}\}")
_GENERATED = frozenset(
    {".venv", "__pycache__", ".DS_Store"}
)  # names skipped in every template tree
_MANIFEST_KEYS = ("seeded", "new_project", "executable", "optional_skills", "variables")


class KitError(Exception):
    """A Kit command could not run. The CLI exits 2."""


class KitRefusal(Exception):
    """The repository's state refuses the request. The CLI exits 1."""


@dataclass(frozen=True)
class Template:
    path: str  # project-relative POSIX path, variables already substituted
    kind: Kind
    content: bytes | None  # None for a symlink
    link: str | None  # "../../.agents/skills/<name>", for .claude/skills/<name>


@dataclass(frozen=True)
class KitManifest:
    seeded: frozenset[str]
    new_project: frozenset[str]
    executable: frozenset[str]
    optional_skills: frozenset[str]
    variables: frozenset[str]


def packaged_templates() -> Path:
    # rapid_ship is a regular package installed unpacked, so this is a filesystem path.
    return Path(str(files("rapid_ship").joinpath("templates")))


def installed_version() -> str:
    return importlib.metadata.version("rapid-ship")


def load_manifest(root: Path | None = None) -> KitManifest:
    path = (root or packaged_templates()) / "kit.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise KitError(f"cannot read the Kit manifest {path}: {error}") from error
    unknown = sorted(set(data) - set(_MANIFEST_KEYS))
    if unknown:
        raise KitError(f"kit.toml: unknown key {unknown[0]!r}")
    lists: dict[str, frozenset[str]] = {}
    for key in _MANIFEST_KEYS:
        items = data.get(key, [])
        if not isinstance(items, list) or not all(isinstance(item, str) and item for item in items):
            raise KitError(f"kit.toml {key}: expected a list of non-empty strings")
        lists[key] = frozenset(items)
    return KitManifest(**lists)


def render_path(path: str, variables: Mapping[str, str]) -> str:
    parts = PurePosixPath(path).parts
    if "__package__" in parts and not variables.get("package"):
        raise KitError(f"{path}: the package variable is required")
    return "/".join(variables["package"] if part == "__package__" else part for part in parts)


def render_files(
    stack: Stack, variables: Mapping[str, str], optional: Sequence[str], *, root: Path | None = None
) -> list[Template]:
    """Render every template for one project, sorted by path. root=None means the packaged ones."""
    root = root or packaged_templates()
    manifest = load_manifest(root)
    unknown = sorted(set(optional) - manifest.optional_skills)
    if unknown:
        raise KitError(f"unknown optional Kit skill {unknown[0]!r}")
    kept = _kept_by_git(root)
    sources = {
        **_layer(root, "common", kept),
        **_layer(root, stack, kept),
    }  # the stack layer overrides common
    templates: list[Template] = []
    for path, source in sorted(sources.items()):
        skill = _skill(path)
        if skill is not None and skill in manifest.optional_skills and skill not in optional:
            continue
        if path in manifest.seeded or path in manifest.new_project:
            text = _render_text(
                path, source.read_bytes().decode("utf-8"), variables, manifest.variables
            )
            templates.append(
                Template(render_path(path, variables), "seeded", text.encode("utf-8"), None)
            )
        elif "__package__" in PurePosixPath(path).parts:
            raise KitError(f"{path}: only seeded templates may use __package__")
        else:
            templates.append(Template(path, "managed", source.read_bytes(), None))
    skills = sorted({name for template in templates if (name := _skill(template.path)) is not None})
    templates += [
        Template(f".claude/skills/{name}", "managed", None, f"../../.agents/skills/{name}")
        for name in skills
    ]
    return sorted(templates, key=lambda template: template.path)


def read_optional_skills(root: Path) -> tuple[str, ...]:
    """[kit] optional: the optional skill directories the project opted into."""
    items = _kit_table(root).get("optional", [])
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise KitError(f"{PROJECT_SETTINGS} [kit] optional: expected a list of skill names")
    return tuple(items)


def read_excluded(root: Path) -> tuple[str, ...]:
    """[kit] exclude: Kit paths the project owns, normalised without "./" or a trailing "/"."""
    items = _kit_table(root).get("exclude", [])
    where = f"{PROJECT_SETTINGS} [kit] exclude"
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise KitError(f"{where}: expected a list of repository paths")
    try:
        return tuple("/".join(relative_parts(item)) for item in items)
    except UnsafePath as error:
        raise KitError(f"{where}: {error}") from error


def is_excluded(path: str, excluded: Sequence[str]) -> bool:
    """True when path is an entry or lies below one. A skill directory also covers its link."""
    parts = PurePosixPath(path).parts
    if (
        len(parts) == 3
        and parts[:2] == (".claude", "skills")
        and _covered(f".agents/skills/{parts[2]}", excluded)
    ):
        return True
    return _covered(path, excluded)


def _covered(path: str, excluded: Sequence[str]) -> bool:
    return any(path == entry or path.startswith(f"{entry}/") for entry in excluded)


def _kit_table(root: Path) -> Mapping[str, object]:
    """The [kit] table of root's project.toml, or {} when the file or the table is absent."""
    try:
        data = tomllib.loads(safe_path(root, PROJECT_SETTINGS).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, UnsafePath) as error:
        raise KitError(f"cannot read {PROJECT_SETTINGS}: {error}") from error
    table = data.get("kit", {})
    if not isinstance(table, dict):
        raise KitError(f"cannot read {PROJECT_SETTINGS}: [kit] must be a table")
    return table


def _skill(path: str) -> str | None:
    """The skill directory name of a path under .agents/skills/<name>/, else None."""
    parts = PurePosixPath(path).parts
    return parts[2] if len(parts) >= 4 and parts[:2] == (".agents", "skills") else None


def _render_text(
    path: str, text: str, variables: Mapping[str, str], declared: frozenset[str]
) -> str:
    """Substitute {{name}} in a seeded template.

    An empty value renders as <name> and comments out its line in a TOML file or CODEOWNERS.
    Any other file refuses an empty value.
    """
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        names = _VARIABLE.findall(line)
        for name in names:
            if name not in declared or name not in variables:
                raise KitError(f"{path}: unknown template variable {name!r}")
        empty = [name for name in names if not variables[name]]
        line = _VARIABLE.sub(lambda match: variables[match.group(1)] or f"<{match.group(1)}>", line)
        if empty and not line.lstrip().startswith("#"):
            if not (path.endswith(".toml") or PurePosixPath(path).name == "CODEOWNERS"):
                raise KitError(f"{path}: {empty[0]} must not be empty")
            line = "# " + line
        lines.append(line)
    return "".join(lines)


def _kept_by_git(root: Path) -> frozenset[str] | None:
    """Root-relative paths git keeps, when root/kit.toml is tracked; otherwise None.

    A source checkout then renders what its wheel ships, since hatch leaves ignored paths out.
    An installed copy is never tracked, even inside another repository's ignored .venv,
    so it is read as it is.
    """
    # Imported here because git.py imports KitError from this module.
    from rapid_ship.kit.git import git

    # Exit 1: kit.toml is not tracked. Exit 128: not in a work tree. Both print nothing.
    if not git(root, "ls-files", "-z", "--error-unmatch", "--", "kit.toml", allowed=(0, 1, 128)):
        return None
    listed = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", ".")
    return frozenset(os.fsdecode(name) for name in listed.split(b"\0") if name)


def _layer(root: Path, layer: str, kept: frozenset[str] | None) -> dict[str, Path]:
    """Map each template file in root/layer, by its path relative to the layer, to its Path."""
    directory = root / layer
    found: dict[str, Path] = {}
    for current, directories, file_names in os.walk(directory):  # never enters a symlinked dir
        directories[:] = [name for name in directories if name not in _GENERATED]
        for name in [*directories, *file_names]:
            path = Path(current, name)
            relative = path.relative_to(directory).as_posix()
            if name in _GENERATED or name.endswith(".pyc"):
                continue
            if kept is not None and f"{layer}/{relative}" not in kept:
                continue  # git does not keep it; real directories land here too
            if path.is_symlink():
                raise KitError(
                    f"template {layer}/{relative} is a symlink; templates must be regular files"
                )
            if path.is_file():
                found[relative] = path
    return found
