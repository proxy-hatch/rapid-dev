"""rapid-ship sync: update the vendored Kit to the installed templates and open a pull request."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable, Mapping
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
from rapid_ship.kit.merge import (
    MergeBases,
    OldTemplates,
    merge_file,
    released_templates,
    template_diff,
)
from rapid_ship.kit.pull_request import pull_request_body, push_and_open_pull_request
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
    bases = MergeBases(old_templates, lock, optional)
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
    bases: MergeBases,
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
        if entry is None:  # the path came from the templates
            _plan_unlocked(path, templates[path], disk, entries, writes, result)
        elif template is None:
            # A path the Kit now seeds is kept: _plan_seeded records the project's file.
            seeded = path in new
            _plan_dropped(path, entry, disk, seeded, entries, deletes, result)
        elif disk is None:
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


def _plan_unlocked(
    path: str,
    template: Template,
    disk: str | None,
    entries: dict[str, LockEntry],
    writes: dict[str, Template],
    result: SyncResult,
) -> None:
    """A managed template with no lock entry: add it, adopt an equal file or report a conflict."""
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


def _plan_dropped(
    path: str,
    entry: LockEntry,
    disk: str | None,
    seeded: bool,
    entries: dict[str, LockEntry],
    deletes: list[str],
    result: SyncResult,
) -> None:
    """A locked file the Kit no longer manages: delete it when unchanged, else release it."""
    if not seeded and (disk is None or disk == entry_fingerprint(entry)):
        result.deleted.append(path)
        if disk is not None:
            deletes.append(path)
    else:
        result.released.append(path)
    del entries[path]


def _merge(
    root: Path,
    path: str,
    entry: LockEntry,
    template: Template,
    disk: str,
    bases: MergeBases,
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
        diff = template_diff(path, base, new_content, bases.version, version)
        result.conflicts.append(Conflict(path, reason, diff))
    return merged


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
        # create_file and symlink_to never replace, so a seeded file stays the project's.
        if template.link is not None:
            target.symlink_to(template.link)
        else:
            create_file(target, content, executable=executable)
        undo.created.append(target)  # only after it exists, so a failed create removes nothing
        return
    undo.before(target)
    if template.link is not None:
        target.unlink()
        target.symlink_to(template.link)
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
