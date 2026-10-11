"""Metrics count observations without changing task state or approval."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from agentic_engineering.metrics import MetricRecord, import_metrics, metrics_report
from agentic_engineering.storage import Store

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)


def record(kind, data, identity="one", *, ago=0, source="fixture", simulated=False):
    return {
        "source": source,
        "id": identity,
        "at": (NOW - timedelta(days=ago)).isoformat(),
        "kind": kind,
        "simulated": simulated,
        "data": data,
    }


def review(identity="one", *, change="a", reviewer="human", seconds=120, **kwargs):
    return record(
        "review",
        {"change_id": change, "reviewer": reviewer, "seconds": seconds},
        identity,
        **kwargs,
    )


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "metrics.sqlite") as value:
        yield value


@pytest.mark.parametrize(
    "changes",
    [
        {"source": " "},
        {"id": ""},
        {"at": "2026-10-10T12:00:00"},
        {"at": 123},
        {"kind": "unknown"},
        {"simulated": "false"},
        {"extra": 1},
        {"data": {"change_id": "a", "reviewer": "human", "seconds": "12"}},
        {"data": {"change_id": "a", "reviewer": "human", "seconds": -1}},
        {"data": {"change_id": "a", "reviewer": "human", "seconds": float("nan")}},
        {"data": {"change_id": "a", "reviewer": "human", "seconds": 1, "unknown": 2}},
    ],
)
def test_record_rejects_ambiguous_or_invalid_fields(changes):
    with pytest.raises((ValidationError, ValueError)):
        MetricRecord.model_validate({**review(), **changes})


def test_kind_schemas_require_meaningful_data():
    invalid = [
        record("incident", {"incident_id": "i"}),
        record("mutation", {"killed": 3, "eligible": 2, "excluded": 0}),
        record("mutation", {"killed": 1, "eligible": 2, "excluded": True}),
        record("enforcement", {"category": "c", "rung": 3, "check": "ci", "reference": "pr/1"}),
        record("enforcement", {"category": "c", "rung": 1, "check": "ci"}),
        record("test", {"test_id": "a", "outcome": "fail"}),
        record("deploy", {"deployment_id": "d", "production": "yes", "failed": False}),
    ]
    for item in invalid:
        with pytest.raises(ValidationError):
            MetricRecord.model_validate(item)


def test_import_normalizes_timezone_and_is_idempotent(store):
    first = review()
    equivalent = {**first, "at": "2026-10-10T20:00:00+08:00"}
    assert import_metrics(store, [first, equivalent]) == {"imported": 1, "duplicates": 1}
    assert import_metrics(store, [equivalent]) == {"imported": 0, "duplicates": 1}
    assert store.events()[0]["kind"] == "metric_reported"
    assert store.events()[0]["payload"]["at"] == "2026-10-10T12:00:00Z"
    assert store.tasks() == []


def test_conflict_with_existing_record_rolls_back_entire_batch(store):
    import_metrics(store, [review()])
    before = store.events()
    with pytest.raises(ValueError, match="conflicting metric identity"):
        import_metrics(store, [review("new"), review(seconds=240)])
    assert store.events() == before


def test_conflict_within_batch_and_validation_failure_leave_no_records(store):
    with pytest.raises(ValueError, match="conflicting metric identity"):
        import_metrics(store, [review(), review(seconds=240)])
    assert store.events() == []
    with pytest.raises(ValidationError):
        import_metrics(store, [review(), {**review("new"), "simulated": "yes"}])
    assert store.events() == []


def test_write_failure_rolls_back_prior_records(store, monkeypatch):
    original = store._event

    def fail_second(kind, payload, now):
        if payload["id"] == "two":
            raise OSError("disk fault")
        original(kind, payload, now)

    monkeypatch.setattr(store, "_event", fail_second)
    with pytest.raises(OSError, match="disk fault"):
        import_metrics(store, [review(), review("two")])
    assert store.events() == []


def test_concurrent_imports_keep_identity_unique(tmp_path):
    path = tmp_path / "concurrent.sqlite"
    with Store(path):
        pass

    def run(seconds):
        with Store(path) as local:
            try:
                return import_metrics(local, [review(seconds=seconds)])
            except ValueError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, [60, 120]))
    assert outcomes.count("conflict") == 1
    with Store(path) as local:
        assert len(local.events()) == 1


def test_missing_is_not_zero_or_trust_authorization(store):
    result = metrics_report(store, now=NOW, observed_at=NOW)
    assert result["provenance"] == "reported"
    assert result["review"]["human"]["minutes_per_pr"] is None
    assert result["review"]["human"]["status"] == "missing"
    assert result["corrections"]["repeat_rate"] is None
    assert result["tests"]["flaky_rate"] is None
    assert result["deployments"]["change_failure_rate"] is None
    assert result["rollbacks"]["per_100_deployments"] is None
    assert result["restoration"]["mean_seconds"] is None
    assert result["mutation"]["weeks"] == {}
    assert "grant" not in result and "concurrency" not in result


def test_stale_simulated_and_future_samples_are_explicit(store):
    import_metrics(
        store, [review("stale", ago=29), review("sim", simulated=True), review("future", ago=-1)]
    )
    report = metrics_report(store, now=NOW, observed_at=NOW)
    human = report["review"]["human"]
    assert human["status"] == "stale" and human["samples"] == 0
    assert human["latest_at"] == (NOW - timedelta(days=29)).isoformat()
    assert human["minutes"] is None
    assert report["excluded_simulated"] == 1 and report["future_records"] == 1
    included = metrics_report(store, now=NOW, include_simulated=True, observed_at=NOW)
    assert included["review"]["human"]["samples"] == 1
    assert included["includes_simulated"] is True


def test_review_aggregates_per_change_and_explicit_pr_separately_by_reviewer(store):
    import_metrics(
        store,
        [
            review("a1", seconds=60),
            review("a2", seconds=120),
            review("b", change="b", seconds=240),
            review("agent", change="b", reviewer="agent", seconds=1800),
            record("pr", {"change_id": "a", "pr": "pr/1"}, "pa"),
            record("pr", {"change_id": "b", "pr": "pr/1"}, "pb"),
        ],
    )
    report = metrics_report(store, now=NOW, observed_at=NOW)["review"]
    human = report["human"]
    assert human["by_change"] == {"a": 3, "b": 4}
    assert human["minutes_per_change"] == 3.5
    assert human["by_pr"] == {"pr/1": 7}
    assert human["minutes_per_pr"] == 7
    assert human["samples"] == 3 and human["sources"] == ["fixture"]
    assert report["agent"]["minutes"] == 30
    assert report["agent"]["samples"] == 1


def test_conflicting_pr_mappings_do_not_invent_per_pr_minutes(store):
    import_metrics(
        store,
        [
            review(),
            record("pr", {"change_id": "a", "pr": "pr/1"}, "p1"),
            record("pr", {"change_id": "a", "pr": "pr/2"}, "p2"),
        ],
    )
    human = metrics_report(store, now=NOW, observed_at=NOW)["review"]["human"]
    assert human["minutes_per_pr"] is None and human["unmapped_samples"] == 1
    assert human["minutes_per_change"] == 2


def test_corrections_dedupe_change_category_and_use_existing_enforcement(store):
    corrections = [
        record("correction", {"category": "timeout", "change_id": "old"}, "old", ago=40),
        record("correction", {"category": "timeout", "change_id": "a"}, "a1"),
        record("correction", {"category": "timeout", "change_id": "a"}, "a2"),
        record("correction", {"category": "escaping", "change_id": "b"}, "b"),
        record(
            "enforcement",
            {"category": "timeout", "rung": 2, "check": "test_timeout", "reference": "pr/2"},
            "check",
            ago=35,
        ),
        record(
            "review",
            {"change_id": "c", "reviewer": "agent", "seconds": 20, "uncategorized_corrections": 2},
            "review",
        ),
    ]
    import_metrics(store, corrections)
    result = metrics_report(store, now=NOW, observed_at=NOW)["corrections"]
    assert result["samples"] == 3 and result["occurrences"] == 2
    assert result["repeated"] == 1 and result["repeat_rate"] == 0.5
    assert result["categories"] == 2 and result["enforced_share"] == 0.5
    assert result["uncategorized"] == 2 and result["coverage"] == "incomplete"


def test_test_flakes_require_repeated_matching_test_commit_recipe_environment(store):
    baseline = {
        "test_id": "test_one",
        "commit": "aaa",
        "recipe": "unit:v1",
        "environment": "python:3.12",
        "outcome": "fail",
    }
    records = [record("test", baseline, "first")]
    for field, value in (
        ("commit", "bbb"),
        ("recipe", "unit:v2"),
        ("environment", "python:3.13"),
        ("test_id", "test_two"),
    ):
        records.append(record("test", {**baseline, field: value, "outcome": "pass"}, field))
    import_metrics(store, records)
    result = metrics_report(store, now=NOW, observed_at=NOW)["tests"]
    assert result["groups"] == 5 and result["repeated_groups"] == 0
    assert result["flaky_rate"] is None
    import_metrics(
        store,
        [
            record("test", {**baseline, "outcome": "pass"}, "rerun"),
            record("test", {**baseline, "test_id": "stable"}, "stable1"),
            record("test", {**baseline, "test_id": "stable"}, "stable2"),
        ],
    )
    result = metrics_report(store, now=NOW, observed_at=NOW)["tests"]
    assert result["repeated_groups"] == 2 and result["flaky_groups"] == 1
    assert result["flaky_rate"] == 0.5


def test_check_commands_do_not_claim_test_flakes_or_ci_runs(store):
    check = {
        "change_id": "a",
        "check_id": "pytest",
        "commit": "aaa",
        "recipe": "unit",
        "environment": "linux",
        "seconds": 10,
        "outcome": "fail",
    }
    import_metrics(
        store,
        [
            record("check", check, "c1"),
            record("check", {**check, "outcome": "pass", "seconds": 20}, "c2"),
            record("ci", {"change_id": "a", "seconds": 90, "outcome": "pass"}, "ci"),
        ],
    )
    report = metrics_report(store, now=NOW, observed_at=NOW)
    assert report["check"]["samples"] == 2 and report["check"]["mean_seconds"] == 15
    assert report["ci"]["samples"] == 1 and report["ci"]["mean_seconds"] == 90
    assert report["tests"]["flaky_rate"] is None


def test_weekly_mutation_excludes_invalid_and_timed_out_from_score(store):
    import_metrics(
        store,
        [
            record(
                "mutation",
                {"killed": 8, "eligible": 10, "excluded": 4, "invalid": 2, "timed_out": 3},
                "m1",
            ),
            record("mutation", {"killed": 2, "eligible": 10, "excluded": 1}, "m2", source="tool"),
            record("mutation", {"killed": 0, "eligible": 0, "excluded": 5}, "old", ago=7),
        ],
    )
    result = metrics_report(store, now=NOW, observed_at=NOW)["mutation"]
    current = result["weeks"]["2026-10-05"]
    assert current["killed"] == 10 and current["eligible"] == 20 and current["score"] == 0.5
    assert current["excluded"] == 5 and current["invalid"] == 2 and current["timed_out"] == 3
    assert current["samples"] == 2 and current["sources"] == ["fixture", "tool"]
    assert result["weeks"]["2026-09-28"]["score"] is None


def test_deployment_denominator_uses_distinct_completed_production_deployments(store):
    deploy = {"deployment_id": "d1", "production": True, "failed": False, "pr": "pr/1"}
    import_metrics(
        store,
        [
            record("deploy", deploy, "d1"),
            record("deploy", deploy, "dupe", source="other"),
            record("deploy", {**deploy, "deployment_id": "d2", "failed": True}, "d2"),
            record("deploy", {**deploy, "deployment_id": "staging", "production": False}, "stage"),
            record("deploy", {**deploy, "deployment_id": "old"}, "old", ago=40),
            record("incident", {"incident_id": "i1", "deployment_id": "d1"}, "incident"),
            record("rollback", {"deployment_id": "d2"}, "r1"),
            record("rollback", {"deployment_id": "d2"}, "r2"),
            record("rollback", {"deployment_id": "missing"}, "unknown"),
        ],
    )
    report = metrics_report(store, now=NOW, observed_at=NOW)
    assert report["deployments"]["completed"] == 2
    assert report["deployments"]["failed"] == 2
    assert report["deployments"]["change_failure_rate"] == 1
    assert report["rollbacks"]["linked_production_events"] == 2
    assert report["rollbacks"]["per_100_deployments"] == 100
    assert report["rollbacks"]["unlinked_or_nonproduction_events"] == 1
    assert report["incidents"]["escaped_defects"] == 1


def test_incidents_retain_old_unresolved_and_measure_real_restoration_intervals(store):
    import_metrics(
        store,
        [
            record("incident", {"incident_id": "old", "pr": "pr/1"}, "old", ago=40),
            record("incident", {"incident_id": "resolved", "pr": "pr/2"}, "new", ago=2),
            record("incident", {"incident_id": "resolved", "pr": "pr/2"}, "duplicate", ago=1),
            record("restoration", {"incident_id": "resolved"}, "done", ago=1),
            record("restoration", {"incident_id": "resolved"}, "done-again"),
            record("restoration", {"incident_id": "old"}, "before-start", ago=41),
            record("restoration", {"incident_id": "absent"}, "unknown"),
        ],
    )
    report = metrics_report(store, now=NOW, observed_at=NOW)
    assert report["incidents"]["new"] == 1 and report["incidents"]["escaped_defects"] == 1
    assert [i["incident_id"] for i in report["incidents"]["unresolved"]] == ["old"]
    assert report["restoration"]["linked_incidents"] == 1
    assert report["restoration"]["mean_seconds"] == 86400
    assert report["restoration"]["invalid_or_unlinked_records"] == 2


@pytest.mark.parametrize("days", [0, -1, True, 1.5])
def test_invalid_windows_rejected(store, days):
    with pytest.raises(ValueError):
        metrics_report(store, days=days, now=NOW)


def test_naive_now_rejected(store):
    with pytest.raises(ValueError, match="timezone"):
        metrics_report(store, now=NOW.replace(tzinfo=None))


def test_boolean_is_not_an_enforcement_rung():
    value = record(
        "enforcement", {"category": "c", "rung": True, "check": "ci", "reference": "pr/1"}
    )
    with pytest.raises(ValidationError, match="integer"):
        MetricRecord.model_validate(value)


def test_import_uses_indexed_identity_and_does_not_load_workflow_history(store, monkeypatch):
    import_metrics(store, [review()])
    store.record_event("workflow", {"message": "unrelated logs"})

    def no_scan():
        raise AssertionError("import must not scan the workflow event history")

    monkeypatch.setattr(store, "events", no_scan)
    assert import_metrics(store, [review(), review("new")]) == {"imported": 1, "duplicates": 1}
    plan = store.connection.execute(
        "EXPLAIN QUERY PLAN SELECT payload FROM events WHERE kind = 'metric_reported' "
        "AND json_extract(payload, '$.source') = ? AND json_extract(payload, '$.id') = ?",
        ("fixture", "one"),
    ).fetchall()
    assert any("USING INDEX metric_identity" in row["detail"] for row in plan)
    assert metrics_report(store, now=NOW, observed_at=NOW)["review"]["human"]["samples"] == 2


def test_database_index_also_rejects_accidental_direct_duplicate_events(store):
    import sqlite3

    import_metrics(store, [review()])
    with pytest.raises(sqlite3.IntegrityError):
        store.record_event(
            "metric_reported", MetricRecord.model_validate(review()).model_dump(mode="json")
        )
    assert len(store.events()) == 1
    store.record_event("workflow", {"source": "fixture", "id": "one"})
    store.record_event("workflow", {"source": "fixture", "id": "one"})
    assert len(store.events()) == 3


def coverage(metric, identity="coverage", *, days=28, end=NOW, source="fixture"):
    return record(
        "coverage",
        {
            "metric": metric,
            "start": (end - timedelta(days=days)).isoformat(),
            "end": end.isoformat(),
        },
        identity,
        source=source,
    )


def metric_denominators():
    return [
        record("deploy", {"deployment_id": "d", "production": True, "failed": False}, "d"),
        record("correction", {"category": "timeout", "change_id": "a"}, "c"),
    ]


def test_absent_and_stale_feeds_do_not_imply_zero_rollbacks_or_enforcement(store):
    import_metrics(store, metric_denominators())
    report = metrics_report(store, now=NOW, observed_at=NOW)
    assert report["rollbacks"]["per_100_deployments"] is None
    assert report["rollbacks"]["coverage"] == "missing"
    assert report["corrections"]["enforced_share"] is None
    assert report["corrections"]["enforcement_coverage"] == "missing"
    import_metrics(
        store,
        [
            record("rollback", {"deployment_id": "d"}, "old", ago=40),
            coverage("rollback", "old-coverage", end=NOW - timedelta(days=40)),
            coverage("enforcement", "old-checks", end=NOW - timedelta(days=40)),
        ],
    )
    report = metrics_report(store, now=NOW, observed_at=NOW)
    assert report["rollbacks"]["per_100_deployments"] is None
    assert report["rollbacks"]["status"] == "stale"
    assert report["corrections"]["enforced_share"] is None


def test_complete_empty_coverage_supports_true_zero_and_keeps_provenance(store):
    import_metrics(
        store,
        [
            *metric_denominators(),
            coverage("rollback", "r", source="ci"),
            coverage("enforcement", "e", source="checks"),
        ],
    )
    report = metrics_report(store, now=NOW, observed_at=NOW)
    assert report["rollbacks"]["per_100_deployments"] == 0
    assert report["rollbacks"]["coverage"] == "complete"
    assert report["rollbacks"]["status"] == "available"
    assert report["rollbacks"]["samples"] == 0
    assert report["rollbacks"]["coverage_samples"] == 1
    assert report["rollbacks"]["sources"] == ["ci"]
    assert report["corrections"]["enforced_share"] == 0
    assert report["corrections"]["enforcement_coverage"] == "complete"
    assert report["corrections"]["enforcement_sources"] == ["checks"]


def test_partial_coverage_does_not_imply_zero(store):
    import_metrics(
        store,
        [
            *metric_denominators(),
            coverage("rollback", "r", days=27),
            coverage("enforcement", "e", days=27),
        ],
    )
    report = metrics_report(store, now=NOW, observed_at=NOW)
    assert report["rollbacks"]["per_100_deployments"] is None
    assert report["rollbacks"]["coverage"] == "partial"
    assert report["corrections"]["enforced_share"] is None
    assert report["corrections"]["enforcement_coverage"] == "partial"


def test_daily_coverage_intervals_join_but_never_fill_a_gap(store):
    rows = [
        coverage("rollback", f"day-{day}", days=1, end=NOW - timedelta(days=day))
        for day in range(28)
    ]
    import_metrics(store, [*metric_denominators(), *rows[:14], *rows[15:]])
    report = metrics_report(store, now=NOW, observed_at=NOW)
    assert report["rollbacks"]["per_100_deployments"] is None
    assert report["rollbacks"]["coverage"] == "partial"
    import_metrics(store, [rows[14]])
    report = metrics_report(store, now=NOW, observed_at=NOW)
    assert report["rollbacks"]["per_100_deployments"] == 0
    assert report["rollbacks"]["coverage"] == "complete"
    assert report["rollbacks"]["coverage_samples"] == 28


def test_positive_observations_report_partial_fractions_without_claiming_full_feed(store):
    import_metrics(
        store,
        [
            *metric_denominators(),
            record("rollback", {"deployment_id": "d"}, "r"),
            record(
                "enforcement",
                {"category": "timeout", "rung": 1, "check": "timeout", "reference": "pr/1"},
                "e",
            ),
        ],
    )
    report = metrics_report(store, now=NOW, observed_at=NOW)
    assert report["rollbacks"]["per_100_deployments"] == 100
    assert report["rollbacks"]["coverage"] == "reported"
    assert report["corrections"]["enforced_share"] == 1
    assert report["corrections"]["enforcement_coverage"] == "reported"


@pytest.mark.parametrize(
    "changes",
    [
        {"start": NOW.isoformat(), "end": (NOW - timedelta(seconds=1)).isoformat()},
        {"start": NOW.isoformat(), "end": NOW.isoformat()},
        {"start": "2026-10-01T00:00:00", "end": NOW.isoformat()},
        {"end": "2026-10-10T12:00:00"},
        {"metric": "unknown"},
        {"end": (NOW + timedelta(days=1)).isoformat()},
    ],
)
def test_invalid_coverage_intervals_rejected(changes):
    value = coverage("rollback")
    value["data"].update(changes)
    with pytest.raises(ValidationError):
        MetricRecord.model_validate(value)


@pytest.mark.parametrize("metric", ["rollback", "enforcement"])
def test_coverage_confirmed_after_midnight_applies_to_prior_event_window(store, metric):
    midnight = NOW.replace(hour=0)
    confirmation = midnight + timedelta(minutes=1)
    rows = metric_denominators()
    for row in rows:
        row["at"] = (midnight - timedelta(hours=1)).isoformat()
    proof = coverage(metric, end=midnight)
    proof["at"] = confirmation.isoformat()
    import_metrics(store, [*rows, proof])
    report = metrics_report(store, now=midnight, observed_at=confirmation)
    if metric == "rollback":
        assert report["rollbacks"]["per_100_deployments"] == 0
        assert report["rollbacks"]["coverage"] == "complete"
    else:
        assert report["corrections"]["enforced_share"] == 0
        assert report["corrections"]["enforcement_coverage"] == "complete"
    assert report["future_records"] == 0
    assert report["observed_at"] == confirmation.isoformat()


@pytest.mark.parametrize("metric", ["rollback", "enforcement"])
def test_confirmation_after_observation_cutoff_cannot_prove_zero(store, metric):
    midnight = NOW.replace(hour=0)
    rows = metric_denominators()
    for row in rows:
        row["at"] = (midnight - timedelta(hours=1)).isoformat()
    proof = coverage(metric, end=midnight)
    proof["at"] = (midnight + timedelta(minutes=2)).isoformat()
    import_metrics(store, [*rows, proof])
    report = metrics_report(store, now=midnight, observed_at=midnight + timedelta(minutes=1))
    assert report["rollbacks"]["per_100_deployments"] is None
    assert report["corrections"]["enforced_share"] is None
    assert report["future_records"] == 1


def test_naive_observation_cutoff_rejected(store):
    with pytest.raises(ValueError, match="timezone"):
        metrics_report(store, now=NOW, observed_at=NOW.replace(tzinfo=None))


def github_snapshot(identity="gh1", *, pr="owner/repo#1", ago=0, simulated=False, **changes):
    data = {
        "pr": pr,
        "created_at": (NOW - timedelta(days=60)).isoformat(),
        "state": "open",
        "draft": False,
        "head_sha": "head-a",
        "commits": 2,
        "additions": 20,
        "deletions": 5,
        "changed_files": 3,
        "review_count": 0,
        "changes_requested": 0,
        "reviewed_heads": [],
        "first_review_at": None,
        "merged_at": None,
        "closed_at": None,
    }
    data.update(changes)
    return record("github_pr", data, identity, ago=ago, simulated=simulated, source="github")


def test_github_repeated_snapshots_and_reviews_count_each_head_once(store):
    import_metrics(
        store,
        [
            github_snapshot("initial", ago=40),
            github_snapshot("one", ago=2, reviewed_heads=["head-a"], review_count=2),
            github_snapshot("two", ago=1, reviewed_heads=["head-a"], review_count=3),
            github_snapshot("three", reviewed_heads=["head-a"], review_count=4),
        ],
    )
    report = metrics_report(store, now=NOW, observed_at=NOW)["github"]
    assert report["samples"] == 3 and report["pr_count"] == 1
    row = report["prs"][0]
    assert row["revision_count"] == 0 and row["review_rounds"] == 1
    assert row["review_count"] == 4 and row["commits"] == 2
    assert row["basis"] == "observed_distinct_heads"
    assert row["completeness"] == "lower_bound"


def test_github_force_push_and_previously_reviewed_heads_add_revisions_not_commits(store):
    import_metrics(
        store,
        [
            github_snapshot("old", ago=40, head_sha="initial", commits=50),
            github_snapshot(
                "new",
                head_sha="force-pushed",
                commits=1,
                reviewed_heads=["initial", "unseen-between-polls"],
                review_count=3,
            ),
        ],
    )
    row = metrics_report(store, now=NOW, observed_at=NOW)["github"]["prs"][0]
    assert row["revision_count"] == 2
    assert row["review_rounds"] == 2
    assert row["commits"] == 1


def test_github_latest_snapshots_have_separate_pr_totals_and_elapsed_times(store):
    created = NOW - timedelta(hours=6)
    reviewed = NOW - timedelta(hours=4)
    merged = NOW - timedelta(hours=1)
    import_metrics(
        store,
        [
            github_snapshot(
                "a",
                created_at=created.isoformat(),
                first_review_at=reviewed.isoformat(),
                merged_at=merged.isoformat(),
                closed_at=merged.isoformat(),
                state="merged",
                review_count=3,
                changes_requested=2,
                reviewed_heads=["head-a"],
            ),
            github_snapshot("b", pr="owner/repo#2", commits=7, draft=True, head_sha="head-b"),
        ],
    )
    report = metrics_report(store, now=NOW, observed_at=NOW)
    github = report["github"]
    assert github["pr_count"] == 2 and github["sources"] == ["github"]
    assert github["totals"]["commits"] == 9 and github["totals"]["changes_requested"] == 2
    assert github["totals"]["merged"] == 1 and github["totals"]["open"] == 1
    assert github["means"]["first_review_seconds"] == 7200
    assert github["means"]["merge_seconds"] == 18000
    assert github["first_review_samples"] == 1 and github["merge_samples"] == 1
    assert github["prs"][1]["first_review_seconds"] is None
    assert github["prs"][1]["first_review_at"] is None
    assert github["prs"][1]["merged_at"] is None
    assert github["prs"][1]["closed_at"] is None
    assert report["review"]["human"]["minutes"] is None


def test_github_historical_reports_exclude_later_snapshots_and_their_reviewed_heads(store):
    import_metrics(
        store,
        [
            github_snapshot("before", ago=1),
            github_snapshot(
                "after", ago=-1, head_sha="new-head", reviewed_heads=["extra-head"], review_count=1
            ),
        ],
    )
    report = metrics_report(store, now=NOW, observed_at=NOW + timedelta(days=2))["github"]
    assert report["samples"] == 1
    assert report["prs"][0]["head_sha"] == "head-a"
    assert report["prs"][0]["revision_count"] == 0
    assert report["prs"][0]["review_rounds"] == 0


def test_github_missing_stale_and_simulated_observations_are_explicit(store):
    absent = metrics_report(store, now=NOW, observed_at=NOW)["github"]
    assert absent["status"] == "missing" and absent["pr_count"] == 0
    assert absent["means"]["revision_count"] is None
    import_metrics(
        store,
        [
            github_snapshot("old", ago=40),
            github_snapshot("sim", simulated=True, head_sha="sim-head"),
        ],
    )
    stale = metrics_report(store, now=NOW, observed_at=NOW)["github"]
    assert stale["status"] == "stale" and stale["samples"] == 0
    assert stale["prs"] == []
    included = metrics_report(store, now=NOW, observed_at=NOW, include_simulated=True)["github"]
    assert included["samples"] == 1 and included["prs"][0]["revision_count"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"pr": "repo/1"},
        {"pr": "owner/repo#0"},
        {"state": "draft"},
        {"draft": "false"},
        {"commits": -1},
        {"additions": True},
        {"review_count": -1},
        {"head_sha": " "},
        {"reviewed_heads": ["head-a", "head-a"], "review_count": 2},
        {"reviewed_heads": ["head-a"], "review_count": 0},
        {"changes_requested": 1, "review_count": 0},
        {"created_at": "2026-10-01T00:00:00"},
        {"first_review_at": (NOW - timedelta(days=61)).isoformat()},
        {"merged_at": (NOW - timedelta(days=61)).isoformat()},
        {"closed_at": (NOW - timedelta(days=61)).isoformat()},
        {"first_review_at": (NOW + timedelta(seconds=1)).isoformat()},
        {"created_at": (NOW + timedelta(seconds=1)).isoformat()},
    ],
)
def test_github_snapshot_rejects_invalid_counts_heads_and_timestamps(changes):
    with pytest.raises(ValidationError):
        MetricRecord.model_validate(github_snapshot(**changes))
