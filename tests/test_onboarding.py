"""Conversational setup saves real choices and keeps local checkout links private."""

import json
import subprocess

import pytest

from agentic_engineering.cli import main
from agentic_engineering.models import ProjectConfig
from agentic_engineering.project.configuration import (
    answer_question,
    init_project,
    load_config,
)


def initialized(root):
    (root / "design.md").write_text("Approved design")
    init_project(root, "hello", "design.md")


def test_new_interview_selects_providers_before_models(tmp_path):
    initialized(tmp_path)
    question = answer_question(tmp_path, "repository", "example/hello")
    assert question["id"] == "providers"
    question = answer_question(tmp_path, "providers", ["codex", "claude"])
    assert question["id"] == "models"
    assert question["blocked"]
    assert load_config(tmp_path).providers == ["codex", "claude"]


def catalog(root, provider, ids, authenticated=True):
    from datetime import UTC, datetime

    path = root / ".devctl/providers.json"
    records = json.loads(path.read_text()) if path.exists() else {}
    records[provider] = {
        "provider": provider,
        "installed": True,
        "authenticated": authenticated,
        "models": [{"id": model, "label": model} for model in ids],
        "checked_at": datetime.now(UTC).isoformat(),
        "ready": authenticated,
    }
    path.write_text(json.dumps(records))


def test_model_choices_require_authenticated_selected_provider_and_exact_catalog_id(tmp_path):
    initialized(tmp_path)
    answer_question(tmp_path, "providers", ["codex", "claude"])
    choices = {
        "small": {"provider": "codex", "model": "worker"},
        "large": {"provider": "claude", "model": "reviewer"},
    }
    catalog(tmp_path, "codex", ["worker"])
    catalog(tmp_path, "claude", ["reviewer"], authenticated=False)
    before = (tmp_path / ".devctl/project.json").read_bytes()
    with pytest.raises(ValueError, match="authenticat"):
        answer_question(tmp_path, "models", choices)
    assert (tmp_path / ".devctl/project.json").read_bytes() == before
    catalog(tmp_path, "claude", ["reviewer"])
    answer_question(tmp_path, "models", choices)
    config = load_config(tmp_path)
    assert config.worker_runner == "codex" and config.worker_model == "worker"
    assert config.reviewer_runner == "claude" and config.reviewer_model == "reviewer"
    assert config.models["large"].model == "reviewer"
    choices["large"]["model"] = "invented-model"
    with pytest.raises(ValueError, match="catalog"):
        answer_question(tmp_path, "models", choices)
    assert load_config(tmp_path).reviewer_model == "reviewer"


def test_required_model_tiers_and_guidance_are_language_neutral():
    config = ProjectConfig(name="hello", design_path="design.md")
    assert "simple" in config.guidance.code.lower()
    assert "concise" in config.guidance.style.lower()
    with pytest.raises(ValueError, match=r"small.*large|large.*small"):
        ProjectConfig(
            name="hello",
            design_path="design.md",
            providers=["codex"],
            models={"small": {"provider": "codex", "model": "one"}},
        )


def test_checkout_link_is_local_ignored_and_preserved(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    framework = tmp_path / "framework"
    framework.mkdir()
    (framework / "pyproject.toml").write_text('[project]\nname="rapid-ship"\n')
    controller = framework / ".controller/bin/devctl"
    controller.parent.mkdir(parents=True)
    controller.write_text('#!/bin/sh\necho "devctl 0.1.0"\n')
    controller.chmod(0o755)
    (project / "design.md").write_text("Approved design")
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    init_project(project, "hello", "design.md", framework_root=framework)
    local = project / ".devctl/local.json"
    data = json.loads(local.read_text())
    assert data == {"framework_root": str(framework), "controller": str(controller)}
    assert (
        subprocess.run(
            ["git", "check-ignore", ".devctl/local.json"], cwd=project, capture_output=True
        ).returncode
        == 0
    )
    before = local.read_bytes()
    init_project(project, "hello", "design.md")
    assert local.read_bytes() == before


def test_cli_logs_read_existing_events_without_creating_missing_state(tmp_path, capsys):
    assert main(["--project", str(tmp_path), "logs"]) == 0
    assert json.loads(capsys.readouterr().out)["events"] == []
    assert list(tmp_path.iterdir()) == []


def test_cli_mutation_log_omits_raw_answers(tmp_path, capsys):
    (tmp_path / "design.md").write_text("Approved design")
    assert (
        main(["--project", str(tmp_path), "init", "--name", "hello", "--design", "design.md"]) == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "--project",
                str(tmp_path),
                "interview",
                "--answer",
                "guidance",
                "--value",
                json.dumps({"style": "private example SECRET_STYLE", "code": "Keep code simple."}),
            ]
        )
        == 0
    )
    capsys.readouterr()
    log = (tmp_path / ".devctl/state/commands.jsonl").read_text()
    assert "SECRET_STYLE" not in log
    assert "interview" in log and "exit_code" in log
    before = log
    main(["--project", str(tmp_path), "doctor"])
    capsys.readouterr()
    assert (tmp_path / ".devctl/state/commands.jsonl").read_text() == before


