"""Public commands preserve project files and report blocked capabilities honestly."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import agentic_engineering.cli as cli
from agentic_engineering.cli import main
from agentic_engineering.execution.controller import Controller
from agentic_engineering.models import TaskSpec
from agentic_engineering.trust.evidence import EvidenceStore


def test_init_then_resumable_interview_and_readonly_doctor(tmp_path, capsys):
    (tmp_path / "design.md").write_text("Approved Python CLI design")
    args = ["--project", str(tmp_path)]
    assert main([*args, "init", "--name", "sample", "--design", "design.md"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["next_question"]["id"] == "repository"
    assert main([*args, "interview", "--answer", "repository", "--value", '"owner/repo"']) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "providers"
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert main([*args, "doctor", "--json"]) == 2
    assert not json.loads(capsys.readouterr().out)["ready"]
    after = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after


def test_invalid_task_graph_never_registers_tasks(tmp_path, capsys):
    (tmp_path / "tasks.json").write_text('[{"id":"incomplete"}]')
    assert (
        main(["--project", str(tmp_path), "decompose", "--tasks", str(tmp_path / "tasks.json")])
        == 3
    )
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"
    assert not (tmp_path / ".devctl/state/workflow.db").exists()


def test_harden_does_not_invent_operator_authorization(tmp_path, capsys):
    assert main(["--project", str(tmp_path), "harden"]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "blocked"
    assert "authority" in output["message"].lower()


def test_status_does_not_initialize_missing_state(tmp_path, capsys):
    assert main(["--project", str(tmp_path), "status"]) == 0
    assert json.loads(capsys.readouterr().out)["tasks"] == []
    assert list(tmp_path.iterdir()) == []


def test_resume_can_explicitly_retarget_a_blocked_dependency_base(tmp_path, capsys):
    from agentic_engineering.models import TaskSpec
    from agentic_engineering.storage import Store

    state = tmp_path / ".devctl/state"
    state.mkdir(parents=True)
    with Store(state / "workflow.db") as store:
        store.add_tasks(
            [
                TaskSpec(
                    id="next",
                    title="next",
                    description="next",
                    owned_paths=["next.py"],
                    acceptance=["works"],
                    environment="default",
                    base_sha="a" * 40,
                )
            ]
        )
        attempt = store.claim("next", "owner")
        store.transition("next", "blocked", attempt, "owner", "dependency base missing")
    assert (
        main(
            [
                "--project",
                str(tmp_path),
                "resume",
                "next",
                "--base",
                "b" * 40,
                "--expected-base",
                "a" * 40,
            ]
        )
        == 0
    )
    value = json.loads(capsys.readouterr().out)
    assert value["task"]["base_sha"] == "b" * 40
    with Store(state / "workflow.db") as store:
        assert store.get_task("next")["state"] == "pending"


def test_offline_cli_workflow_produces_sealed_simulated_evidence(tmp_path, capsys, monkeypatch):
    """Real Git/native checks with simulated models cannot grant live autonomy."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "design.md").write_text("Approved design: create an independently reviewed greeting.\n")

    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    def command(*args):
        code = main(["--project", str(root), *args])
        return code, json.loads(capsys.readouterr().out)

    git("init", "-q")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Offline fixture")
    code, initialized = command("init", "--name", "offline", "--design", "design.md")
    assert code == 0
    assert initialized["next_question"]["id"] == "repository"
    checks = {
        "unit": [
            sys.executable,
            "-c",
            "from pathlib import Path; "
            "assert Path('greeting.txt').read_text() == 'hello fixture\\n'",
        ]
    }
    # Offline fixture: these reports do not assert live provider authentication.
    from datetime import UTC, datetime

    from agentic_engineering.project.configuration import save_provider_records

    save_provider_records(
        root,
        [
            {
                "provider": provider,
                "authenticated": True,
                "checked_at": datetime.now(UTC).isoformat(),
                "models": [{"id": model, "label": model}],
            }
            for provider, model in (("codex", "simulated-worker"), ("claude", "simulated-reviewer"))
        ],
    )
    answers = {
        "repository": "owner/offline-fixture",
        "providers": ["codex", "claude"],
        "models": {
            "small": {"provider": "codex", "model": "simulated-worker"},
            "large": {"provider": "claude", "model": "simulated-reviewer"},
        },
        "guidance": {"style": "Use plain language.", "code": "Keep code simple."},
        "execution": "native",
        "allow_native": True,
        "resources": {"memory_budget_mb": 8192, "cpu_budget": 4, "max_parallel": 1},
        "test_resources": [],
        "checks": checks,
        "release_target": "none",
    }
    for key, answer in answers.items():
        code, interview = command("interview", "--answer", key, "--value", json.dumps(answer))
        assert code == 0, interview
    assert interview == {"complete": True}
    code, readiness = command("doctor", "--json")
    assert code == 0, readiness
    assert readiness["configuration_ready"]
    assert readiness["ready"]
    assert not readiness["autonomy_ready"]
    git("add", ".")
    git("commit", "-qm", "Approved fixture configuration")
    base = git("rev-parse", "HEAD")
    task = TaskSpec(
        id="greet",
        title="Greeting",
        description="Write the greeting to the assigned file",
        owned_paths=["greeting.txt"],
        acceptance=["Greeting contains hello fixture"],
        environment="default",
        base_sha=base,
        checks=["unit"],
    )
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([task.model_dump(mode="json")]))
    code, decomposed = command("decompose", "--tasks", str(tasks))
    assert code == 0
    assert decomposed == {"registered": ["greet"]}
    code, status = command("status")
    assert code == 0
    assert status["tasks"][0]["state"] == "pending"
    roles = []

    class SimulatedRunner:
        def run(self, execute, prompt, *, role, timeout_seconds, **kwargs):
            roles.append(role)
            payload = json.loads(prompt)
            if role == "worker":
                target = payload["task"]["owned_paths"][0]
                result = execute(
                    [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; "
                        f"Path({target!r}).write_text('hello fixture\\n')",
                    ],
                    timeout_seconds,
                )
                assert result.returncode == 0, result.stderr
                return SimpleNamespace(
                    text="Simulated implementation", session_id="fixture", events=()
                )
            assert role == "reviewer"
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "binding": payload["binding"],
                        "verdict": "approve",
                        "findings": [],
                        "reviewer_runner": "claude",
                        "independent": True,
                        "summary": "Explicitly simulated fixture review",
                    }
                ),
                session_id="fixture-review",
                events=(),
            )

    def simulated_controller(project, config, state):
        return Controller(
            project,
            config,
            state,
            runner_factory=lambda name, model: SimulatedRunner(),
        )

    monkeypatch.setattr(cli, "Controller", simulated_controller)
    code, result = command("run", "--tasks", str(tasks))
    assert code == 0, result
    assert result["tasks"][0]["state"] == "approved"
    assert not result["autonomy_granted"]
    assert roles == ["worker", "reviewer"]
    code, output = command("evidence")
    assert code == 0
    assert len(output["receipts"]) == 1
    receipt = output["receipts"][0]
    sealed = EvidenceStore(root / ".devctl/state/receipts").load(Path(receipt["path"]))
    assert sealed.model_dump(mode="json") == {k: v for k, v in receipt.items() if k != "path"}
    assert not sealed.live
    assert sealed.binding.task_id == "greet"
    assert sealed.binding.base_sha == base
    assert sealed.binding.head_sha != base
    assert sealed.binding.attempt_id == result["tasks"][0]["attempt_id"]
    assert sealed.review is not None
    assert sealed.review.independent and sealed.review.verdict == "approve"
    assert sealed.review.binding == sealed.binding
    assert [(check.name, check.argv, check.exit_code) for check in sealed.checks] == [
        ("unit", checks["unit"], 0)
    ]
    assert git("rev-parse", "HEAD") == base
    assert not (root / "greeting.txt").exists()


