"""Offline integration: simulated native CLI protocols exercise real provider setup."""

import json
import sys

import pytest
from test_providers import agy_events, executable

from agentic_engineering.cli import main
from agentic_engineering.project.configuration import (
    answer_question,
    doctor,
    init_project,
    load_config,
    provider_records,
)


def provider_command(root, capsys, *args):
    code = main(["--project", str(root), "providers", "--provider", "agy", *args])
    output = json.loads(capsys.readouterr().out)
    assert len(output["providers"]) == 1, output
    return code, output["providers"][0]


def project_files(root):
    return {
        str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }


def initialized_project(root):
    root.mkdir()
    (root / "design.md").write_text("Approved offline provider setup fixture.\n")
    init_project(root, "offline-provider-setup", "design.md")
    answer_question(root, "repository", "owner/offline-fixture")
    answer_question(root, "providers", ["agy"])


def test_offline_agy_proof_survives_discovery_and_keeps_completed_setup_ready(
    tmp_path, monkeypatch, capsys
):
    root = tmp_path / "project"
    initialized_project(root)
    cli_dir = tmp_path / "bin"
    cli_dir.mkdir()
    _, invocations = catalog_controlled_agy(cli_dir, monkeypatch)

    code, worker = provider_command(root, capsys, "--verify", "--model", "worker-exact")
    assert code == 0, worker
    assert worker["selected_model"] == "worker-exact"
    assert worker["model_verifications"] == {"worker-exact": worker["verified_at"]}
    assert provider_records(root)["agy"] == worker

    code, verified = provider_command(root, capsys, "--verify", "--model", "reviewer-exact")

    assert code == 0, verified
    assert verified["selected_model"] == "reviewer-exact"
    assert verified["authenticated"] is True
    assert verified["verified"] is True
    assert verified["request_sent"] is True
    assert verified["ready"] is True
    proofs = {"worker-exact": worker["verified_at"], "reviewer-exact": verified["verified_at"]}
    assert verified["model_verifications"] == proofs
    assert provider_records(root)["agy"] == verified

    choices = {
        "small": {"provider": "agy", "model": "worker-exact"},
        "large": {"provider": "agy", "model": "reviewer-exact"},
    }
    answers = {
        "models": choices,
        "guidance": {"style": "Use plain language.", "code": "Keep code simple."},
        "execution": "docker",
        "image": "offline-fixture:latest",
        "resources": {"memory_budget_mb": 8192, "cpu_budget": 4, "max_parallel": 1},
        "test_resources": [],
        "checks": {"unit": [sys.executable, "-c", "assert 1 + 1 == 2"]},
        "release_target": "none",
    }
    for question, answer in answers.items():
        interview = answer_question(root, question, answer)
    assert interview == {"complete": True}
    config = load_config(root)
    assert (config.worker_runner, config.worker_model) == ("agy", "worker-exact")
    assert (config.reviewer_runner, config.reviewer_model) == ("agy", "reviewer-exact")
    before_doctor = project_files(root)
    before_invocations = invocations.read_bytes()

    readiness = doctor(root)

    assert readiness["blockers"] == []
    assert readiness["configuration_ready"] is True
    assert readiness["ready"] is True
    assert readiness["autonomy_ready"] is False
    assert project_files(root) == before_doctor
    assert invocations.read_bytes() == before_invocations

    before_prompts = (cli_dir / "prompts.jsonl").read_bytes()
    code, discovered = provider_command(root, capsys)

    assert code == 2, discovered
    assert discovered["authenticated"] is None
    assert discovered["ready"] is False
    assert discovered["model_verifications"] == proofs
    assert provider_records(root)["agy"] == discovered
    assert (cli_dir / "prompts.jsonl").read_bytes() == before_prompts
    assert answer_question(root, "models", choices) == {"complete": True}
    before_doctor = project_files(root)

    readiness = doctor(root)

    assert readiness["blockers"] == []
    assert readiness["configuration_ready"] is True
    assert readiness["ready"] is True
    assert readiness["autonomy_ready"] is False
    assert project_files(root) == before_doctor


