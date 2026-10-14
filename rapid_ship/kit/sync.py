"""rapid-ship sync: update the vendored Kit to the installed templates and open a pull request."""

from __future__ import annotations

import difflib
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence, Sized
from dataclasses import dataclass, field
from pathlib import Path

from rapid_ship.files import UnsafePath, atomic_replace, create_file
from rapid_ship.kit.git import git, is_clean
from rapid_ship.kit.lock import (
    LOCK_PATH,
    Lock,
    LockEntry,
    entry_for,
    file_sha256,
    read_lock,
    write_lock,
)
from rapid_ship.kit.status import entry_fingerprint, fingerprint, locate, template_fingerprint
from rapid_ship.kit.templates import (
    KitError,
    KitRefusal,
    Template,
    installed_version,
    is_excluded,
    load_manifest,
    read_excluded,
    read_optional_skills,
    render_files,
    render_path,
)

KIT_SOURCE = "git+https://github.com/proxy-hatch/rapid-ship"

# A Kit version taken from the lock. It must not add uvx options or change the source URL.
_RELEASE_VERSION = re.compile(r"[0-9][0-9A-Za-z.+!-]*")
_DIFF_LINES = 200
_BODY_LIMIT = 60_000  # below GitHub's pull request body limit; the exact limit was not checked
_DIFF_OVERHEAD = 100  # the fence and the cut note around each conflict diff
WAYS_OUT = (
    "sync left each file and its lock entry unchanged. To clear one, make the file equal the new "
    "template, or list the path under `[kit] exclude` in `.rapid-ship/project.toml`."
)

OldTemplates = Callable[[str], Path]  # Kit version to that release's template root
OpenPullRequest = Callable[[Path, str, str, str, str], str]  # root, branch, base, title, body


@dataclass(frozen=True)
class Conflict:
    path: str
    reason: str
    diff: str  # the template change from the old Kit to the new one; "" when there is none


