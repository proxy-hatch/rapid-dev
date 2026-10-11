"""Reported delivery metrics. These records never grant approval or change concurrency."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agentic_engineering.storage import Store

Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
Count = Annotated[int, Field(ge=0)]
Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]


def _aware_time(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC)


class _Data(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class _Change(_Data):
    change_id: Text
    pr: Text | None = None


class _AuditChange(_Change):
    commit: Text | None = None
    recipe: Text | None = None
    environment: Text | None = None
    attempt_id: Text | None = None


class _Review(_AuditChange):
    reviewer: Literal["human", "agent"]
    seconds: Seconds
    uncategorized_corrections: Count = 0


class _Correction(_AuditChange):
    category: Text


class _Enforcement(_Data):
    category: Text
    rung: Literal[1, 2]
    check: Text
    reference: Text

    @field_validator("rung", mode="before")
    @classmethod
    def integer_rung(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("rung must be integer 1 or 2")
        return value


class _Test(_Data):
    test_id: Text
    commit: Text
    recipe: Text
    environment: Text
    outcome: Literal["pass", "fail"]


class _CI(_Change):
    seconds: Seconds
    outcome: Literal["pass", "fail"]


class _Check(_CI):
    check_id: Text
    commit: Text
    recipe: Text
    environment: Text


class _Mutation(_Data):
    killed: Count
    eligible: Count
    excluded: Count
    invalid: Count = 0
    timed_out: Count = 0

    @model_validator(mode="after")
    def valid_counts(self) -> Self:
        if self.killed > self.eligible:
            raise ValueError("killed cannot exceed eligible")
        return self


class _Deploy(_Data):
    deployment_id: Text
    production: bool
    failed: bool
    pr: Text | None = None


class _Rollback(_Data):
    deployment_id: Text


class _Incident(_Data):
    incident_id: Text
    pr: Text | None = None
    deployment_id: Text | None = None

    @model_validator(mode="after")
    def linked(self) -> Self:
        if self.pr is None and self.deployment_id is None:
            raise ValueError("incident requires pr or deployment_id")
        return self


class _Restoration(_Data):
    incident_id: Text


class _PR(_Change):
    pr: Text


class _GitHubPR(_Data):
    pr: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*$")]
    created_at: datetime
    state: Literal["open", "closed", "merged"]
    draft: bool
    head_sha: Text
    commits: Count
    additions: Count
    deletions: Count
    changed_files: Count
    review_count: Count
    changes_requested: Count
    reviewed_heads: list[Text]
    first_review_at: datetime | None = None
    merged_at: datetime | None = None
    closed_at: datetime | None = None

    @field_validator("created_at", "first_review_at", "merged_at", "closed_at", mode="before")
    @classmethod
    def aware_time(cls, value: Any) -> datetime | None:
        return None if value is None else _aware_time(value)

    @field_validator("reviewed_heads")
    @classmethod
    def distinct_heads(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("reviewed_heads must be distinct")
        return sorted(value)

    @model_validator(mode="after")
    def valid_snapshot(self) -> Self:
        if (
            self.changes_requested > self.review_count
            or len(self.reviewed_heads) > self.review_count
        ):
            raise ValueError("review counts cannot exceed review_count")
        for value in (self.first_review_at, self.merged_at, self.closed_at):
            if value is not None and value < self.created_at:
                raise ValueError("PR activity cannot precede created_at")
        return self


class _Coverage(_Data):
    metric: Literal["rollback", "enforcement"]
    start: datetime
    end: datetime

    @field_validator("start", "end", mode="before")
    @classmethod
    def aware_time(cls, value: Any) -> datetime:
        return _aware_time(value)

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if self.start >= self.end:
            raise ValueError("coverage start must be before end")
        return self


_DATA_MODELS: dict[str, type[_Data]] = {
    "review": _Review,
    "correction": _Correction,
    "enforcement": _Enforcement,
    "test": _Test,
    "check": _Check,
    "ci": _CI,
    "mutation": _Mutation,
    "deploy": _Deploy,
    "rollback": _Rollback,
    "incident": _Incident,
    "restoration": _Restoration,
    "pr": _PR,
    "coverage": _Coverage,
    "github_pr": _GitHubPR,
}


class MetricRecord(BaseModel):
    """One immutable observation, identified by source and its stable source ID.

    ``at`` is the event time (review/check end, completed deployment, incident
    start, or restoration). A deploy record describes a completed deployment;
    pending/cancelled runs do not belong in that denominator. Mutation counts
    are disjoint: eligible includes killed and survived; excluded, invalid,
    and timed_out are reported separately and are not scored.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    source: Text
    id: Text
    at: datetime
    kind: Literal[
        "review",
        "correction",
        "enforcement",
        "test",
        "check",
        "ci",
        "mutation",
        "deploy",
        "rollback",
        "incident",
        "restoration",
        "pr",
        "coverage",
        "github_pr",
    ]
    simulated: bool = False
    data: dict[str, Any]

    @field_validator("at", mode="before")
    @classmethod
    def aware_time(cls, value: Any) -> datetime:
        return _aware_time(value)

    @model_validator(mode="after")
    def validate_data(self) -> Self:
        parsed = _DATA_MODELS[self.kind].model_validate(self.data)
        if isinstance(parsed, _Coverage) and parsed.end > self.at:
            raise ValueError("coverage end cannot be after the observation time")
        if isinstance(parsed, _GitHubPR):
            for value in (
                parsed.created_at,
                parsed.first_review_at,
                parsed.merged_at,
                parsed.closed_at,
            ):
                if value is not None and value > self.at:
                    raise ValueError("PR timestamps cannot be after snapshot collection")
        object.__setattr__(self, "data", parsed.model_dump(mode="json", exclude_none=True))
        return self


