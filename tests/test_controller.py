"""Actual Git/process integration with explicitly simulated model responses."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentic_engineering.controller import Controller
from agentic_engineering.evidence import EvidenceStore
from agentic_engineering.models import EnvironmentSpec, ProjectConfig, TaskSpec
from agentic_engineering.storage import Store


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "Fixture")
    (root / "design.md").write_text("A CLI with independent features a and b.\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "initial")
    spec = EnvironmentSpec(
        name="local",
        execution="native",
        workspace="clone",
        allow_native=True,
        private_network=False,
    )
    config = ProjectConfig(
        name="fixture",
        max_parallel=2,  # Explicit parallel fixture; new projects start with one task.
        design_path="design.md",
        environments=[spec],
        checks={"unit": [sys.executable, "-c", "assert 2 + 2 == 4"]},
    )
    return root, config, git(root, "rev-parse", "HEAD"), tmp_path / "state"


class FixtureRunner:
    def run(self, execute, prompt, *, role, timeout_seconds, **kwargs):
        payload = json.loads(prompt)
        if role == "worker":
            target = payload["task"]["owned_paths"][0]
            result = execute(
                [
                    sys.executable,
                    "-c",
                    f"from pathlib import Path; Path({target!r}).write_text('fixture change\\n')",
                ],
                timeout_seconds,
            )
            assert result.returncode == 0
            return SimpleNamespace(text="Implemented", session_id="fixture", events=())
        return SimpleNamespace(
            text=json.dumps(
                {
                    "binding": payload["binding"],
                    "verdict": "approve",
                    "findings": [],
                    "reviewer_runner": "claude",
                    "independent": True,
                    "summary": "Fixture approval",
                }
            ),
            session_id="review-fixture",
            events=(),
        )


def task(base, name="a", **kwargs):
    return TaskSpec(
        id=name,
        title=name,
        description="Write the assigned file",
        owned_paths=[f"{name}.txt"],
        acceptance=["File exists"],
        environment="local",
        base_sha=base,
        checks=["unit"],
        **kwargs,
    )


def test_disjoint_tasks_produce_sealed_simulated_evidence_and_preserve_parent(project):
    root, config, base, state = project
    controller = Controller(root, config, state, runner_factory=lambda name, model: FixtureRunner())
    result = controller.run([task(base), task(base, "b")])
    assert {row["state"] for row in result} == {"approved"}
    assert git(root, "rev-parse", "HEAD") == base
    assert not (root / "a.txt").exists()
    with Store(state / "workflow.db") as store:
        receipts = [e["payload"]["receipt"] for e in store.events() if e["kind"] == "evidence"]
    assert len(receipts) == 2
    vault = EvidenceStore(state / "receipts")
    for receipt in receipts:
        evidence = vault.load(Path(receipt))
        assert not evidence.live
        assert evidence.binding.head_sha != base
        assert evidence.review.independent


def test_changes_outside_ownership_are_blocked(project):
    root, config, base, state = project

    class EscapingRunner(FixtureRunner):
        def run(self, execute, prompt, **kwargs):
            if kwargs["role"] == "worker":
                execute([sys.executable, "-c", "open('unowned.txt','w').write('escape')"], 5)
            return super().run(execute, prompt, **kwargs)

    controller = Controller(
        root, config, state, runner_factory=lambda name, model: EscapingRunner()
    )
    result = controller.run([task(base)])
    assert result[0]["state"] == "blocked"
    assert "ownership" in result[0]["note"]


def test_dependency_waits_for_candidate_to_be_integrated_into_base(project):
    root, config, base, state = project
    controller = Controller(root, config, state, runner_factory=lambda name, model: FixtureRunner())
    result = {
        row["id"]: row
        for row in controller.run(
            [
                task(base),
                task(base, "b", depends_on=["a"]),
            ]
        )
    }
    assert result["a"]["state"] == "approved"
    assert result["b"]["state"] == "blocked"
    assert "dependency" in result["b"]["note"]


def test_failed_check_never_runs_reviewer_or_approves(project):
    root, config, base, state = project
    config = config.model_copy(update={"checks": {"unit": [sys.executable, "-c", "exit(1)"]}})

    class NoReview(FixtureRunner):
        def run(self, execute, prompt, **kwargs):
            assert kwargs["role"] == "worker"
            return super().run(execute, prompt, **kwargs)

    result = Controller(root, config, state, runner_factory=lambda name, model: NoReview()).run(
        [
            task(base),
        ]
    )
    assert result[0]["state"] == "blocked"
    assert "Check unit failed" in result[0]["note"]
    assert list((state / "artifacts").rglob("*.bundle"))
    assert not list((state / "receipts").glob("*.json"))


def test_shared_test_resource_serializes_instead_of_blocking_second_task(project):
    import threading
    import time

    root, config, base, state = project
    env = config.environments[0].model_copy(update={"exclusive_resources": ["host-port:8000"]})
    config = config.model_copy(update={"environments": [env]})
    lock = threading.Lock()
    executing = 0

    class SerialRunner(FixtureRunner):
        def run(self, execute, prompt, **kwargs):
            nonlocal executing
            if kwargs["role"] == "worker":
                with lock:
                    executing += 1
                    assert executing == 1
                time.sleep(0.1)
                result = super().run(execute, prompt, **kwargs)
                with lock:
                    executing -= 1
                return result
            return super().run(execute, prompt, **kwargs)

    result = Controller(root, config, state, runner_factory=lambda n, m: SerialRunner()).run(
        [
            task(base),
            task(base, "b"),
        ]
    )
    assert [row["state"] for row in result] == ["approved", "approved"]


def test_review_repair_uses_previous_candidate_and_is_bounded(project):
    root, config, base, state = project
    reviewed = 0

    class RepairRunner(FixtureRunner):
        def run(self, execute, prompt, **kwargs):
            nonlocal reviewed
            result = super().run(execute, prompt, **kwargs)
            if kwargs["role"] == "reviewer":
                reviewed += 1
                value = json.loads(result.text)
                value["verdict"] = "changes_requested"
                value["summary"] = "Needs another change"
                result.text = json.dumps(value)
            return result

    result = Controller(root, config, state, runner_factory=lambda n, m: RepairRunner()).run(
        [
            task(base),
        ]
    )
    assert result[0]["state"] == "blocked"
    assert reviewed == config.max_repair_rounds + 1


def test_stale_review_binding_never_seals_evidence(project):
    root, config, base, state = project

    class StaleReview(FixtureRunner):
        def run(self, execute, prompt, **kwargs):
            result = super().run(execute, prompt, **kwargs)
            if kwargs["role"] == "reviewer":
                value = json.loads(result.text)
                value["binding"]["head_sha"] = "different"
                result.text = json.dumps(value)
            return result

    result = Controller(root, config, state, runner_factory=lambda n, m: StaleReview()).run(
        [
            task(base),
        ]
    )
    assert result[0]["state"] == "blocked"
    assert not list((state / "receipts").glob("*.json"))


def test_worker_replacement_refs_cannot_hide_unowned_changes(project):
    root, config, base, state = project

    class ReplacementRunner(FixtureRunner):
        def run(self, execute, prompt, **kwargs):
            if kwargs["role"] == "worker":
                execute([sys.executable, "-c", "open('unowned.txt','w').write('hidden')"], 5)
                execute(["git", "add", "unowned.txt"], 5)
                tree = execute(["git", "write-tree"], 5).stdout.strip()
                replacement = execute(
                    [
                        "git",
                        "-c",
                        "user.name=fixture",
                        "-c",
                        "user.email=fixture@localhost",
                        "commit-tree",
                        tree,
                        "-m",
                        "replacement",
                    ],
                    5,
                ).stdout.strip()
                assert execute(["git", "replace", base, replacement], 5).returncode == 0
            return super().run(execute, prompt, **kwargs)

    rows = Controller(root, config, state, runner_factory=lambda n, m: ReplacementRunner()).run(
        [
            task(base),
        ]
    )
    assert rows[0]["state"] == "blocked"
    assert "ownership" in rows[0]["note"]


def test_uncertain_preparation_retains_resource_and_handle_receipts(project):
    from agentic_engineering.environments import EnvironmentManager

    root, config, base, state = project
    env = config.environments[0].model_copy(
        update={
            "test_resources": ["fixture"],
            "exclusive_resources": ["shared"],
        }
    )
    config = config.model_copy(update={"environments": [env]})
    prepared = []

    class UncertainResource:
        required_leases = ["shared"]

        def inspect(self, spec):
            return []

        def prepare(self, handle):
            prepared.append(handle.id)
            raise TimeoutError("effect applied, acknowledgement lost")

        def cleanup(self, handle, metadata):
            raise RuntimeError("cleanup outcome uncertain")

    def manager_factory(directory):
        manager = EnvironmentManager(directory)
        manager.register_resource("fixture", UncertainResource())
        return manager

    Controller(
        root,
        config,
        state,
        manager_factory=manager_factory,
        runner_factory=lambda n, m: FixtureRunner(),
    ).run([task(base), task(base, "b")])
    assert len(prepared) == 1
    with Store(state / "workflow.db") as store:
        assert store.connection.execute("SELECT count(*) FROM resources").fetchone()[0] == 1
        assert any(event["kind"] == "environment" for event in store.events())


def test_controller_collects_check_review_and_correction_metrics(project):
    from agentic_engineering.metrics import metrics_report

    root, config, base, state = project

    class CategorizedReview(FixtureRunner):
        def run(self, execute, prompt, **kwargs):
            result = super().run(execute, prompt, **kwargs)
            if kwargs["role"] == "reviewer":
                value = json.loads(result.text)
                value["findings"] = [
                    {
                        "severity": "minor",
                        "message": "Use a clearer fixture label",
                        "category": "unclear-label",
                        "path": "a.txt",
                        "line": 1,
                    }
                ]
                result.text = json.dumps(value)
            return result

    rows = Controller(
        root, config, state, runner_factory=lambda name, model: CategorizedReview()
    ).run([task(base)])
    assert rows[0]["state"] == "approved"
    with Store(state / "workflow.db") as store:
        report = metrics_report(store, include_simulated=True)
        normal = metrics_report(store)
        records = [e["payload"] for e in store.events() if e["kind"] == "metric_reported"]
    assert report["check"]["samples"] == 1
    assert report["check"]["mean_seconds"] >= 0
    assert report["review"]["agent"]["samples"] == 1
    assert report["review"]["human"]["minutes_per_pr"] is None
    assert report["corrections"]["occurrences"] == 1
    assert report["corrections"]["repeat_rate"] == 0
    assert normal["check"]["samples"] == 0
    assert normal["review"]["agent"]["samples"] == 0
    assert all(r["simulated"] for r in records)
    assert all(r["data"]["commit"] != base for r in records)