def test_installed_framework_uses_venv_prefix_not_resolved_python(tmp_path, monkeypatch):
    from agentic_engineering.project.configuration import _installed_framework

    install = tmp_path / ".controller"
    install.mkdir()
    (install / "source.json").write_text(json.dumps({"framework_root": str(tmp_path)}))
    monkeypatch.setattr("sys.prefix", str(install))
    assert _installed_framework() == tmp_path


@pytest.mark.parametrize(
    "bad_report",
    [
        [],
        None,
        {"authenticated": True, "checked_at": 42},
        {"authenticated": True, "checked_at": "yesterday"},
    ],
)
def test_malformed_provider_cache_is_an_actionable_blocker(tmp_path, capsys, bad_report):
    initialized(tmp_path)
    answer_question(tmp_path, "repository", "example/hello")
    answer_question(tmp_path, "providers", ["codex", "claude"])
    (tmp_path / ".devctl/providers.json").write_text(json.dumps({"codex": bad_report}))
    assert main(["--project", str(tmp_path), "interview"]) == 0
    assert "blocked" in json.loads(capsys.readouterr().out)


def test_model_choices_reject_stale_cache_and_invalid_catalog(tmp_path):
    from datetime import UTC, datetime, timedelta

    initialized(tmp_path)
    answer_question(tmp_path, "providers", ["codex"])
    choices = {
        tier: {"provider": "codex", "model": model}
        for tier, model in (("small", "worker"), ("large", "reviewer"))
    }
    catalog(tmp_path, "codex", ["worker", "reviewer"])
    path = tmp_path / ".devctl/providers.json"
    records = json.loads(path.read_text())
    records["codex"]["checked_at"] = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    path.write_text(json.dumps(records))
    with pytest.raises(ValueError, match="Refresh"):
        answer_question(tmp_path, "models", choices)
    records["codex"]["checked_at"] = datetime.now(UTC).isoformat()
    records["codex"]["models"] = None
    path.write_text(json.dumps(records))
    with pytest.raises(ValueError, match="catalog"):
        answer_question(tmp_path, "models", choices)


def test_provider_cli_caches_discovery_and_verifies_only_an_explicit_model(
    tmp_path, capsys, monkeypatch
):
    from datetime import UTC, datetime

    from agentic_engineering.project.configuration import provider_records

    initialized(tmp_path)
    calls = []
    report = {
        "provider": "agy",
        "installed": True,
        "authenticated": None,
        "ready": False,
        "checked_at": datetime.now(UTC).isoformat(),
        "models": [{"id": "exact-id"}],
    }
    monkeypatch.setattr(
        "agentic_engineering.project.providers.inspect_provider", lambda name: report
    )

    def verify(name, model):
        calls.append((name, model))
        return {
            **report,
            "authenticated": True,
            "ready": True,
            "verified": True,
            "selected_model": model,
            "verification_method": "inference",
            "verified_at": datetime.now(UTC).isoformat(),
            "request_sent": True,
        }

    monkeypatch.setattr("agentic_engineering.project.providers.verify_provider", verify)
    args = ["--project", str(tmp_path), "providers", "--provider", "agy"]
    assert main(args) == 2
    assert calls == []
    assert provider_records(tmp_path)["agy"]["authenticated"] is None
    capsys.readouterr()
    assert main([*args, "--verify"]) == 3
    assert calls == []
    capsys.readouterr()
    assert main([*args, "--verify", "--model", "exact-id"]) == 0
    assert calls == [("agy", "exact-id")]
    capsys.readouterr()
    assert provider_records(tmp_path)["agy"]["authenticated"] is True


def test_reselecting_compatible_providers_preserves_model_tiers(tmp_path):
    initialized(tmp_path)
    answer_question(tmp_path, "providers", ["codex"])
    choices = {
        tier: {"provider": "codex", "model": model}
        for tier, model in (("small", "worker"), ("large", "reviewer"))
    }
    catalog(tmp_path, "codex", ["worker", "reviewer"])
    answer_question(tmp_path, "models", choices)
    before = load_config(tmp_path).models
    for providers in (["codex"], ["codex", "claude"]):
        answer_question(tmp_path, "providers", providers)
        assert load_config(tmp_path).models == before
        answers = json.loads((tmp_path / ".devctl/interview.json").read_text())["answers"]
        assert answers["models"]["value"] == choices


