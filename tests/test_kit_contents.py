"""The packaged Kit's templates match spec 1, section 4 (offline)."""

import re
import tomllib
from pathlib import Path

import pytest

from devctl.check.diff import codeowners_match
from devctl.process import run_process
from rapid_ship.kit.templates import (
    STACKS,
    Stack,
    Template,
    load_manifest,
    packaged_templates,
    render_files,
)

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
    "docs/AGENTS.md",
    "docs/features/README.md",
    "docs/patterns/README.md",
    "tools/AGENTS.md",
}


def rendered(stack: Stack = "python", **variables: str) -> dict[str, Template]:
    return {t.path: t for t in render_files(stack, {**VARIABLES, **variables}, ())}


def text(stack: Stack, path: str, **variables: str) -> str:
    return content(rendered(stack, **variables)[path]).decode()


def content(template: Template) -> bytes:
    assert template.content is not None, f"{template.path} is a symlink"
    return template.content


def test_every_manifest_path_exists_in_a_layer() -> None:
    manifest = load_manifest()
    root = packaged_templates()
    for path in manifest.seeded | manifest.new_project | manifest.executable:
        assert any((root / layer / path).is_file() for layer in ("common", *STACKS)), path


@pytest.mark.parametrize("stack", STACKS)
def test_the_spec_seeded_files_are_seeded(stack: Stack) -> None:
    kinds = {path: t.kind for path, t in rendered(stack).items()}
    assert {path for path in SEEDED if kinds.get(path) == "seeded"} == SEEDED


def test_python_new_project_seeds() -> None:
    kinds = {path: t.kind for path, t in rendered().items()}
    paths = (
        ".gitignore",
        "pyproject.toml",
        "src/AGENTS.md",
        "src/demo_app/__init__.py",
        "tests/AGENTS.md",
        "tests/test_import.py",
    )
    assert {kinds[p] for p in paths} == {"seeded"}
    assert text("python", ".gitignore") == "__pycache__/\n*.py[cod]\n.venv/\ndist/\n"


@pytest.mark.parametrize(("stack", "roots"), [("python", ["src/demo_app"]), ("agnostic", [])])
def test_project_settings_seed_has_the_spec_defaults(stack: Stack, roots: list[str]) -> None:
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
        "map": {"source_roots": roots, "unguided": [], "exclude": []},
        "tests": {"unit": ["tests/unit/**"]},
        "release": {"method": "none"},
    }
    assert "github" in tomllib.loads(text(stack, ".rapid-ship/project.toml", repository=""))
    assert (
        "repository"
        not in tomllib.loads(text(stack, ".rapid-ship/project.toml", repository=""))["github"]
    )


def test_gate_seed_has_the_spec_defaults() -> None:
    gate = tomllib.loads(text("agnostic", ".rapid-ship/gate.toml"))
    assert gate["mode"] == "walk"
    assert gate["flight_lease_until"] == ""
    assert gate["owner_approves_behavioural_test_removal"] is True
    limits = {"max_revisions_per_pr": 1.0, "max_rollbacks": 1, "max_open_alarms": 0}
    assert gate["thresholds"] == {
        "promotion": {"window": 30, **limits},
        "demotion": {"window": 20, **limits},
    }


def test_exceptions_seed_lists_none() -> None:
    assert tomllib.loads(text("agnostic", ".rapid-ship/exceptions.toml")) == {}


def active(lines: list[str]) -> list[str]:
    return [line for line in lines if line.strip() and not line.startswith("#")]


# Plan 4's doctor requires these in Flight: PROTECTED_PATHS, plus PYTHON_PROTECTED_PATHS for Python.
PROTECTED = (
    "/.github/",
    "/.githooks/",
    "/devctl",
    "/tools/devctl/",
    "/.agents/skills/",
    # Agent instructions: everything under .claude/, and every AGENTS.md and CLAUDE.md.
    "/.claude/",
    "/**/AGENTS.md",
    "/**/CLAUDE.md",
    "/.rapid-ship/",
    # A settings file can switch its check off, so the secrets and workflows tools' are listed.
    "/.gitleaks.toml",
    "/.gitleaksignore",
    "/zizmor.yml",
    "/zizmor.yaml",
)
# Every file the Python tools read their settings from. Ruff uses the nearest ruff.toml or
# .ruff.toml, so those match at any depth; mypy, pytest and import-linter read the root only.
PYTHON_PROTECTED = (
    "/pyproject.toml",
    "/**/ruff.toml",
    "/**/.ruff.toml",
    "/mypy.ini",
    "/.mypy.ini",
    "/pytest.ini",
    "/.pytest.ini",
    "/pytest.toml",
    "/.pytest.toml",
    "/setup.cfg",
    "/tox.ini",
    "/.importlinter",
)


@pytest.mark.parametrize(("stack", "extra"), [("python", PYTHON_PROTECTED), ("agnostic", ())])
def test_codeowners_has_the_walk_line_and_the_stack_protected_set(
    stack: Stack, extra: tuple[str, ...]
) -> None:
    lines = text(stack, ".github/CODEOWNERS").splitlines()
    assert active(lines) == ["* @octo"]
    protected = [line for line in lines if re.fullmatch(r"# /\S+ @octo", line)]
    assert protected == [f"# {path} @octo" for path in (*PROTECTED, *extra)]


@pytest.mark.parametrize("stack", STACKS)
def test_the_flight_set_protects_every_agent_instruction(stack: Stack) -> None:
    lines = text(stack, ".github/CODEOWNERS").splitlines()
    patterns = [line.split()[1] for line in lines if re.fullmatch(r"# /\S+ @octo", line)]
    instructions = (
        "AGENTS.md",
        "src/demo_app/AGENTS.md",
        "CLAUDE.md",
        "docs/CLAUDE.md",
        ".claude/settings.json",
        ".claude/skills/rs-tdd",
    )
    for path in instructions:
        assert any(codeowners_match(pattern, path) for pattern in patterns), path
    assert not any(codeowners_match(pattern, "src/demo_app/app.py") for pattern in patterns)


