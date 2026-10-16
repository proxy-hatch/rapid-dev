"""Run the Python/repository CI suite against the current working checkout."""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(root: Path, *command: str) -> None:
    print(f"\nChecking: {shlex.join(command)}", flush=True)
    subprocess.run(command, cwd=root, check=True)


def copy_source(root: Path, destination: Path) -> None:
    """Copy edited and new source, preserving aliases and excluding generated state."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    for name in sorted(set(result.stdout.split(b"\0")) - {b""}):
        relative = Path(os.fsdecode(name))
        source = root / relative
        if not source.exists() and not source.is_symlink():
            continue  # An unstaged deletion is part of the current checkout.
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python = sys.executable
    try:
        run(root, python, "scripts/check_repository.py")
        run(root, python, "-m", "rapid_ship", "status", "--strict")
        run(root, python, "-m", "ruff", "check", ".")
        run(root, python, "-m", "ruff", "format", "--check", ".")
        run(root, python, "-m", "mypy")
        run(root, python, "-m", "pytest")
        # Build from a temporary copy of current source: ignored local state stays out
        # of the archives, and the checkout gains no dist/ directory.
        with tempfile.TemporaryDirectory(prefix="rapid-ship-check-") as temporary:
            source = Path(temporary).resolve()
            copy_source(root, source)
            run(source, "uv", "build")
            run(source, python, "scripts/smoke_distribution.py")
    except subprocess.CalledProcessError as error:
        print(f"Validation failed ({error.returncode}): {shlex.join(error.cmd)}", file=sys.stderr)
        return error.returncode if error.returncode > 0 else 1
    except OSError as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        return 1
    print("\nPython and repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
