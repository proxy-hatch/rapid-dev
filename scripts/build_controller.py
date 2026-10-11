#!/usr/bin/env python3
"""Install a wheel in this checkout; replacing an installation is explicit."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(root: Path, *args: str) -> None:
    subprocess.run(["uv", *args], cwd=root, check=True)


def install(root: Path, rebuild: bool) -> None:
    destination = root / ".controller"
    if destination.is_symlink():
        raise ValueError("Refusing symlink at .controller")
    if destination.exists() and not rebuild:
        executable = destination / "bin/devctl"
        result = subprocess.run(
            [str(executable), "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode or result.stdout.strip() != "devctl 0.1.0":
            raise ValueError(
                "Controller is incomplete. Review the checkout and use setup --rebuild."
            )
        print("Using .controller/bin/devctl. Use setup --rebuild to install reviewed changes.")
        return
    with tempfile.TemporaryDirectory(prefix=".controller-build-", dir=root) as temporary:
        work = Path(temporary)
        wheels = work / "wheels"
        run(root, "build", "--wheel", "--out-dir", str(wheels))
        requirements = work / "requirements.txt"
        run(
            root,
            "export",
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--output-file",
            str(requirements),
            "--quiet",
        )
        candidates = list(wheels.glob("rapid_ship-*.whl"))
        if len(candidates) != 1:
            raise ValueError("Expected one rapid-ship wheel")
        backup = work / "previous"
        if destination.exists():
            destination.rename(backup)
        try:
            # Install at the final path: virtualenv entry points contain absolute paths.
            run(root, "venv", "--python", sys.executable, str(destination))
            run(
                root,
                "pip",
                "install",
                "--python",
                str(destination / "bin/python"),
                "--requirements",
                str(requirements),
                str(candidates[0]),
            )
            result = subprocess.run(
                [str(destination / "bin/devctl"), "--version"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.stdout.strip() != "devctl 0.1.0":
                raise ValueError("Built controller has the wrong version")
            (destination / "source.json").write_text(
                json.dumps({"framework_root": str(root)}, indent=2) + "\n"
            )
        except BaseException:
            if destination.exists():
                shutil.rmtree(destination)
            if backup.exists():
                backup.rename(destination)
            raise
    print("Installed .controller/bin/devctl. Open your coding agent here and use rapid-ship setup.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Replace the installation after stopping running project sessions",
    )
    args = parser.parse_args()
    if sys.version_info < (3, 12):  # noqa: UP036 - invoked before project setup
        parser.error("Python 3.12 or newer is required")
    root = Path(__file__).resolve().parents[1]
    # Separate installers must not race a rebuild or remove one another's files.
    try:
        fd = os.open(root / ".controller-setup.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            install(root, args.rebuild)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Controller setup failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
