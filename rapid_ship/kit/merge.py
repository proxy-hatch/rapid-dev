"""sync's three-way merge: the merge base from the locked Kit release, and git merge-file."""

from __future__ import annotations

import difflib
import re
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from rapid_ship.kit.lock import Lock, LockEntry
from rapid_ship.kit.status import entry_fingerprint, template_fingerprint
from rapid_ship.kit.templates import KitError, Template, load_manifest, render_files

KIT_SOURCE = "git+https://github.com/proxy-hatch/rapid-ship"

# A Kit version taken from the lock. It must not add uvx options or change the source URL.
_RELEASE_VERSION = re.compile(r"[0-9][0-9A-Za-z.+!-]*")

OldTemplates = Callable[[str], Path]  # Kit version to that release's template root


def released_templates(version: str) -> Path:
    """The template root of the Kit release tagged v<version> (spec section 3).

    uv builds the tag's wheel with its declared backend, hatchling. The script below finds the
    package without importing it, so no rapid-ship code from the tag runs.
    """
    if not _RELEASE_VERSION.fullmatch(version):
        raise KitError(f"the lock's kit_version {version!r} is not a release version")
    source = f"{KIT_SOURCE}@v{version}"
    script = (
        "import importlib.util; "
        "print(importlib.util.find_spec('rapid_ship').submodule_search_locations[0])"
    )
    command = ["uvx", "--from", source, "python", "-I", "-c", script]
    # A neutral directory keeps the project's uv settings out of the fetch.
    with tempfile.TemporaryDirectory() as neutral:
        try:
            result = subprocess.run(  # noqa: S603  # rs-exception: EX-5
                command, cwd=neutral, capture_output=True, text=True, check=False, timeout=600
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise KitError(f"cannot fetch rapid-ship {version} from {source}: {error}") from error
    if result.returncode != 0:
        raise KitError(f"cannot fetch rapid-ship {version} from {source}: {result.stderr.strip()}")
    root = Path(result.stdout.strip()) / "templates"
    if not (root / "kit.toml").is_file():
        raise KitError(f"rapid-ship {version} has no Kit templates")
    return root


class MergeBases:
    """The merge bases: the locked Kit version's templates, fetched once, on the first merge."""

    def __init__(self, old_templates: OldTemplates, lock: Lock, optional: Sequence[str]) -> None:
        self.version = lock.kit_version
        self._old_templates = old_templates
        self._lock = lock
        self._optional = optional
        self._templates: dict[str, Template] | None = None
        self._error: KitError | None = None  # a failed fetch fails every later merge too

    def content(self, path: str, entry: LockEntry) -> bytes:
        template = self._load().get(path)
        if template is None or template_fingerprint(template) != entry_fingerprint(entry):
            raise KitError(
                f"the locked copy is not rapid-ship {self.version}'s template, "
                "so there is no merge base"
            )
        return template.content or b""

    def _load(self) -> dict[str, Template]:
        if self._error is not None:
            raise self._error
        if self._templates is None:
            try:
                root = self._old_templates(self.version)
                known = load_manifest(root).optional_skills
                optional = [name for name in self._optional if name in known]
                rendered = render_files(self._lock.stack, self._lock.variables, optional, root=root)
            except KitError as error:
                self._error = error
                raise
            self._templates = {template.path: template for template in rendered}
        return self._templates


def merge_file(
    local: bytes, base: bytes, template: bytes, labels: tuple[str, str, str]
) -> bytes | None:
    """Three-way merge with git merge-file. None means it conflicted."""
    with tempfile.TemporaryDirectory(prefix="rapid-ship-merge-") as temporary:
        directory = Path(temporary)
        for name, content in (("local", local), ("base", base), ("template", template)):
            (directory / name).write_bytes(content)
        command = ["git", "merge-file", "--stdout"]
        for label in labels:
            command += ["-L", label]
        command += ["local", "base", "template"]
        try:
            result = subprocess.run(  # noqa: S603  # rs-exception: EX-6
                command, cwd=directory, capture_output=True, check=False
            )
        except OSError as error:
            raise KitError(f"cannot run git merge-file: {error}") from error
    if result.returncode == 0:
        return result.stdout
    if 0 < result.returncode < 128:  # the number of conflicts; git exits 255 on an error
        return None
    raise KitError(f"git merge-file failed: {result.stderr.decode(errors='replace').strip()}")


def template_diff(
    path: str, base: bytes, template: bytes, old_version: str, new_version: str
) -> str:
    """The template change from the old Kit to the new one, as a unified diff."""
    lines = difflib.unified_diff(
        base.decode("utf-8", errors="replace").splitlines(),
        template.decode("utf-8", errors="replace").splitlines(),
        fromfile=f"{path} (rapid-ship {old_version})",
        tofile=f"{path} (rapid-ship {new_version})",
        lineterm="",
    )
    return "\n".join(lines)
