"""Offline broker gates with real SQLite and controller-sealed receipts.

Authorization and GitHub responses are deliberately simulated. The receipt's
live flag only exercises broker gates; these tests provide no promotion evidence.
"""

import hashlib
import json
from types import SimpleNamespace

import pytest

import agentic_engineering.github as github
from agentic_engineering.evidence import EvidenceStore
from agentic_engineering.github import GitHubBroker
from agentic_engineering.models import (
    CheckResult,
    EvidenceBinding,
    ReviewDecision,
    TaskEvidence,
    TaskSpec,
    digest,
)
from agentic_engineering.storage import Store


@pytest.fixture
def candidate(tmp_path):
    commands = {"unit": ["pytest"]}
    with Store(tmp_path / "workflow.db") as store:
        store.add_tasks(
            [
                TaskSpec(
                    id="delivery",
                    title="Delivery fixture",
                    description="Offline broker tests",
                    owned_paths=["delivery.py"],
                    acceptance=["Reviewed candidate is integrated"],
                    environment="docker",
                    base_sha="b" * 40,
                )
            ]
        )
        attempt = store.claim("delivery", "controller")
        for state in ["verifying", "reviewing", "approved"]:
            store.transition("delivery", state, attempt, "controller")
        binding = EvidenceBinding(
            task_id="delivery",
            attempt_id=attempt,
            head_sha="a" * 40,
            base_sha="b" * 40,
            policy_digest="policy",
            recipe_digest=digest(commands),
            environment_digest="environment",
            controller_version="0.1.0",
        )
        evidence = TaskEvidence(
            binding=binding,
            live=True,
            checks=[
                CheckResult(
                    name="unit",
                    argv=commands["unit"],
                    exit_code=0,
                    duration_seconds=0.1,
                    stdout="Simulated check",
                    stderr="",
                )
            ],
            review=ReviewDecision(
                binding=binding,
                verdict="approve",
                findings=[],
                reviewer_runner="claude",
                independent=True,
                summary="Simulated independent review",
            ),
        )
        vault = EvidenceStore(tmp_path / "receipts")
        yield SimpleNamespace(
            store=store,
            vault=vault,
            binding=binding,
            evidence=evidence,
            receipt=vault.save(evidence),
            commands=commands,
            state_dir=tmp_path,
        )


def simulated_authorization(capability, evidence):
    """A fixture authority adapter; never usable as a real authorization grant."""
    return []


def broker(candidate, request):
    return GitHubBroker(
        candidate.store,
        request,
        "owner/repo",
        "main",
        "devctl",
        42,
        evidence_store=candidate.vault,
        authorization=simulated_authorization,
    )


def protection():
    return {
        "required_status_checks": {"strict": True, "checks": [{"context": "devctl", "app_id": 42}]},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
    }


class SimulatedTransport:
    def __init__(self, candidate):
        self.calls = []
        self.base_sha = candidate.binding.base_sha
        self.pr = {
            "head": {"sha": candidate.binding.head_sha, "repo": {"full_name": "owner/repo"}},
            "base": {
                "sha": candidate.binding.base_sha,
                "ref": "main",
                "repo": {"full_name": "owner/repo"},
            },
            "merged": False,
            "merge_commit_sha": "c" * 40,
        }
        self.tag = {"object": {"type": "commit", "sha": "c" * 40}}
        self.release = {
            "id": 9,
            "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
            "draft": True,
            "assets": [{"name": "package.whl", "digest": "sha256:" + "d" * 64}],
        }

    def __call__(self, method, endpoint, payload=None):
        self.calls.append((method, endpoint, payload))
        if method == "GET" and endpoint.endswith("/protection"):
            return protection()
        if method == "GET" and endpoint.endswith("/pulls/7"):
            return self.pr
        if method == "GET" and endpoint.endswith("/git/ref/heads/main"):
            return {"object": {"sha": self.base_sha}}
        if method == "GET" and "/check-runs?" in endpoint:
            return {
                "check_runs": [
                    {
                        "name": "devctl",
                        "app": {"id": 42},
                        "status": "completed",
                        "conclusion": "success",
                    }
                ]
            }
        if method == "PUT" and endpoint.endswith("/pulls/7/merge"):
            self.pr["merged"] = True
            return {"merged": True, "sha": self.pr["merge_commit_sha"]}
        if method == "GET" and endpoint.endswith("/git/ref/tags/v1.0.0"):
            return self.tag
        if method == "GET" and endpoint.endswith("/releases/tags/v1.0.0"):
            return self.release
        if method == "PATCH" and endpoint.endswith("/releases/9"):
            self.release["draft"] = False
            return self.release
        pytest.fail(f"Unexpected simulated GitHub request: {method} {endpoint}")

    def mutations(self):
        return [call for call in self.calls if call[0] != "GET"]


