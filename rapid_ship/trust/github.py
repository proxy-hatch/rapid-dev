"""Credential-bearing GitHub broker. No candidate commands execute here."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from ..metrics import import_metrics
from ..models import EvidenceBinding, TaskEvidence, digest
from ..process import run_process
from ..storage import Store
from .evidence import EvidenceStore, validate_evidence

Transport = Callable[[str, str, dict[str, Any] | None], Any]
Authorization = Callable[[str, TaskEvidence], list[str]]


class GitHubError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def gh_request(method: str, endpoint: str, payload: dict[str, Any] | None = None) -> Any:
    """Use only gh's configured broker authentication, never credential argv."""
    argv = ["gh", "api", "--method", method, endpoint, "-H", "Accept: application/vnd.github+json"]
    if payload is not None:
        argv += ["--input", "-"]
    result = run_process(
        argv,
        Path.home(),
        60,
        env={"HOME": str(Path.home())},
        input_text=json.dumps(payload) if payload is not None else None,
    )
    if result.returncode or result.timed_out or result.cancelled:
        status = re.search(r"\(HTTP (\d{3})\)", result.stderr)
        raise GitHubError(
            "GitHub operation failed: " + result.stderr[-2000:],
            int(status.group(1)) if status else None,
        )
    if "[output truncated]" in result.stdout:
        raise ValueError("GitHub response exceeds broker budget")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def inspect_protection(protection: dict[str, Any], context: str, app_id: int) -> list[str]:
    problems: list[str] = []
    status = protection.get("required_status_checks") or {}
    if status.get("strict") is not True:
        problems.append("Strict required status checks are missing")
    if app_id <= 0 or not any(
        check.get("context") == context and check.get("app_id") == app_id
        for check in status.get("checks", [])
    ):
        problems.append("The controller check must be bound to a specific GitHub App")
    if (protection.get("enforce_admins") or {}).get("enabled") is not True:
        problems.append("Administrator bypass must be disabled")
    for key in ("allow_force_pushes", "allow_deletions"):
        if (protection.get(key) or {}).get("enabled") is not False:
            problems.append(f"{key} must be explicitly disabled")
    bypass = (protection.get("required_pull_request_reviews") or {}).get(
        "bypass_pull_request_allowances", {}
    )
    if any(bypass.get(key) for key in ("users", "teams", "apps")):
        problems.append("Pull request bypass allowances are not supported")
    return problems


