"""Projects invoke an explicitly selected controller without replacing local wrappers."""

import shlex
import stat
import subprocess
from pathlib import Path

import pytest

from agentic_engineering.configuration import init_project


def project(root: Path) -> Path:
    root.mkdir()
    (root / "design.md").write_text("Approved design\n")
    return root


def controller(path: Path, version: str = "devctl 0.1.0", version_exit: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' {shlex.quote(version)}\n"
        f"  exit {version_exit}\n"
        "fi\n"
        "printf '%s\\n' \"$PWD\" \"$@\"\n"
        "printf '%s\\n' 'controller stderr' >&2\n"
        "exit 17\n"
    )
    path.chmod(0o755)
    return path


def run_wrapper(root: Path, selected: str | None, *args: str) -> subprocess.CompletedProcess[str]:
    environment = {"PATH": "/usr/bin:/bin"}
    if selected is not None:
        environment["DEVCTL_CONTROLLER"] = selected
    return subprocess.run(
        [str(root / "devctl"), *args],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


def test_init_installs_executable_wrapper_that_preserves_arguments_and_exit_status(tmp_path: Path):
    root = project(tmp_path / "project with spaces")
    trusted = controller(tmp_path / "installed controller" / "devctl")

    initialized = init_project(root, "sample", "design.md")

    assert "devctl" in initialized["created"]
    assert stat.S_IMODE((root / "devctl").stat().st_mode) == 0o755
    result = run_wrapper(root, str(trusted), "status", "two words", "", "$(exit 99);*")
    assert result.returncode == 17
    assert result.stdout == f"{root}\nstatus\ntwo words\n\n$(exit 99);*\n"
    assert result.stderr == "controller stderr\n"


def test_reinitialization_preserves_installed_wrapper(tmp_path: Path):
    root = project(tmp_path / "project")
    init_project(root, "sample", "design.md")
    wrapper = root / "devctl"
    assert wrapper.is_file()
    original = wrapper.read_bytes()
    wrapper.chmod(0o700)

    result = init_project(root, "different", "design.md")

    assert "devctl" not in result["created"]
    assert wrapper.read_bytes() == original
    assert stat.S_IMODE(wrapper.stat().st_mode) == 0o700


@pytest.mark.parametrize("mode", [0o640, 0o750])
def test_init_preserves_existing_wrapper_bytes_and_mode(tmp_path: Path, mode: int):
    root = project(tmp_path / "project")
    wrapper = root / "devctl"
    original = b"#!/bin/sh\n# Local project wrapper\nexit 42\n"
    wrapper.write_bytes(original)
    wrapper.chmod(mode)

    result = init_project(root, "sample", "design.md")

    assert "devctl" not in result["created"]
    assert wrapper.read_bytes() == original
    assert stat.S_IMODE(wrapper.stat().st_mode) == mode


@pytest.mark.parametrize("target_exists", [False, True])
def test_init_rejects_wrapper_symlink_without_changing_target(tmp_path: Path, target_exists: bool):
    root = project(tmp_path / "project")
    target = tmp_path / "outside-controller"
    if target_exists:
        target.write_bytes(b"leave this file alone\n")
        target.chmod(0o640)
    wrapper = root / "devctl"
    wrapper.symlink_to(target)

    with pytest.raises(ValueError, match="symlink"):
        init_project(root, "sample", "design.md")

    assert wrapper.is_symlink()
    assert target.exists() is target_exists
    if target_exists:
        assert target.read_bytes() == b"leave this file alone\n"
        assert stat.S_IMODE(target.stat().st_mode) == 0o640


@pytest.mark.parametrize("selected", [None, "", ".venv/bin/devctl"])
def test_wrapper_requires_absolute_controller_without_project_source_fallback(
    tmp_path: Path, selected: str | None
):
    root = project(tmp_path / "project")
    controller(root / ".venv/bin/devctl")
    init_project(root, "sample", "design.md")
    assert (root / "devctl").is_file()

    result = run_wrapper(root, selected, "status")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "absolute path" in result.stderr


@pytest.mark.parametrize("exists", [False, True])
def test_wrapper_rejects_missing_or_nonexecutable_controller(tmp_path: Path, exists: bool):
    root = project(tmp_path / "project")
    trusted = tmp_path / "installed-controller"
    if exists:
        controller(trusted).chmod(0o644)
    init_project(root, "sample", "design.md")
    assert (root / "devctl").is_file()

    result = run_wrapper(root, str(trusted), "status")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "executable installed controller" in result.stderr


@pytest.mark.parametrize(
    ("version", "version_exit"), [("devctl 0.0.9", 0), ("", 64), ("devctl 0.1.0", 1)]
)
def test_wrapper_rejects_wrong_missing_or_failed_version_before_dispatch(
    tmp_path: Path, version: str, version_exit: int
):
    root = project(tmp_path / "project")
    trusted = controller(tmp_path / "installed-controller", version, version_exit)
    init_project(root, "sample", "design.md")
    assert (root / "devctl").is_file()

    result = run_wrapper(root, str(trusted), "status")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "version must be devctl 0.1.0" in result.stderr
    assert "controller stderr" not in result.stderr
