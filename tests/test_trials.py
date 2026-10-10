"""Sealed evidence and exact external human authorization gate each capability."""

import json

import pytest

from agentic_engineering.evidence import EvidenceStore
from agentic_engineering.models import CheckResult, EvidenceBinding, ReviewDecision, TaskEvidence
from agentic_engineering.policy import (
    AuthorityDecision,
    CapabilityBinding,
    Policy,
    PolicyStore,
    Recipe,
    validate_authorization,
)
from agentic_engineering.trials import TrialStore


def setup(tmp_path, *, execution="docker", decision_changes=None):
    candidate = tmp_path / "candidate"
    candidate.mkdir(exist_ok=True)
    policy = Policy(
        project_id="demo",
        controller_version="0.1.0",
        recipes=(Recipe(name="unit", checks=(("unit", ("pytest",)),)),),
        capabilities=("create_pr", "merge"),
    )
    policies = PolicyStore(tmp_path / "host-policy", candidate)
    policies.initialize(policy)
    binding = CapabilityBinding(
        capability="merge",
        policy_digest=policy.digest,
        recipe_digest=policy.recipes[0].digest,
        environment_digest="real-env",
        controller_version="0.1.0",
        risk_class="low",
        execution=execution,
    )
    # This fake represents an out-of-process operator service. It does not claim live identity.
    requests = {}

    def authority(request):
        if request.digest not in requests:
            raise ValueError("No externally signed operator approval")
        values = dict(
            request_digest=request.digest,
            authorized=True,
            human_reviewed=True,
            environment_verified=True,
            authority_isolated=True,
            provenance="simulated external authority fixture",
        )
        return AuthorityDecision(**(values | (decision_changes or {})))

    receipts = EvidenceStore(tmp_path / "host-receipts")
    trials = TrialStore(tmp_path / "host-trials", candidate, receipts, policies, authority)
    return policy, binding, requests, authority, receipts, trials


def evidence(binding, change, *, live=True, command="pytest"):
    exact = EvidenceBinding(
        task_id=change,
        attempt_id=f"attempt-{change}",
        head_sha=change,
        base_sha="base",
        policy_digest=binding.policy_digest,
        recipe_digest=binding.recipe_digest,
        environment_digest=binding.environment_digest,
        controller_version=binding.controller_version,
    )
    return TaskEvidence(
        binding=exact,
        live=live,
        checks=[
            CheckResult(
                name="unit",
                argv=[command],
                exit_code=0,
                duration_seconds=0.1,
                stdout="passed",
                stderr="",
            )
        ],
        review=ReviewDecision(
            binding=exact,
            verdict="approve",
            reviewer_runner="independent-reviewer",
            independent=True,
            summary="approved",
        ),
    )


def record(trials, receipts, requests, binding, name, kind, **changes):
    path = receipts.save(evidence(binding, name, **changes))
    request = trials.trial_request(
        binding, path, kind=kind, change_id=name, authorization_id=f"human-{name}"
    )
    requests[request.digest] = request
    return trials.record_trial(
        binding, path, kind=kind, change_id=name, authorization_id=f"human-{name}"
    )


def calibration(trials, receipts, requests, binding):
    return [
        record(trials, receipts, requests, binding, str(i), kind)
        for i, kind in enumerate(["representative"] * 3 + ["recovery", "adversarial"])
    ]


def promote(trials, requests, binding, records):
    ids = tuple(item.digest for item in records)
    request = trials.promotion_request(binding, ids, authorization_id="operator-promote")
    requests[request.digest] = request
    return trials.promote(binding, ids, authorization_id="operator-promote")


def test_exact_trials_and_external_operator_authorization_create_narrow_grant(tmp_path):
    policy, binding, requests, authority, receipts, trials = setup(tmp_path)
    records = calibration(trials, receipts, requests, binding)
    grant = promote(trials, requests, binding, records)
    assert trials.load_grant(grant.digest) == grant
    assert validate_authorization(policy, grant, binding, authority) == []
    changed = binding.model_copy(update={"capability": "create_pr"})
    assert validate_authorization(policy, grant, changed, authority)
    changed = binding.model_copy(update={"risk_class": "high"})
    assert validate_authorization(policy, grant, changed, authority)
    assert validate_authorization(policy, grant, binding)
    forged = grant.model_copy(update={"trial_digests": ()})
    assert validate_authorization(policy, forged, binding, authority)
    requests.clear()
    assert validate_authorization(policy, grant, binding, authority)


@pytest.mark.parametrize("changes", [{"live": False}, {"command": "true"}])
def test_simulated_or_unapproved_checks_cannot_record_qualifying_trials(tmp_path, changes):
    _, binding, requests, _, receipts, trials = setup(tmp_path)
    with pytest.raises(ValueError, match="Simulated|approved command"):
        record(trials, receipts, requests, binding, "a", "representative", **changes)


def test_self_asserted_json_and_unsigned_human_claim_are_rejected(tmp_path):
    _, binding, _, _, receipts, trials = setup(tmp_path)
    path = tmp_path / "candidate" / "forged.json"
    path.write_text(evidence(binding, "a").model_dump_json())
    with pytest.raises(ValueError, match="receipt|Receipt"):
        trials.record_trial(
            binding, path, kind="representative", change_id="a", authorization_id="human-true"
        )
    path = receipts.save(evidence(binding, "a"))
    with pytest.raises(ValueError, match="authority"):
        trials.record_trial(
            binding, path, kind="representative", change_id="a", authorization_id="human-true"
        )