def _records(store: Store) -> list[MetricRecord]:
    return [
        MetricRecord.model_validate(json.loads(row["payload"]))
        for row in store.connection.execute(
            "SELECT payload FROM events WHERE kind = 'metric_reported' ORDER BY id"
        )
    ]


def import_metrics(store: Store, records: list[dict[str, Any]]) -> dict[str, int]:
    """Validate and import a whole batch, or leave the database unchanged.

    Uses Store's transaction/event primitives together because record_event()
    starts a transaction per record. BEGIN IMMEDIATE makes the identity check
    and append atomic across separate importer processes.
    """
    parsed = [MetricRecord.model_validate(record) for record in records]
    added = 0
    duplicates = 0
    with store._transaction():
        store.connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS metric_identity ON events "
            "(json_extract(payload, '$.source'), json_extract(payload, '$.id')) "
            "WHERE kind = 'metric_reported'"
        )
        for record in parsed:
            payload = record.model_dump(mode="json")
            existing = store.connection.execute(
                "SELECT payload FROM events WHERE kind = 'metric_reported' "
                "AND json_extract(payload, '$.source') = ? "
                "AND json_extract(payload, '$.id') = ?",
                (record.source, record.id),
            ).fetchone()
            if existing is not None:
                if json.loads(existing["payload"]) != payload:
                    raise ValueError(f"conflicting metric identity: {record.source}/{record.id}")
                duplicates += 1
                continue
            store._event("metric_reported", payload, store._now())
            added += 1
    return {"imported": added, "duplicates": duplicates}


def _meta(current: list[MetricRecord], history: list[MetricRecord]) -> dict[str, Any]:
    latest = max((record.at for record in history), default=None)
    return {
        "status": "available" if current else "stale" if history else "missing",
        "samples": len(current),
        "sources": sorted({record.source for record in current}),
        "latest_at": latest.isoformat() if latest else None,
    }


def _ratio(numerator: int, denominator: int, scale: int = 1) -> float | None:
    return numerator / denominator * scale if denominator else None


