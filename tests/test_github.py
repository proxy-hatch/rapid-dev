"""Simulated GitHub transport exercises lost responses without external writes."""

import pytest

from agentic_engineering.storage import Store
from agentic_engineering.trust.github import GitHubBroker, inspect_protection


def protection():
    return {
        "required_status_checks": {"strict": True, "checks": [{"context": "devctl", "app_id": 42}]},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
    }


def test_protection_requires_strict_checks_from_specific_app_and_no_admin_bypass():
    assert inspect_protection(protection(), "devctl", 42) == []
    for key, value in [
        ("required_status_checks", {"strict": False, "checks": []}),
        ("enforce_admins", {"enabled": False}),
    ]:
        assert inspect_protection(protection() | {key: value}, "devctl", 42)
    assert inspect_protection(protection(), "devctl", -1)


def test_lost_mutation_response_is_reconciled_and_never_repeated(tmp_path):
    with Store(tmp_path / "state.db") as store:
        broker = GitHubBroker(store, lambda *args: {}, "owner/repo", "main", "devctl", 42)
        created = []

        def mutate():
            created.append({"number": 1})
            raise TimeoutError("response lost after creation")

        with pytest.raises(TimeoutError):
            broker.effect(
                "operation",
                "create_pr",
                {"head": "abc"},
                lambda: created[0] if created else None,
                mutate,
            )
        assert store.get_effect("operation")["status"] == "uncertain"
        assert broker.effect(
            "operation", "create_pr", {"head": "abc"}, lambda: created[0], mutate
        ) == {"number": 1}
        assert len(created) == 1


def test_pending_after_crash_does_not_retry_when_lookup_is_empty(tmp_path):
    with Store(tmp_path / "state.db") as store:
        store.begin_effect("operation", "create_pr", {"head": "abc"})
        broker = GitHubBroker(store, lambda *args: {}, "owner/repo", "main", "devctl", 42)
        with pytest.raises(ValueError, match="reconciliation"):
            broker.effect(
                "operation",
                "create_pr",
                {"head": "abc"},
                lambda: None,
                lambda: pytest.fail("must never retry"),
            )


def test_missing_authority_blocks_before_any_transport(tmp_path):
    with Store(tmp_path / "state.db") as store:
        broker = GitHubBroker(
            store,
            lambda *args: pytest.fail("must not call GitHub"),
            "owner/repo",
            "main",
            "devctl",
            42,
        )
        with pytest.raises(ValueError, match="authority"):
            broker.require_authority("merge", None)


def test_pr_creation_with_moved_head_remains_uncertain(tmp_path):
    from agentic_engineering.models import (
        CheckResult,
        EvidenceBinding,
        ReviewDecision,
        TaskEvidence,
        TaskSpec,
        digest,
    )
    from agentic_engineering.trust.evidence import EvidenceStore

    commands = {"unit": ["pytest"]}
    with Store(tmp_path / "workflow.db") as store:
        store.add_tasks(
            [
                TaskSpec(
                    id="a",
                    title="a",
                    description="a",
                    owned_paths=["a.py"],
                    acceptance=["a"],
                    environment="docker",
                    base_sha="base",
                )
            ]
        )
        attempt = store.claim("a", "controller")
        for state in ["verifying", "reviewing", "approved"]:
            store.transition("a", state, attempt, "controller")
        binding = EvidenceBinding(
            task_id="a",
            attempt_id=attempt,
            head_sha="head",
            base_sha="base",
            policy_digest="policy",
            recipe_digest=digest(commands),
            environment_digest="env",
            controller_version="0.1.0",
        )
        review = ReviewDecision(
            binding=binding,
            verdict="approve",
            findings=[],
            reviewer_runner="claude",
            independent=True,
            summary="offline fixture",
        )
        evidence = TaskEvidence(
            binding=binding,
            review=review,
            live=True,
            checks=[
                CheckResult(
                    name="unit",
                    argv=["pytest"],
                    exit_code=0,
                    duration_seconds=0.1,
                    stdout="",
                    stderr="",
                )
            ],
        )
        vault = EvidenceStore(tmp_path / "receipts")
        receipt = vault.save(evidence)

        def request(method, endpoint, payload=None):
            if endpoint.endswith("/protection"):
                return protection()
            if "/git/ref/heads/" in endpoint:
                return {"object": {"sha": "base" if endpoint.endswith("/main") else "head"}}
            if method == "GET" and "/pulls?" in endpoint:
                return []
            assert method == "POST"
            return {
                "number": 1,
                "html_url": "https://github.com/owner/repo/pull/1",
                "head": {"sha": "unreviewed", "repo": {"full_name": "owner/repo"}},
                "base": {"sha": "base", "ref": "main", "repo": {"full_name": "owner/repo"}},
            }

        broker = GitHubBroker(
            store,
            request,
            "owner/repo",
            "main",
            "devctl",
            42,
            evidence_store=vault,
            authorization=lambda capability, ev: [],
        )
        with pytest.raises(ValueError, match="binding"):
            broker.create_pr("codex/a", "title", "body", receipt, binding, commands)
        started = [event for event in store.events() if event["kind"] == "effect_started"]
        assert store.get_effect(started[0]["payload"]["key"])["status"] == "uncertain"
