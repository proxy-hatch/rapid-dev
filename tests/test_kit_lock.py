"""Kit lock reading and writing (offline)."""

import hashlib
import re
import stat
from pathlib import Path

import pytest

from rapid_ship.kit.lock import LOCK_PATH, Lock, LockEntry, file_sha256, read_lock, write_lock
from rapid_ship.kit.templates import KitError

SHA = hashlib.sha256(b"content\n").hexdigest()
VARIABLES = {"owner": "", "package": "demo_app", "project_name": "demo-app", "repository": ""}
GOOD = f"""kit_version = "0.2.0"
stack = "python"

[variables]
package = "demo_app"

[[file]]
path = "devctl"
kind = "managed"
sha256 = "{SHA}"
"""


def test_file_sha256_is_the_hex_digest() -> None:
    assert file_sha256(b"content\n") == SHA


def test_round_trip_keeps_every_field_and_sorts_entries(tmp_path: Path) -> None:
    entries = (
        LockEntry("tools/devctl/devctl/cli.py", "managed", SHA, None, None),
        LockEntry(".claude/skills/rs-tdd", "managed", None, "../../.agents/skills/rs-tdd", None),
        LockEntry("AGENTS.md", "seeded", None, None, SHA),
    )
    write_lock(tmp_path, Lock("0.2.0", "python", VARIABLES, entries))

    restored = read_lock(tmp_path)

    expected = tuple(sorted(entries, key=lambda entry: entry.path))
    assert restored == Lock("0.2.0", "python", VARIABLES, expected)
    assert stat.S_IMODE((tmp_path / LOCK_PATH).stat().st_mode) == 0o644


def test_a_missing_lock_says_to_run_init(tmp_path: Path) -> None:
    with pytest.raises(KitError, match="run rapid-ship init"):
        read_lock(tmp_path)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("kit_version = ", "cannot read .rapid-ship/kit.lock"),
        (GOOD.replace('kit_version = "0.2.0"\n', ""), "kit_version must be a non-empty string"),
        (GOOD.replace('stack = "python"', 'stack = "rust"'), "stack must be python or agnostic"),
        (
            GOOD.replace('package = "demo_app"', "package = 1"),
            "[variables] must map names to strings",
        ),
        (GOOD + "extra = 1\n", "unknown key 'extra'"),
        (GOOD.replace('path = "devctl"', 'path = "../outside"'), "must stay inside the repository"),
        (
            GOOD.replace('path = "devctl"', 'path = "/etc/passwd"'),
            "must stay inside the repository",
        ),
        (
            GOOD.replace('path = "devctl"', 'path = "./devctl"'),
            "path './devctl' must be written as 'devctl'",
        ),
        (
            GOOD.replace('path = "devctl"', 'path = "devctl/"'),
            "path 'devctl/' must be written as 'devctl'",
        ),
        (
            GOOD.replace('path = "devctl"', 'path = "tools//devctl"'),
            "path 'tools//devctl' must be written as 'tools/devctl'",
        ),
        (GOOD + GOOD[GOOD.index("[[file]]") :], "devctl is listed twice"),
        (GOOD.replace(f'sha256 = "{SHA}"', 'sha256 = "abc"'), "a managed entry has sha256 or link"),
        (GOOD.replace('kind = "managed"', 'kind = "seeded"'), "a managed entry has sha256 or link"),
        (GOOD + 'link = "../x"\n', "a managed entry has sha256 or link"),
    ],
)
def test_an_invalid_lock_is_an_error(tmp_path: Path, text: str, message: str) -> None:
    (tmp_path / ".rapid-ship").mkdir()
    (tmp_path / LOCK_PATH).write_text(text)

    with pytest.raises(KitError, match=re.escape(message)):
        read_lock(tmp_path)


def test_the_lock_is_never_written_through_a_symlink(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".rapid-ship").symlink_to(outside)

    with pytest.raises(KitError, match="is a symlink"):
        write_lock(root, Lock("0.2.0", "python", VARIABLES, ()))
    assert list(outside.iterdir()) == []
