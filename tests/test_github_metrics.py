"""GitHub imports observe activity without inventing work or human time."""

from copy import deepcopy
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest

from agentic_engineering.github_metrics import collect_github_metrics

NOW = datetime(2026, 10, 10, tzinfo=UTC)
SHA = "a" * 40
OTHER_SHA = "b" * 40


def pr(number=1, **changes):
    value = {
        "number": number,
        "state": "open",
        "draft": False,
        "created_at": "2026-09-20T00:00:00Z",
        "updated_at": "2026-10-09T00:00:00Z",
        "closed_at": None,
        "merged_at": None,
        "head": {"sha": SHA},
        "commits": 3,
        "additions": 20,
        "deletions": 5,
        "changed_files": 2,
    }
    value.update(changes)
    return value


def review(identifier=1, state="APPROVED", **changes):
    value = {
        "id": identifier,
        "state": state,
        "submitted_at": "2026-10-08T00:00:00Z",
        "commit_id": SHA,
    }
    value.update(changes)
    return value


def run(identifier=9, attempt=1, **changes):
    value = {
        "id": identifier,
        "run_attempt": attempt,
        "status": "completed",
        "conclusion": "success",
        "head_sha": SHA,
        "created_at": "2026-10-08T00:00:00Z",
        "pull_requests": [{"number": 1, "url": "https://api.github.com/repos/owner/repo/pulls/1"}],
    }
    value.update(changes)
    return value


def job(identifier=10, **changes):
    value = {
        "id": identifier,
        "status": "completed",
        "conclusion": "success",
        "started_at": "2026-10-08T00:01:00Z",
        "completed_at": "2026-10-08T00:03:00Z",
    }
    value.update(changes)
    return value


class API:
    def __init__(self):
        self.calls = []
        self.all_prs = [pr()]
        self.open_prs = [pr()]
        self.details = {1: pr()}
        self.reviews = {1: [review()]}
        self.runs = [run()]
        self.attempts = {(9, 1): run()}
        self.jobs = {(9, 1): [job()]}
        self.override = None

    def __call__(self, method, endpoint, payload):
        assert method == "GET" and payload is None
        self.calls.append(endpoint)
        if self.override:
            value = self.override(endpoint)
            if value is not None:
                return value
        parsed = urlsplit(endpoint)
        path = parsed.path.removeprefix("repos/owner/repo/")
        query = parse_qs(parsed.query)
        page = int(query.get("page", ["1"])[0])

        def portion(rows):
            return deepcopy(rows[(page - 1) * 100 : page * 100])

        if path == "pulls":
            return portion(self.open_prs if query["state"] == ["open"] else self.all_prs)
        if path.startswith("pulls/"):
            parts = path.split("/")
            number = int(parts[1])
            return (
                portion(self.reviews[number]) if len(parts) == 3 else deepcopy(self.details[number])
            )
        if path == "actions/runs":
            return {"total_count": len(self.runs), "workflow_runs": portion(self.runs)}
        parts = path.split("/")
        key = (int(parts[2]), int(parts[4]))
        if len(parts) == 6:
            return {"total_count": len(self.jobs[key]), "jobs": portion(self.jobs[key])}
        return deepcopy(self.attempts[key])


def test_collects_pr_snapshot_and_ci_without_inventing_human_time():
    api = API()
    result = collect_github_metrics("owner/repo", api, now=NOW)
    assert result["pull_requests"] == result["workflow_attempts"] == 1
    assert result["workflow_discovery"] == {
        "created_since": "2026-09-12T00:00:00+00:00",
        "older_reruns_included": False,
    }
    assert len(result["warnings"]) == 1 and "older runs" in result["warnings"][0]
    snapshot, ci = result["records"]
    assert snapshot["kind"] == "github_pr"
    assert snapshot["data"]["reviewed_heads"] == [SHA]
    assert snapshot["data"]["review_count"] == 1
    assert ci["kind"] == "ci"
    assert ci["data"] == {
        "change_id": f"github:owner/repo:{SHA}",
        "pr": "owner/repo#1",
        "seconds": 120.0,
        "outcome": "pass",
    }
    assert ci["at"] == "2026-10-08T00:03:00+00:00"
    assert all(record["kind"] != "review" for record in result["records"])
    assert collect_github_metrics("owner/repo", api, now=NOW) == result


def test_old_open_pr_is_included_without_old_closed_prs():
    api = API()
    old = pr(2, created_at="2020-01-01T00:00:00Z", updated_at="2020-01-02T00:00:00Z")
    api.all_prs.append(pr(3, state="closed", updated_at="2020-01-02T00:00:00Z"))
    api.open_prs.append(old)
    api.details[2], api.reviews[2] = old, []
    result = collect_github_metrics("owner/repo", api, now=NOW)
    assert result["pull_requests"] == 2
    assert [r["data"]["pr"] for r in result["records"] if r["kind"] == "github_pr"] == [
        "owner/repo#1",
        "owner/repo#2",
    ]
    assert not any("pulls/3" in call for call in api.calls)


