"""rapid-ship sync: update the vendored Kit to the installed templates and open a pull request."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Collection, Mapping, Sequence, Sized
from dataclasses import dataclass, field
from pathlib import Path

from rapid_ship.files import UnsafePath, relative_parts
from rapid_ship.kit.git import commit_paths, git, head_branch, is_clean, leave_branch
from rapid_ship.kit.lock import (
    LOCK_PATH,
    Lock,
    LockEntry,
    entry_for,
    file_sha256,
    read_lock,
    seeded_entry,
    template_hash,
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
from rapid_ship.kit.writes import Undo, delete_file, write_template

REVERT = "rapid-ship sync --revert <path>"

OpenPullRequest = Callable[[Path, str, str, str, str], str]  # root, branch, base, title, body


@dataclass(frozen=True)
class Conflict:
    """A new Kit path that sync cannot write: a project file or a symlink is in the way."""

    path: str
    reason: str


@dataclass
class SyncResult:
    kit_version: str
    updated: list[str] = field(default_factory=list)
    reverted: list[str] = field(default_factory=list)
    adopted: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    owned: list[str] = field(default_factory=list)  # managed files the project edited or deleted
    seeded_changed: list[str] = field(default_factory=list)
    seeded_existing: list[str] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    branch: str | None = None
    pull_request: str | None = None

    @property
    def changed(self) -> bool:
        """True when sync writes the lock. A conflict alone writes nothing."""
        return any(
            (
                self.updated,
                self.reverted,
                self.adopted,
                self.added,
                self.deleted,
                self.owned,
                self.seeded_changed,
                self.seeded_existing,
            )
        )


def push_and_open_pull_request(root: Path, branch: str, base: str, title: str, body: str) -> str:
    """Push branch to origin and open a pull request into base with gh. Returns its URL."""
    retry = f"check gh pr list --head {branch} before retrying"
    print(f"Pushing {branch} to origin.", flush=True)
    try:
        git(root, "push", "--set-upstream", "origin", branch)
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
    revert: Sequence[str] = (),
    open_pull_request: OpenPullRequest = push_and_open_pull_request,
) -> SyncResult:
    """Bring the vendored Kit to the templates at templates_root (None: the packaged ones).

    Without in_place, the changes land as one commit on rapid-ship/kit-sync-<version> and a
    pull request. in_place writes the work tree only; it accepts uncommitted work, because it
    replaces or deletes only files equal to their locked content. revert names Kit-managed paths
    the project owns, or edited, to replace with the current template and manage again.
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
    reverting = _revert_paths(revert, new, entries, excluded)  # refuses before any write
    planned = {path: entry for path, entry in entries.items() if not is_excluded(path, excluded)}
    writes: dict[str, Template] = {}
    deletes: list[str] = []
    _plan_managed(root, new, planned, writes, deletes, result, reverting)
    new_project_only = {render_path(path, lock.variables) for path in manifest.new_project}
    _plan_seeded(root, new, planned, writes, result, new_project_only)
    # [kit] exclude is the only record of an exclusion, so the lock carries no mark.
    kept = {path: entry for path, entry in entries.items() if is_excluded(path, excluded)}
    if not result.changed:
        result.kit_version = lock.kit_version
        return result
    branch = f"rapid-ship/kit-sync-{version}"
    base = None if in_place else _start_branch(root, branch)
    undo = Undo(root)
    try:
        if base is not None:
            # git can fail after it has switched, so the switch is undone like a write.
            git(root, "switch", "--quiet", branch)
        for path, template in writes.items():  # managed paths in path order, then new seeded files
            write_template(root, template, path in manifest.executable, undo)
        for path in deletes:
            undo.before(locate(root, path))
            delete_file(root, path)
        lock_entries = tuple({**planned, **kept}.values())
        undo.before(locate(root, LOCK_PATH))  # a failed commit below must restore it too
        write_lock(root, Lock(version, lock.stack, lock.variables, lock_entries))  # atomic, last
        if base is not None:
            # Only paths sync wrote or deleted: a dropped file that was already absent has none.
            # The commit holds only Kit files, and CI runs the full check on the pull request.
            touched = sorted({*writes, *deletes})
            commit_paths(root, [*touched, LOCK_PATH], f"chore: sync rapid-ship Kit to {version}")
    except (OSError, UnsafePath, KitError) as error:
        raise _stopped(root, error, undo, base, branch) from error
    if base is not None:
        result.branch = branch
        title = f"Sync rapid-ship Kit to {version}"
        body = pull_request_body(result, lock.kit_version)
        result.pull_request = open_pull_request(root, branch, base, title, body)
    return result


