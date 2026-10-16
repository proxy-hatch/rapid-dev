"""This repository's .gitleaks.toml, run through the secrets step and real gitleaks (offline).

gitleaks 8.30.1 must be on PATH, as for the integration tests. Each secret below is assembled at
run time, so this file holds nothing for gitleaks to find.
"""

from __future__ import annotations

import base64
import secrets
import shutil
import string
from pathlib import Path

import pytest

from check_workspace import Workspace
from devctl.check.stacks.agnostic import SecretsStep

SETTINGS = Path(__file__).resolve().parents[1] / ".gitleaks.toml"
PLAN = "docs/superpowers/plans/2026-10-14-github-commands.md"
DASHES = "-" * 5
# The fixture line that commit 55fc5dfa added to PLAN. gitleaks's private-key match runs from its
# header to the first "KEY" and five dashes at least 64 characters on: here, the last line.
PLACEHOLDER = (
    f'    pem = b"{DASHES}BEGIN RSA PRIVATE KEY{DASHES}\\nMIIE\\n'
    f'{DASHES}END RSA PRIVATE KEY{DASHES}\\n"\n'
    + "    assert pem\n" * 8
    + f'    footer = "PRIVATE KEY{DASHES}"\n'
)


def token() -> str:
    alphabet = string.ascii_letters + string.digits
    return "ghp_" + "".join(secrets.choice(alphabet) for _ in range(36))


def key() -> str:
    body = base64.b64encode(secrets.token_bytes(900)).decode()
    lines = [body[start : start + 64] for start in range(0, len(body), 64)]
    return "\n".join(
        [f"{DASHES}BEGIN RSA PRIVATE KEY{DASHES}", *lines, f"{DASHES}END RSA PRIVATE KEY{DASHES}"]
    )


@pytest.mark.parametrize("settings", [True, False])
def test_only_the_quoted_placeholder_key_is_allowed(workspace: Workspace, settings: bool) -> None:
    if settings:
        shutil.copyfile(SETTINGS, workspace.root / ".gitleaks.toml")
    workspace.write(PLAN, "```python\n" + PLACEHOLDER + "```\n")
    workspace.write("docs/other.md", "```python\n" + PLACEHOLDER + "```\n")
    workspace.write("app.py", f'TOKEN = "{token()}"\n')
    workspace.commit("quote the placeholder")
    workspace.write(PLAN, "```python\n" + PLACEHOLDER + "```\n\n```\n" + key() + "\n```\n")
    workspace.commit("add a real-looking key to the same document")

    result = SecretsStep().run(workspace.context())

    # gitleaks's default rules still apply, and so does every other path and key.
    found = {detail.split(" (commit ")[0] for detail in result.details}
    allowed = {f"private-key {PLAN}:2"}
    expected = {"github-pat app.py:1", "private-key docs/other.md:2", f"private-key {PLAN}:15"}
    assert result.status == "failed"
    assert found == (expected if settings else expected | allowed)