class GitHubBroker:
    """Constructed by trusted host wiring, never from candidate Python callbacks.

    No authority adapter is installed by default. The adapter must validate a
    sealed grant, the current governing policy, and fresh external authorization.
    Public mutators also require a sealed receipt and an exact live candidate.
    """

    def __init__(
        self,
        store: Store,
        request: Transport,
        repository: str,
        branch: str,
        check_context: str,
        check_app_id: int,
        *,
        evidence_store: EvidenceStore | None = None,
        authorization: Authorization | None = None,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("Invalid GitHub repository")
        if not branch or branch.startswith("-") or any(c.isspace() for c in branch):
            raise ValueError("Invalid base branch")
        self.store, self.request = store, request
        self.repository, self.branch = repository, branch
        self.context, self.app_id = check_context, check_app_id
        self.receipts, self.authorization = evidence_store, authorization
        database = store.connection.execute("PRAGMA database_list").fetchone()[2]
        self.lock = Path(database).resolve().with_suffix(".broker.lock")

    def _api(self, method: str, suffix: str, data: dict[str, Any] | None = None) -> Any:
        return self.request(method, f"repos/{self.repository}/{suffix}", data)

    def preflight(self) -> dict[str, Any]:
        try:
            protection = self._api("GET", f"branches/{quote(self.branch, safe='')}/protection")
            problems = inspect_protection(protection, self.context, self.app_id)
        except (ValueError, RuntimeError, OSError) as exc:
            problems = [f"Server protection could not be verified: {exc}"]
        if self.authorization is None:
            problems.append("No isolated authority adapter is installed")
        return {
            "ready": not problems,
            "blockers": problems,
            "repository": self.repository,
            "branch": self.branch,
        }

    def require_authority(self, capability: str, evidence: TaskEvidence | None) -> None:
        if self.authorization is None or evidence is None:
            raise ValueError("An isolated authority adapter and sealed evidence are required")
        problems = self.authorization(capability, evidence)
        if problems:
            raise ValueError("; ".join(problems))

    def _validate(
        self,
        capability: str,
        receipt: Path,
        expected: EvidenceBinding,
        commands: dict[str, list[str]],
    ) -> TaskEvidence:
        if self.receipts is None:
            raise ValueError("A controller evidence store is required")
        evidence = self.receipts.load(receipt)
        self.require_authority(capability, evidence)
        problems = validate_evidence(
            evidence, expected, list(commands), require_live=True, commands=commands
        )
        if expected.recipe_digest != digest(dict(commands)):
            problems.append("Approved recipe digest mismatch")
        task = self.store.get_task(expected.task_id)
        eligible_states = {
            "create_pr": {"approved"},
            "merge": {"approved", "merged", "released"},
            "release": {"merged", "released"},
        }
        if task["attempt_id"] != expected.attempt_id or task["state"] not in eligible_states.get(
            capability, set()
        ):
            problems.append("The candidate attempt is not currently approved for this capability")
        problems.extend(self.preflight()["blockers"])
        if problems:
            raise ValueError("; ".join(problems))
        return evidence

    def effect(
        self,
        key: str,
        kind: str,
        payload: dict[str, Any],
        lookup: Callable[[], dict[str, Any] | None],
        mutate: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """Durable effect primitive; callers must validate authority before entering."""
        with self.lock.open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                self.store.get_effect(key)
                existed = True
            except ValueError:
                existed = False
            record = self.store.begin_effect(key, kind, payload)
            if record["status"] == "completed":
                completed_result = record["result"]
                if completed_result is None:
                    raise ValueError("Completed effect has no result")
                return dict(completed_result)
            found = lookup()
            if found is not None:
                self.store.finish_effect(key, found)
                return found
            if existed:
                raise ValueError(
                    "Effect reconciliation required; an uncertain operation is not retried"
                )
            try:
                result = mutate()
            except BaseException as exc:
                self.store.mark_effect_uncertain(key, str(exc))
                raise
            self.store.finish_effect(key, result)
            return result

    def _advance(self, expected: EvidenceBinding, state: str, effect_key: str) -> None:
        """Reconcile local state after a durable, confirmed remote result.

        A crash between effect completion and transition is safe: the next call
        reads the completed effect and retries only this local transition.
        """
        with self.lock.open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            task = self.store.get_task(expected.task_id)
            if task["attempt_id"] != expected.attempt_id:
                raise ValueError("Candidate attempt changed before effect reconciliation")
            if task["state"] == state or (state == "merged" and task["state"] == "released"):
                return
            self.store.transition(
                expected.task_id,
                state,
                expected.attempt_id,
                task["owner"],
                f"Confirmed broker effect {effect_key}",
            )

    def create_pr(
        self,
        head_branch: str,
        title: str,
        body: str,
        receipt: Path,
        expected: EvidenceBinding,
        commands: dict[str, list[str]],
    ) -> dict[str, Any]:
        self._validate("create_pr", receipt, expected, commands)
        head = self._api("GET", f"git/ref/heads/{quote(head_branch, safe='')}")
        base = self._api("GET", f"git/ref/heads/{quote(self.branch, safe='')}")
        if head["object"]["sha"] != expected.head_sha or base["object"]["sha"] != expected.base_sha:
            raise ValueError("Remote head or base changed; fresh evidence is required")
        payload = {
            "repository": self.repository,
            "head": head_branch,
            "base": self.branch,
            "head_sha": expected.head_sha,
            "base_sha": expected.base_sha,
            "title": title,
            "body": body,
            "evidence": digest(expected),
        }
        key = "pr:" + digest(dict(payload))
        marker = f"<!-- devctl:{key} -->"

        def lookup() -> dict[str, Any] | None:
            query = urlencode(
                {
                    "state": "all",
                    "head": self.repository.split("/")[0] + ":" + head_branch,
                    "base": self.branch,
                    "per_page": 100,
                }
            )
            matches = [
                pr
                for pr in self._api("GET", "pulls?" + query)
                if marker in (pr.get("body") or "")
                and pr["head"]["sha"] == expected.head_sha
                and pr["head"]["repo"]["full_name"] == self.repository
                and pr["base"]["ref"] == self.branch
            ]
            if len(matches) > 1:
                raise ValueError("Ambiguous PR reconciliation")
            return (
                {"number": matches[0]["number"], "url": matches[0]["html_url"]} if matches else None
            )

        def mutate() -> dict[str, Any]:
            pr = self._api(
                "POST",
                "pulls",
                {
                    "head": head_branch,
                    "base": self.branch,
                    "title": title,
                    "body": body + "\n\n" + marker,
                    "draft": False,
                },
            )
            if (
                pr.get("head", {}).get("sha") != expected.head_sha
                or pr.get("head", {}).get("ref") != head_branch
                or pr.get("head", {}).get("repo", {}).get("full_name") != self.repository
                or pr.get("base", {}).get("sha") != expected.base_sha
                or pr.get("base", {}).get("ref") != self.branch
                or pr.get("base", {}).get("repo", {}).get("full_name") != self.repository
            ):
                raise ValueError("Created PR binding differs from reviewed candidate")
            return {"number": pr["number"], "url": pr["html_url"]}

        result = self.effect(key, "create_pr", payload, lookup, mutate)
        completed = self.store.get_effect(key)
        import_metrics(
            self.store,
            [
                {
                    "source": "devctl:github",
                    "id": key,
                    "at": datetime.fromtimestamp(completed["updated_at"], UTC).isoformat(),
                    "kind": "pr",
                    "data": {
                        "change_id": expected.task_id,
                        "pr": f"{self.repository}#{result['number']}",
                    },
                }
            ],
        )
        return result

    def push_candidate(
        self,
        state_dir: Path,
        receipt: Path,
        expected: EvidenceBinding,
        commands: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Push a sealed Git bundle from a clean bare repository with no checkout."""
        evidence = self._validate("create_pr", receipt, expected, commands)
        if len(evidence.artifact_paths) != 1:
            raise ValueError("Exactly one candidate bundle is required")
        source = state_dir / evidence.artifact_paths[0]
        if source.is_symlink() or not source.resolve().is_relative_to(state_dir.resolve()):
            raise ValueError("Bundle path escaped controller state")
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 100_000_000:
                raise ValueError("Bundle must be a bounded regular file")
            data = stream.read(100_000_001)
        if len(data) > 100_000_000 or source.name != hashlib.sha256(data).hexdigest() + ".bundle":
            raise ValueError("Candidate bundle digest mismatch")
        if not re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", expected.head_sha):
            raise ValueError("Candidate requires a full commit ID")
        branch = f"codex/{expected.task_id}-{expected.head_sha[:12]}"
        payload = {
            "repository": self.repository,
            "branch": branch,
            "head_sha": expected.head_sha,
            "bundle_sha256": hashlib.sha256(data).hexdigest(),
        }
        key = "push:" + digest(dict(payload))

        def lookup() -> dict[str, Any] | None:
            try:
                ref = self._api("GET", f"git/ref/heads/{quote(branch, safe='')}")
            except GitHubError as exc:
                if exc.status == 404:
                    return None
                raise
            if ref["object"]["sha"] != expected.head_sha:
                raise ValueError("Candidate branch exists with a different commit")
            return {"branch": branch, "sha": expected.head_sha}

        def mutate() -> dict[str, Any]:
            with tempfile.TemporaryDirectory(prefix="devctl-broker-") as directory:
                temp = Path(directory)
                bundle = temp / "candidate.bundle"
                bundle.write_bytes(data)
                bare = temp / "objects.git"
                env = {
                    "HOME": str(Path.home()),
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                    "GIT_TERMINAL_PROMPT": "0",
                    "GIT_NO_LAZY_FETCH": "1",
                    "GIT_ALLOW_PROTOCOL": "file:https",
                }
                prefix = ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]

                def git(*args: str) -> None:
                    result = run_process([*prefix, *args], temp, 120, env=env)
                    if result.returncode or result.timed_out or result.cancelled:
                        raise RuntimeError("Broker Git operation failed: " + result.stderr[-2000:])

                git("init", "--bare", str(bare))
                git("-C", str(bare), "fetch", "--no-tags", str(bundle), "HEAD")
                git("-C", str(bare), "cat-file", "-e", f"{expected.head_sha}^{{commit}}")
                git(
                    "-C",
                    str(bare),
                    "-c",
                    "credential.helper=",
                    "-c",
                    "credential.https://github.com.helper=!gh auth git-credential",
                    "push",
                    f"--force-with-lease=refs/heads/{branch}:",
                    f"https://github.com/{self.repository}.git",
                    f"{expected.head_sha}:refs/heads/{branch}",
                )
            result = lookup()
            if result is None:
                raise RuntimeError("Push was not confirmed by GitHub")
            return result

        return self.effect(key, "push", payload, lookup, mutate)

    def merge(
        self, number: int, receipt: Path, expected: EvidenceBinding, commands: dict[str, list[str]]
    ) -> dict[str, Any]:
        self._validate("merge", receipt, expected, commands)
        if number <= 0:
            raise ValueError("Positive PR number required")
        payload = {
            "repository": self.repository,
            "number": number,
            "head_sha": expected.head_sha,
            "evidence": digest(expected),
        }
        key = "merge:" + digest(payload)

        def lookup() -> dict[str, Any] | None:
            pr = self._api("GET", f"pulls/{number}")
            if pr["head"]["sha"] != expected.head_sha or pr["base"]["ref"] != self.branch:
                raise ValueError("PR head/base identity mismatch")
            if pr.get("merged") is True:
                return {"merged": True, "sha": pr["merge_commit_sha"], "number": number}
            return None

        def mutate() -> dict[str, Any]:
            base = self._api("GET", f"git/ref/heads/{quote(self.branch, safe='')}")
            if base["object"]["sha"] != expected.base_sha:
                raise ValueError("Base advanced; rebase and verify again")
            checks = self._api("GET", f"commits/{expected.head_sha}/check-runs?per_page=100")
            matching = [
                check
                for check in checks.get("check_runs", [])
                if check.get("name") == self.context
                and check.get("app", {}).get("id") == self.app_id
            ]
            if not matching or any(
                check.get("conclusion") != "success" or check.get("status") != "completed"
                for check in matching
            ):
                raise ValueError("The app-bound controller check has not passed")
            response = self._api(
                "PUT", f"pulls/{number}/merge", {"sha": expected.head_sha, "merge_method": "merge"}
            )
            if response.get("merged") is not True or not response.get("sha"):
                raise ValueError("GitHub did not confirm the expected merge")
            return {"merged": True, "sha": response["sha"], "number": number}

        result = self.effect(key, "merge", payload, lookup, mutate)
        self._advance(expected, "merged", key)
        return result

    def publish_release(
        self,
        tag: str,
        commit: str,
        asset_digests: dict[str, str],
        receipt: Path,
        expected: EvidenceBinding,
        commands: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Publish a staged draft only after GitHub confirms tag and asset digests.

        Staging/building/uploading is a separate recipe. This broker never builds
        artifacts or assumes a local filename is the artifact GitHub received.
        """
        self._validate("release", receipt, expected, commands)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", tag) or not asset_digests:
            raise ValueError("A safe tag and verified artifact digests are required")
        if any(not re.fullmatch(r"sha256:[a-f0-9]{64}", value) for value in asset_digests.values()):
            raise ValueError("Release artifacts require SHA256 digests")
        task = self.store.get_task(expected.task_id)
        if task["state"] not in {"merged", "released"}:
            raise ValueError("Only an integrated candidate may be released")
        merge_receipts = [
            self.store.get_effect(event["payload"]["key"])
            for event in self.store.events()
            if event["kind"] == "effect_started"
            and event["payload"]["kind"] == "merge"
            and event["payload"]["payload"].get("evidence") == digest(expected)
        ]
        if not any(
            record["status"] == "completed"
            and record["result"] is not None
            and record["result"].get("sha") == commit
            for record in merge_receipts
        ):
            raise ValueError("Release commit does not match the reconciled merge receipt")
        payload = {
            "repository": self.repository,
            "tag": tag,
            "commit": commit,
            "assets": asset_digests,
            "evidence": digest(expected),
        }
        key = "release:" + digest(dict(payload))

        def inspect_release() -> dict[str, Any]:
            ref = self._api("GET", f"git/ref/tags/{quote(tag, safe='')}")
            if ref["object"]["type"] != "commit" or ref["object"]["sha"] != commit:
                raise ValueError("Tag target mismatch; annotated tag resolution is unsupported")
            release = self._api("GET", f"releases/tags/{quote(tag, safe='')}")
            actual = {asset["name"]: asset.get("digest") for asset in release.get("assets", [])}
            if actual != asset_digests:
                raise ValueError("Release artifact digest mismatch")
            return dict(release)

        def lookup() -> dict[str, Any] | None:
            release = inspect_release()
            if release.get("draft") is False:
                return {"id": release["id"], "url": release["html_url"], "tag": tag}
            return None

        def mutate() -> dict[str, Any]:
            release = inspect_release()
            result = self._api("PATCH", f"releases/{release['id']}", {"draft": False})
            if result.get("id") != release["id"] or result.get("draft") is not False:
                raise ValueError("GitHub did not confirm the expected release publication")
            confirmed = inspect_release()
            if confirmed.get("id") != release["id"] or confirmed.get("draft") is not False:
                raise ValueError("GitHub did not confirm the expected release identity")
            return {"id": confirmed["id"], "url": confirmed["html_url"], "tag": tag}

        result = self.effect(key, "release", payload, lookup, mutate)
        self._advance(expected, "released", key)
        return result
