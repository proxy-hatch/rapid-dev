"""Small declarative profiles; commands are data, never executed while loading."""
from __future__ import annotations

import copy
from typing import Any

_OWNERSHIP = {
    "project": [".devctl/project.json", ".devctl/interview.json"],
    "generated": [".devctl/AGENTS.md", ".devctl/profile.json"],
    "runtime": [".devctl/state/"],
}

_CUSTOM: dict[str, Any] = {
    "id": "custom",
    "version": "1",
    "ownership": _OWNERSHIP,
}

_PYTHON_CLI: dict[str, Any] = {
    "id": "python-cli",
    "version": "1",
    "language": "python",
    "tools": ["uv", "python"],
    "checks": {
        "lint": ["uv", "run", "ruff", "check", "."],
        "types": ["uv", "run", "mypy", "src"],
        "unit": ["uv", "run", "pytest"],
    },
    "ownership": _OWNERSHIP,
}

_PROFILES = {"custom": _CUSTOM, "python-cli": _PYTHON_CLI}


def get_profile(name: str) -> dict[str, Any]:
    if name not in _PROFILES:
        raise ValueError(f"Unknown profile: {name}")
    return copy.deepcopy(_PROFILES[name])


def list_profiles() -> list[dict[str, Any]]:
    return [get_profile(name) for name in _PROFILES]
