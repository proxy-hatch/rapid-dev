"""devctl settings loading, defaults and errors (offline)."""

import json
import re
from pathlib import Path

import pytest

from devctl.settings import (
    EXCEPTIONS,
    GATE,
    PROJECT,
    Agent,
    GateSettings,
    ProjectSettings,
    SettingsError,
    load_exceptions,
    load_gate,
    load_project,
)
from rapid_ship.kit.init import resolve_variables
from rapid_ship.kit.templates import KitError, render_files

ROOT = Path(__file__).resolve().parents[2]
VARIABLES = {"project_name": "demo-app", "package": "demo_app", "owner": "", "repository": ""}
LOADERS = {PROJECT: load_project, GATE: load_gate, EXCEPTIONS: load_exceptions}


def write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_the_seeded_settings_load_with_the_spec_defaults(tmp_path):
    for template in render_files("python", VARIABLES, ()):
        if template.path.startswith(".rapid-ship/"):
            write(tmp_path, template.path, template.content.decode())

    assert load_project(tmp_path) == ProjectSettings(
        stack="python",
        worker=None,
        reviewer=None,
        repository=None,
        worker_app_id=None,
        reviewer_app_id=None,
        linear_team_id=None,
        linear_project_id=None,
        optional_skills=(),
        excluded=(),
        max_workers=5,
        attempt_limit=3,
        worktree_root="../demo-app.worktrees",
        source_roots=("src/demo_app",),
        unguided=(),
        unit_tests=("tests/unit/**",),
        release_method="none",
    )
    assert load_gate(tmp_path) == GateSettings(
        "walk", None, owner_approves_behavioural_test_removal=True
    )
    assert load_exceptions(tmp_path) == []


def test_absent_keys_take_their_defaults(tmp_path):
    write(tmp_path, PROJECT, 'stack = "agnostic"\n')
    write(tmp_path, GATE, "")

    project = load_project(tmp_path)

    assert (project.max_workers, project.attempt_limit, project.unit_tests) == (
        5,
        3,
        ("tests/unit/**",),
    )
    assert project.worktree_root == f"../{tmp_path.name}.worktrees"
    assert load_gate(tmp_path) == GateSettings("walk", None, True)


def test_agents_keep_the_exact_model(tmp_path):
    write(
        tmp_path,
        PROJECT,
        'stack = "python"\n[agents.reviewer]\nharness = "claude"\nmodel = "claude-opus-5-5"\n',
    )

    assert load_project(tmp_path).reviewer == Agent("claude", "claude-opus-5-5")


def test_kit_exclude_is_loaded_and_normalised(tmp_path):
    write(
        tmp_path,
        PROJECT,
        'stack = "python"\n[kit]\n'
        'exclude = ["devctl", "tools/devctl/", "./.agents/skills/rs-tdd"]\n',
    )

    assert load_project(tmp_path).excluded == ("devctl", "tools/devctl", ".agents/skills/rs-tdd")


def test_this_repository_settings_load():
    project = load_project(ROOT)
    assert (project.repository, project.source_roots) == ("proxy-hatch/rapid-ship", ("rapid_ship",))
    # Nothing is excluded here, so status --strict holds every Kit file to its template.
    assert project.excluded == ()
    assert load_gate(ROOT).mode == "walk"


def test_a_missing_file_is_a_settings_error(tmp_path):
    with pytest.raises(SettingsError, match=re.escape(".rapid-ship/project.toml: missing")):
        load_project(tmp_path)


EXCEPTION = (
    '[[exception]]\nid = "EX-1"\npath = "a.py"\nrule = "S603"\nreason = "r"\nremove_when = "w"\n'
)


