"""The packaged Kit's templates match spec 1, section 4 (offline)."""

import re
import subprocess
import tomllib

import pytest

from rapid_ship.kit.templates import STACKS, load_manifest, packaged_templates, render_files

VARIABLES = {
    "project_name": "demo-app",
    "package": "demo_app",
    "owner": "octo",
    "repository": "octo/demo-app",
}
SEEDED = {
    ".github/CODEOWNERS",
    ".rapid-ship/exceptions.toml",
    ".rapid-ship/gate.toml",
    ".rapid-ship/project.toml",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/features/README.md",
    "docs/patterns/README.md",
}


def rendered(stack="python", **variables):
    return {t.path: t for t in render_files(stack, {**VARIABLES, **variables}, ())}


def text(stack, path, **variables):
    return rendered(stack, **variables)[path].content.decode()


def test_every_manifest_path_exists_in_a_layer():
    manifest = load_manifest()
    root = packaged_templates()
    for path in manifest.seeded | manifest.new_project | manifest.executable:
        assert any((root / layer / path).is_file() for layer in ("common", *STACKS)), path


@pytest.mark.parametrize("stack", STACKS)
def test_the_spec_seeded_files_are_seeded(stack):
    kinds = {path: t.kind for path, t in rendered(stack).items()}
    assert {path for path in SEEDED if kinds.get(path) == "seeded"} == SEEDED


def test_python_new_project_seeds():
    kinds = {path: t.kind for path, t in rendered().items()}
    assert {
        kinds[p] for p in ("pyproject.toml", "src/demo_app/__init__.py", "tests/test_import.py")
    } == {"seeded"}


@pytest.mark.parametrize(("stack", "roots"), [("python", ["src/demo_app"]), ("agnostic", [])])
def test_project_settings_seed_has_the_spec_defaults(stack, roots):
    settings = tomllib.loads(text(stack, ".rapid-ship/project.toml"))
    assert settings == {
        "stack": stack,
        "github": {"repository": "octo/demo-app", "worker_app_id": 0, "reviewer_app_id": 0},
        "kit": {"optional": [], "exclude": []},
        "linear": {"team_id": "", "project_id": ""},
        "dispatch": {
            "max_workers": 5,
            "attempt_limit": 3,
            "worktree_root": "../demo-app.worktrees",
        },
        "map": {"source_roots": roots, "unguided": []},
        "tests": {"unit": ["tests/unit/**"]},
        "release": {"method": "none"},
    }
    assert "github" in tomllib.loads(text(stack, ".rapid-ship/project.toml", repository=""))
    assert (
        "repository"
        not in tomllib.loads(text(stack, ".rapid-ship/project.toml", repository=""))["github"]
    )


def test_gate_seed_has_the_spec_defaults():
    gate = tomllib.loads(text("agnostic", ".rapid-ship/gate.toml"))
    assert gate["mode"] == "walk" and gate["flight_lease_until"] == ""
    assert gate["owner_approves_behavioural_test_removal"] is True
    limits = {"max_revisions_per_pr": 1.0, "max_rollbacks": 1, "max_open_alarms": 0}
    assert gate["thresholds"] == {
        "promotion": {"window": 30, **limits},
        "demotion": {"window": 20, **limits},
    }


def test_exceptions_seed_lists_none():
    assert tomllib.loads(text("agnostic", ".rapid-ship/exceptions.toml")) == {}


def active(lines):
    return [line for line in lines if line.strip() and not line.startswith("#")]


# Plan 4's doctor requires these in Flight: PROTECTED_PATHS, plus PYTHON_PROTECTED_PATHS for Python.
PROTECTED = (
    "/.github/",
    "/.githooks/",
    "/devctl",
    "/tools/devctl/",
    "/.agents/skills/",
    "/.claude/skills/",
    "/.rapid-ship/",
)


@pytest.mark.parametrize(("stack", "extra"), [("python", ("/pyproject.toml",)), ("agnostic", ())])
def test_codeowners_has_the_walk_line_and_the_stack_protected_set(stack, extra):
    lines = text(stack, ".github/CODEOWNERS").splitlines()
    assert active(lines) == ["* @octo"]
    protected = [line for line in lines if re.fullmatch(r"# /\S+ @octo", line)]
    assert protected == [f"# {path} @octo" for path in (*PROTECTED, *extra)]


def test_the_python_codeowners_only_adds_pyproject():
    python = text("python", ".github/CODEOWNERS").splitlines()
    agnostic = text("agnostic", ".github/CODEOWNERS").splitlines()
    assert [line for line in python if line != "# /pyproject.toml @octo"] == agnostic


def test_codeowners_without_an_owner_leaves_the_owner_to_rs_setup():
    lines = text("agnostic", ".github/CODEOWNERS", owner="").splitlines()
    assert active(lines) == []
    assert "# * @<owner>" in lines and "# /devctl @<owner>" in lines