def test_agy_verification_is_exact_and_survives_catalog_refresh_without_renewal(tmp_path):
    from datetime import UTC, datetime, timedelta

    from agentic_engineering.project.configuration import provider_records, save_provider_records

    initialized(tmp_path)
    answer_question(tmp_path, "providers", ["agy", "claude"])
    catalog(tmp_path, "claude", ["reviewer"])
    checked = datetime.now(UTC).isoformat()
    discovery = {
        "provider": "agy",
        "authenticated": None,
        "checked_at": checked,
        "models": [{"id": "worker"}, {"id": "other-worker"}],
    }
    verified = {
        **discovery,
        "authenticated": True,
        "verified": True,
        "verification_method": "inference",
        "selected_model": "worker",
        "verified_at": checked,
        "request_sent": True,
    }
    save_provider_records(tmp_path, [verified])
    choices = {
        "small": {"provider": "agy", "model": "other-worker"},
        "large": {"provider": "claude", "model": "reviewer"},
    }
    with pytest.raises(ValueError, match="other-worker"):
        answer_question(tmp_path, "models", choices)
    choices["small"]["model"] = "worker"
    answer_question(tmp_path, "models", choices)
    save_provider_records(tmp_path, [discovery])
    answer_question(tmp_path, "models", choices)
    records = provider_records(tmp_path)
    assert records["agy"]["model_verifications"]["worker"] == checked
    stale = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    records["agy"]["model_verifications"]["worker"] = stale
    (tmp_path / ".devctl/providers.json").write_text(json.dumps(records))
    save_provider_records(tmp_path, [discovery])
    with pytest.raises(ValueError, match=r"authenticat|worker"):
        answer_question(tmp_path, "models", choices)


def verify_agy(root, selected, models):
    from datetime import UTC, datetime

    from agentic_engineering.project.configuration import save_provider_records

    checked = datetime.now(UTC).isoformat()
    save_provider_records(
        root,
        [
            {
                "provider": "agy",
                "authenticated": True,
                "checked_at": checked,
                "models": [{"id": model} for model in models],
                "verified": True,
                "verification_method": "inference",
                "selected_model": selected,
                "verified_at": checked,
                "request_sent": True,
            }
        ],
    )


def test_verified_agy_model_can_be_the_large_reviewer(tmp_path):
    initialized(tmp_path)
    answer_question(tmp_path, "providers", ["claude", "agy"])
    catalog(tmp_path, "claude", ["worker"])
    verify_agy(tmp_path, "reviewer", ["reviewer"])
    choices = {
        "small": {"provider": "claude", "model": "worker"},
        "large": {"provider": "agy", "model": "reviewer"},
    }
    answer_question(tmp_path, "models", choices)
    config = load_config(tmp_path)
    assert (config.reviewer_runner, config.reviewer_model) == ("agy", "reviewer")


def test_agy_large_reviewer_needs_its_own_model_verification(tmp_path):
    from datetime import UTC, datetime

    from agentic_engineering.project.configuration import save_provider_records

    initialized(tmp_path)
    answer_question(tmp_path, "providers", ["claude", "agy"])
    catalog(tmp_path, "claude", ["worker"])
    choices = {
        "small": {"provider": "claude", "model": "worker"},
        "large": {"provider": "agy", "model": "reviewer"},
    }
    discovery = {
        "provider": "agy",
        "authenticated": None,
        "checked_at": datetime.now(UTC).isoformat(),
        "models": [{"id": "reviewer"}, {"id": "other"}],
    }
    save_provider_records(tmp_path, [discovery])
    with pytest.raises(ValueError, match="authenticat"):
        answer_question(tmp_path, "models", choices)
    verify_agy(tmp_path, "other", ["reviewer", "other"])
    with pytest.raises(ValueError, match="agy model reviewer"):
        answer_question(tmp_path, "models", choices)


def test_agy_can_fill_both_roles_with_two_verified_models(tmp_path):
    initialized(tmp_path)
    answer_question(tmp_path, "providers", ["agy"])
    verify_agy(tmp_path, "worker", ["worker", "reviewer"])
    verify_agy(tmp_path, "reviewer", ["worker", "reviewer"])
    choices = {
        "small": {"provider": "agy", "model": "worker"},
        "large": {"provider": "agy", "model": "reviewer"},
    }
    answer_question(tmp_path, "models", choices)
    config = load_config(tmp_path)
    assert (config.worker_runner, config.reviewer_runner) == ("agy", "agy")


def test_failed_agy_probe_invalidates_only_its_model_verification(tmp_path):
    from datetime import UTC, datetime

    from agentic_engineering.project.configuration import provider_records, save_provider_records

    initialized(tmp_path)
    report = {
        "provider": "agy",
        "authenticated": True,
        "checked_at": datetime.now(UTC).isoformat(),
        "models": [{"id": "a"}, {"id": "b"}],
        "verified": True,
        "verification_method": "inference",
        "verified_at": datetime.now(UTC).isoformat(),
        "request_sent": True,
    }
    for model in ("a", "b"):
        save_provider_records(tmp_path, [{**report, "selected_model": model}])
    save_provider_records(
        tmp_path,
        [
            {
                **report,
                "selected_model": "b",
                "authenticated": None,
                "verified": False,
                "verified_at": None,
            }
        ],
    )
    assert list(provider_records(tmp_path)["agy"]["model_verifications"]) == ["a"]
