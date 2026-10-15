"""Check the built wheel ships every template, then run its rapid-ship in scratch repositories."""

import os
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

TEMPLATES = "rapid_ship/templates/"
# rapid-ship init commits the Kit, so each scratch repository has its own identity and no signing.
SCRATCH_GIT_CONFIG = {
    "user.name": "Smoke",
    "user.email": "smoke@example.invalid",
    "commit.gpgsign": "false",
}
WORKSPACE_PYPROJECT = """[project]
name = "existing-app"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["tools/*"]
"""
# rs-setup adds this to the workspace table above (plan 5);
# without it the project's own uv lock fails.
DEVCTL_EXCLUDE = 'exclude = ["tools/devctl"]\n'


def run(cwd: Path, *command: str) -> str:
    print(f"Smoke: {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(
            f"Smoke failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stdout}{result.stderr}"
        )
    return result.stdout


def scratch_repository(path: Path) -> None:
    path.mkdir()
    run(path, "git", "init", "-q")
    for key, value in SCRATCH_GIT_CONFIG.items():
        run(path, "git", "config", key, value)


def expect_kit_commit(path: Path, branch: str) -> None:
    """init committed the Kit on branch and left the work tree clean."""
    if run(path, "git", "branch", "--show-current").strip() != branch:
        raise SystemExit(f"init left {path.name} off the branch {branch}")
    if run(path, "git", "status", "--porcelain", "--untracked-files=all"):
        raise SystemExit(f"init left uncommitted files in {path.name}")


def expected_templates(root: Path) -> set[str]:
    """Template files git keeps. check.py's temporary copy holds exactly these and has no .git."""
    if (root / ".git").exists():
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
                TEMPLATES,
            ],
            capture_output=True,
            check=True,
        ).stdout
        return {os.fsdecode(name) for name in listed.split(b"\0") if name}
    return {
        path.relative_to(root).as_posix()
        for path in (root / TEMPLATES).rglob("*")
        if path.is_file()
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    project_version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    wheels = sorted((root / "dist").glob("rapid_ship-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected one rapid-ship wheel in dist/; run uv build first")
    with zipfile.ZipFile(wheels[0]) as wheel:
        shipped = {name for name in wheel.namelist() if name.startswith(TEMPLATES)}
    missing = sorted(expected_templates(root) - shipped)
    if missing:
        raise SystemExit(
            "The wheel lacks template files; hatch drops git-ignored paths:\n" + "\n".join(missing)
        )
    with tempfile.TemporaryDirectory(prefix="rapid-ship-smoke-") as temporary:
        work = Path(temporary).resolve()
        run(work, "uv", "venv", "--quiet", "--python", sys.executable, str(work / "venv"))
        python = str(work / "venv/bin/python")
        run(work, "uv", "pip", "install", "--quiet", "--python", python, str(wheels[0]))
        location = Path(
            run(work, python, "-I", "-c", "import rapid_ship; print(rapid_ship.__file__)").strip()
        )
        if location.resolve().is_relative_to(root):
            raise SystemExit("The smoke imported the source checkout instead of the wheel")
        rapid_ship = str(work / "venv/bin/rapid-ship")
        reported = run(work, rapid_ship, "--version")
        if reported != f"rapid-ship {project_version}\n":
            raise SystemExit(
                f"Installed rapid-ship reported {reported!r}, expected {project_version}"
            )

        new = work / "new-app"
        scratch_repository(new)
        default_branch = run(new, "git", "symbolic-ref", "--short", "HEAD").strip()
        run(new, rapid_ship, "init", "--stack", "python", "--owner", "smoke-owner")
        expect_kit_commit(new, default_branch)  # no commits yet, so the Kit is the first
        run(new, rapid_ship, "status", "--strict")
        run(new, "uv", "lock", "--check", "--project", "tools/devctl")
        version = run(new, "./devctl", "--version")

        existing = work / "existing-app"
        scratch_repository(existing)
        (existing / "pyproject.toml").write_text(WORKSPACE_PYPROJECT)
        run(existing, "git", "add", "pyproject.toml")
        run(existing, "git", "commit", "-q", "-m", "Existing project")
        run(existing, rapid_ship, "init")
        expect_kit_commit(existing, "rapid-ship/init")
        if run(existing, "./devctl", "--version") != version:
            raise SystemExit("devctl reported different versions in the two projects")
        with (existing / "pyproject.toml").open("a", encoding="utf-8") as pyproject:
            pyproject.write(DEVCTL_EXCLUDE)
        run(existing, "uv", "lock")
        run(existing, "uv", "lock", "--check", "--project", "tools/devctl")
    print("Wheel templates, isolated init and its commit, status and devctl smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