def test_reviews_paginate_pending_is_ignored_and_dismissed_is_still_observed():
    api = API()
    api.reviews[1] = [review(i) for i in range(1, 101)] + [
        {"id": 101, "state": "PENDING"},
        review(102, "DISMISSED", commit_id=OTHER_SHA),
        review(103, "CHANGES_REQUESTED"),
    ]
    snapshot = collect_github_metrics("owner/repo", api, now=NOW)["records"][0]
    assert snapshot["data"]["review_count"] == 102
    assert snapshot["data"]["changes_requested"] == 1
    assert snapshot["data"]["reviewed_heads"] == [SHA, OTHER_SHA]
    assert any("reviews?per_page=100&page=2" in call for call in api.calls)


def test_each_retry_attempt_has_one_stable_record_and_job_wall_duration():
    api = API()
    api.runs = [run(attempt=2)]
    api.attempts[9, 1] = run(conclusion="failure")
    api.attempts[9, 2] = run(attempt=2)
    api.jobs[9, 1] = [job(conclusion="failure")]
    api.jobs[9, 2] = [
        job(),
        job(11, started_at="2026-10-08T00:02:00Z", completed_at="2026-10-08T00:05:00Z"),
        job(12, conclusion="skipped", started_at=None, completed_at=None),
    ]
    result = collect_github_metrics("owner/repo", api, now=NOW)
    ci = [r for r in result["records"] if r["kind"] == "ci"]
    assert result["workflow_attempts"] == 2
    assert len({record["id"] for record in ci}) == 2
    assert [(r["data"]["seconds"], r["data"]["outcome"]) for r in ci] == [
        (120.0, "fail"),
        (240.0, "pass"),
    ]
    assert collect_github_metrics("owner/repo", api, now=NOW)["records"] == result["records"]


def test_ambiguous_pr_link_does_not_duplicate_ci():
    api = API()
    api.attempts[9, 1]["pull_requests"] = [{"number": 1}, {"number": 2}]
    result = collect_github_metrics("owner/repo", api, now=NOW)
    ci = [r for r in result["records"] if r["kind"] == "ci"]
    assert len(ci) == 1 and "pr" not in ci[0]["data"]
    assert any("links several PRs" in warning for warning in result["warnings"])


def test_cancelled_attempt_is_skipped_with_warning():
    api = API()
    api.attempts[9, 1]["conclusion"] = "cancelled"
    result = collect_github_metrics("owner/repo", api, now=NOW)
    assert result["workflow_attempts"] == 0
    assert any("cancelled" in warning for warning in result["warnings"])
    assert not any(r["kind"] == "ci" for r in result["records"])


@pytest.mark.parametrize(
    "repository", ["../repo", "owner/../repo", "owner/repo?x=y", "owner/.", "-owner/repo"]
)
def test_invalid_repository_never_calls_api(repository):
    api = API()
    with pytest.raises(ValueError):
        collect_github_metrics(repository, api, now=NOW)
    assert api.calls == []


@pytest.mark.parametrize(
    "change",
    [
        lambda api: api.details[1].update(commits=True),
        lambda api: api.details[1].update(head={"sha": "short"}),
        lambda api: api.reviews[1][0].update(submitted_at="2026-10-08T00:00:00"),
        lambda api: api.jobs[9, 1][0].update(status="in_progress"),
        lambda api: api.jobs[9, 1][0].update(completed_at=None),
        lambda api: api.attempts[9, 1].update(id=123),
    ],
)
def test_malformed_response_fails_entire_collection(change):
    api = API()
    change(api)
    with pytest.raises(ValueError):
        collect_github_metrics("owner/repo", api, now=NOW)


def test_api_failure_propagates_without_returning_partial_records():
    api = API()

    def fail(endpoint):
        if "actions/runs" in endpoint:
            raise RuntimeError("read failed")
        return None

    api.override = fail
    with pytest.raises(RuntimeError, match="read failed"):
        collect_github_metrics("owner/repo", api, now=NOW)


def test_actions_cap_and_incomplete_page_fail():
    for response in [
        {"total_count": 1000, "workflow_runs": [run()]},
        {"total_count": 2, "workflow_runs": [run()]},
        {"total_count": 1},
    ]:
        api = API()
        api.override = lambda endpoint, value=response: (
            value if "actions/runs?" in endpoint else None
        )
        with pytest.raises(ValueError):
            collect_github_metrics("owner/repo", api, now=NOW)


