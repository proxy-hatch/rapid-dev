"""The diff step: what a change does to the tests, compared with its base.

The base is the PR base in CI, or the merge base with the default branch locally. The head is
the work tree, with untracked files that Git does not ignore.

A test is removed when it is present at the base and absent everywhere at the head. A test's
identity is its name within its file (`test_x` or `TestA::test_x`), so a test moved to another
file is not removed. Each removal must be declared under `Removed tests:` in the PR's Evidence
section, and is classed unit when its path matches a `[tests] unit` glob, else behavioural.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from devctl.check.evidence import removed_test_declarations
from devctl.check.stacks.python import is_test_file, test_identities
from devctl.check.steps import (
    CheckContext,
    StepResult,
    Tier,
    blocked,
    failed,
    not_applicable,
    passed,
)
from devctl.repo import Repo, RepoError

# What reading and parsing a test file raises for text that is not valid Python: bad syntax,
# a null byte, or bytes that are not UTF-8.
_UNPARSABLE = (SyntaxError, ValueError)

_UNDECLARED = "declare it under 'Removed tests:' in the PR's Evidence section"
_NO_BODY = " (pass --pr-body <file> to check a body locally)"
_OWNER_WAITS = "; in Flight this waits for the owner's approval"


@dataclass(frozen=True)
class Change:
    path: str
    status: Literal["A", "M", "D"]


def changed_files(repo: Repo, base: str) -> list[Change]:
    """Changes from base to the work tree, plus untracked files that Git does not ignore."""
    fields = repo.git("diff", "--name-status", "-z", "--no-renames", base).split("\0")
    changes = [
        Change(path, "A" if status == "A" else "D" if status == "D" else "M")
        for status, path in zip(fields[0::2], fields[1::2], strict=False)
        if path
    ]
    known = {change.path for change in changes}
    untracked = repo.git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    return changes + [Change(path, "A") for path in untracked if path and path not in known]


def _removed(identities: Mapping[str, tuple[list[str], list[str]]]) -> list[tuple[str, str]]:
    """The (path, identity) of each removed test, by identity, then path."""
    totals: Counter[str] = Counter()
    places: dict[str, list[str]] = defaultdict(list)
    for path, (before, after) in sorted(identities.items()):
        totals.update(before)
        totals.subtract(after)
        for name, count in sorted((Counter(before) - Counter(after)).items()):
            places[name].extend([path] * count)
    return [
        (path, name)
        for name, paths in sorted(places.items())
        for path in paths[: max(totals[name], 0)]
    ]


def removed_tests(identities: Mapping[str, tuple[list[str], list[str]]]) -> list[str]:
    """identities maps each changed test file to its test identities at (base, head).

    Files that did not change hold the same tests at both ends, so they are left out.
    """
    return [f"{path}::{name}" for path, name in _removed(identities)]


def _glob(pattern: str) -> str:
    parts, index = [], 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            parts.append(".*")
            index += 2
        else:
            char = pattern[index]
            parts.append("[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char))
            index += 1
    return "".join(parts)


def glob_match(pattern: str, path: str) -> bool:
    """Whether path matches pattern; "**" spans directories, "*" and "?" do not."""
    return re.fullmatch(_glob(pattern), path) is not None


def _base_tests(repo: Repo, base: str, path: str) -> list[str] | None:
    """The tests in path at base; None when that text does not parse."""
    try:
        return test_identities(repo.git("show", f"{base}:{path}"))
    except _UNPARSABLE:
        return None


def _changed_tests(
    repo: Repo, base: str, changes: Sequence[Change]
) -> tuple[dict[str, tuple[list[str], list[str]]], list[str]]:
    """Each changed test file's tests at (base, head), and a problem per file that stops parsing.

    A head that does not parse counts as holding its base's tests, so its problem is reported
    once rather than as a removal of each test.
    """
    identities: dict[str, tuple[list[str], list[str]]] = {}
    problems: list[str] = []
    for change in changes:
        if not is_test_file(change.path):
            continue
        before = None if change.status == "A" else _base_tests(repo, base, change.path)
        head = repo.root / change.path
        try:
            after = (
                [] if change.status == "D" else test_identities(head.read_text(encoding="utf-8"))
            )
        except _UNPARSABLE as error:
            if before is not None:
                problems.append(f"{change.path}: cannot parse the tests at head ({error})")
            after = before or []
        identities[change.path] = (before or [], after)
    return identities, problems


def _removals(
    context: CheckContext, removed: Sequence[tuple[str, str]]
) -> tuple[list[str], list[str]]:
    """A problem for each undeclared removal and a note for each declared one, in removed order."""
    body = context.pr_body
    declared = {} if body is None else removed_test_declarations(body)[0]
    gate = context.gate
    owner_waits = gate.mode == "flight" and gate.owner_approves_behavioural_test_removal
    problems: list[str] = []
    notes: list[str] = []
    for path, name in removed:
        test = f"{path}::{name}"
        unit = any(glob_match(pattern, path) for pattern in context.project.unit_tests)
        removal = f"removed {'unit' if unit else 'behavioural'} test {test}"
        if test not in declared:
            problems.append(f"{removal}: {_UNDECLARED}{_NO_BODY if body is None else ''}")
        else:
            waits = owner_waits and not unit
            notes.append(f"{removal}: declared ({declared[test]}){_OWNER_WAITS if waits else ''}")
    return problems, notes


class DiffStep:
    name = "diff"
    tier: Tier = "full"

    def run(self, context: CheckContext) -> StepResult:
        base = context.base
        if base is None:
            return not_applicable(
                self.name, "no base commit: not a change (pass --base to check one)"
            )
        identities: dict[str, tuple[list[str], list[str]]] = {}
        unparsable: list[str] = []
        try:
            changes = changed_files(context.repo, base)
            if context.project.stack == "python":
                identities, unparsable = _changed_tests(context.repo, base, changes)
        except (RepoError, OSError) as error:
            return blocked(self.name, str(error))
        problems, notes = _removals(context, _removed(identities))
        problems += unparsable
        return failed(self.name, *problems, *notes) if problems else passed(self.name, *notes)
