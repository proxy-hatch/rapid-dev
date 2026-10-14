"""Kit template types and errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Stack = Literal["python", "neutral"]
Kind = Literal["managed", "seeded"]
STACKS: tuple[Stack, ...] = ("python", "neutral")


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
