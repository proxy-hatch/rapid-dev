"""rapid-ship status: classify the vendored Kit against its lock and the templates (offline)."""

from collections.abc import Callable
from pathlib import Path

from rapid_ship.kit.init import init_repository
from rapid_ship.kit.status import StatusReport, classify
from rapid_ship.kit.sync import sync_repository


def states(report: StatusReport) -> dict[str, str]:
    return {item.path: item.state for item in report.files}


def vendor(root: Path, templates: Path, variables: dict[str, str]) -> None:
    init_repository(root, stack="python", variables=variables, templates_root=templates)


def test_a_fresh_init_is_strictly_current(
    git_repo: Path, make_templates: Callable[..., Path], kit_variables: dict[str, str]
) -> None:
    templates = make_templates()
    vendor(git_repo, templates, kit_variables)

    report = classify(git_repo, templates_root=templates)

    assert set(states(report).values()) == {"unchanged"}
    assert (report.outdated, report.not_installed) == ((), ())
    assert report.strict_ok


def test_modified_and_missing_managed_files(
    git_repo: Path, make_templates: Callable[..., Path], kit_variables: dict[str, str]
) -> None:
    templates = make_templates()
    vendor(git_repo, templates, kit_variables)
    (git_repo / "devctl").write_text("changed\n")
    (git_repo / "tools/devctl/devctl/cli.py").unlink()
    (git_repo / ".claude/skills/rs-demo").unlink()
    (git_repo / ".claude/skills/rs-demo").write_text("a copy\n")

    report = classify(git_repo, templates_root=templates)

    assert states(report)["devctl"] == "modified"
    assert states(report)["tools/devctl/devctl/cli.py"] == "missing"
    assert states(report)[".claude/skills/rs-demo"] == "modified"
    assert not report.strict_ok


def test_strict_fails_when_the_lock_matches_disk_but_not_the_installed_template(
    git_repo: Path, make_templates: Callable[..., Path], kit_variables: dict[str, str]
) -> None:
    vendor(git_repo, make_templates("old"), kit_variables)
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    report = classify(git_repo, templates_root=new)

    assert states(report)["devctl"] == "unchanged"
    assert report.outdated == ("devctl",)
    assert not report.strict_ok


def test_strict_fails_when_a_managed_template_is_not_installed(
    git_repo: Path, make_templates: Callable[..., Path], kit_variables: dict[str, str]
) -> None:
    vendor(git_repo, make_templates("old"), kit_variables)
    new = make_templates("new", {"common/.agents/skills/rs-new/SKILL.md": "new\n"})

    report = classify(git_repo, templates_root=new)

    assert report.not_installed == (".agents/skills/rs-new/SKILL.md", ".claude/skills/rs-new")
    assert not report.strict_ok


def test_a_dropped_template_makes_its_entry_outdated(
    git_repo: Path, make_templates: Callable[..., Path], kit_variables: dict[str, str]
) -> None:
    vendor(git_repo, make_templates("old"), kit_variables)
    new = make_templates("new", {"common/tools/devctl/devctl/cli.py": None})

    assert classify(git_repo, templates_root=new).outdated == ("tools/devctl/devctl/cli.py",)


def test_seeded_files_report_only_template_updates(
    git_repo: Path, make_templates: Callable[..., Path], kit_variables: dict[str, str]
) -> None:
    templates = make_templates("old")
    vendor(git_repo, templates, kit_variables)
    (git_repo / "AGENTS.md").write_text("# Ours\n")
    assert "AGENTS.md" not in states(classify(git_repo, templates_root=templates))

    new = make_templates("new", {"common/AGENTS.md": "# {{project_name}}\n\nNew section.\n"})
    report = classify(git_repo, templates_root=new)

    assert states(report)["AGENTS.md"] == "template updated"
    assert report.strict_ok  # --strict covers managed files only


def test_a_managed_file_the_project_made_its_own_reports_only_template_updates(
    git_repo: Path, make_templates: Callable[..., Path], kit_variables: dict[str, str]
) -> None:
    templates = make_templates("old")
    vendor(git_repo, templates, kit_variables)
    (git_repo / "devctl").write_text("ours\n")
    assert states(classify(git_repo, templates_root=templates))["devctl"] == "modified"
    sync_repository(git_repo, in_place=True, templates_root=templates, kit_version="9.9.9")
    assert "devctl" not in states(classify(git_repo, templates_root=templates))

    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})
    report = classify(git_repo, templates_root=new)

    assert states(report)["devctl"] == "template updated"
    assert "devctl" not in report.outdated


def test_status_ignores_project_files_and_changes_nothing(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    commit_all: Callable[..., None],
    run_git: Callable[..., str],
) -> None:
    templates = make_templates()
    vendor(git_repo, templates, kit_variables)
    commit_all(git_repo)
    (git_repo / "notes.md").write_text("mine\n")
    before = run_git(git_repo, "status", "--porcelain")

    report = classify(git_repo, templates_root=templates)

    assert "notes.md" not in states(report)
    assert run_git(git_repo, "status", "--porcelain") == before


def test_excluded_paths_are_reported_and_ignored_by_strict(
    git_repo: Path,
    make_templates: Callable[..., Path],
    kit_variables: dict[str, str],
    write_kit_settings: Callable[..., None],
) -> None:
    vendor(git_repo, make_templates("old"), kit_variables)
    write_kit_settings(git_repo, exclude=["devctl", "tools/devctl", ".agents/skills/rs-demo"])
    (git_repo / "devctl").write_text("ours\n")
    (git_repo / "tools/devctl/devctl/cli.py").unlink()
    (git_repo / ".claude/skills/rs-demo").unlink()
    new = make_templates(
        "new",
        {"common/devctl": "#!/bin/sh\necho newer\n", "common/tools/devctl/devctl/new.py": "x\n"},
    )

    report = classify(git_repo, templates_root=new)

    assert states(report) == {
        "devctl": "excluded",
        "tools/devctl/devctl/cli.py": "excluded",
        ".agents/skills/rs-demo/SKILL.md": "excluded",
        ".claude/skills/rs-demo": "excluded",
    }
    assert (report.outdated, report.not_installed) == ((), ())
    assert report.strict_ok
