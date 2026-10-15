"""Core steps appear in spec section 5's order for each stack."""

from __future__ import annotations

from check_workspace import project_settings
from devctl.check import core_steps

PYTHON = [
    "format",
    "lint",
    "map",
    "exceptions",
    "file-size",
    "kit",
    "types",
    "contracts",
    "tests",
    "audit",
    "secrets",
    "workflows",
    "diff",
    "evidence",
]


def test_core_steps_follow_the_spec() -> None:
    python = core_steps(project_settings(stack="python"))
    agnostic = core_steps(project_settings(stack="agnostic"))

    assert [step.name for step in python] == PYTHON
    assert [step.name for step in agnostic] == [
        "map",
        "exceptions",
        "file-size",
        "kit",
        "secrets",
        "workflows",
        "diff",
        "evidence",
    ]
    assert [step.name for step in python if step.tier == "fast"] == PYTHON[:6]