def _coverage(
    records: list[MetricRecord],
    metric: str,
    start: datetime,
    end: datetime,
    observed: bool,
) -> dict[str, Any]:
    records = [r for r in records if r.data["metric"] == metric]
    intervals = [
        (max(_aware_time(r.data["start"]), start), min(_aware_time(r.data["end"]), end), r)
        for r in records
    ]
    intervals = [item for item in intervals if item[0] < item[1]]
    cursor = start
    for left, right, _ in sorted(intervals, key=lambda item: (item[0], item[1])):
        if left > cursor:
            break
        cursor = max(cursor, right)
    full = cursor >= end
    latest = max((_aware_time(r.data["end"]) for r in records), default=None)
    return {
        "coverage": "complete"
        if full
        else "reported"
        if observed
        else "partial"
        if intervals
        else "missing",
        "coverage_samples": len(intervals),
        "coverage_sources": sorted({r.source for _, _, r in intervals}),
        "coverage_latest_at": latest.isoformat() if latest else None,
    }


def _github_report(current: list[MetricRecord], history: list[MetricRecord]) -> dict[str, Any]:
    latest: dict[str, MetricRecord] = {}
    samples: dict[str, int] = defaultdict(int)
    heads: dict[str, set[str]] = defaultdict(set)
    reviewed: dict[str, set[str]] = defaultdict(set)
    sources: dict[str, set[str]] = defaultdict(set)
    for record in history:
        pr = record.data["pr"]
        heads[pr].add(record.data["head_sha"])
        heads[pr].update(record.data["reviewed_heads"])
        reviewed[pr].update(record.data["reviewed_heads"])
        sources[pr].add(record.source)
    for record in current:
        pr = record.data["pr"]
        latest[pr] = record
        samples[pr] += 1
    rows: list[dict[str, Any]] = []
    for pr, record in sorted(latest.items()):
        row = dict(record.data)
        for timestamp in ("first_review_at", "merged_at", "closed_at"):
            row.setdefault(timestamp, None)
        created = _aware_time(row["created_at"])
        for event, field in (
            ("first_review_at", "first_review_seconds"),
            ("merged_at", "merge_seconds"),
        ):
            row[field] = (
                (_aware_time(row[event]) - created).total_seconds()
                if row[event] is not None
                else None
            )
        row.update(
            {
                "revision_count": max(0, len(heads[pr]) - 1),
                "review_rounds": len(reviewed[pr]),
                "basis": "observed_distinct_heads",
                "completeness": "lower_bound",
                "observed_heads": sorted(heads[pr]),
                "sources": sorted(sources[pr]),
                "samples": samples[pr],
                "latest_at": record.at.isoformat(),
            }
        )
        rows.append(row)
    totals = {
        field: sum(row[field] for row in rows)
        for field in (
            "revision_count",
            "review_rounds",
            "review_count",
            "changes_requested",
            "commits",
            "additions",
            "deletions",
            "changed_files",
        )
    }
    totals.update(
        {
            state: sum(row["state"] == state for row in rows)
            for state in ("open", "closed", "merged")
        }
    )
    totals["draft"] = sum(row["draft"] for row in rows)
    means: dict[str, float | None] = {}
    for field in (
        "revision_count",
        "review_rounds",
        "commits",
        "first_review_seconds",
        "merge_seconds",
    ):
        values = [row[field] for row in rows if row[field] is not None]
        means[field] = sum(values) / len(values) if values else None
    return {
        **_meta(current, history),
        "pr_count": len(rows),
        "prs": rows,
        "totals": totals,
        "means": means,
        "first_review_samples": sum(row["first_review_seconds"] is not None for row in rows),
        "merge_samples": sum(row["merge_seconds"] is not None for row in rows),
        "basis": "observed_distinct_heads",
        "completeness": "lower_bound",
    }