def _revert_paths(
    paths: Sequence[str],
    new: Mapping[str, Template],
    entries: Mapping[str, LockEntry],
    excluded: Sequence[str],
) -> frozenset[str]:
    """The paths to give back to the Kit. Any path that cannot be reverted refuses the sync."""
    accepted: set[str] = set()
    refused: list[str] = []
    for given in paths:
        try:
            path = "/".join(relative_parts(given))
        except UnsafePath:
            refused.append(f"{given}: not a Kit file")
            continue
        template = new.get(path)  # new holds no excluded path
        if is_excluded(path, excluded):
            refused.append(f"{path}: listed under [kit] exclude; remove it there first")
        elif template is None and path in entries:
            refused.append(f"{path}: the Kit no longer has a template for it")
        elif template is None:
            refused.append(f"{path}: not a Kit file")
        elif template.kind == "seeded":
            refused.append(f"{path}: a seeded Kit file, which the project owns from the start")
        else:
            accepted.add(path)
    if refused:
        raise KitRefusal("cannot revert " + "; ".join(refused))
    return frozenset(accepted)


def _plan_managed(
    root: Path,
    new: Mapping[str, Template],
    entries: dict[str, LockEntry],
    writes: dict[str, Template],
    deletes: list[str],
    result: SyncResult,
    revert: Collection[str],
) -> None:
    """Apply the decision table to each managed path, in path order. Nothing is written yet.

    A managed file the project edited or deleted becomes its own: sync never changes it and
    records it as seeded (spec section 3, sync step 4). revert undoes that for the paths it names.
    """
    paths = {path for path, entry in entries.items() if entry.kind == "managed" or path in revert}
    paths |= {path for path, t in new.items() if t.kind == "managed" and path not in entries}
    for path in sorted(paths):
        entry, template = entries.get(path), new.get(path)
        try:
            disk = fingerprint(root, path)
        except UnsafePath as error:
            if entry is None:
                result.conflicts.append(
                    Conflict(path, f"{error}; sync never writes through a symlink")
                )
                continue
            disk = "other"  # status reports it as modified too
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
                result.conflicts.append(Conflict(path, reason))
            continue
        edited = entry.kind == "seeded" or disk != entry_fingerprint(entry)
        if path in revert and edited:
            assert template is not None  # _revert_paths accepts only managed templates
            result.reverted.append(path)
            writes[path] = template
            entries[path] = entry_for(template)
        elif (
            template is not None
            and template.kind == "managed"
            and disk == template_fingerprint(template)
        ):
            if disk != entry_fingerprint(entry):
                result.adopted.append(path)
                entries[path] = entry_for(template)
        elif edited and (disk is not None or template is not None):
            result.owned.append(path)
            entries[path] = _owned_entry(entry, template)
        elif template is None:  # the Kit dropped it; delete the file if it is still there
            result.deleted.append(path)
            if disk is not None:
                deletes.append(path)
            del entries[path]
        elif template.kind == "seeded":  # the Kit seeds it now, so the file is the project's
            result.seeded_existing.append(path)
            entries[path] = entry_for(template)
        else:
            result.updated.append(path)
            writes[path] = template
            entries[path] = entry_for(template)


