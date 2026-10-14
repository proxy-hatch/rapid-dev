"""devctl's command line, from the vendored copy (offline)."""

from pathlib import Path

import pytest

import devctl
import devctl_project
from devctl import cli

ROOT = Path(__file__).resolve().parents[2]


def test_tests_import_the_vendored_copy():
    assert Path(devctl.__file__).resolve().parent == ROOT / "tools/devctl/devctl"


def test_version_prints_the_package_version(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["--version"])
    assert raised.value.code == 0
    assert capsys.readouterr().out == f"devctl {devctl.__version__}\n"


def test_a_project_verb_returns_its_handler_exit_code(monkeypatch):
    def register(commands):
        commands.add_parser("hello").set_defaults(handler=lambda args: 7)

    monkeypatch.setattr(devctl_project, "register", register)

    assert cli.main(["hello"]) == 7


def test_a_command_is_required():
    with pytest.raises(SystemExit) as raised:
        cli.main([])
    assert raised.value.code == 2


def test_the_seeded_project_hooks_add_nothing():
    assert devctl_project.check_steps() == []