def test_status_on_corrupted_database_returns_structured_failure(tmp_path, capsys):
    state = tmp_path / ".devctl/state"
    state.mkdir(parents=True)
    database = state / "workflow.db"
    original = b"corrupted SQLite fixture, not a database"
    database.write_bytes(original)

    code = main(["--project", str(tmp_path), "status"])

    output = json.loads(capsys.readouterr().out)
    assert code == 4
    assert output["status"] == "failed"
    assert "database" in output["message"].lower()
    assert database.read_bytes() == original


def test_resume_without_resource_adapter_blocks_and_retains_expired_reservation(tmp_path, capsys):
    from agentic_engineering.execution.environments import EnvironmentManager
    from agentic_engineering.models import EnvironmentSpec
    from agentic_engineering.storage import Store

    root = tmp_path / "project"
    root.mkdir()

    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    git("init", "-q")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Offline resource fixture")
    (root / "design.md").write_text("A project with an explicitly registered test resource.\n")
    git("add", ".")
    git("commit", "-qm", "Initial resource fixture")
    base = git("rev-parse", "HEAD")
    state = root / ".devctl/state"
    state.mkdir(parents=True)
    manager = EnvironmentManager(state / "workspaces")
    cleanup_calls = []

    class SimulatedResource:
        required_leases = ["shared"]

        def inspect(self, spec):
            return []

        def prepare(self, handle):
            return {"id": "offline-resource"}

        def cleanup(self, handle, metadata):
            cleanup_calls.append(handle.id)

    manager.register_resource("fixture", SimulatedResource())
    environment = EnvironmentSpec(
        name="default",
        workspace="clone",
        execution="native",
        allow_native=True,
        private_network=False,
        test_resources=["fixture"],
        exclusive_resources=["shared"],
    )
    # A fixed past clock expires both leases when the CLI opens its real-clock Store.
    with Store(state / "workflow.db", clock=lambda: 1000.0) as store:
        store.add_tasks(
            [
                TaskSpec(
                    id="recover",
                    title="Recover resource fixture",
                    description="A stopped attempt requiring registered resource cleanup",
                    owned_paths=["resource.txt"],
                    acceptance=["Resource is cleaned before retry"],
                    environment="default",
                    base_sha=base,
                )
            ]
        )
        attempt = store.claim("recover", "controller", ttl_seconds=60)
        store.acquire_resources(attempt, "controller", ["shared"], ttl_seconds=60)

        def observed(handle):
            store.record_event(
                "environment",
                {
                    "task_id": "recover",
                    "attempt_id": attempt,
                    "role": "worker",
                    "id": handle.id,
                    "workspace": str(handle.workspace),
                    "provider_id": handle.provider_id,
                    "metadata": handle.metadata,
                    "spec": handle.spec.model_dump(mode="json"),
                },
            )

        manager.set_observer(observed)
        handle = manager.prepare(environment, root, "recover", base)

    try:
        code = main(["--project", str(root), "resume", "recover", "--attempt", attempt])
        output = json.loads(capsys.readouterr().out)
        assert code == 2
        assert output["status"] == "blocked"
        message = output["message"].lower()
        assert "fixture" in message
        assert "register" in message or "adapter" in message
    finally:
        with Store(state / "workflow.db") as store:
            task = store.get_task("recover")
            assert task["state"] == "blocked"
            assert task["reconciliation_required"]
            reservation = store.connection.execute(
                "SELECT attempt_id, owner FROM resources WHERE name = ?", ("shared",)
            ).fetchone()
            assert reservation is not None
            assert tuple(reservation) == (attempt, "controller")
            assert not any(event["kind"] == "environment_cleaned" for event in store.events())
        assert cleanup_calls == []
        assert handle.workspace.exists()


