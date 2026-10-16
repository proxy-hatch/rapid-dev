"""devctl's command line, from the vendored copy (offline)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import NoReturn

import pytest

import devctl
import devctl_project
from devctl import cli

ROOT = Path(__file__).resolve().parents[2]


def test_tests_import_the_vendored_copy() -> None:
    assert Path(devctl.__file__).resolve().parent == ROOT / "tools/devctl/devctl"


def test_version_prints_the_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["--version"])
    assert raised.value.code == 0
    assert capsys.readouterr().out == f"devctl {devctl.__version__}\n"


def test_a_project_verb_returns_its_handler_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        commands.add_parser("hello").set_defaults(handler=lambda args: 7)

    monkeypatch.setattr(devctl_project, "register", register)

    assert cli.main(["hello"]) == 7


def test_a_command_is_required() -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main([])
    assert raised.value.code == 2


def test_a_settings_error_exits_2_with_its_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from devctl.settings import SettingsError

    def broken(args: argparse.Namespace) -> NoReturn:
        raise SettingsError(".rapid-ship/gate.toml mode: expected walk or flight")

    monkeypatch.setattr(
        devctl_project,
        "register",
        lambda commands: commands.add_parser("go").set_defaults(handler=broken),
    )

    assert cli.main(["go"]) == 2
    assert "devctl: .rapid-ship/gate.toml mode: expected walk or flight" in capsys.readouterr().err


def test_a_repo_error_exits_2_with_its_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from devctl.repo import RepoError

    def broken(args: argparse.Namespace) -> NoReturn:
        raise RepoError("git rev-parse: not a git repository")

    monkeypatch.setattr(
        devctl_project,
        "register",
        lambda commands: commands.add_parser("go").set_defaults(handler=broken),
    )

    assert cli.main(["go"]) == 2
    assert "devctl: git rev-parse: not a git repository" in capsys.readouterr().err
