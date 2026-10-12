"""Engineering instructions shipped with the installed controller."""

from importlib.resources import files
from typing import Literal


def session_guidance(role: Literal["worker", "reviewer"]) -> dict[str, str]:
    references = files("agentic_engineering").joinpath("skills/rapid-ship-engineering/references")
    names = (
        ("writing", "ponytail", "implement", "tdd")
        if role == "worker"
        else ("writing", "ponytail", "review")
    )
    return {name: references.joinpath(f"{name}.md").read_text(encoding="utf-8") for name in names}