def test_page_budget_cannot_silently_truncate_reviews():
    api = API()
    api.reviews[1] = [review(i) for i in range(1, 101)]
    with pytest.raises(ValueError, match="page"):
        collect_github_metrics("owner/repo", api, now=NOW, max_pages=1)


def test_pulls_and_job_pages_are_fetched():
    api = API()
    api.all_prs = [pr(i) for i in range(1, 102)]
    api.open_prs = api.all_prs
    api.details = {item["number"]: item for item in api.all_prs}
    api.reviews = {i: [] for i in api.details}
    api.jobs[9, 1] = [job(i) for i in range(1, 102)]
    result = collect_github_metrics("owner/repo", api, now=NOW)
    assert result["pull_requests"] == 101
    assert result["workflow_attempts"] == 1
    assert any("jobs?per_page=100&page=2" in call for call in api.calls)
    assert any("state=open" in call and "page=2" in call for call in api.calls)


def test_every_review_timestamp_is_validated_not_only_the_first():
    api = API()
    api.reviews[1].append(review(2, submitted_at="2026-10-11T00:00:00Z"))
    with pytest.raises(ValueError, match="later"):
        collect_github_metrics("owner/repo", api, now=NOW)


def test_workflow_list_paginates_and_keeps_unlinked_runs():
    api = API()
    api.runs = [run(i) for i in range(1, 102)]
    api.attempts = {(i, 1): run(i, pull_requests=[]) for i in range(1, 102)}
    api.jobs = {(i, 1): [job(i)] for i in range(1, 102)}
    result = collect_github_metrics("owner/repo", api, now=NOW)
    assert result["workflow_attempts"] == 101
    assert all("pr" not in r["data"] for r in result["records"] if r["kind"] == "ci")
    assert any("actions/runs?" in call and "page=2" in call for call in api.calls)


def test_missing_jobs_does_not_become_zero_duration():
    api = API()
    api.jobs[9, 1] = []
    result = collect_github_metrics("owner/repo", api, now=NOW)
    assert result["workflow_attempts"] == 0
    assert any("no completed" in warning for warning in result["warnings"])


def test_unknown_job_conclusion_cannot_produce_a_ci_measurement():
    api = API()
    api.jobs[9, 1][0]["conclusion"] = "not-an-api-state"
    with pytest.raises(ValueError, match="conclusion"):
        collect_github_metrics("owner/repo", api, now=NOW)


def test_merged_snapshot_and_timed_out_attempt_are_reported():
    api = API()
    api.details[1].update(
        state="closed",
        merged_at="2026-10-09T00:00:00Z",
        closed_at="2026-10-09T00:00:00Z",
    )
    api.open_prs = []
    api.attempts[9, 1]["conclusion"] = "timed_out"
    api.jobs[9, 1][0]["conclusion"] = "timed_out"
    records = collect_github_metrics("owner/repo", api, now=NOW)["records"]
    assert records[0]["data"]["state"] == "merged"
    assert records[1]["data"]["outcome"] == "fail"


@pytest.mark.parametrize("target", ["pr", "review", "job"])
def test_nested_data_in_enum_fields_is_a_validation_failure(target):
    api = API()
    if target == "pr":
        api.details[1]["state"] = {"not": "a state"}
    elif target == "review":
        api.reviews[1][0]["state"] = ["APPROVED"]
    else:
        api.jobs[9, 1][0]["conclusion"] = ["success"]
    with pytest.raises(ValueError):
        collect_github_metrics("owner/repo", api, now=NOW)


def test_failed_matrix_attempt_includes_completed_cancelled_job_time():
    api = API()
    api.attempts[9, 1]["conclusion"] = "failure"
    api.jobs[9, 1] = [
        job(conclusion="failure"),
        job(11, conclusion="cancelled", completed_at="2026-10-08T00:04:00Z"),
    ]
    result = collect_github_metrics("owner/repo", api, now=NOW)
    assert result["workflow_attempts"] == 1
    ci = result["records"][-1]
    assert ci["data"]["seconds"] == 180.0
    assert ci["data"]["outcome"] == "fail"
    assert ci["at"] == "2026-10-08T00:04:00+00:00"


def test_upstream_pr_link_is_not_misattributed_to_fork_repository():
    api = API()
    api.attempts[9, 1]["pull_requests"] = [
        {"number": 1, "url": "https://api.github.com/repos/upstream/repo/pulls/1"}
    ]
    result = collect_github_metrics("owner/repo", api, now=NOW)
    assert "pr" not in result["records"][-1]["data"]
    assert any("does not identify this repository" in warning for warning in result["warnings"])