def test_python_seed_has_the_spec_guardrails():
    data = tomllib.loads(text("python", "pyproject.toml"))
    lint = data["tool"]["ruff"]["lint"]
    assert set(lint["select"]) == {
        "E",
        "W",
        "F",
        "I",
        "B",
        "UP",
        "SIM",
        "C4",
        "RUF",
        "PGH",
        "ERA",
        "T20",
        "S",
        "TID",
        "PT",
        "PTH",
        "DTZ",
        "C90",
        "TD",
        "BLE",
        "ANN401",
    }
    assert lint["mccabe"]["max-complexity"] == 10
    assert lint["flake8-tidy-imports"] == {"ban-relative-imports": "all", "banned-api": {}}
    assert data["tool"]["ruff"]["extend-exclude"] == ["tools/devctl"]
    mypy = data["tool"]["mypy"]
    assert mypy["strict"] is True and mypy["warn_unreachable"] is True
    assert set(mypy["enable_error_code"]) == {
        "ignore-without-code",
        "redundant-expr",
        "truthy-bool",
    }
    assert mypy["files"] == ["src", "tests"]
    pytest_options = data["tool"]["pytest"]["ini_options"]
    assert pytest_options["addopts"] == ["--strict-markers", "--strict-config"]
    assert pytest_options["xfail_strict"] is True and pytest_options["filterwarnings"] == ["error"]
    assert [c["type"] for c in data["tool"]["importlinter"]["contracts"]] == ["layers", "forbidden"]
    names = {re.split(r"[<>=]", requirement)[0] for requirement in data["dependency-groups"]["dev"]}
    assert names == {"import-linter", "mypy", "pytest", "ruff"}
    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/demo_app"]


def test_python_seeds_are_valid_python():
    for path in ("src/demo_app/__init__.py", "tests/test_import.py"):
        compile(text("python", path), path, "exec")
    assert 'importlib.import_module("demo_app")' in text("python", "tests/test_import.py")


def test_root_guide_skeleton_follows_the_spec():
    guide = text("agnostic", "AGENTS.md")
    headings = re.findall(r"^#+ .*$", guide, flags=re.MULTILINE)
    assert headings == [
        "# demo-app",
        "## Commands",
        "## Find the change",
        "## Rules",
        "## Shared language and decisions",
    ]
    rules = guide.split("## Rules")[1].split("##")[0]
    bullets = [line for line in rules.splitlines() if line.startswith("- ")]
    assert bullets and all(re.search(r"(enforced by: \S+|advisory)$", line) for line in bullets)
    # Spec section 3, "Who owns what": the guide says how a Kit file becomes the project's own,
    # how to keep updates instead, and how to give a file back.
    owned = next(line for line in bullets if "Kit-managed file" in line)
    for words in (
        "makes it this project's own and stops its Kit updates",
        "`tools/devctl/devctl_project/`",
        "`[kit] exclude`",
        "To give one back to the Kit, run `rapid-ship sync --revert <path>`.",
    ):
        assert words in owned
    assert re.findall(r"\]\(([^)]+)\)", guide) == [
        "docs/features/README.md",
        "docs/patterns/README.md",
    ]
    for pointer in (
        "`GLOSSARY.md`",
        "`docs/adr/`",
        "`rs-writing`",
        "`rs-ponytail`",
        "`./devctl check`",
        "`./devctl doctor`",
    ):
        assert pointer in guide


def test_claude_md_imports_the_guide():
    assert text("agnostic", "CLAUDE.md") == "@AGENTS.md\n"


def test_feature_and_pattern_formats_name_every_key():
    features = text("agnostic", "docs/features/README.md")
    for key in ("purpose", "entry_points", "data", "observe", "reproduce"):
        assert f"`{key}`" in features
    # Plan 3's map check requires at least one entry point.
    assert "| Paths where the feature is entered | A non-empty list; each path exists |" in features
    patterns = text("agnostic", "docs/patterns/README.md")
    for key in (
        "`reference`",
        "`enforced_by`",
        "`check:",
        "`test:",
        "`ruff:",
        "`banned:",
        "`contract:",
        "`type:",
    ):
        assert key in patterns


def test_the_devctl_shim_is_managed_executable_and_valid_sh(tmp_path):
    shim = rendered("agnostic")["devctl"]
    assert shim.kind == "managed" and "devctl" in load_manifest().executable
    assert (
        b'exec uv run --project "$root/tools/devctl" --frozen --quiet devctl "$@"' in shim.content
    )
    (tmp_path / "devctl").write_bytes(shim.content)
    subprocess.run(["sh", "-n", str(tmp_path / "devctl")], check=True)


def test_devctl_is_its_own_uv_workspace_and_its_versions_agree():
    files = rendered("agnostic")
    project = tomllib.loads(files["tools/devctl/pyproject.toml"].content.decode())
    assert project["tool"]["uv"]["workspace"] == {"members": []}
    assert project["project"]["scripts"] == {"devctl": "devctl.cli:main"}
    assert project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "devctl",
        "devctl_project",
    ]
    version = project["project"]["version"]
    lock = tomllib.loads(files["tools/devctl/uv.lock"].content.decode())
    locked = {p["name"]: p.get("version") for p in lock["package"]}
    assert locked["devctl"] == version
    # Plans 3 and 4 add dependencies. uv.lock records each under its normalized name.
    declared = {
        re.sub(r"[-_.]+", "-", re.split(r"[\[<>=!~;\s]", requirement, maxsplit=1)[0]).lower()
        for requirement in project["project"]["dependencies"]
    }
    assert declared <= locked.keys()
    assert f'__version__ = "{version}"' in files["tools/devctl/devctl/__init__.py"].content.decode()


def test_devctl_project_is_seeded_and_the_environment_is_ignored():
    files = rendered("agnostic")
    assert files["tools/devctl/devctl_project/__init__.py"].kind == "seeded"
    assert files["tools/devctl/.gitignore"].content == b"/.venv/\n__pycache__/\n"