@pytest.mark.parametrize(
    ("relative", "text", "message"),
    [
        (PROJECT, "", "stack: required"),
        (PROJECT, "stack = \n", "project.toml: Invalid value"),
        (PROJECT, 'stack = "rust"\n', "stack: expected python or agnostic"),
        (PROJECT, 'stack = "python"\n[test]\nunit = []\n', "unknown key 'test'"),
        (
            PROJECT,
            'stack = "python"\n[github]\nworker_app_id = true\n',
            "worker_app_id: expected an integer of at least 0",
        ),
        (
            PROJECT,
            'stack = "python"\n[dispatch]\nmax_workers = 0\n',
            "max_workers: expected an integer of at least 1",
        ),
        (PROJECT, 'stack = "python"\n[agents.worker]\nharness = "agy"\n', "model: required"),
        (
            PROJECT,
            'stack = "python"\n[agents.worker]\nharness = "agy"\nmodel = " m "\n',
            "model: required",
        ),
        (
            PROJECT,
            'stack = "python"\n[agents.worker]\nharness = "x"\nmodel = "m"\n',
            "harness: expected claude or codex or agy",
        ),
        (
            PROJECT,
            'stack = "python"\n[github]\nrepository = "not a repo"\n',
            "repository: expected owner/name",
        ),
        (
            PROJECT,
            'stack = "python"\n[github]\nrepository = "owner/.."\n',
            "repository: expected owner/name",
        ),
        (
            PROJECT,
            'stack = "python"\n[tests]\nunit = "tests/unit/**"\n',
            "unit: expected a list of non-empty strings",
        ),
        (
            PROJECT,
            'stack = "python"\n[kit]\nexclude = "devctl"\n',
            "exclude: expected a list of non-empty strings",
        ),
        (
            PROJECT,
            'stack = "python"\n[kit]\nexclude = ["../outside"]\n',
            "exclude: expected paths inside the repository",
        ),
        (
            PROJECT,
            'stack = "python"\n[kit]\nexclude = ["/etc"]\n',
            "exclude: expected paths inside the repository",
        ),
        (GATE, 'mode = "run"\n', "mode: expected walk or flight"),
        (GATE, 'owner_approves_behavioural_test_removal = "false"\n', "expected true or false"),
        (
            GATE,
            "owner_approves_behavioral_test_removal = false\n",
            "unknown key 'owner_approves_behavioral_test_removal'",
        ),
        (GATE, "[thresholds.weekly]\nwindow = 7\n", "unknown key 'weekly'"),
        (EXCEPTIONS, EXCEPTION.replace('remove_when = "w"\n', ""), "remove_when: required"),
        (EXCEPTIONS, EXCEPTION + EXCEPTION, "EX-1 is listed twice"),
        (EXCEPTIONS, EXCEPTION.replace("EX-1", "EX-01"), "id: expected EX-<n>"),
        (
            EXCEPTIONS,
            EXCEPTION.replace('"a.py"', '"../a.py"'),
            "path: expected a path inside the repository",
        ),
    ],
)
def test_invalid_settings_raise_settings_error(tmp_path, relative, text, message):
    write(tmp_path, relative, text)

    with pytest.raises(SettingsError, match=re.escape(message)):
        LOADERS[relative](tmp_path)


@pytest.mark.parametrize(
    ("repository", "valid"),
    [
        ("octo/demo", True),
        ("octo-cat/my.app", True),
        ("octo/.github", True),
        ("octo/a..b", True),
        ("octo", False),
        ("octo/", False),
        ("octo/.", False),
        ("octo/..", False),
        ("-octo/demo", False),
        ("octo/de mo", False),
        ("octo/demo\n", False),
    ],
)
def test_devctl_and_init_accept_the_same_repositories(tmp_path, repository, valid):
    # devctl is vendored into projects without rapid-ship, so it keeps its own copy of the pattern.
    write(tmp_path, PROJECT, f'stack = "python"\n[github]\nrepository = {json.dumps(repository)}\n')

    try:
        load_project(tmp_path)
        devctl_accepts = True
    except SettingsError:
        devctl_accepts = False
    try:
        # --name keeps the repository's own name, such as .github, out of the project-name check.
        resolve_variables(tmp_path, name="demo-app", repository=repository)
        init_accepts = True
    except KitError:
        init_accepts = False

    assert (devctl_accepts, init_accepts) == (valid, valid)