def recorded_merge(candidate, *, commit="c" * 40, evidence=None, completed=True):
    """Arrange a prior durable broker receipt and integrated task through public APIs."""
    candidate.store.transition("delivery", "merged")
    payload = {
        "repository": "owner/repo",
        "number": 7,
        "head_sha": candidate.binding.head_sha,
        "evidence": digest(candidate.binding) if evidence is None else evidence,
    }
    key = "merge:" + digest(payload)
    candidate.store.begin_effect(key, "merge", payload)
    if completed:
        candidate.store.finish_effect(key, {"merged": True, "sha": commit, "number": 7})


def publish(candidate, transport):
    return broker(candidate, transport).publish_release(
        "v1.0.0",
        "c" * 40,
        {"package.whl": "sha256:" + "d" * 64},
        candidate.receipt,
        candidate.binding,
        candidate.commands,
    )


def test_confirmed_merge_sends_expected_head_and_persists_integrated_state(candidate):
    transport = SimulatedTransport(candidate)

    result = broker(candidate, transport).merge(
        7, candidate.receipt, candidate.binding, candidate.commands
    )

    assert result == {"merged": True, "sha": "c" * 40, "number": 7}
    assert transport.mutations() == [
        (
            "PUT",
            "repos/owner/repo/pulls/7/merge",
            {"sha": candidate.binding.head_sha, "merge_method": "merge"},
        )
    ]
    assert candidate.store.get_task("delivery")["state"] == "merged"


def test_already_merged_pr_reconciles_task_state_without_another_mutation(candidate):
    transport = SimulatedTransport(candidate)
    transport.pr["merged"] = True

    result = broker(candidate, transport).merge(
        7, candidate.receipt, candidate.binding, candidate.commands
    )

    assert result == {"merged": True, "sha": "c" * 40, "number": 7}
    assert transport.mutations() == []
    assert candidate.store.get_task("delivery")["state"] == "merged"


@pytest.mark.parametrize("mismatch", ["pr-base-branch", "advanced-base"])
def test_merge_rejects_changed_base_before_mutation(candidate, mismatch):
    transport = SimulatedTransport(candidate)
    if mismatch == "pr-base-branch":
        transport.pr["base"]["ref"] = "unreviewed"
    else:
        transport.base_sha = "e" * 40

    with pytest.raises(ValueError, match="[Bb]ase"):
        broker(candidate, transport).merge(
            7, candidate.receipt, candidate.binding, candidate.commands
        )

    assert transport.mutations() == []
    assert candidate.store.get_task("delivery")["state"] == "approved"


def test_confirmed_staged_release_returns_identity_and_persists_released_state(candidate):
    recorded_merge(candidate)
    transport = SimulatedTransport(candidate)

    result = publish(candidate, transport)

    assert result == {"id": 9, "url": transport.release["html_url"], "tag": "v1.0.0"}
    assert transport.mutations() == [("PATCH", "repos/owner/repo/releases/9", {"draft": False})]
    assert candidate.store.get_task("delivery")["state"] == "released"


