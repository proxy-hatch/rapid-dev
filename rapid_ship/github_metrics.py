"""Read GitHub observations without changing a repository or inventing review time."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urlsplit

from .metrics import MetricRecord
from .trust.github import Transport, gh_request


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"GitHub {label} must be an object")
    return value


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"GitHub {label} must be an integer >= {minimum}")
    return int(value)


def _time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"GitHub {label} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"GitHub {label} must be a timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"GitHub {label} must include a timezone")
    return parsed.astimezone(UTC)


def _sha(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value):
        raise ValueError("GitHub commit must be a full hexadecimal SHA")
    return value.lower()


def _rows(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError(f"GitHub {label} must be an array with at most 100 entries")
    return [_object(item, label) for item in value]


class _API:
    def __init__(self, repository: str, request: Transport, max_pages: int) -> None:
        self.prefix = f"repos/{repository}/"
        self.request = request
        self.max_pages = max_pages

    def get(self, path: str) -> Any:
        return self.request("GET", self.prefix + path, None)

    def pages(
        self, path: str, query: dict[str, str] | None = None, *, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for page in range(1, self.max_pages + 1):
            params = dict(query or {}, per_page="100", page=str(page))
            rows = _rows(self.get(path + "?" + urlencode(params)), path)
            old = False
            for row in rows:
                if since is not None and _time(row.get("updated_at"), "updated_at") < since:
                    old = True
                else:
                    result.append(row)
            if len(rows) < 100 or old:
                return result
        raise ValueError(f"GitHub {path} exceeded the page budget; narrow the date window")

    def counted(
        self, path: str, key: str, query: dict[str, str] | None = None, *, cap: int | None = None
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        expected: int | None = None
        for page in range(1, self.max_pages + 1):
            params = dict(query or {}, per_page="100", page=str(page))
            response = _object(self.get(path + "?" + urlencode(params)), path)
            count = _integer(response.get("total_count"), "total_count")
            if response.get("incomplete_results") is True:
                raise ValueError(f"GitHub {path} reported incomplete results")
            if cap is not None and count >= cap:
                raise ValueError(f"GitHub {path} reached its {cap}-result cap; narrow the window")
            if expected is not None and count != expected:
                raise ValueError(f"GitHub {path} changed while paging; retry the collection")
            expected = count
            rows = _rows(response.get(key), key)
            result.extend(rows)
            if len(result) == count:
                return result
            if len(result) > count or len(rows) < 100:
                raise ValueError(f"GitHub {path} returned an incomplete or inconsistent page")
        raise ValueError(f"GitHub {path} exceeded the page budget; narrow the date window")


def _unique(rows: list[dict[str, Any]], key: str, label: str) -> dict[int, dict[str, Any]]:
    values: dict[int, dict[str, Any]] = {}
    for row in rows:
        identifier = _integer(row.get(key), key, 1)
        if identifier in values:
            raise ValueError(f"GitHub {label} repeated an ID while paging; retry the collection")
        values[identifier] = row
    return values


def _pr_snapshot(
    api: _API, repository: str, number: int, timestamps: list[datetime]
) -> dict[str, Any]:
    detail = _object(api.get(f"pulls/{number}"), "pull request")
    if _integer(detail.get("number"), "PR number", 1) != number:
        raise ValueError("GitHub returned a different pull request")
    state = detail.get("state")
    if (
        not isinstance(state, str)
        or state not in {"open", "closed"}
        or type(detail.get("draft")) is not bool
    ):
        raise ValueError("GitHub pull request state/draft is invalid")
    created = _time(detail.get("created_at"), "created_at")
    updated = _time(detail.get("updated_at"), "updated_at")
    if updated < created:
        raise ValueError("GitHub pull request update precedes creation")
    dates: dict[str, str | None] = {}
    for key in ("closed_at", "merged_at"):
        if key not in detail:
            raise ValueError(f"GitHub pull request is missing {key}")
        value = detail[key]
        dates[key] = None if value is None else _time(value, key).isoformat()
    if (state == "open" and any(dates.values())) or (state == "closed" and not dates["closed_at"]):
        raise ValueError("GitHub pull request state and close time disagree")
    reviews = _unique(api.pages(f"pulls/{number}/reviews"), "id", "reviews")
    submitted: list[datetime] = []
    heads: set[str] = set()
    changes_requested = 0
    for review in reviews.values():
        review_state = review.get("state")
        if review_state == "PENDING":
            continue
        if not isinstance(review_state, str) or review_state not in {
            "APPROVED",
            "CHANGES_REQUESTED",
            "COMMENTED",
            "DISMISSED",
        }:
            raise ValueError("GitHub returned an unknown submitted review state")
        submitted_at = _time(review.get("submitted_at"), "submitted_at")
        if submitted_at < created:
            raise ValueError("GitHub review precedes pull request creation")
        submitted.append(submitted_at)
        heads.add(_sha(review.get("commit_id")))
        changes_requested += review_state == "CHANGES_REQUESTED"
    timestamps.extend([created, updated, *submitted])
    return {
        "pr": f"{repository}#{number}",
        "created_at": created.isoformat(),
        "state": "merged" if dates["merged_at"] else state,
        "draft": detail["draft"],
        "head_sha": _sha(_object(detail.get("head"), "head").get("sha")),
        "commits": _integer(detail.get("commits"), "commits"),
        "additions": _integer(detail.get("additions"), "additions"),
        "deletions": _integer(detail.get("deletions"), "deletions"),
        "changed_files": _integer(detail.get("changed_files"), "changed_files"),
        "review_count": len(submitted),
        "changes_requested": changes_requested,
        "reviewed_heads": sorted(heads),
        "first_review_at": min(submitted).isoformat() if submitted else None,
        **dates,
    }


def _attempt(
    api: _API, repository: str, run_id: int, attempt: int, warnings: list[str]
) -> dict[str, Any] | None:
    path = f"actions/runs/{run_id}/attempts/{attempt}"
    run = _object(api.get(path), "workflow attempt")
    if (
        _integer(run.get("id"), "run ID", 1) != run_id
        or _integer(run.get("run_attempt"), "run attempt", 1) != attempt
    ):
        raise ValueError("GitHub returned a different workflow attempt")
    status, conclusion = run.get("status"), run.get("conclusion")
    if not isinstance(status, str) or not status:
        raise ValueError("GitHub workflow attempt is missing status")
    if status != "completed":
        warnings.append(f"Skipped workflow {run_id} attempt {attempt}: {status}.")
        return None
    if not isinstance(conclusion, str) or not conclusion:
        raise ValueError("GitHub completed workflow is missing conclusion")
    if conclusion not in {"success", "failure", "timed_out"}:
        warnings.append(f"Skipped workflow {run_id} attempt {attempt}: {conclusion}.")
        return None
    sha = _sha(run.get("head_sha"))
    created = _time(run.get("created_at"), "workflow created_at")
    links = _unique(_rows(run.get("pull_requests"), "workflow pull_requests"), "number", "PR links")
    jobs = _unique(api.counted(path + "/jobs", "jobs"), "id", "jobs")
    starts: list[datetime] = []
    ends: list[datetime] = []
    for job in jobs.values():
        if job.get("status") != "completed":
            raise ValueError("GitHub completed workflow has an incomplete job")
        job_conclusion = job.get("conclusion")
        if job_conclusion == "skipped":
            continue
        if not isinstance(job_conclusion, str) or job_conclusion not in {
            "success",
            "failure",
            "neutral",
            "cancelled",
            "timed_out",
            "action_required",
            "startup_failure",
            "stale",
        }:
            raise ValueError("GitHub completed job has an unknown conclusion")
        started = _time(job.get("started_at"), "job started_at")
        ended = _time(job.get("completed_at"), "job completed_at")
        if started < created or ended < started:
            raise ValueError("GitHub job timestamps are inconsistent")
        starts.append(started)
        ends.append(ended)
    if not starts:
        warnings.append(
            f"Skipped workflow {run_id} attempt {attempt}: no completed, non-skipped jobs."
        )
        return None
    data: dict[str, Any] = {
        "change_id": f"github:{repository}:{sha}",
        "seconds": (max(ends) - min(starts)).total_seconds(),
        "outcome": "pass" if conclusion == "success" else "fail",
    }
    if len(links) == 1:
        number, link = next(iter(links.items()))
        url = link.get("url")
        parsed = urlsplit(url) if isinstance(url, str) else None
        expected_path = f"/repos/{repository}/pulls/{number}"
        if (
            parsed is not None
            and parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.path.lower().endswith(expected_path.lower())
        ):
            data["pr"] = f"{repository}#{number}"
        else:
            warnings.append(
                f"Workflow {run_id} attempt {attempt} PR link does not identify this repository; "
                "kept unassigned."
            )
    elif len(links) > 1:
        warnings.append(f"Workflow {run_id} attempt {attempt} links several PRs; kept unassigned.")
    return {
        "source": f"github:{repository}",
        "id": f"workflow:{run_id}:attempt:{attempt}",
        "at": max(ends).isoformat(),
        "kind": "ci",
        "data": data,
    }


def collect_github_metrics(
    repository: str,
    request: Transport = gh_request,
    *,
    now: datetime | None = None,
    days: int = 28,
    max_pages: int = 100,
) -> dict[str, Any]:
    """Return one complete read-only batch, or raise before the caller imports it.

    PR observations describe current API state. Workflow identities use attempt
    numbers and job completion times so later reruns do not rewrite old records.
    """
    if not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", repository
    ) or repository.split("/")[-1] in {".", ".."}:
        raise ValueError("Repository must have the form owner/repository")
    _integer(days, "days", 1)
    _integer(max_pages, "max_pages", 1)
    cutoff = now or datetime.now(UTC)
    if not isinstance(cutoff, datetime) or cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("Collection time must include a timezone")
    cutoff = cutoff.astimezone(UTC)
    start = cutoff - timedelta(days=days)
    api = _API(repository, request, max_pages)
    order = {"sort": "updated", "direction": "desc"}
    recent = _unique(
        api.pages("pulls", {"state": "all", **order}, since=start), "number", "pull requests"
    )
    opened = _unique(api.pages("pulls", {"state": "open", **order}), "number", "open PRs")
    numbers = sorted(recent.keys() | opened.keys())
    timestamps: list[datetime] = []
    snapshots = [_pr_snapshot(api, repository, number, timestamps) for number in numbers]
    runs = _unique(
        api.counted(
            "actions/runs",
            "workflow_runs",
            {"status": "completed", "created": f"{start.isoformat()}..{cutoff.isoformat()}"},
            cap=1000,
        ),
        "id",
        "workflow runs",
    )
    warnings = [
        "Workflow discovery uses run creation dates; reruns of older runs are not included. "
        "Use a longer --days window to include those runs."
    ]
    records: list[dict[str, Any]] = []
    for run_id, run in runs.items():
        created = _time(run.get("created_at"), "workflow created_at")
        if not start <= created <= cutoff:
            raise ValueError("GitHub workflow is outside the requested creation window")
        if run.get("status") != "completed":
            raise ValueError("GitHub completed-workflow listing includes an unfinished run")
        attempts = _integer(run.get("run_attempt"), "run attempt", 1)
        if attempts > max_pages * 100:
            raise ValueError("GitHub workflow attempts exceed the collection budget")
        for attempt in range(1, attempts + 1):
            record = _attempt(api, repository, run_id, attempt, warnings)
            if record is not None:
                records.append(record)
    observed = cutoff if now is not None else datetime.now(UTC)
    if any(timestamp > observed for timestamp in timestamps):
        raise ValueError("GitHub timestamp is later than the collection time")
    snapshot_records: list[dict[str, Any]] = []
    for number, data in zip(numbers, snapshots, strict=True):
        payload = {"at": observed.isoformat(), "data": data}
        identity = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        snapshot_records.append(
            {
                "source": f"github:{repository}",
                "id": f"pr:{number}:{identity}",
                "kind": "github_pr",
                **payload,
            }
        )
    all_records = snapshot_records + records
    for record in all_records:
        parsed = MetricRecord.model_validate(record)
        if parsed.at > observed:
            raise ValueError("GitHub event is later than the collection time")
    return {
        "records": all_records,
        "repository": repository,
        "warnings": warnings,
        "pull_requests": len(snapshots),
        "workflow_attempts": len(records),
        "workflow_discovery": {
            "created_since": start.isoformat(),
            "older_reruns_included": False,
        },
    }
