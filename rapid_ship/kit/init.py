"""rapid-ship init: vendor the Kit into a repository and commit it on its own branch.

It creates files and never replaces one.
"""

from __future__ import annotations

import keyword
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from rapid_ship.files import UnsafePath, create_file, safe_path
from rapid_ship.kit.existing_checks import find_existing_checks
from rapid_ship.kit.git import (
    changed_paths,
    commit_paths,
    git,
    head_branch,
    head_commit,
    leave_branch,
    work_tree_root,
)
from rapid_ship.kit.lock import LOCK_PATH, Lock, entry_for, write_lock
from rapid_ship.kit.status import locate
from rapid_ship.kit.templates import (
    KitError,
    KitRefusal,
    Stack,
    Template,
    installed_version,
    load_manifest,
    render_files,
    render_path,
)
from rapid_ship.kit.writes import Undo

INIT_BRANCH = "rapid-ship/init"
_LISTED = 20  # dirty paths a refusal lists before it counts the rest
_PROJECT_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")  # PEP 508 name
_LOGIN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")  # GitHub login, at most 39
# devctl's settings.py keeps a copy of this pattern; tests/devctl checks that the two agree.
_REPOSITORY = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*/(?!\.{1,2}$)[A-Za-z0-9._-]+")
_MAX_LOGIN = 39
# A github.com remote: https://, http:// or ssh:// with an optional user (or user:token), or the
# scp form git@github.com:owner/name. The path is checked against _REPOSITORY afterwards.
_GITHUB_REMOTE = re.compile(
    r"(?:(?:https?|ssh)://(?:[^/@]+@)?github\.com/|(?:[^/@:]+@)?github\.com:)(.+?)(?:\.git)?/?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InitResult:
    stack: Stack
    created: tuple[str, ...]  # includes .rapid-ship/kit.lock; empty when there are conflicts
    skipped: tuple[str, ...]  # seeded files that already existed; rs-setup merges them
    conflicts: tuple[str, ...]  # "path: reason"; when present, init wrote nothing
    branch: str = ""  # the branch that holds the Kit commit; "" when there are conflicts
    commit: str = ""  # the Kit commit
    # The branch or, for a detached HEAD, the commit init started from. None when the repository
    # had no commits, so the Kit commit is its first, on the current branch.
    base: str | None = None
    # Tool settings, hooks and workflows the repository already had, for rs-setup to combine with
    # devctl's checks. Listed only when init succeeded.
    existing_checks: tuple[str, ...] = ()


def resolve_variables(
    root: Path,
    *,
    name: str | None = None,
    package: str | None = None,
    owner: str | None = None,
    repository: str | None = None,
) -> dict[str, str]:
    """The four template variables. These values are substituted into TOML strings and
    CODEOWNERS, so each is validated. An absent owner or repository is "".
    """
    if repository is not None and not _REPOSITORY.fullmatch(repository):
        raise KitError(f"repository {repository!r} is not owner/name; check --repository")
    project_name = _default_project_name(root, repository) if name is None else name
    if not _PROJECT_NAME.fullmatch(project_name):
        raise KitError(f"project name {project_name!r} is not a valid project name; check --name")
    if package is None:
        package = re.sub(r"[^a-z0-9]+", "_", project_name.lower()).strip("_")
    if not package.isidentifier() or keyword.iskeyword(package):
        raise KitError(f"package {package!r} is not a Python package name; check --package")
    if owner is not None and (len(owner) > _MAX_LOGIN or not _LOGIN.fullmatch(owner)):
        raise KitError(f"owner {owner!r} is not a GitHub login; check --owner")
    return {
        "project_name": project_name,
        "package": package,
        "owner": owner or "",
        "repository": repository or "",
    }


def _default_project_name(root: Path, repository: str | None) -> str:
    """The GitHub repository name, else the main checkout's directory name.

    The order is the validated --repository, the origin remote, then the directory that holds the
    main .git. A linked worktree such as .claude/worktrees/<random> therefore gets the project's
    name. Outside a work tree, or when git cannot run, the name is root's own directory name.
    The remote URL can carry a token, so only the parsed name leaves this function.
    """
    if repository is not None:
        return repository.partition("/")[2]
    try:
        # Exit 2 means there is no origin; stdout is then empty and gives no name.
        url = git(root, "remote", "get-url", "origin", allowed=(0, 2))
        name = _github_repository_name(os.fsdecode(url).strip())
        if name is not None:
            return name
        common = git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    except (KitError, KitRefusal, OSError):
        return root.resolve().name
    git_dir = Path(os.fsdecode(common.rstrip(b"\n")))
    # Another layout, such as a bare repository or a submodule, has no main checkout to name.
    return git_dir.parent.name if git_dir.name == ".git" else root.resolve().name


def _github_repository_name(url: str) -> str | None:
    """The repository name in a github.com remote URL, else None for any other host or shape."""
    match = _GITHUB_REMOTE.fullmatch(url)
    if match is None or not _REPOSITORY.fullmatch(match[1]):
        return None
    return match[1].partition("/")[2]


def init_repository(
    root: Path,
    *,
    stack: Stack | None,
    variables: Mapping[str, str],
    templates_root: Path | None = None,
) -> InitResult:
    root = root.resolve()
    top = work_tree_root(root)
    if top != root:
        raise KitRefusal(f"run init from the top of the work tree, {top}")
    dirty = changed_paths(root)
    if dirty:
        raise KitRefusal(_dirty(dirty))
    if os.path.lexists(root / LOCK_PATH):
        raise KitRefusal(f"{LOCK_PATH} exists; use rapid-ship status or rapid-ship sync")
    start = head_commit(root)
    if start is not None and git(root, "branch", "--list", INIT_BRANCH).strip():
        raise KitRefusal(
            f"branch {INIT_BRANCH} exists; a previous init may have committed the Kit there. "
            f"Open its pull request, or delete it with git branch -D {INIT_BRANCH}"
        )
    existing_project = os.path.lexists(root / "pyproject.toml")
    stack = stack or ("python" if existing_project else None)
    if stack is None:
        raise KitError("there is no pyproject.toml; pass --stack python or --stack agnostic")
    manifest = load_manifest(templates_root)
    new_project_only = {render_path(path, variables) for path in manifest.new_project}
    templates = [
        template
        for template in render_files(stack, variables, (), root=templates_root)
        if not (existing_project and template.path in new_project_only)
    ]
    writes, skipped, conflicts = _plan(root, templates)
    if conflicts:
        return InitResult(stack, (), tuple(skipped), tuple(conflicts))
    existing_checks = find_existing_checks(root)  # before the branch and the writes: as it was
    version = installed_version()
    lock = Lock(version, stack, dict(variables), tuple(entry_for(t) for t in templates))
    current = head_branch(root)
    base = None if start is None else current or start  # a detached HEAD returns to its commit
    if base is not None:
        # git branch makes the branch or fails without one, so a failure leaves nothing to undo.
        git(root, "branch", "--quiet", INIT_BRANCH)
    undo = Undo(root)
    try:
        if base is not None:
            # git can fail after it has switched, so the switch is undone like a write.
            git(root, "switch", "--quiet", INIT_BRANCH)
        created = _write(root, writes, manifest.executable, lock, undo)
        commit_paths(root, created, f"chore: vendor the rapid-ship Kit {version}")
    except (OSError, KitError) as error:
        raise _stopped(root, error, undo, base, detached=current is None) from error
    commit = git(root, "rev-parse", "HEAD").decode().strip()
    branch = INIT_BRANCH if base is not None else current or ""
    return InitResult(
        stack, tuple(created), tuple(skipped), (), branch, commit, base, existing_checks
    )


def _dirty(paths: Sequence[str]) -> str:
    listed = [f"  {path}" for path in paths[:_LISTED]]
    if len(paths) > _LISTED:
        listed.append(f"  and {len(paths) - _LISTED} more")
    return "\n".join(
        [
            "the work tree has changes, so init wrote nothing. Uncommitted and untracked paths:",
            *listed,
            "The rs-setup skill in your coding agent can help commit or stash them; "
            "then run rapid-ship init again.",
        ]
    )


def _stopped(
    root: Path, error: Exception, undo: Undo, base: str | None, *, detached: bool
) -> KitError:
    """Remove what init created, return to where it started, and say what is left to do."""
    try:
        undo.restore()
    except OSError as failure:
        return KitError(
            f"init stopped ({error}) and could not remove every file it created ({failure}); "
            "check git status"
        )
    done = f"init stopped ({error}) and removed the files it had created"
    try:
        if base is None:
            git(root, "reset", "--quiet")  # unstage what init added; there is no branch to leave
            return KitError(done)
        leave_branch(root, base, INIT_BRANCH, detached=detached)
    except KitError as failure:
        back = (
            "git reset"
            if base is None
            else f"git reset, git switch {base} and git branch -D {INIT_BRANCH}"
        )
        return KitError(f"{done}, but could not go back ({failure}); run {back}")
    return KitError(f"{done}; back on {base}, {INIT_BRANCH} deleted")


def _plan(
    root: Path, templates: Sequence[Template]
) -> tuple[list[tuple[Template, Path]], list[str], list[str]]:
    """Sort the templates into writes, skipped seeded files and conflicts. Nothing is written."""
    writes: list[tuple[Template, Path]] = []
    skipped: list[str] = []
    conflicts: list[str] = []
    checked: set[str] = set()
    seeded = {template.path for template in templates if template.kind == "seeded"}
    for path in [*(template.path for template in templates), LOCK_PATH]:
        try:
            safe_path(root, path)
        except UnsafePath as error:
            # init never writes over a seeded file, so a seeded file that is itself a link, such
            # as CLAUDE.md -> AGENTS.md, is skipped below. A link above it is still a conflict.
            if path not in seeded or not _directories_are_real(root, path):
                conflicts.append(str(error))
                continue
        checked.add(path)
    for template in templates:
        if template.path not in checked:
            continue
        target = locate(root, template.path)
        blocker = next(
            (
                p
                for p in reversed(target.parents)
                if p.is_relative_to(root) and p != root and p.exists() and not p.is_dir()
            ),
            None,
        )
        if blocker is not None:
            conflicts.append(f"{template.path}: {blocker.relative_to(root)} is not a directory")
        elif os.path.lexists(target):
            if template.kind == "managed":
                conflicts.append(f"{template.path}: exists")
            else:
                skipped.append(template.path)
        else:
            writes.append((template, target))
    # A Kit file that git ignores could never be committed, so CI would run without it.
    candidates = [template.path for template, _ in writes]
    if LOCK_PATH in checked:
        candidates.append(LOCK_PATH)
    if candidates:
        output = git(
            root,
            "check-ignore",
            "-z",
            "--stdin",
            stdin=b"\0".join(map(os.fsencode, candidates)),
            allowed=(0, 1),
            literal=False,  # check-ignore refuses pathspec flags; stdin paths are literal
        )
        conflicts += [
            f"{os.fsdecode(path)}: ignored by git, so it could not be committed"
            for path in output.split(b"\0")
            if path
        ]
    return writes, skipped, conflicts


def _directories_are_real(root: Path, path: str) -> bool:
    """True when no directory on the way to path is a symlink. path itself may be one."""
    try:
        locate(root, path)
    except UnsafePath:
        return False
    return True


def _write(
    root: Path,
    writes: Sequence[tuple[Template, Path]],
    executable: frozenset[str],
    lock: Lock,
    undo: Undo,
) -> list[str]:
    """Create every file, then the lock, noting each in undo. Returns the created paths."""
    for template, target in writes:
        undo.make_parents(target)
        if template.link is not None:
            os.symlink(template.link, target)
        else:
            create_file(target, template.content or b"", executable=template.path in executable)
        undo.created.append(target)  # only after it exists, so a failed create removes nothing
    undo.make_parents(root / LOCK_PATH)
    undo.created.append(root / LOCK_PATH)  # removed with missing_ok if write_lock fails
    write_lock(root, lock)
    return [*(template.path for template, _ in writes), LOCK_PATH]
