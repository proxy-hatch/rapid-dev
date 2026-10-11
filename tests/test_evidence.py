"""Delivery accepts only complete independent evidence for the exact candidate."""

import pytest

from agentic_engineering.evidence import validate_evidence
from agentic_engineering.models import (
    CheckResult,
    EvidenceBinding,
    ReviewDecision,
    ReviewFinding,
    TaskEvidence,
    digest,
)


def binding(**changes):
    data = dict(
        task_id="task",
        attempt_id="attempt",
        head_sha="head",
        base_sha="base",
        policy_digest="policy",
        recipe_digest="recipe",
        environment_digest="env",
        controller_version="0.1.0",
    )
    return EvidenceBinding(**(data | changes))


def evidence(**changes):
    value = binding()
    data = dict(
        binding=value,
        live=True,
        checks=[
            CheckResult(
                name="unit",
                argv=["pytest"],
                exit_code=0,
                duration_seconds=0.1,
                stdout="passed",
                stderr="",
            )
        ],
        review=ReviewDecision(
            binding=value,
            verdict="approve",
            findings=[],
            reviewer_runner="claude",
            independent=True,
            summary="Reviewed",
        ),
    )
    return TaskEvidence(**(data | changes))


def test_matching_passes():
    assert validate_evidence(evidence(), binding(), ["unit"]) == []


@pytest.mark.parametrize(
    "field",
    [
        "head_sha",
        "base_sha",
        "policy_digest",
        "recipe_digest",
        "environment_digest",
        "controller_version",
        "attempt_id",
    ],
)
def test_changed_inputs_invalidate_evidence(field):
    assert validate_evidence(evidence(), binding(**{field: "changed"}), ["unit"])


def test_missing_failed_and_duplicate_checks_are_rejected():
    source = evidence()
    assert validate_evidence(source, binding(), ["unit", "integration"])
    failed = source.checks[0].model_copy(update={"exit_code": 1})
    assert validate_evidence(evidence(checks=[failed]), binding(), ["unit"])
    assert validate_evidence(evidence(checks=source.checks * 2), binding(), ["unit"])


def test_self_review_or_blocking_findings_do_not_approve():
    source = evidence()
    assert source.review is not None
    self_review = source.review.model_copy(update={"independent": False})
    assert validate_evidence(evidence(review=self_review), binding(), ["unit"])
    finding = ReviewFinding(severity="important", message="Missing authorization")
    bad_review = source.review.model_copy(update={"findings": [finding]})
    assert validate_evidence(evidence(review=bad_review), binding(), ["unit"])
    assert validate_evidence(evidence(review=None), binding(), ["unit"])


def test_simulation_is_not_live_evidence():
    assert validate_evidence(evidence(live=False), binding(), ["unit"], require_live=True)
    assert validate_evidence(evidence(live=False), binding(), ["unit"], require_live=False) == []


def test_controller_receipt_detects_tampering(tmp_path):
    import json

    from agentic_engineering.evidence import EvidenceStore

    vault = EvidenceStore(tmp_path / "receipts")
    path = vault.save(evidence())
    assert vault.load(path) == evidence()
    value = json.loads(path.read_text())
    value["evidence"]["binding"]["head_sha"] = "forged"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="signature"):
        vault.load(path)


def test_matching_name_with_replaced_check_command_is_rejected():
    assert validate_evidence(evidence(), binding(), ["unit"], commands={"unit": ["false"]})


def test_interrupted_receipt_publication_can_be_retried(tmp_path, monkeypatch):
    import agentic_engineering.evidence as module

    vault = module.EvidenceStore(tmp_path / "receipts")
    original = module.os.fsync

    def interrupted(fd):
        raise OSError("simulated disk interruption")

    monkeypatch.setattr(module.os, "fsync", interrupted)
    with pytest.raises(OSError):
        vault.save(evidence())
    assert not list(vault.directory.glob("*.json"))
    monkeypatch.setattr(module.os, "fsync", original)
    assert vault.load(vault.save(evidence())) == evidence()


def test_receipt_without_finding_category_keeps_its_original_digest(tmp_path):
    import json

    from agentic_engineering.evidence import EvidenceStore

    vault = EvidenceStore(tmp_path / "receipts")
    source = evidence()
    review = source.review.model_copy(
        update={"findings": [ReviewFinding(severity="minor", message="Clarify the example")]}
    )
    payload = evidence(review=review).model_dump(mode="json")
    payload["review"]["findings"][0].pop("category", None)
    original_digest = digest(payload)
    path = vault.directory / f"{original_digest}.json"
    path.write_text(
        json.dumps({"schema_version": 1, "evidence": payload, "signature": vault._seal(payload)})
    )

    loaded = vault.load(path)

    assert loaded.review.findings[0].category is None
    assert digest(loaded) == original_digest
    assert loaded.model_dump(mode="json") == payload
    assert vault.save(loaded) == path
    assert vault.load(vault.directory / f"{digest(loaded)}.json") == loaded


def test_categorized_findings_are_saved_and_included_in_receipt_digest(tmp_path):
    from agentic_engineering.evidence import EvidenceStore

    source = evidence()
    finding = ReviewFinding(severity="minor", message="Clarify the example", category="docs")
    review = source.review.model_copy(update={"findings": [finding]})
    categorized = evidence(review=review)
    vault = EvidenceStore(tmp_path / "receipts")
    path = vault.save(categorized)
    loaded = vault.load(path)

    assert loaded.review.findings[0].category == "docs"
    assert digest(loaded) == digest(categorized) == path.stem
    uncategorized = evidence(
        review=review.model_copy(
            update={"findings": [finding.model_copy(update={"category": None})]}
        )
    )
    assert digest(uncategorized) != digest(categorized)
