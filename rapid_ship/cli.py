"""Command-line entry point: init, status and sync for the vendored Kit."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError
from pathlib import Path

from rapid_ship.kit.git import work_tree_root
from rapid_ship.kit.init import init_repository, resolve_variables
from rapid_ship.kit.status import classify
from rapid_ship.kit.sync import REVERT, sync_repository
from rapid_ship.kit.templates import STACKS, KitError, KitRefusal, installed_version

_NO_METADATA = (
    "cannot read rapid-ship's package metadata; run the installed command, "
    "such as uv run rapid-ship"
)


class _Version(argparse.Action):
    """--version, which reads the package metadata only when the option is given."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str = argparse.SUPPRESS,
        default: str = argparse.SUPPRESS,
        help: str | None = None,
    ) -> None:
        super().__init__(option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        print(f"rapid-ship {installed_version()}")
        parser.exit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rapid-ship", description="Vendor rapid-ship's Kit and keep it current."
    )
    parser.add_argument("--version", action=_Version, help="show the version and exit")
    commands = parser.add_subparsers(dest="command", metavar="<command>", required=True)
    init = commands.add_parser(
        "init",
        help=(
            "vendor the Kit at the top of this work tree and commit it on the branch "
            "rapid-ship/init; the work tree must be clean"
        ),
    )
    init.add_argument("--stack", choices=STACKS, help="required when there is no pyproject.toml")
    init.add_argument(
        "--owner", help="your GitHub login, for CODEOWNERS; rs-setup fills it when absent"
    )
    init.add_argument("--repository", help="owner/name on GitHub")
    init.add_argument(
        "--name",
        help="project name; default: the GitHub repository name, else the main checkout's name",
    )
    init.add_argument(
        "--package", help="Python package name; default: derived from the project name"
    )
    status = commands.add_parser(
        "status", help="compare the vendored Kit with its lock and this release"
    )
    status.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 unless every managed file is unchanged and current",
    )
    status.add_argument("--json", action="store_true", help="print the report as JSON")
    sync = commands.add_parser("sync", help="update the vendored Kit and open a pull request")
    sync.add_argument(
        "--in-place",
        action="store_true",
        help="write the work tree; no branch, commit or pull request",
    )
    sync.add_argument(
        "--revert",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "replace a Kit-managed file the project edited or deleted with the current template, "
            "so sync updates it again; a path as status prints it; repeatable"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        root = work_tree_root(Path.cwd())
        if args.command == "init":
            return _init(root, args)
        if args.command == "status":
            return _status(root, strict=args.strict, as_json=args.json)
        return _sync(root, in_place=args.in_place, revert=args.revert)
    except KitRefusal as error:
        print(f"rapid-ship: {error}", file=sys.stderr)
        return 1
    except KitError as error:
        print(f"rapid-ship: {error}", file=sys.stderr)
        return 2
    except PackageNotFoundError:
        print(f"rapid-ship: {_NO_METADATA}", file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError) as error:  # an unreadable file or template, for one
        print(f"rapid-ship: {error}", file=sys.stderr)
        return 2


def _init(root: Path, args: argparse.Namespace) -> int:
    variables = resolve_variables(
        root,
        name=args.name,
        package=args.package,
        owner=args.owner,
        repository=args.repository,
    )
    result = init_repository(root, stack=args.stack, variables=variables)
    if result.conflicts:
        print(
            "rapid-ship init wrote nothing. These Kit files conflict with the repository:",
            file=sys.stderr,
        )
        for conflict in result.conflicts:
            print(f"  {conflict}", file=sys.stderr)
        return 1
    print(
        f"Vendored the {result.stack} Kit {installed_version()} "
        f"for {variables['project_name']} (package {variables['package']})."
    )
    _print_paths("Created:", result.created)
    if result.skipped:
        _print_paths("Skipped existing seeded files; rs-setup merges them:", result.skipped)
    if not variables["owner"]:
        print("CODEOWNERS has no owner line yet; rs-setup writes it.")
    commit = result.commit[:12]
    if result.base is None:
        print(
            "The repository had no commits, so the Kit is its first commit, "
            f"{commit} on {result.branch}."
        )
        next_step = "Next: run the rs-setup skill in your coding agent."
    else:
        print(f"Committed the Kit as {commit} on {result.branch}, a new branch from {result.base}.")
        next_step = (
            f"Next: open a pull request from {result.branch}. "
            "The rs-setup skill in your coding agent does it."
        )
    if result.existing_checks:
        _print_paths(
            "Already in this repository (rs-setup will help combine these with devctl check):",
            result.existing_checks,
        )
    print(next_step)
    return 0


def _status(root: Path, *, strict: bool, as_json: bool) -> int:
    report = classify(root)
    if as_json:
        document = {
            "kit_version": report.kit_version,
            "installed_version": report.installed_version,
            "stack": report.stack,
            "files": [asdict(item) for item in report.files],
            "outdated": report.outdated,
            "not_installed": report.not_installed,
            "strict_ok": report.strict_ok,
        }
        print(json.dumps(document, indent=2))
    else:
        print(
            f"Kit {report.kit_version} (installed rapid-ship {report.installed_version}), "
            f"stack {report.stack}"
        )
        lines: list[tuple[str, str]] = [
            (item.state, item.path) for item in report.files if item.state != "unchanged"
        ]
        lines += [("outdated", path) for path in report.outdated]
        lines += [("not installed", path) for path in report.not_installed]
        for state, path in lines:
            print(f"{state:<17} {path}")
        if any(item.state in ("modified", "missing") for item in report.files):
            print(
                "The next rapid-ship sync makes each modified or missing file the project's own "
                f"and stops its updates. To keep the Kit's version, run {REVERT}."
            )
        current = sum(
            1 for item in report.files if item.kind == "managed" and item.state == "unchanged"
        )
        print(f"{current} managed {'file' if current == 1 else 'files'} unchanged.")
    return 1 if strict and not report.strict_ok else 0


def _sync(root: Path, *, in_place: bool, revert: Sequence[str]) -> int:
    result = sync_repository(root, in_place=in_place, revert=revert)
    if not result.changed and not result.conflicts:
        print("Kit is current; nothing to sync.")
    buckets = [
        ("Replaced with the new template:", result.updated),
        ("Reverted to the Kit's template; sync updates them again:", result.reverted),
        ("Already equal to the new template; only the lock changed:", result.adopted),
        ("Added:", result.added),
        ("Deleted, because the Kit dropped them:", result.deleted),
        (
            "Now the project's own, because it edited or deleted them; "
            "sync no longer updates them:",
            result.owned,
        ),
        ("Seeded files whose template changed; sync did not change them:", result.seeded_changed),
        (
            "New seeded templates where the project already has a file; "
            "sync recorded them and kept the files:",
            result.seeded_existing,
        ),
    ]
    for heading, paths in buckets:
        if paths:
            _print_paths(heading, paths)
    if result.owned:
        print(f"To give one back to the Kit, run {REVERT}.")
    for conflict in result.conflicts:
        print(f"Conflict: {conflict.path}: {conflict.reason}")
    if result.changed:
        if in_place:
            print("Wrote the changes to the work tree.")
        else:
            print(f"Opened {result.pull_request} on {result.branch}.")
    elif result.conflicts:
        print("Nothing was written.")
    return 1 if result.conflicts else 0


def _print_paths(heading: str, paths: Sequence[str]) -> None:
    print(heading)
    for path in paths:
        print(f"  {path}")