def metrics_report(
    store: Store,
    days: int = 28,
    now: datetime | None = None,
    include_simulated: bool = False,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Summarize event-time observations, with explicit denominators and gaps.

    Incidents and prevention rules retain their history so an older unresolved
    incident remains visible and an existing check can cover a recent category.
    ``now`` ends the event window. ``observed_at`` limits confirmation time and
    defaults to the current UTC clock, allowing coverage confirmed after an
    earlier window closed. Pass both times for a reproducible snapshot.
    Metrics are reported observations, not a verified quality or approval score.
    """
    if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
        raise ValueError("days must be a positive integer")
    observed = observed_at or datetime.now(UTC)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("observed_at must include a timezone")
    observed = observed.astimezone(UTC)
    end = now or observed
    if end.tzinfo is None or end.utcoffset() is None:
        raise ValueError("now must include a timezone")
    end = end.astimezone(UTC)
    start = end - timedelta(days=days)
    saved = _records(store)
    all_records = [
        r
        for r in saved
        if (include_simulated or not r.simulated)
        and r.at <= observed
        and (r.kind == "coverage" or r.at <= end)
    ]
    history: dict[str, list[MetricRecord]] = defaultdict(list)
    current: dict[str, list[MetricRecord]] = defaultdict(list)
    for record in sorted(all_records, key=lambda r: (r.at, r.source, r.id)):
        history[record.kind].append(record)
        if start <= record.at <= end:
            current[record.kind].append(record)
    result: dict[str, Any] = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "observed_at": observed.isoformat(),
        "days": days,
        "provenance": "reported",
        "includes_simulated": include_simulated,
        "excluded_simulated": sum(r.simulated and start <= r.at <= end for r in saved)
        if not include_simulated
        else 0,
        "future_records": sum(r.at > observed for r in saved),
    }
    mappings: dict[str, set[str]] = defaultdict(set)
    for record in all_records:
        if "change_id" in record.data and "pr" in record.data:
            mappings[record.data["change_id"]].add(record.data["pr"])

    def metadata(kind: str) -> dict[str, Any]:
        return _meta(current[kind], history[kind])

    review: dict[str, Any] = {}
    for reviewer in ("human", "agent"):
        records = [r for r in current["review"] if r.data["reviewer"] == reviewer]
        previous = [r for r in history["review"] if r.data["reviewer"] == reviewer]
        by_change: dict[str, float] = defaultdict(float)
        by_pr: dict[str, float] = defaultdict(float)
        unmapped = 0
        for record in records:
            change = record.data["change_id"]
            minutes = record.data["seconds"] / 60
            by_change[change] += minutes
            targets = mappings[change]
            if len(targets) == 1:
                by_pr[next(iter(targets))] += minutes
            else:
                unmapped += 1
        review[reviewer] = {
            **_meta(records, previous),
            "minutes": sum(by_change.values()) if records else None,
            "changes": len(by_change),
            "prs": len(by_pr),
            "minutes_per_change": sum(by_change.values()) / len(by_change) if by_change else None,
            "minutes_per_pr": sum(by_pr.values()) / len(by_pr) if by_pr else None,
            "by_change": dict(sorted(by_change.items())),
            "by_pr": dict(sorted(by_pr.items())),
            "unmapped_samples": unmapped,
        }
    result["review"] = review
    result["github"] = _github_report(current["github_pr"], history["github_pr"])

    counts: dict[str, int] = defaultdict(int)
    seen_corrections: set[tuple[str, str]] = set()
    occurrences: list[MetricRecord] = []
    repeated = 0
    for record in history["correction"]:
        category = record.data["category"]
        identity = (category, record.data["change_id"])
        if identity in seen_corrections:
            continue
        seen_corrections.add(identity)
        if record.at >= start:
            occurrences.append(record)
            if counts[category]:
                repeated += 1
        counts[category] += 1
    categories = {r.data["category"] for r in occurrences}
    uncategorized = sum(r.data["uncategorized_corrections"] for r in current["review"])
    enforced = {r.data["category"] for r in history["enforcement"]} & categories
    enforcement_feed = _coverage(history["coverage"], "enforcement", start, end, bool(enforced))
    enforcement_known = enforcement_feed["coverage"] in {"complete", "reported"}
    result["corrections"] = {
        **metadata("correction"),
        "repeated": repeated,
        "occurrences": len(occurrences),
        "repeat_rate": _ratio(repeated, len(occurrences)),
        "uncategorized": uncategorized,
        "coverage": "incomplete" if uncategorized else "reported categories only",
        "categories": len(categories),
        "enforced_categories": len(enforced),
        "enforced_share": _ratio(len(enforced), len(categories)) if enforcement_known else None,
        "enforcement_coverage": enforcement_feed["coverage"],
        "enforcement_coverage_samples": enforcement_feed["coverage_samples"],
        "enforcement_coverage_latest_at": enforcement_feed["coverage_latest_at"],
        "enforcement_sources": sorted(
            {r.source for r in history["enforcement"] if r.data["category"] in enforced}
            | set(enforcement_feed["coverage_sources"])
        ),
        "definition": (
            "Later changes with the same category / distinct category-change pairs in window"
        ),
    }
    groups: dict[tuple[str, ...], list[MetricRecord]] = defaultdict(list)
    for record in current["test"]:
        key = tuple(record.data[field] for field in ("test_id", "commit", "recipe", "environment"))
        groups[key].append(record)
    repeated_groups = [records for records in groups.values() if len(records) >= 2]
    flaky = sum(len({r.data["outcome"] for r in records}) > 1 for records in repeated_groups)
    result["tests"] = {
        **metadata("test"),
        "groups": len(groups),
        "repeated_groups": len(repeated_groups),
        "flaky_groups": flaky,
        "flaky_rate": _ratio(flaky, len(repeated_groups)),
        "definition": (
            "Matching test/commit/recipe/environment groups with pass and fail / repeated groups"
        ),
    }
    for kind in ("check", "ci"):
        durations = [r.data["seconds"] for r in current[kind]]
        result[kind] = {
            **metadata(kind),
            "seconds": sum(durations) if durations else None,
            "mean_seconds": sum(durations) / len(durations) if durations else None,
            "failed": sum(r.data["outcome"] == "fail" for r in current[kind]),
        }
    weeks: dict[str, dict[str, Any]] = {}
    for record in current["mutation"]:
        week = (record.at - timedelta(days=record.at.weekday())).date().isoformat()
        if week not in weeks:
            weeks[week] = {
                field: 0 for field in ("killed", "eligible", "excluded", "invalid", "timed_out")
            }
            weeks[week].update({"samples": 0, "sources": set()})
        bucket = weeks[week]
        for field in ("killed", "eligible", "excluded", "invalid", "timed_out"):
            bucket[field] += record.data[field]
        bucket["samples"] += 1
        bucket["sources"].add(record.source)
    for bucket in weeks.values():
        bucket["score"] = _ratio(bucket["killed"], bucket["eligible"])
        bucket["sources"] = sorted(bucket["sources"])
    result["mutation"] = {**metadata("mutation"), "weeks": weeks}

    production = {r.data["deployment_id"] for r in history["deploy"] if r.data["production"]}
    deployed = {r.data["deployment_id"] for r in current["deploy"] if r.data["production"]}
    failed = {r.data["deployment_id"] for r in history["deploy"] if r.data["failed"]}
    failed.update(r.data["deployment_id"] for r in history["incident"] if "deployment_id" in r.data)
    rolled_back = [r for r in current["rollback"] if r.data["deployment_id"] in production]
    failed.update(
        r.data["deployment_id"]
        for r in history["rollback"]
        if r.data["deployment_id"] in production
    )
    deployment_records = [r for r in current["deploy"] if r.data["production"]]
    deployment_history = [r for r in history["deploy"] if r.data["production"]]
    result["deployments"] = {
        **_meta(deployment_records, deployment_history),
        "completed": len(deployed),
        "failed": len(deployed & failed),
        "change_failure_rate": _ratio(len(deployed & failed), len(deployed)),
        "failure_sources": sorted(
            {
                r.source
                for kind in ("deploy", "incident", "rollback")
                for r in history[kind]
                if r.data.get("deployment_id") in deployed & failed
            }
        ),
    }
    rollback_feed = _coverage(history["coverage"], "rollback", start, end, bool(rolled_back))
    rollback_known = rollback_feed["coverage"] in {"complete", "reported"}
    rollback_meta = metadata("rollback")
    if rollback_feed["coverage_samples"]:
        rollback_meta["status"] = "available"
    elif rollback_feed["coverage_latest_at"] and rollback_meta["status"] == "missing":
        rollback_meta["status"] = "stale"
    rollback_meta["sources"] = sorted(
        set(rollback_meta["sources"]) | set(rollback_feed["coverage_sources"])
    )
    rollback_meta["latest_at"] = max(
        (
            value
            for value in (rollback_meta["latest_at"], rollback_feed["coverage_latest_at"])
            if value
        ),
        default=None,
    )
    result["rollbacks"] = {
        **rollback_meta,
        **rollback_feed,
        "linked_production_events": len(rolled_back),
        "unlinked_or_nonproduction_events": len(current["rollback"]) - len(rolled_back),
        "completed_production_deployments": len(deployed),
        "per_100_deployments": _ratio(len(rolled_back), len(deployed), 100)
        if rollback_known
        else None,
        "definition": (
            "Production rollback events in window / "
            "completed production deployments in window * 100"
        ),
    }
    incidents: dict[str, MetricRecord] = {}
    for record in history["incident"]:
        incidents.setdefault(record.data["incident_id"], record)
    restored: dict[str, MetricRecord] = {}
    invalid_restorations = 0
    for record in history["restoration"]:
        incident_id = record.data["incident_id"]
        if incident_id not in incidents or record.at < incidents[incident_id].at:
            invalid_restorations += 1
        else:
            restored.setdefault(incident_id, record)
    new_incidents = [r for r in incidents.values() if r.at >= start]
    restored_in_window = {key: r for key, r in restored.items() if r.at >= start}
    restoration_seconds = [
        (r.at - incidents[key].at).total_seconds() for key, r in restored_in_window.items()
    ]
    deploy_prs = {
        r.data["deployment_id"]: r.data["pr"] for r in history["deploy"] if "pr" in r.data
    }
    traced = sum("pr" in r.data or r.data.get("deployment_id") in deploy_prs for r in new_incidents)
    result["incidents"] = {
        **_meta(new_incidents, list(incidents.values())),
        "new": len(new_incidents),
        "escaped_defects": traced,
        "deployment_only": len(new_incidents) - traced,
        "unresolved": [
            {"incident_id": key, "at": r.at.isoformat(), **r.data}
            for key, r in incidents.items()
            if key not in restored
        ],
        "restored": len(restored_in_window),
        "mean_restore_seconds": sum(restoration_seconds) / len(restoration_seconds)
        if restoration_seconds
        else None,
        "restoration_sources": sorted({r.source for r in restored_in_window.values()}),
        "invalid_or_unlinked_restorations": invalid_restorations,
    }
    result["restoration"] = {
        **metadata("restoration"),
        "linked_incidents": len(restored_in_window),
        "mean_seconds": sum(restoration_seconds) / len(restoration_seconds)
        if restoration_seconds
        else None,
        "intervals": [
            {"incident_id": key, "seconds": (r.at - incidents[key].at).total_seconds()}
            for key, r in restored_in_window.items()
        ],
        "invalid_or_unlinked_records": invalid_restorations,
    }
    return result