def _owned_entry(entry: LockEntry, template: Template | None) -> LockEntry:
    """The seeded entry for a managed file the project edited or deleted.

    It records the current template, so only later template changes are reported. When the Kit
    dropped the file, it records the locked content, which is the template the file came from.
    """
    if template is not None:
        return seeded_entry(entry.path, template_hash(template))
    if entry.link is not None:
        return seeded_entry(entry.path, file_sha256(entry.link.encode("utf-8")))
    assert entry.sha256 is not None  # read_lock gives a managed entry a hash or a link
    return seeded_entry(entry.path, entry.sha256)


def _plan_seeded(
    root: Path,
    new: Mapping[str, Template],
    entries: dict[str, LockEntry],
    writes: dict[str, Template],
    result: SyncResult,
    new_project_only: set[str],
) -> None:
    """Record template changes for the project's files. A new seed is written only where nothing
    exists. A seeded entry's template may be managed, after the project edited a managed file."""
    for path, template in new.items():
        entry = entries.get(path)
        if entry is not None:
            # The file is the project's: sync never reads or writes it.
            if entry.kind == "seeded" and entry.template_sha256 != template_hash(template):
                result.seeded_changed.append(path)
                entries[path] = seeded_entry(path, template_hash(template))
            continue
        if template.kind != "seeded" or path in new_project_only:
            continue  # _plan_managed adds managed files; sync never adds a new-project seed
        try:
            disk = fingerprint(root, path)
        except UnsafePath as error:
            result.conflicts.append(Conflict(path, f"{error}; sync never writes through a symlink"))
            continue
        if disk is None:
            result.added.append(path)
            writes[path] = template  # create_file never replaces a file that appears meanwhile
        else:
            result.seeded_existing.append(path)
        entries[path] = entry_for(template)


def _stopped(root: Path, error: Exception, undo: Undo, base: str | None, branch: str) -> KitError:
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
        leave_branch(root, base, branch)
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


def _start_branch(root: Path, branch: str) -> str:
    """Create the sync branch at HEAD. Returns the branch it starts from.

    git branch makes the branch or fails without one, so a failure leaves nothing to undo.
    sync_repository switches to it inside its undo.
    """
    base = head_branch(root)
    if base is None:
        raise KitRefusal("HEAD is detached; check out the branch the pull request should target")
    if git(root, "branch", "--list", branch).strip():
        raise KitRefusal(
            f"branch {branch} exists; a previous sync may have opened a pull request "
            f"(gh pr list --head {branch})"
        )
    git(root, "branch", "--quiet", branch)
    return base


def pull_request_body(result: SyncResult, old_version: str) -> str:
    """The pull request text. The Evidence section comes last."""
    new_version = result.kit_version
    parts = [
        f"This pull request updates the vendored rapid-ship Kit from {old_version} to "
        f"{new_version}. `rapid-ship sync` generated it.",
        "## Changes",
    ]
    changes = [
        ("Replaced with the new template:", result.updated),
        ("Reverted to the Kit's template; sync updates them again:", result.reverted),
        ("Already equal to the new template; only the lock changed:", result.adopted),
        ("Added:", result.added),
        ("Deleted, because the Kit dropped them:", result.deleted),
    ]
    listed = [_bullets(heading, paths) for heading, paths in changes if paths]
    parts += listed or ["Only the lock changed."]
    parts.append("## Needs the owner")
    owner_lists = [
        (
            "Kit files the project edited or deleted. sync kept them and recorded them as the "
            "project's own, so the Kit no longer updates them. To give one back to the Kit, "
            f"run `{REVERT}`:",
            result.owned,
        ),
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
    ]
    needs = [_bullets(heading, paths) for heading, paths in owner_lists if paths]
    if result.conflicts:
        lines = [f"- `{conflict.path}`: {conflict.reason}" for conflict in result.conflicts]
        needs.append(
            "\n".join(["Conflicts. sync did not write or record these paths:", "", *lines])
        )
    parts += needs or ["Nothing."]
    counted: dict[str, Sized] = {
        "updated": result.updated,
        "reverted": result.reverted,
        "adopted": result.adopted,
        "added": result.added,
        "deleted": result.deleted,
        "owned": result.owned,
        "seeded_changed": result.seeded_changed,
        "seeded_existing": result.seeded_existing,
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