def test_the_python_codeowners_only_adds_the_python_settings() -> None:
    python = text("python", ".github/CODEOWNERS").splitlines()
    agnostic = text("agnostic", ".github/CODEOWNERS").splitlines()
    added = [f"# {path} @octo" for path in PYTHON_PROTECTED]
    assert python == [*agnostic, *added]


def test_codeowners_without_an_owner_leaves_the_owner_to_rs_setup() -> None:
    lines = text("agnostic", ".github/CODEOWNERS", owner="").splitlines()
    assert active(lines) == []
    assert "# * @<owner>" in lines
    assert "# /devctl @<owner>" in lines


def test_python_seed_has_the_spec_guardrails() -> None:
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
    assert mypy["strict"] is True
    assert mypy["warn_unreachable"] is True
    assert set(mypy["enable_error_code"]) == {
        "ignore-without-code",
        "redundant-expr",
        "truthy-bool",
    }
    assert mypy["files"] == ["src", "tests"]
    pytest_options = data["tool"]["pytest"]["ini_options"]
    assert pytest_options["addopts"] == ["--strict-markers", "--strict-config"]
    assert pytest_options["xfail_strict"] is True
    assert pytest_options["filterwarnings"] == ["error"]
    assert [c["type"] for c in data["tool"]["importlinter"]["contracts"]] == ["layers", "forbidden"]
    names = {re.split(r"[<>=]", requirement)[0] for requirement in data["dependency-groups"]["dev"]}
    assert names == {"import-linter", "mypy", "pytest", "ruff"}
    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/demo_app"]


def test_python_seeds_are_valid_python() -> None:
    for path in ("src/demo_app/__init__.py", "tests/test_import.py"):
        compile(text("python", path), path, "exec")
    assert 'importlib.import_module("demo_app")' in text("python", "tests/test_import.py")


ROOT_GUIDE_LINKS = [
    "docs/features/README.md",
    "docs/patterns/README.md",
    "docs/AGENTS.md",
    "tools/AGENTS.md",
]
POINTERS = (
    "`GLOSSARY.md`",
    "`docs/adr/`",
    "`rs-writing`",
    "`rs-ponytail`",
    "`./devctl check`",
    "`./devctl doctor`",
)


@pytest.mark.parametrize(
    ("stack", "links"),
    [
        ("agnostic", ROOT_GUIDE_LINKS),
        ("python", [*ROOT_GUIDE_LINKS, "src/AGENTS.md", "tests/AGENTS.md"]),
    ],
)
def test_root_guide_skeleton_follows_the_spec(stack: Stack, links: list[str]) -> None:
    guide = text(stack, "AGENTS.md")
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
    assert bullets
    assert all(re.search(r"(enforced by: \S+|advisory)$", line) for line in bullets)
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
    assert re.findall(r"\]\(([^)]+)\)", guide) == links
    assert all(pointer in guide for pointer in POINTERS)


def test_the_python_root_guide_only_adds_the_source_and_test_rows() -> None:
    python = text("python", "AGENTS.md").splitlines()
    rows = [line for line in python if "](src/AGENTS.md)" in line or "](tests/AGENTS.md)" in line]

    assert len(rows) == 2
    assert [line for line in python if line not in rows] == text(
        "agnostic", "AGENTS.md"
    ).splitlines()


def test_claude_md_imports_the_guide() -> None:
    assert text("agnostic", "CLAUDE.md") == "@AGENTS.md\n"


def test_feature_and_pattern_formats_name_every_key() -> None:
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


def test_the_devctl_shim_is_managed_executable_and_valid_sh(tmp_path: Path) -> None:
    shim = rendered("agnostic")["devctl"]
    assert shim.kind == "managed"
    assert "devctl" in load_manifest().executable
    assert b'exec uv run --project "$root/tools/devctl" --frozen --quiet devctl "$@"' in content(
        shim
    )
    (tmp_path / "devctl").write_bytes(content(shim))
    result = run_process(["sh", "-n", str(tmp_path / "devctl")], tmp_path, 30)
    assert result.returncode == 0, result.stderr


def test_devctl_is_its_own_uv_workspace_and_its_versions_agree() -> None:
    files = rendered("agnostic")
    project = tomllib.loads(content(files["tools/devctl/pyproject.toml"]).decode())
    assert project["tool"]["uv"]["workspace"] == {"members": []}
    assert project["project"]["scripts"] == {"devctl": "devctl.cli:main"}
    assert project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "devctl",
        "devctl_project",
    ]
    version = project["project"]["version"]
    lock = tomllib.loads(content(files["tools/devctl/uv.lock"]).decode())
    locked = {p["name"]: p.get("version") for p in lock["package"]}
    assert locked["devctl"] == version
    # Plans 3 and 4 add dependencies. uv.lock records each under its normalized name.
    declared = {
        re.sub(r"[-_.]+", "-", re.split(r"[\[<>=!~;\s]", requirement, maxsplit=1)[0]).lower()
        for requirement in project["project"]["dependencies"]
    }
    assert declared <= locked.keys()
    assert (
        f'__version__ = "{version}"' in content(files["tools/devctl/devctl/__init__.py"]).decode()
    )


def test_devctl_project_is_seeded_and_the_environment_is_ignored() -> None:
    files = rendered("agnostic")
    assert files["tools/devctl/devctl_project/__init__.py"].kind == "seeded"
    assert files["tools/devctl/.gitignore"].content == b"/.venv/\n__pycache__/\n"
