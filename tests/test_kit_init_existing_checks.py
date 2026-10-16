"""rapid-ship init lists the tool settings, hooks and workflows already in the repository, for
rs-setup to combine with devctl's checks (offline; real git in scratch repositories)."""

import os

import pytest

from rapid_ship.kit.init import init_repository


@pytest.fixture(autouse=True)
def default_hooks_directory(git_repo, run_git, monkeypatch):
    """git_repo turns hooks off with core.hooksPath=/dev/null. Remove that, and the machine's own
    git configuration, so init sees git's default hooks directory, .git/hooks."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    run_git(git_repo, "config", "--unset", "core.hooksPath")


def write(root, files):
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def listed(git_repo, make_templates, kit_variables, commit_all, files):
    """What init lists for a repository that holds exactly these committed files."""
    write(git_repo, files)
    commit_all(git_repo)
    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )
    assert result.conflicts == () and result.commit
    return list(result.existing_checks)


def test_init_lists_the_settings_hooks_and_workflows_already_there_sorted_without_samples(
    git_repo, make_templates, kit_variables, commit_all
):
    write(
        git_repo,
        {
            "ruff.toml": b"line-length = 100\n",
            ".pre-commit-config.yaml": b"repos: []\n",
            "pyproject.toml": b"[tool.mypy]\nstrict = true\n",
            ".github/workflows/ci.yml": b"name: ci\n",
        },
    )
    commit_all(git_repo)
    hooks = git_repo / ".git/hooks"
    for name, mode in (("pre-commit", 0o755), ("pre-commit.sample", 0o755), ("commit-msg", 0o644)):
        (hooks / name).write_text("#!/bin/sh\n")
        (hooks / name).chmod(mode)  # commit-msg is not executable, so git would not run it

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert result.existing_checks == (
        ".git/hooks/pre-commit",
        ".github/workflows/ci.yml",
        ".pre-commit-config.yaml",
        "pyproject.toml",
        "ruff.toml",
    )


def test_a_repository_without_checks_lists_nothing(
    git_repo, make_templates, kit_variables, commit_all
):
    files = {"README.md": b"# Hi\n", ".editorconfig": b"root = true\n"}  # not a check

    assert listed(git_repo, make_templates, kit_variables, commit_all, files) == []


@pytest.mark.parametrize(
    "name",
    [
        "ruff.toml",
        ".ruff.toml",
        "mypy.ini",
        ".mypy.ini",
        "pytest.ini",
        ".flake8",
        ".pylintrc",
        ".isort.cfg",
        ".pre-commit-config.yaml",
        "lefthook.yml",
        "lefthook.yaml",
    ],
)
def test_a_settings_or_hook_file_is_listed_by_its_name(
    git_repo, make_templates, kit_variables, commit_all, name
):
    files = {name: b"x = 1\n"}

    assert listed(git_repo, make_templates, kit_variables, commit_all, files) == [name]


def test_a_husky_directory_is_listed(git_repo, make_templates, kit_variables, commit_all):
    files = {".husky/pre-commit": b"npx lint-staged\n"}

    assert listed(git_repo, make_templates, kit_variables, commit_all, files) == [".husky/"]


@pytest.mark.parametrize("name", ["setup.cfg", "tox.ini"])
@pytest.mark.parametrize("section", ["mypy", "flake8", "tool:pytest", "pytest", "isort"])
def test_a_shared_config_file_is_listed_for_a_tool_section(
    git_repo, make_templates, kit_variables, commit_all, name, section
):
    files = {name: f"[metadata]\nname = demo\n\n[{section}]\nx = 1\n".encode()}

    assert listed(git_repo, make_templates, kit_variables, commit_all, files) == [name]


@pytest.mark.parametrize(
    "text",
    [
        "[metadata]\nname = demo\n",
        "[tox]\nenvlist = py312\n",
        "[metadata]\n# [mypy]\ndescription =\n  [flake8]\n",  # a comment, an indented line
    ],
)
def test_a_shared_config_file_without_a_tool_section_is_not_listed(
    git_repo, make_templates, kit_variables, commit_all, text
):
    files = {"setup.cfg": text.encode(), "tox.ini": text.encode()}

    assert listed(git_repo, make_templates, kit_variables, commit_all, files) == []


@pytest.mark.parametrize(
    "table",
    [
        "tool.ruff",
        "tool.ruff.lint",
        "tool.mypy",
        "tool.pytest.ini_options",
        "tool.black",
        "tool.isort",
        "tool.pylint",
    ],
)
def test_a_pyproject_with_a_tool_table_is_listed(
    git_repo, make_templates, kit_variables, commit_all, table
):
    files = {"pyproject.toml": f'[project]\nname = "demo"\n\n[{table}]\n'.encode()}

    assert listed(git_repo, make_templates, kit_variables, commit_all, files) == ["pyproject.toml"]


@pytest.mark.parametrize(
    "text",
    [
        '[project]\nname = "demo"\n',
        '[project]\nname = "demo"\n\n[tool.hatch.build]\npackages = ["demo"]\n',
        '[project]\nname = "demo"\ndescription = "uses [tool.mypy] and ruff"\n',
        '[project]\nname = "demo"\n\n[tool]\nruff = "none"\n',  # a value, not a table
    ],
)
def test_a_pyproject_without_a_tool_table_is_not_listed(
    git_repo, make_templates, kit_variables, commit_all, text
):
    files = {"pyproject.toml": text.encode()}

    assert listed(git_repo, make_templates, kit_variables, commit_all, files) == []


DEEPLY_NESTED = b"x = " + b"[" * 5000 + b"]" * 5000 + b"\n"


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"pyproject.toml": b"[tool.mypy\n"}, ["pyproject.toml (unreadable)"]),
        ({"pyproject.toml": b"\xff\xfe[tool.mypy]\n"}, ["pyproject.toml (unreadable)"]),
        ({"setup.cfg": b"\xff\xfe[mypy]\n"}, ["setup.cfg (unreadable)"]),
        ({"tox.ini": b"\xff\xfe[mypy]\n", "ruff.toml": b""}, ["ruff.toml", "tox.ini (unreadable)"]),
        # tomllib recurses once per nesting level, so a deep enough array exhausts the stack.
        ({"pyproject.toml": DEEPLY_NESTED}, ["pyproject.toml (unreadable)"]),
    ],
)
def test_a_file_that_cannot_be_read_is_listed_as_unreadable_and_init_succeeds(
    git_repo, make_templates, kit_variables, commit_all, files, expected
):
    assert listed(git_repo, make_templates, kit_variables, commit_all, files) == expected


def test_only_yml_and_yaml_files_directly_in_workflows_are_listed(
    git_repo, make_templates, kit_variables, commit_all
):
    files = {
        ".github/workflows/ci.yml": b"name: ci\n",
        ".github/workflows/release.yaml": b"name: release\n",
        ".github/workflows/README.md": b"# Workflows\n",
        ".github/workflows/old.yml.disabled": b"name: old\n",
        ".github/workflows/nested/inner.yml": b"name: inner\n",
        ".github/CODEOWNERS": b"* @octo\n",
    }

    assert listed(git_repo, make_templates, kit_variables, commit_all, files) == [
        ".github/workflows/ci.yml",
        ".github/workflows/release.yaml",
    ]


def test_a_configured_hooks_path_is_listed_with_its_executable_hooks(
    git_repo, make_templates, kit_variables, commit_all, run_git
):
    write(git_repo, {".githooks/pre-push": b"#!/bin/sh\n", ".githooks/README": b"hooks\n"})
    (git_repo / ".githooks/pre-push").chmod(0o755)
    commit_all(git_repo)
    run_git(git_repo, "config", "core.hooksPath", ".githooks")

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    # git ignores .git/hooks once core.hooksPath is set, so its samples and hooks are not listed.
    assert result.existing_checks == (".githooks (core.hooksPath)", ".githooks/pre-push")


def test_a_hooks_path_of_dev_null_is_not_a_hook(
    git_repo, make_templates, kit_variables, commit_all, run_git
):
    commit_all(git_repo)
    run_git(git_repo, "config", "core.hooksPath", "/dev/null")  # hooks off, as git_repo has it
    hook = git_repo / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\n")
    hook.chmod(0o755)

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert result.existing_checks == ()


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a directory with mode 000")
def test_an_unreadable_hooks_directory_is_listed_and_init_succeeds(
    git_repo, make_templates, kit_variables, commit_all
):
    commit_all(git_repo)
    hooks = git_repo / ".git/hooks"
    hooks.chmod(0)
    try:
        result = init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )
    finally:
        hooks.chmod(0o755)

    assert result.existing_checks == (".git/hooks (unreadable)",)
    assert result.commit


def test_a_file_the_kit_writes_is_not_listed_because_init_looks_before_it_writes(
    git_repo, make_templates, kit_variables, commit_all
):
    commit_all(git_repo)
    templates = make_templates(
        changes={
            "common/ruff.toml": "line-length = 100\n",
            "common/.github/workflows/devctl-check.yml": "name: devctl check\n",
        }
    )

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=templates
    )

    assert {"ruff.toml", ".github/workflows/devctl-check.yml"} <= set(result.created)
    assert result.existing_checks == ()


def test_a_conflict_lists_no_checks(git_repo, make_templates, kit_variables, commit_all):
    write(git_repo, {"devctl": b"ours\n", "ruff.toml": b""})
    commit_all(git_repo)

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert result.conflicts == ("devctl: exists",)
    assert result.existing_checks == ()