@pytest.mark.parametrize("missing", [0, 3, 4])
def test_missing_representative_recovery_or_adversarial_trials_block_promotion(tmp_path, missing):
    _, binding, requests, _, receipts, trials = setup(tmp_path)
    records = calibration(trials, receipts, requests, binding)
    del records[missing]
    with pytest.raises(ValueError, match="three|recovery|adversarial"):
        promote(trials, requests, binding, records)


@pytest.mark.parametrize(
    "changes",
    [
        {"human_reviewed": False},
        {"environment_verified": False},
        {"authority_isolated": False},
        {"request_digest": "other"},
    ],
)
def test_unverified_or_unbound_external_decision_is_blocked(tmp_path, changes):
    _, binding, requests, _, receipts, trials = setup(tmp_path, decision_changes=changes)
    with pytest.raises(ValueError):
        record(trials, receipts, requests, binding, "a", "representative")


def test_native_trials_cannot_promote_unattended_even_with_signoff(tmp_path):
    _, binding, requests, _, receipts, trials = setup(tmp_path, execution="native")
    records = calibration(trials, receipts, requests, binding)
    with pytest.raises(ValueError, match="native|Native"):
        promote(trials, requests, binding, records)


def test_changed_controller_policy_and_trial_envelope_cannot_promote(tmp_path):
    _, binding, requests, _, receipts, trials = setup(tmp_path)
    records = calibration(trials, receipts, requests, binding)
    changed = binding.model_copy(update={"controller_version": "candidate-upgrade"})
    with pytest.raises(ValueError, match="policy|controller"):
        promote(trials, requests, changed, records)
    path = trials.directory / f"trial-{records[0].digest}.json"
    value = json.loads(path.read_text())
    value["payload"]["kind"] = "adversarial"
    path.chmod(0o600)
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="signature"):
        promote(trials, requests, binding, records)


def test_hardening_requires_exact_authority_and_cannot_increase_grant(tmp_path):
    policy, binding, requests, authority, receipts, trials = setup(tmp_path)
    grant = promote(trials, requests, binding, calibration(trials, receipts, requests, binding))
    request = trials.hardening_request(
        binding, "prevent stale merge", "contract", "operator-hardening"
    )
    with pytest.raises(ValueError, match="authority"):
        trials.harden(binding, "prevent stale merge", "contract", "operator-hardening")
    requests[request.digest] = request
    hardening = trials.harden(binding, "prevent stale merge", "contract", "operator-hardening")
    assert hardening.rung == "contract"
    assert validate_authorization(policy, grant, binding, authority) == []


def test_operator_provenance_is_retained_on_trial_grant_and_hardening(tmp_path):
    _, binding, requests, _, receipts, trials = setup(tmp_path)
    records = calibration(trials, receipts, requests, binding)
    grant = promote(trials, requests, binding, records)
    assert (
        trials.load_trial(records[0].digest).authority_provenance
        == "simulated external authority fixture"
    )
    assert (
        trials.load_grant(grant.digest).authority_provenance
        == "simulated external authority fixture"
    )
    request = trials.hardening_request(
        binding, "prevent stale merge", "contract", "operator-hardening"
    )
    requests[request.digest] = request
    assert trials.harden(
        binding, "prevent stale merge", "contract", "operator-hardening"
    ).authority_provenance


def test_relabeling_same_head_does_not_supply_three_representative_changes(tmp_path):
    _, binding, requests, _, receipts, trials = setup(tmp_path)
    records = []
    path = receipts.save(evidence(binding, "same-head"))
    for change in ("a", "b", "c"):
        request = trials.trial_request(
            binding, path, kind="representative", change_id=change, authorization_id=change
        )
        requests[request.digest] = request
        records.append(
            trials.record_trial(
                binding, path, kind="representative", change_id=change, authorization_id=change
            )
        )
    records.extend(
        record(trials, receipts, requests, binding, kind, kind)
        for kind in ("recovery", "adversarial")
    )
    with pytest.raises(ValueError, match="three"):
        promote(trials, requests, binding, records)


def test_controller_upgrade_cannot_use_capability_trial_promotion(tmp_path):
    _, binding, requests, _, receipts, trials = setup(tmp_path)
    records = calibration(trials, receipts, requests, binding)
    binding = binding.model_copy(update={"capability": "controller_upgrade"})
    with pytest.raises(ValueError, match="ceremony"):
        promote(trials, requests, binding, records)


@pytest.mark.parametrize(
    "field", ["recipe_digest", "environment_digest", "policy_digest", "controller_version"]
)
def test_stale_trial_receipt_bindings_do_not_record(tmp_path, field):
    _, binding, requests, _, receipts, trials = setup(tmp_path)
    source = evidence(binding, "a")
    stale_binding = source.binding.model_copy(update={field: "stale"})
    stale = source.model_copy(
        update={
            "binding": stale_binding,
            "review": source.review.model_copy(update={"binding": stale_binding}),
        }
    )
    path = receipts.save(stale)
    with pytest.raises(ValueError, match="binding"):
        trials.trial_request(
            binding, path, kind="representative", change_id="a", authorization_id="human"
        )


def test_trial_store_rejects_receipt_vault_inside_candidate(tmp_path):
    policy, binding, requests, authority, _, trials = setup(tmp_path)
    receipts = EvidenceStore(tmp_path / "candidate" / "receipts")
    with pytest.raises(ValueError, match="candidate"):
        TrialStore(
            tmp_path / "new-host-trials",
            tmp_path / "candidate",
            receipts,
            trials.policy_store,
            authority,
        )
    assert not (tmp_path / "new-host-trials").exists()
