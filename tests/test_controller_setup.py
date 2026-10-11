"""Installer lifecycle tests use a fake uv; CI also builds and runs a real wheel."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def checkout(tmp_path):
    root = tmp_path / "framework"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts/build_controller.py", root / "scripts")
    (root / "pyproject.toml").write_text('[project]\nname="rapid-ship"\n')
    (root / "uv.lock").write_text("fixture")
    executable = tmp_path / "tools/uv"
    executable.parent.mkdir()
    executable.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, sys\n"
        "a=sys.argv[1:]\n"
        "if a[0]=='build':\n"
        " p=pathlib.Path(a[a.index('--out-dir')+1]);p.mkdir(exist_ok=True)\n"
        " (p/'rapid_ship-0.1.0-py3-none-any.whl').touch()\n"
        "elif a[0]=='venv':\n"
        " p=pathlib.Path(a[-1])/'bin';p.mkdir(parents=True)\n"
        " (p/'python').touch()\n"
        "elif a[:2]==['pip','install']:\n"
        " if os.environ.get('FAIL_INSTALL'): sys.exit(3)\n"
        " p=pathlib.Path(a[a.index('--python')+1]).parent/'devctl'\n"
        " p.write_text('#!/bin/sh\\necho \\\"devctl 0.1.0\\\"\\n');p.chmod(0o755)\n"
    )
    executable.chmod(0o755)
    return root, {**os.environ, "PATH": f"{executable.parent}:{os.environ['PATH']}"}


def setup(root, env, *args):
    return subprocess.run(
        [sys.executable, str(root / "scripts/build_controller.py"), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_setup_reuses_installed_wheel_until_explicit_rebuild(tmp_path):
    import json

    root, env = checkout(tmp_path)
    assert setup(root, env).returncode == 0
    marker = root / ".controller/source.json"
    assert json.loads(marker.read_text())["framework_root"] == str(root)
    local = root / ".controller/keep"
    local.touch()
    assert setup(root, env).returncode == 0
    assert local.exists()
    assert setup(root, env, "--rebuild").returncode == 0
    assert not local.exists()


def test_failed_rebuild_restores_previous_install(tmp_path):
    root, env = checkout(tmp_path)
    assert setup(root, env).returncode == 0
    (root / ".controller/keep").write_text("previous installation")
    result = setup(root, {**env, "FAIL_INSTALL": "1"}, "--rebuild")
    assert result.returncode != 0
    assert (root / ".controller/keep").read_text() == "previous installation"
    assert (root / ".controller/bin/devctl").is_file()


def test_setup_rejects_symlink_destination(tmp_path):
    root, env = checkout(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / ".controller").symlink_to(outside)
    result = setup(root, env, "--rebuild")
    assert result.returncode != 0
    assert "symlink" in result.stderr
    assert list(outside.iterdir()) == []