def catalog_controlled_agy(cli_dir, monkeypatch):
    """Simulate two native models while allowing their catalog to change between probes."""
    catalog = cli_dir / "catalog.txt"
    catalog.write_text("worker-exact\tWorker\nreviewer-exact\tReviewer\n")
    invocations = cli_dir / "invocations.jsonl"
    events = {model: agy_events(model) for model in ("worker-exact", "reviewer-exact")}
    executable(
        cli_dir,
        monkeypatch,
        "agy",
        f"""
import json, pathlib, sys
with open({str(invocations)!r}, 'a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1:] == ['models']:
    print(pathlib.Path({str(catalog)!r}).read_text(), end='')
    sys.exit(0)
events = {events!r}[sys.argv[sys.argv.index('--model') + 1]]
print(json.dumps(events[0]), flush=True)
for line in sys.stdin:
    with open({str(cli_dir / "prompts.jsonl")!r}, 'a') as stream:
        stream.write(line)
    for event in events[1:]:
        print(json.dumps(event), flush=True)
    break
""",
    )
    return catalog, invocations


def test_offline_failed_probe_for_removed_model_revokes_only_its_proof(
    tmp_path, monkeypatch, capsys
):
    root = tmp_path / "project"
    initialized_project(root)
    cli_dir = tmp_path / "bin"
    cli_dir.mkdir()
    catalog, invocations = catalog_controlled_agy(cli_dir, monkeypatch)

    code, worker = provider_command(root, capsys, "--verify", "--model", "worker-exact")
    assert code == 0, worker
    assert worker["selected_model"] == "worker-exact"
    code, reviewer = provider_command(root, capsys, "--verify", "--model", "reviewer-exact")
    assert code == 0, reviewer
    assert reviewer["selected_model"] == "reviewer-exact"
    proofs = {"worker-exact": worker["verified_at"], "reviewer-exact": reviewer["verified_at"]}
    assert reviewer["model_verifications"] == proofs
    assert provider_records(root)["agy"] == reviewer
    choices = {
        "small": {"provider": "agy", "model": "worker-exact"},
        "large": {"provider": "agy", "model": "reviewer-exact"},
    }
    answer_question(root, "models", choices)

    catalog.write_text("worker-exact\tWorker\n")
    code, discovered = provider_command(root, capsys)
    assert code == 2, discovered
    assert discovered["model_verifications"] == proofs
    before_invocations = invocations.read_text().splitlines()
    before_prompts = (cli_dir / "prompts.jsonl").read_bytes()

    code, failed = provider_command(root, capsys, "--verify", "--model", "reviewer-exact")

    assert code == 2, failed
    assert failed["selected_model"] == "reviewer-exact"
    assert failed["verified"] is False
    assert failed["authenticated"] is None
    assert failed["ready"] is False
    assert failed["request_sent"] is False
    assert failed["model_verifications"] == {"worker-exact": worker["verified_at"]}
    assert provider_records(root)["agy"] == failed
    assert invocations.read_text().splitlines() == [*before_invocations, json.dumps(["models"])]
    assert (cli_dir / "prompts.jsonl").read_bytes() == before_prompts

    # Returning to the catalog cannot replace the explicit verification that just failed.
    catalog.write_text("worker-exact\tWorker\nreviewer-exact\tReviewer\n")
    code, rediscovered = provider_command(root, capsys)
    assert code == 2, rediscovered
    assert rediscovered["model_verifications"] == {"worker-exact": worker["verified_at"]}
    before_rejected_choice = project_files(root)
    with pytest.raises(ValueError, match="reviewer-exact"):
        answer_question(root, "models", choices)
    assert project_files(root) == before_rejected_choice