def test_already_published_release_reconciles_task_without_republishing(candidate):
    recorded_merge(candidate)
    transport = SimulatedTransport(candidate)
    transport.release["draft"] = False

    result = publish(candidate, transport)

    assert result == {"id": 9, "url": transport.release["html_url"], "tag": "v1.0.0"}
    assert transport.mutations() == []
    assert candidate.store.get_task("delivery")["state"] == "released"


@pytest.mark.parametrize("mismatch", ["tag-commit", "annotated-tag", "asset-digest", "extra-asset"])
def test_release_rejects_unverified_tag_or_asset_before_publication(candidate, mismatch):
    recorded_merge(candidate)
    transport = SimulatedTransport(candidate)
    if mismatch == "tag-commit":
        transport.tag["object"]["sha"] = "e" * 40
    elif mismatch == "annotated-tag":
        transport.tag["object"]["type"] = "tag"
    elif mismatch == "asset-digest":
        transport.release["assets"][0]["digest"] = "sha256:" + "e" * 64
    else:
        transport.release["assets"].append(
            {"name": "unexpected.whl", "digest": "sha256:" + "e" * 64}
        )

    with pytest.raises(ValueError, match="[Tt]ag target|artifact digest"):
        publish(candidate, transport)

    assert transport.mutations() == []
    assert candidate.store.get_task("delivery")["state"] == "merged"


@pytest.mark.parametrize("mismatch", ["commit", "candidate", "unconfirmed"])
def test_release_requires_completed_merge_receipt_for_same_candidate_and_commit(
    candidate, mismatch
):
    recorded_merge(
        candidate,
        commit="e" * 40 if mismatch == "commit" else "c" * 40,
        evidence="unrelated-candidate" if mismatch == "candidate" else None,
        completed=mismatch != "unconfirmed",
    )
    transport = SimulatedTransport(candidate)

    with pytest.raises(ValueError, match="merge receipt"):
        publish(candidate, transport)

    assert transport.mutations() == []
    assert not any("/releases/" in endpoint for _, endpoint, _ in transport.calls)
    assert candidate.store.get_task("delivery")["state"] == "merged"


def test_mutated_sealed_bundle_is_rejected_before_git_or_candidate_transport(
    candidate, monkeypatch
):
    original = b"sealed candidate bundle fixture"
    name = hashlib.sha256(original).hexdigest() + ".bundle"
    bundle = candidate.state_dir / name
    bundle.write_bytes(original)
    evidence = candidate.evidence.model_copy(update={"artifact_paths": [name]})
    receipt = candidate.vault.save(evidence)
    bundle.write_bytes(b"modified after the controller sealed its identity")
    transport = SimulatedTransport(candidate)

    def no_git(*args, **kwargs):
        pytest.fail("A mutated candidate bundle must not reach Git subprocesses")

    monkeypatch.setattr(github, "run_process", no_git)
    with pytest.raises(ValueError, match="bundle digest"):
        broker(candidate, transport).push_candidate(
            candidate.state_dir, receipt, candidate.binding, candidate.commands
        )

    assert transport.calls == [("GET", "repos/owner/repo/branches/main/protection", None)]
    assert not any(event["kind"] == "effect_started" for event in candidate.store.events())


def test_tampered_receipt_is_rejected_before_authority_git_or_network(candidate, monkeypatch):
    envelope = json.loads(candidate.receipt.read_text())
    envelope["evidence"]["binding"]["head_sha"] = "e" * 40
    candidate.receipt.write_text(json.dumps(envelope))
    transport = SimulatedTransport(candidate)

    def forbidden(*args, **kwargs):
        pytest.fail("Tampered evidence must not reach authority or Git")

    monkeypatch.setattr(github, "run_process", forbidden)
    subject = GitHubBroker(
        candidate.store,
        transport,
        "owner/repo",
        "main",
        "devctl",
        42,
        evidence_store=candidate.vault,
        authorization=forbidden,
    )
    with pytest.raises(ValueError, match="signature"):
        subject.push_candidate(
            candidate.state_dir, candidate.receipt, candidate.binding, candidate.commands
        )

    assert transport.calls == []
    assert not any(event["kind"] == "effect_started" for event in candidate.store.events())