def test_metrics_missing_data_is_unknown_and_does_not_create_project(tmp_path, capsys):
    assert main(["--project", str(tmp_path), "metrics"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["review"]["human"]["samples"] == 0
    assert report["deployments"]["change_failure_rate"] is None
    assert list(tmp_path.iterdir()) == []


def test_metrics_import_is_repeatable_and_reports_human_time(tmp_path, capsys):
    from datetime import UTC, datetime

    source = tmp_path / "observations.json"
    source.write_text(
        json.dumps(
            [
                {
                    "source": "human-review-log",
                    "id": "review-1",
                    "at": datetime.now(UTC).isoformat(),
                    "kind": "review",
                    "data": {
                        "change_id": "task-1",
                        "pr": "owner/repo#2",
                        "reviewer": "human",
                        "seconds": 180.0,
                    },
                }
            ]
        )
    )
    args = ["--project", str(tmp_path), "metrics"]
    assert main([*args, "import", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["imported"] == 1
    assert main([*args, "import", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["duplicates"] == 1
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["review"]["human"]["samples"] == 1
    assert report["review"]["agent"]["samples"] == 0


def test_metrics_report_has_explicit_time_window(tmp_path, capsys):
    args = ["--project", str(tmp_path), "metrics", "--days", "7", "--until"]
    assert main([*args, "2026-10-10T00:00:00Z"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["from"] == "2026-10-03T00:00:00+00:00"
    assert report["to"] == "2026-10-10T00:00:00+00:00"
    assert main([*args, "2026-10-10T00:00:00"]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"
    assert list(tmp_path.iterdir()) == []


def test_github_metrics_sync_imports_and_deduplicates_completed_runs(tmp_path, capsys, monkeypatch):
    from datetime import UTC, datetime

    record = {
        "source": "github:owner/repo",
        "id": "ci:7:1",
        "at": datetime.now(UTC).isoformat(),
        "kind": "ci",
        "data": {"change_id": "owner/repo:abc", "seconds": 45.0, "outcome": "pass"},
    }
    calls = []

    def collect(repository, request, *, days):
        calls.append((repository, days))
        return {"records": [record], "warnings": [], "repository": repository}

    monkeypatch.setattr(cli, "collect_github_metrics", collect)
    args = ["--project", str(tmp_path), "metrics"]
    sync = [*args, "sync-github", "--repository", "owner/repo", "--days", "7"]
    assert main(sync) == 0
    assert json.loads(capsys.readouterr().out)["imported"] == 1
    assert main(sync) == 0
    assert json.loads(capsys.readouterr().out)["duplicates"] == 1
    assert calls == [("owner/repo", 7), ("owner/repo", 7)]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ci"]["samples"] == 1
    assert report["review"]["human"]["minutes"] is None


def test_failed_github_metrics_sync_creates_no_state(tmp_path, capsys, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("GitHub rate limit exceeded")

    monkeypatch.setattr(cli, "collect_github_metrics", fail)
    assert (
        main(["--project", str(tmp_path), "metrics", "sync-github", "--repository", "owner/repo"])
        == 4
    )
    assert "rate limit" in json.loads(capsys.readouterr().out)["message"]
    assert list(tmp_path.iterdir()) == []


def test_github_metrics_sync_uses_configured_repository(tmp_path, capsys, monkeypatch):
    (tmp_path / "design.md").write_text("Approved project design")
    args = ["--project", str(tmp_path)]
    assert main([*args, "init", "--name", "example", "--design", "design.md"]) == 0
    assert (
        main([*args, "interview", "--answer", "repository", "--value", '"owner/configured"']) == 0
    )
    capsys.readouterr()
    repositories = []

    def empty(repository, request, *, days):
        repositories.append(repository)
        return {"records": [], "warnings": []}

    monkeypatch.setattr(cli, "collect_github_metrics", empty)
    assert main([*args, "metrics", "sync-github"]) == 0
    assert json.loads(capsys.readouterr().out)["imported"] == 0
    assert repositories == ["owner/configured"]
    assert not (tmp_path / ".devctl/state/workflow.db").exists()
    assert (tmp_path / ".devctl/state/commands.jsonl").is_file()
