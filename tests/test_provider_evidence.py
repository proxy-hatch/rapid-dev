"""Provider evidence keeps explicit proofs separate from catalog observations."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from rapid_ship.models import ProjectConfig
from rapid_ship.project.configuration import provider_records, save_provider_records
from rapid_ship.project.provider_evidence import check_model_readiness


def observation(provider="agy", **changes):
    return {
        "provider": provider,
        "authenticated": None if provider == "agy" else True,
        "checked_at": datetime.now(UTC).isoformat(),
        "models": [{"id": "worker"}, {"id": "reviewer"}],
        **changes,
    }


def verification(model="worker", **changes):
    return {
        **observation(
            authenticated=True,
            verified=True,
            verification_method="inference",
            selected_model=model,
            verified_at=datetime.now(UTC).isoformat(),
            request_sent=True,
        ),
        **changes,
    }


def config(provider="agy"):
    return ProjectConfig(
        name="offline-evidence-fixture",
        design_path="design.md",
        providers=[provider],
        models={
            "small": {"provider": provider, "model": "worker"},
            "large": {"provider": provider, "model": "reviewer"},
        },
    )


def test_incomplete_successful_observation_cannot_replace_saved_evidence(tmp_path):
    (tmp_path / ".devctl").mkdir()
    save_provider_records(tmp_path, [observation()])
    path = tmp_path / ".devctl/providers.json"
    before = path.read_bytes()

    with pytest.raises(ValueError, match="Invalid provider observation"):
        save_provider_records(tmp_path, [observation(authenticated=True, ready=True)])

    assert path.read_bytes() == before


def test_save_returns_the_effective_report_including_retained_proofs(tmp_path):
    (tmp_path / ".devctl").mkdir()
    verified = verification()
    save_provider_records(tmp_path, [verified])
    discovery = observation()

    effective = save_provider_records(tmp_path, [discovery])

    assert effective == [{**discovery, "model_verifications": {"worker": verified["verified_at"]}}]
    assert effective == [provider_records(tmp_path)["agy"]]
    assert "model_verifications" not in discovery


@pytest.mark.parametrize(
    "field",
    ["authenticated", "verified", "verification_method", "selected_model", "verified_at"],
)
def test_agy_success_requires_every_part_of_exact_model_proof(tmp_path, field):
    (tmp_path / ".devctl").mkdir()
    report = verification(ready=True)
    del report[field]

    with pytest.raises(ValueError, match="Invalid provider observation"):
        save_provider_records(tmp_path, [report])

    assert not (tmp_path / ".devctl/providers.json").exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"authenticated": False},
        {"authenticated": "true"},
        {"verified": False},
        {"verified": 1},
        {"verification_method": "native-status"},
        {"selected_model": "other"},
        {"verified_at": None},
        {"verified_at": "2026-10-12T12:00:00"},
        {"verified_at": "SECRET_INVALID_TIMESTAMP"},
        {"models": [{"id": "worker"}, {"id": "worker"}]},
    ],
)
def test_invalid_agy_success_is_rejected_without_exposing_input(tmp_path, changes):
    (tmp_path / ".devctl").mkdir()
    with pytest.raises(ValueError, match="Invalid provider observation") as error:
        save_provider_records(tmp_path, [verification(**changes)])

    assert "SECRET" not in str(error.value)
    assert not (tmp_path / ".devctl/providers.json").exists()


def test_invalid_later_observation_cannot_partially_update_a_batch(tmp_path):
    (tmp_path / ".devctl").mkdir()
    save_provider_records(tmp_path, [verification()])
    path = tmp_path / ".devctl/providers.json"
    before = path.read_bytes()
    failure = observation(selected_model="worker", verification_method="inference", verified=False)

    with pytest.raises(ValueError, match="Invalid provider observation"):
        save_provider_records(
            tmp_path, [failure, observation("codex", checked_at="SECRET_INVALID_TIMESTAMP")]
        )

    assert path.read_bytes() == before


@pytest.mark.parametrize("timestamp", ["2026-10-12T01:02:03Z", "2026-10-12T09:02:03+08:00"])
def test_sparse_reports_preserve_original_timestamps_and_absent_fields(tmp_path, timestamp):
    (tmp_path / ".devctl").mkdir()
    native = observation("codex", checked_at=timestamp)
    assert save_provider_records(tmp_path, [native]) == [native]
    assert provider_records(tmp_path)["codex"] == native
    proof = verification(checked_at=timestamp, verified_at=timestamp)
    save_provider_records(tmp_path, [proof])
    discovery = observation(checked_at=timestamp)

    effective = save_provider_records(tmp_path, [discovery])

    assert effective == [{**discovery, "model_verifications": {"worker": timestamp}}]
    assert effective[0]["authenticated"] is None
    assert "verified" not in effective[0]
    assert "ready" not in effective[0]


@pytest.mark.parametrize("bad_report", [None, [], {"checked_at": "SECRET_BROKEN"}])
def test_refresh_repairs_selected_record_and_keeps_unrelated_malformed_data(tmp_path, bad_report):
    (tmp_path / ".devctl").mkdir()
    path = tmp_path / ".devctl/providers.json"
    unrelated = {"private": "UNCHANGED_UNRELATED"}
    path.write_text(json.dumps({"agy": bad_report, "claude": unrelated}))
    discovery = observation()

    effective = save_provider_records(tmp_path, [discovery])

    assert effective == [{**discovery, "model_verifications": {}}]
    assert provider_records(tmp_path) == {"agy": effective[0], "claude": unrelated}


def test_failed_explicit_probe_invalidates_model_missing_from_catalog(tmp_path):
    (tmp_path / ".devctl").mkdir()
    worker, reviewer = verification(), verification("reviewer")
    save_provider_records(tmp_path, [worker, reviewer])
    failure = observation(
        models=[{"id": "reviewer"}],
        selected_model="worker",
        verification_method="inference",
        verified=False,
        request_sent=False,
    )

    effective = save_provider_records(tmp_path, [failure])

    assert effective == [{**failure, "model_verifications": {"reviewer": reviewer["verified_at"]}}]


@pytest.mark.parametrize("field", ["catalog", "proof"])
@pytest.mark.parametrize("age", [0, 86400, 86400.000001, -0.000001])
def test_readiness_applies_inclusive_24_hour_limit_to_catalog_and_each_proof(field, age):
    now = datetime(2026, 10, 12, 12, tzinfo=UTC)
    timestamp = (now - timedelta(seconds=age)).isoformat()
    report = observation(
        checked_at=timestamp if field == "catalog" else now.isoformat(),
        model_verifications={
            "worker": timestamp if field == "proof" else now.isoformat(),
            "reviewer": now.isoformat(),
        },
    )

    if 0 <= age <= 86400:
        check_model_readiness({"agy": report}, config(), now=now)
    else:
        with pytest.raises(ValueError, match=r"Refresh|Verify"):
            check_model_readiness({"agy": report}, config(), now=now)


@pytest.mark.parametrize("field", ["checked_at", "model_verifications"])
def test_timezone_naive_saved_times_cannot_establish_readiness(field):
    now = datetime(2026, 10, 12, 12, tzinfo=UTC)
    report = observation(
        checked_at=now.isoformat(),
        model_verifications={"worker": now.isoformat(), "reviewer": now.isoformat()},
    )
    if field == "checked_at":
        report[field] = "2026-10-12T12:00:00"
    else:
        report[field]["worker"] = "2026-10-12T12:00:00"

    with pytest.raises(ValueError, match="Refresh provider checks for agy"):
        check_model_readiness({"agy": report}, config(), now=now)


def test_saved_provider_key_must_match_the_report():
    with pytest.raises(ValueError, match="Refresh provider checks for codex"):
        check_model_readiness({"codex": observation("claude")}, config("codex"))


def test_native_status_verification_does_not_require_an_inference_request(tmp_path):
    (tmp_path / ".devctl").mkdir()
    report = observation(
        "codex",
        selected_model="worker",
        verification_method="native-status",
        verified=True,
        verified_at=datetime.now(UTC).isoformat(),
        request_sent=False,
    )

    assert save_provider_records(tmp_path, [report]) == [report]
    check_model_readiness(provider_records(tmp_path), config("codex"))


@pytest.mark.parametrize(
    "changes",
    [
        {"authenticated": False, "ready": True},
        {"models": [], "ready": True},
        {"verified": True},
    ],
)
def test_native_success_claims_must_match_the_observation(tmp_path, changes):
    (tmp_path / ".devctl").mkdir()

    with pytest.raises(ValueError, match="Invalid provider observation"):
        save_provider_records(tmp_path, [observation("codex", **changes)])


def test_repeated_provider_in_batch_returns_its_final_saved_evidence(tmp_path):
    (tmp_path / ".devctl").mkdir()
    worker, reviewer = verification(), verification("reviewer")

    effective = save_provider_records(tmp_path, [worker, reviewer])

    saved = provider_records(tmp_path)["agy"]
    assert effective == [saved, saved]
    assert saved["model_verifications"] == {
        "worker": worker["verified_at"],
        "reviewer": reviewer["verified_at"],
    }


@pytest.mark.parametrize("request_sent", [False, None])
def test_agy_success_without_a_sent_request_cannot_update_the_cache(tmp_path, request_sent):
    (tmp_path / ".devctl").mkdir()
    save_provider_records(tmp_path, [verification()])
    path = tmp_path / ".devctl/providers.json"
    before = path.read_bytes()
    report = verification("reviewer", request_sent=request_sent)
    if request_sent is None:
        del report["request_sent"]

    with pytest.raises(ValueError, match="Invalid provider observation"):
        save_provider_records(tmp_path, [report])

    assert path.read_bytes() == before


@pytest.mark.parametrize("request_sent", [False, None])
def test_saved_agy_success_without_a_sent_request_cannot_establish_readiness(request_sent):
    timestamp = datetime.now(UTC).isoformat()
    report = verification(
        request_sent=request_sent,
        model_verifications={"worker": timestamp, "reviewer": timestamp},
    )
    if request_sent is None:
        del report["request_sent"]

    with pytest.raises(ValueError, match="Refresh provider checks for agy"):
        check_model_readiness({"agy": report}, config())