@pytest.mark.parametrize("operation", ["merge", "release"])
def test_completed_effect_recovers_local_transition_after_restart(
    candidate, monkeypatch, operation
):
    transport = SimulatedTransport(candidate)
    if operation == "release":
        recorded_merge(candidate)
    subject = broker(candidate, transport)

    def local_failure(*args, **kwargs):
        raise RuntimeError("Simulated crash after durable remote result")

    monkeypatch.setattr(subject, "_advance", local_failure)
    with pytest.raises(RuntimeError, match="Simulated crash"):
        if operation == "merge":
            subject.merge(7, candidate.receipt, candidate.binding, candidate.commands)
        else:
            subject.publish_release(
                "v1.0.0",
                "c" * 40,
                {"package.whl": "sha256:" + "d" * 64},
                candidate.receipt,
                candidate.binding,
                candidate.commands,
            )
    original_mutations = list(transport.mutations())

    def invoke():
        if operation == "merge":
            return broker(candidate, transport).merge(
                7, candidate.receipt, candidate.binding, candidate.commands
            )
        return publish(candidate, transport)

    expected_state = "merged" if operation == "merge" else "released"
    first = invoke()
    assert invoke() == first
    assert transport.mutations() == original_mutations
    assert candidate.store.get_task("delivery")["state"] == expected_state


def test_unconfirmed_release_response_does_not_advance_state(candidate):
    recorded_merge(candidate)
    transport = SimulatedTransport(candidate)

    def unconfirmed(method, endpoint, payload=None):
        if method == "PATCH":
            return {**transport.release, "draft": True}
        return transport(method, endpoint, payload)

    with pytest.raises(ValueError, match="confirm"):
        publish(candidate, unconfirmed)
    assert candidate.store.get_task("delivery")["state"] == "merged"
    effects = [
        candidate.store.get_effect(event["payload"]["key"])
        for event in candidate.store.events()
        if event["kind"] == "effect_started" and event["payload"]["kind"] == "release"
    ]
    assert len(effects) == 1 and effects[0]["status"] == "uncertain"


def test_pr_mapping_is_saved_once_for_review_metrics(candidate):
    created = []

    def request(method, endpoint, payload=None):
        if endpoint.endswith("/protection"):
            return protection()
        if "/git/ref/heads/" in endpoint:
            sha = (
                candidate.binding.base_sha
                if endpoint.endswith("/main")
                else candidate.binding.head_sha
            )
            return {"object": {"sha": sha}}
        if method == "GET" and "/pulls?" in endpoint:
            return created
        assert method == "POST" and endpoint.endswith("/pulls")
        pr = {
            "number": 7,
            "html_url": "https://github.com/owner/repo/pull/7",
            "body": payload["body"],
            "head": {
                "sha": candidate.binding.head_sha,
                "ref": "codex/delivery",
                "repo": {"full_name": "owner/repo"},
            },
            "base": {
                "sha": candidate.binding.base_sha,
                "ref": "main",
                "repo": {"full_name": "owner/repo"},
            },
        }
        created.append(pr)
        return pr

    subject = broker(candidate, request)
    for _ in range(2):
        result = subject.create_pr(
            "codex/delivery",
            "Delivery",
            "Reviewed change",
            candidate.receipt,
            candidate.binding,
            candidate.commands,
        )
        assert result["number"] == 7
    mappings = [
        e["payload"]
        for e in candidate.store.events()
        if e["kind"] == "metric_reported" and e["payload"]["kind"] == "pr"
    ]
    assert len(created) == len(mappings) == 1
    assert mappings[0]["data"] == {"change_id": "delivery", "pr": "owner/repo#7"}