@dataclass
class SyncResult:
    kit_version: str
    updated: list[str] = field(default_factory=list)
    merged: list[str] = field(default_factory=list)
    adopted: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    released: list[str] = field(default_factory=list)
    seeded_changed: list[str] = field(default_factory=list)
    seeded_existing: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    branch: str | None = None
    pull_request: str | None = None

    @property
    def changed(self) -> bool:
        """True when sync writes the lock. Missing files and conflicts change nothing."""
        return any(
            (
                self.updated,
                self.merged,
                self.adopted,
                self.added,
                self.deleted,
                self.released,
                self.seeded_changed,
                self.seeded_existing,
            )
        )


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
            result = subprocess.run(
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


def push_and_open_pull_request(root: Path, branch: str, base: str, title: str, body: str) -> str:
    """Push branch to origin and open a pull request into base with gh. Returns its URL."""
    retry = f"check gh pr list --head {branch} before retrying"
    print(f"Pushing {branch} to origin.", flush=True)
    try:
        git(root, "push", "--no-verify", "--set-upstream", "origin", branch)
    except KitError as error:
        raise KitError(f"{error}; the sync commit is on the local branch {branch}") from error
    print("Opening a pull request with gh.", flush=True)
    command = ["gh", "pr", "create", "--base", base, "--head", branch, "--title", title]
    try:
        result = subprocess.run(
            [*command, "--body-file", "-"],
            cwd=root,
            input=body,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise KitError(f"cannot run gh ({error}); {branch} is pushed, so {retry}") from error
    lines = result.stdout.strip().splitlines()
    if result.returncode != 0 or not lines:
        reason = result.stderr.strip() or "it printed no pull request URL"
        raise KitError(f"gh pr create failed ({reason}); {branch} is pushed, so {retry}")
    return lines[-1]


def sync_repository(
    root: Path,
    *,
    in_place: bool,
    templates_root: Path | None = None,
    kit_version: str | None = None,
    old_templates: OldTemplates = released_templates,
    open_pull_request: OpenPullRequest = push_and_open_pull_request,
) -> SyncResult:
    """Bring the vendored Kit to the templates at templates_root (None: the packaged ones).

    Without in_place, the changes land as one commit on rapid-ship/kit-sync-<version> and a
    pull request. in_place writes the work tree only; it accepts uncommitted work, because it
    replaces or deletes only files equal to their locked content and a merge keeps local edits.
    """
    root = root.resolve()
    lock = read_lock(root)
    if not in_place and not is_clean(root):
        raise KitRefusal("the work tree has changes; commit them first, or use --in-place")
    version = kit_version or installed_version()
    optional = read_optional_skills(root)
    excluded = read_excluded(root)
    manifest = load_manifest(templates_root)
    rendered = render_files(lock.stack, lock.variables, optional, root=templates_root)
    # Excluded paths get no action at all; their lock entries go back unchanged below.
    new = {t.path: t for t in rendered if not is_excluded(t.path, excluded)}
    result = SyncResult(kit_version=version)
    entries = {entry.path: entry for entry in lock.entries}
    planned = {path: entry for path, entry in entries.items() if not is_excluded(path, excluded)}
    writes: dict[str, Template] = {}
    merges: dict[str, bytes] = {}
    deletes: list[str] = []
    bases = _Bases(old_templates, lock, optional)
    _plan_managed(root, new, bases, planned, writes, merges, deletes, result, version)
    new_project_only = {render_path(path, lock.variables) for path in manifest.new_project}
    _plan_seeded(root, new, planned, writes, result, new_project_only)
    # [kit] exclude is the only record of an exclusion, so the lock carries no mark.
    kept = {path: entry for path, entry in entries.items() if is_excluded(path, excluded)}
    if not result.changed:
        result.kit_version = lock.kit_version
        return result
    branch = f"rapid-ship/kit-sync-{version}"
    base = None if in_place else _start_branch(root, branch)
    undo = _Undo(root)
    try:
        for path, template in writes.items():  # managed paths in path order, then new seeded files
            _write_template(root, template, path in manifest.executable, undo)
        for path, content in merges.items():
            undo.before(locate(root, path))
            _replace(locate(root, path), content, path in manifest.executable)
        for path in deletes:
            undo.before(locate(root, path))
            _delete(root, path)
        lock_entries = tuple({**planned, **kept}.values())
        undo.before(locate(root, LOCK_PATH))  # a failed commit below must restore it too
        write_lock(root, Lock(version, lock.stack, lock.variables, lock_entries))  # atomic, last
        if base is not None:
            # Only paths sync wrote or deleted: a dropped file that was already absent has none.
            touched = sorted({*writes, *merges, *deletes})
            # add fails on a new Kit path that git ignores, commit on a signing error or a
            # missing identity; both undo the writes. The commit holds only Kit files, and CI
            # runs the full check on the pull request.
            git(root, "add", "--all", "--", *touched, LOCK_PATH)
            message = f"chore: sync rapid-ship Kit to {version}"
            git(root, "commit", "--no-verify", "--quiet", "--message", message)
    except (OSError, UnsafePath, KitError) as error:
        raise _stopped(root, error, undo, base, branch) from error
    if base is not None:
        result.branch = branch
        title = f"Sync rapid-ship Kit to {version}"
        body = pull_request_body(result, lock.kit_version)
        result.pull_request = open_pull_request(root, branch, base, title, body)
    return result


def _plan_managed(
    root: Path,
    new: Mapping[str, Template],
    bases: _Bases,
    entries: dict[str, LockEntry],
    writes: dict[str, Template],
    merges: dict[str, bytes],
    deletes: list[str],
    result: SyncResult,
    version: str,
) -> None:
    """Apply the decision table to each managed path, in path order. Nothing is written yet."""
    locked = {path: entry for path, entry in entries.items() if entry.kind == "managed"}
    templates = {path: template for path, template in new.items() if template.kind == "managed"}
    for path in sorted(locked.keys() | templates.keys()):
        entry, template = locked.get(path), templates.get(path)
        try:
            disk = fingerprint(root, path)
        except UnsafePath as error:
            reason = f"{error}; sync never writes through a symlink"
            result.conflicts.append(Conflict(path, reason, ""))
            continue
        if entry is None:
            assert template is not None  # the path came from the entries or the templates
            if disk is None:
                result.added.append(path)
                writes[path] = template
                entries[path] = entry_for(template)
            elif disk == template_fingerprint(template):
                result.adopted.append(path)
                entries[path] = entry_for(template)
            else:
                reason = (
                    "exists and is not managed; remove it to take the Kit's file, "
                    "or list it under [kit] exclude to keep it"
                )
                result.conflicts.append(Conflict(path, reason, ""))
            continue
        if template is None:
            # A path the Kit now seeds is kept: _plan_seeded records the project's file.
            if path not in new and (disk is None or disk == entry_fingerprint(entry)):
                result.deleted.append(path)
                if disk is not None:
                    deletes.append(path)
            else:
                result.released.append(path)
            del entries[path]
            continue
        if disk is None:
            result.missing.append(path)
        elif template_fingerprint(template) == entry_fingerprint(entry):
            pass  # the template did not change
        elif disk == template_fingerprint(template):
            result.adopted.append(path)
            entries[path] = entry_for(template)
        elif disk == entry_fingerprint(entry):
            result.updated.append(path)
            writes[path] = template
            entries[path] = entry_for(template)
        else:
            merged = _merge(root, path, entry, template, disk, bases, result, version)
            if merged is not None:
                result.merged.append(path)
                merges[path] = merged
                # The template's hash: status still shows the edit, and the next merge uses
                # this template as its base.
                entries[path] = entry_for(template)


def _merge(
    root: Path,
    path: str,
    entry: LockEntry,
    template: Template,
    disk: str,
    bases: _Bases,
    result: SyncResult,
    version: str,
) -> bytes | None:
    """Merge the template change into the project's edit. None means a conflict, now listed."""
    if entry.link is not None or template.link is not None:
        reason = "a changed symlink; set it to the template's link by hand"
        result.conflicts.append(Conflict(path, reason, ""))
        return None
    if not disk.startswith("sha256:"):
        reason = "not a regular file (a symlink or a directory); sync merges only regular files"
        result.conflicts.append(Conflict(path, reason, ""))
        return None
    new_content = template.content or b""
    try:
        base = bases.content(path, entry)
    except KitError as error:
        result.conflicts.append(Conflict(path, str(error), ""))
        return None
    labels = ("local", f"rapid-ship {bases.version}", f"rapid-ship {version}")
    try:
        merged = merge_file(locate(root, path).read_bytes(), base, new_content, labels)
    except KitError as error:  # binary content, for one; the other files still sync
        result.conflicts.append(Conflict(path, str(error), ""))
        return None
    if merged is None:
        # Applying the diff by hand while keeping the edit does not clear this; WAYS_OUT does.
        reason = "local changes conflict with the template change below"
        diff = _diff(path, base, new_content, bases.version, version)
        result.conflicts.append(Conflict(path, reason, diff))
    return merged


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
        try:
            result = subprocess.run(
                [*command, "local", "base", "template"],
                cwd=directory,
                capture_output=True,
                check=False,
            )
        except OSError as error:
            raise KitError(f"cannot run git merge-file: {error}") from error
    if result.returncode == 0:
        return result.stdout
    if 0 < result.returncode < 128:  # the number of conflicts; git exits 255 on an error
        return None
    raise KitError(f"git merge-file failed: {result.stderr.decode(errors='replace').strip()}")


def _diff(path: str, base: bytes, template: bytes, old_version: str, new_version: str) -> str:
    lines = difflib.unified_diff(
        base.decode("utf-8", errors="replace").splitlines(),
        template.decode("utf-8", errors="replace").splitlines(),
        fromfile=f"{path} (rapid-ship {old_version})",
        tofile=f"{path} (rapid-ship {new_version})",
        lineterm="",
    )
    return "\n".join(lines)


def _plan_seeded(
    root: Path,
    new: Mapping[str, Template],
    entries: dict[str, LockEntry],
    writes: dict[str, Template],
    result: SyncResult,
    new_project_only: set[str],
) -> None:
    """Record seeded template changes. A new seed is written only where nothing exists."""
    for path, template in new.items():
        if template.kind != "seeded":
            continue
        entry = entries.get(path)
        if entry is not None:
            # The file is the project's: sync never reads or writes it.
            changed = entry.template_sha256 != file_sha256(template.content or b"")
            if entry.kind == "seeded" and changed:
                result.seeded_changed.append(path)
                entries[path] = entry_for(template)
            continue
        if path in new_project_only:
            continue  # sync never adds or records a new-project seed
        try:
            disk = fingerprint(root, path)
        except UnsafePath as error:
            reason = f"{error}; sync never writes through a symlink"
            result.conflicts.append(Conflict(path, reason, ""))
            continue
        if disk is None:
            result.added.append(path)
            writes[path] = template  # create_file never replaces a file that appears meanwhile
        else:
            result.seeded_existing.append(path)
        entries[path] = entry_for(template)


class _Bases:
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


@dataclass
class _Undo:
    """What sync changed, so a failed sync can put the work tree back."""

    root: Path
    replaced: list[tuple[Path, bytes, str | None, int]] = field(
        default_factory=list
    )  # path, bytes, link, mode
    created: list[Path] = field(
        default_factory=list
    )  # files, links and directories, in creation order

    def before(self, path: Path) -> None:
        """Keep an existing file or link before sync replaces or deletes it."""
        if path.is_symlink():
            self.replaced.append((path, b"", str(path.readlink()), 0))
        elif path.is_file():
            self.replaced.append((path, path.read_bytes(), None, stat.S_IMODE(path.stat().st_mode)))

    def make_parents(self, path: Path) -> None:
        for directory in reversed(path.parents):
            if (
                directory.is_relative_to(self.root)
                and directory != self.root
                and not directory.exists()
            ):
                directory.mkdir()
                self.created.append(directory)

    def restore(self) -> None:
        for path in reversed(self.created):
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            else:
                path.unlink(missing_ok=True)
        for path, content, link, mode in reversed(self.replaced):
            path.parent.mkdir(parents=True, exist_ok=True)  # _delete may have removed it
            if os.path.lexists(path):
                path.unlink()
            if link is not None:
                path.symlink_to(link)
            else:
                atomic_replace(path, content, mode=mode)


def _stopped(root: Path, error: Exception, undo: _Undo, base: str | None, branch: str) -> KitError:
    """Put the work tree back after a failed write or commit, and say what is left to do."""
    on_branch = "" if base is None else f"; you are on {branch}"
    try:
        undo.restore()
    except OSError as failure:
        return KitError(
            f"sync stopped ({error}) and could not restore every file ({failure}){on_branch}; "
            "check git status"
        )
    if base is None:
        return KitError(f"sync stopped ({error}) and restored the files it had changed")
    try:
        # Branch mode starts from a clean tree, so the index holds only what sync staged.
        git(root, "reset", "--quiet")
        git(root, "switch", "--quiet", base)
        git(root, "branch", "--quiet", "--delete", "--force", branch)
    except KitError as failure:
        return KitError(
            f"sync stopped ({error}) and restored the files it had changed, but could not "
            f"go back ({failure}){on_branch}; run git reset, git switch {base} and "
            f"git branch -D {branch}"
        )
    return KitError(
        f"sync stopped ({error}) and restored the files it had changed; "
        f"back on {base}, {branch} deleted"
    )


def _write_template(root: Path, template: Template, executable: bool, undo: _Undo) -> None:
    target = locate(root, template.path)
    undo.make_parents(target)
    content = template.content or b""
    if template.kind == "seeded" or not os.path.lexists(target):
        # create_file and os.symlink never replace, so a seeded file stays the project's.
        if template.link is not None:
            os.symlink(template.link, target)
        else:
            create_file(target, content, executable=executable)
        undo.created.append(target)  # only after it exists, so a failed create removes nothing
        return
    undo.before(target)
    if template.link is not None:
        target.unlink()
        os.symlink(template.link, target)
    else:
        _replace(target, content, executable)


def _replace(path: Path, content: bytes, executable: bool) -> None:
    """Replace a file's bytes and keep its mode; atomic_replace alone would publish 0o600."""
    mode = stat.S_IMODE(path.stat().st_mode)
    if executable:
        mode |= (mode & 0o444) >> 2
    atomic_replace(path, content, mode=mode)


def _delete(root: Path, path: str) -> None:
    """Delete a file, then each parent directory left empty, up to the repository root."""
    target = locate(root, path)
    target.unlink()
    for directory in target.parents:
        if directory == root or any(directory.iterdir()):
            break
        directory.rmdir()


def _start_branch(root: Path, branch: str) -> str:
    """Create and switch to the sync branch. Returns the branch it started from."""
    base = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", allowed=(0, 1)).decode().strip()
    if not base:
        raise KitRefusal("HEAD is detached; check out the branch the pull request should target")
    if git(root, "branch", "--list", branch).strip():
        raise KitRefusal(
            f"branch {branch} exists; a previous sync may have opened a pull request "
            f"(gh pr list --head {branch})"
        )
    git(root, "switch", "--quiet", "--create", branch)
    return base


def pull_request_body(result: SyncResult, old_version: str) -> str:
    """The pull request text. The Evidence section comes last and is never cut."""
    diffs = [_first_lines(conflict.diff) for conflict in result.conflicts]
    body = _body(result, old_version, diffs)
    if len(body) > _BODY_LIMIT:
        spare = _BODY_LIMIT - len(_body(result, old_version, [""] * len(diffs)))
        share = max(spare // max(len(diffs), 1) - _DIFF_OVERHEAD, 0)
        diffs = [_fit(diff, share) for diff in diffs]
        body = _body(result, old_version, diffs)
    return body


def _body(result: SyncResult, old_version: str, diffs: Sequence[str]) -> str:
    new_version = result.kit_version
    parts = [
        f"This pull request updates the vendored rapid-ship Kit from {old_version} to "
        f"{new_version}. `rapid-ship sync` generated it.",
        "## Changes",
    ]
    changes = [
        ("Replaced with the new template:", result.updated),
        ("Merged the template change into the project's edits:", result.merged),
        ("Already equal to the new template; only the lock changed:", result.adopted),
        ("Added:", result.added),
        ("Deleted, because the Kit dropped them:", result.deleted),
    ]
    listed = [_bullets(heading, paths) for heading, paths in changes if paths]
    parts += listed or ["Only the lock changed."]
    parts.append("## Needs the owner")
    needs: list[str] = []
    if result.conflicts:
        needs.append(f"Conflicts. {WAYS_OUT}")
        for conflict, diff in zip(result.conflicts, diffs, strict=True):
            needs.append(f"- `{conflict.path}`: {conflict.reason}")
            if diff:
                fence = "`" * max(3, _longest_backtick_run(diff) + 1)
                needs.append(f"{fence}diff\n{diff}\n{fence}")
    owner_lists = [
        (
            "Seeded files whose template changed. sync did not change them; "
            "apply the template change by hand if the project wants it:",
            result.seeded_changed,
        ),
        (
            "New seeded templates where the project already has a file. sync recorded them "
            "and kept the files; merge the template by hand if the project wants it:",
            result.seeded_existing,
        ),
        (
            "Files the Kit dropped after the project edited them. sync kept them, "
            "and the project owns them now:",
            result.released,
        ),
        (
            "Managed files missing from the work tree. Restore them, or list them under "
            "`[kit] exclude` in `.rapid-ship/project.toml`:",
            result.missing,
        ),
    ]
    needs += [_bullets(heading, paths) for heading, paths in owner_lists if paths]
    parts += needs or ["Nothing."]
    counted: dict[str, Sized] = {
        "updated": result.updated,
        "merged": result.merged,
        "adopted": result.adopted,
        "added": result.added,
        "deleted": result.deleted,
        "released": result.released,
        "seeded_changed": result.seeded_changed,
        "seeded_existing": result.seeded_existing,
        "missing": result.missing,
        "conflicts": result.conflicts,
    }
    counts = ", ".join(
        f"{len(items)} {name.replace('_', ' ')}" for name, items in counted.items() if items
    )
    parts += [
        "## Evidence",
        f"- `rapid-ship sync`: rapid-ship {old_version} to {new_version}; "
        f"{counts or 'nothing changed'}",
        "Not covered: sync did not run ./devctl check; CI runs it on this pull request.",
    ]
    return "\n\n".join(parts) + "\n"


def _bullets(heading: str, paths: Sequence[str]) -> str:
    return "\n".join([heading, "", *(f"- `{path}`" for path in paths)])


def _first_lines(diff: str) -> str:
    lines = diff.splitlines()
    if len(lines) <= _DIFF_LINES:
        return diff
    return "\n".join([*lines[:_DIFF_LINES], f"[diff cut at {_DIFF_LINES} lines]"])


def _fit(diff: str, size: int) -> str:
    """Keep whole lines of diff within size characters, then say it was cut."""
    if len(diff) <= size:
        return diff
    kept: list[str] = []
    used = 0
    for line in diff.splitlines():
        used += len(line) + 1
        if used > size:
            break
        kept.append(line)
    return "\n".join([*kept, "[diff cut to fit the pull request body]"])


def _longest_backtick_run(text: str) -> int:
    return max((len(run) for run in re.findall(r"`+", text)), default=0)
