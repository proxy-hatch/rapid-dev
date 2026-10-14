"""Suppressions that need no parsing: gitleaks's allow comment and zizmor's ignore comment."""

from __future__ import annotations

import re

# Split so that documents quoting this code do not contain gitleaks's allow comment.
# rapid_ship/kit/adopt.py copies _GITLEAKS_ALLOW.
_GITLEAKS_ALLOW = "gitleaks" + ":allow"
_ZIZMOR = re.compile(r"#\s*zizmor:\s*ignore\[(?P<names>[^\]]+)\]")


def text_rules(path: str, text: str) -> list[str]:
    rules = ["gitleaks"] * text.count(_GITLEAKS_ALLOW)
    if path.endswith((".yml", ".yaml")):
        for match in _ZIZMOR.finditer(text):
            names = sorted(name for name in re.split(r"[\s,]+", match.group("names")) if name)
            rules.append("zizmor:" + ",".join(names))
    return rules
