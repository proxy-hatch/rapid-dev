"""The devctl command line: decisions, workflow state, and explicit capability gates."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from .execution.controller import Controller
from .execution.environments import EnvironmentBlocked, EnvironmentHandle, EnvironmentManager
from .github_metrics import collect_github_metrics
from .logs import read_logs, record_command
from .metrics import MetricRecord, import_metrics, metrics_report
from .models import EnvironmentSpec, TaskSpec, validate_task_graph
from .project.configuration import (
    answer_question,
    doctor,
    init_project,
    interview_next,
    load_config,
    save_provider_records,
    scaffold_feature,
)
from .storage import ACTIVE_STATES, Store
from .trust.evidence import EvidenceStore
from .trust.github import GitHubBroker, gh_request


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="devctl")
    result.add_argument("--version", action="version", version=f"devctl {version('rapid-ship')}")
    result.add_argument("--project", type=Path, default=Path.cwd())
    result.add_argument("--state-dir", type=Path)
    commands = result.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Initialize from an approved design without overwrites")
    init.add_argument("--name", required=True)
    init.add_argument("--design", required=True)
    init.add_argument("--framework", type=Path, help="Local rapid-ship checkout backlink")
    check = commands.add_parser("doctor", help="Read-only readiness check")
    check.add_argument("--json", action="store_true")
    interview = commands.add_parser("interview", help="Show or answer the next setup question")
    interview.add_argument("--answer")
    interview.add_argument("--value", help="JSON value for the answer")
    for name in ("decompose", "run"):
        sub = commands.add_parser(
            name,
            help="Validate/register task contracts"
            if name == "decompose"
            else "Execute ready tasks in their configured environments",
        )
        sub.add_argument("--tasks", type=Path, required=True, help="JSON array of TaskSpec objects")
    commands.add_parser("status", help="Show durable task state")
    providers = commands.add_parser("providers", help="Check provider authentication and models")
    providers.add_argument("--provider", action="append", choices=["codex", "claude", "agy"])
    providers.add_argument("--verify", action="store_true", help="Verify one selected model")
    providers.add_argument("--model", help="Exact model chosen from the provider catalog")
    logs = commands.add_parser("logs", help="Read local command and task event summaries")
    logs.add_argument("--task")
    logs.add_argument("--limit", type=int, default=50)
    metrics = commands.add_parser("metrics", help="Show delivery measurements and missing data")
    metrics.add_argument(
        "operation", nargs="?", choices=["report", "import", "sync-github"], default="report"
    )
    metrics.add_argument("file", nargs="?", type=Path, help="JSON array of metric observations")
    metrics.add_argument("--days", type=int, default=28)
    metrics.add_argument("--until", help="Report end time as ISO 8601 with timezone")
    metrics.add_argument("--include-simulated", action="store_true")
    metrics.add_argument(
        "--repository", help="GitHub owner/repository; defaults to project settings"
    )
    resume = commands.add_parser("resume", help="Reconcile stopped environments and resume a task")
    resume.add_argument("task_id")
    resume.add_argument("--attempt", help="Exact attempt being reconciled")
    resume.add_argument("--base", help="Explicit new full base commit after dependency integration")
    resume.add_argument("--expected-base", help="Prior base from status, required with --base")
    cancel = commands.add_parser("cancel", help="Request cancellation of one exact task attempt")
    cancel.add_argument("task_id")
    evidence = commands.add_parser("evidence", help="Read saved check and review results")
    evidence.add_argument("--receipt", type=Path)
    new = commands.add_parser("new", help="Generate a small feature and executable test")
    new.add_argument("name")
    commands.add_parser("trial", help="Show calibration requirements and authority status")
    commands.add_parser("harden", help="Check whether capability promotion can be authorized")
    github = commands.add_parser("github", help="Inspect GitHub server enforcement")
    github.add_argument("operation", choices=["preflight", "create-pr", "merge"])
    github.add_argument("--check-context", default="devctl/evidence")
    github.add_argument("--app-id", type=int, default=0)
    commands.add_parser("release", help="Check release authority readiness")
    return result


def _tasks(path: Path) -> list[TaskSpec]:
    data = json.loads(path.read_text())
    if not isinstance(data, list) or not data:
        raise ValueError("Task file must contain a nonempty array")
    tasks = [TaskSpec.model_validate(item) for item in data]
    validate_task_graph(tasks)
    return tasks


def _authority_block() -> None:
    raise EnvironmentBlocked(
        "No isolated operator authority adapter is installed. Configure a trusted external "
        "AuthorityVerifier, then record three human-reviewed representative changes plus recovery "
        "and adversarial trials for the exact recipe/environment. Unit tests and configuration "
        "flags cannot grant live merge or release authority. See docs/authority.md."
    )


def execute(args: argparse.Namespace) -> tuple[Any, int]:
    root = args.project.resolve()
    state = (args.state_dir or root / ".devctl/state").resolve()
    database = state / "workflow.db"
    if args.command == "init":
        return init_project(root, args.name, args.design, framework_root=args.framework), 0
    if args.command == "logs":
        return read_logs(state, args.task, args.limit), 0
    if args.command == "providers":
        from .project.providers import inspect_provider, verify_provider

        selected = (
            args.provider
            or (load_config(root).providers if (root / ".devctl/project.json").exists() else [])
            or ["codex", "claude", "agy"]
        )
        if args.verify:
            if len(selected) != 1 or not args.model:
                raise ValueError("Verification requires one --provider and an exact --model")
            reports = [verify_provider(selected[0], args.model)]
        else:
            if args.model:
                raise ValueError("--model requires --verify")
            reports = [inspect_provider(name) for name in dict.fromkeys(selected)]
        if (root / ".devctl/project.json").is_file():
            reports = save_provider_records(root, reports)
        return {"providers": reports}, 0 if all(item["ready"] for item in reports) else 2
    if args.command == "interview":
        if args.answer is None:
            return interview_next(root), 0
        if args.value is None:
            raise ValueError("--answer requires --value as JSON")
        return answer_question(root, args.answer, json.loads(args.value)), 0
    if args.command == "doctor":
        report = doctor(root)
        if report["configuration_ready"]:
            manager = EnvironmentManager(state / "workspaces")
            for spec in load_config(root).environments:
                report["blockers"].extend(f"{spec.name}: {item}" for item in manager.inspect(spec))
        report["ready"] = not report["blockers"]
        return report, 0 if report["ready"] else 2
    if args.command in {"decompose", "run"}:
        tasks = _tasks(args.tasks)
        config = load_config(root)
        if args.command == "run":
            report = doctor(root)
            if not report["ready"]:
                raise EnvironmentBlocked("; ".join(report["blockers"]))
            controller = Controller(root, config, state)
            rows = controller.run(tasks)
            return {"tasks": rows, "autonomy_granted": False}, (
                0 if all(row["state"] in {"approved", "merged", "released"} for row in rows) else 2
            )
        known = {env.name for env in config.environments}
        if any(task.environment not in known for task in tasks):
            raise ValueError("Every task must select a configured environment")
        state.mkdir(parents=True, exist_ok=True)
        with Store(database) as store:
            store.add_tasks(tasks)
        return {"registered": [task.id for task in tasks]}, 0
    if args.command == "metrics":
        if args.operation == "sync-github":
            if args.file is not None or args.until or args.include_simulated:
                raise ValueError("sync-github accepts --repository and --days")
            repository = args.repository or load_config(root).repository
            if repository is None:
                raise ValueError("Configure a GitHub repository or pass --repository owner/repo")
            collected = collect_github_metrics(repository, gh_request, days=args.days)
            records = collected.pop("records")
            for record in records:
                MetricRecord.model_validate(record)
            if not records:
                return {**collected, "imported": 0, "duplicates": 0}, 0
            state.mkdir(parents=True, exist_ok=True)
            with Store(database) as store:
                return {**collected, **import_metrics(store, records)}, 0
        if args.repository:
            raise ValueError("--repository is only used with metrics sync-github")
        if args.operation == "import":
            if args.file is None:
                raise ValueError("metrics import requires a JSON file")
            records = json.loads(args.file.read_text())
            if not isinstance(records, list) or not records:
                raise ValueError("Metrics file must contain a nonempty array")
            # Validate before creating project state; the importer also checks conflicts atomically.
            for record in records:
                MetricRecord.model_validate(record)
            state.mkdir(parents=True, exist_ok=True)
            with Store(database) as store:
                return import_metrics(store, records), 0
        if args.file is not None:
            raise ValueError("Use metrics import FILE to add observations")
        with Store(database if database.exists() else Path(":memory:")) as store:
            return metrics_report(
                store,
                args.days,
                now=datetime.fromisoformat(args.until.replace("Z", "+00:00"))
                if args.until
                else None,
                include_simulated=args.include_simulated,
            ), 0
    if args.command == "status":
        if not database.exists():
            return {"tasks": []}, 0
        with Store(database) as store:
            return {"tasks": store.tasks()}, 0
    if args.command == "evidence":
        directory = state / "receipts"
        if not directory.exists():
            return {"receipts": []}, 0
        vault = EvidenceStore(directory)
        paths = [args.receipt] if args.receipt else sorted(directory.glob("*.json"))
        return {
            "receipts": [
                {"path": str(path), **vault.load(path).model_dump(mode="json")} for path in paths
            ]
        }, 0
    if args.command == "new":
        return {"created": scaffold_feature(root, args.name)}, 0
    if args.command in {"trial", "harden", "release"}:
        _authority_block()
    if args.command == "github":
        if args.operation != "preflight":
            _authority_block()
        config = load_config(root)
        if config.repository is None:
            raise ValueError("Configure a GitHub repository first")
        # Read-only remote preflight. The in-memory store creates no project state.
        with Store(Path(":memory:")) as store:
            report = GitHubBroker(
                store,
                gh_request,
                config.repository,
                config.default_branch,
                args.check_context,
                args.app_id,
            ).preflight()
        return report, 0 if report["ready"] else 2
    if args.command in {"cancel", "resume"}:
        if not database.exists():
            raise ValueError("There are no registered tasks")
        with Store(database) as store:
            row = store.get_task(args.task_id)
            if args.command == "cancel":
                if row["state"] in ACTIVE_STATES:
                    destination = state / "cancel" / row["attempt_id"]
                    destination.parent.mkdir(exist_ok=True)
                    destination.touch(exist_ok=True)
                    return {"cancellation_requested": row["attempt_id"]}, 0
                store.transition(args.task_id, "cancelled")
                return {"cancelled": args.task_id}, 0
            if bool(args.base) != bool(args.expected_base):
                raise ValueError("--base and --expected-base must be provided together")
            store.recover_expired()
            row = store.get_task(args.task_id)
            if row["reconciliation_required"]:
                if args.attempt != row["attempt_id"]:
                    raise EnvironmentBlocked("Supply the exact --attempt from status for recovery")
                events = [
                    event["payload"]
                    for event in store.events()
                    if event["kind"] == "environment"
                    and event["payload"]["attempt_id"] == args.attempt
                ]
                if not events:
                    raise EnvironmentBlocked(
                        "Environment preparation is uncertain; operator reconciliation required"
                    )
                manager = EnvironmentManager(state / "workspaces")
                latest = {record["id"]: record for record in events}
                cleaned = {
                    event["payload"]["id"]
                    for event in store.events()
                    if event["kind"] == "environment_cleaned"
                    and event["payload"]["attempt_id"] == args.attempt
                }
                for record in reversed(list(latest.values())):
                    if record["id"] in cleaned:
                        continue
                    handle = EnvironmentHandle(
                        record["id"],
                        EnvironmentSpec.model_validate(record["spec"]),
                        Path(record["workspace"]),
                        record["provider_id"],
                        record["metadata"],
                    )
                    manager.recover(handle)
                    manager.cleanup(handle)
                    store.record_event(
                        "environment_cleaned",
                        {
                            "task_id": args.task_id,
                            "attempt_id": args.attempt,
                            "id": handle.id,
                        },
                    )
                store.release_recovered(args.task_id, args.attempt)
            if args.base:
                store.rebase_task(args.task_id, args.base, args.expected_base)
            if store.get_task(args.task_id)["state"] == "blocked":
                store.transition(args.task_id, "pending")
            elif store.get_task(args.task_id)["state"] != "pending":
                raise ValueError("Only inactive blocked or pending tasks can resume")
            updated = store.get_task(args.task_id)["spec"]
        return {
            "resumed": args.task_id,
            "task": updated,
            "next": "Update this task in the input file to match, then run",
        }, 0
    raise ValueError("Unknown command")


def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace | None = None
    started = time.monotonic()
    try:
        args = parser().parse_args(argv)
        value, code = execute(args)
    except EnvironmentBlocked as error:
        value, code = {"status": "blocked", "message": str(error)}, 2
    except (ValueError, OSError) as error:
        value, code = {"status": "invalid", "message": str(error)}, 3
    except (RuntimeError, sqlite3.Error) as error:
        value, code = {"status": "failed", "message": str(error)}, 4
    except KeyboardInterrupt:
        value, code = {"status": "interrupted", "message": "Inspect status before resuming"}, 130
    if args is not None and (args.project / ".devctl/project.json").is_file():
        mutating = args.command in {"init", "providers", "decompose", "run", "resume", "cancel"}
        mutating = mutating or (args.command == "interview" and args.answer is not None)
        mutating = mutating or (args.command == "metrics" and args.operation != "report")
        if mutating:
            try:
                record_command(
                    (args.state_dir or args.project / ".devctl/state").resolve(),
                    args.command,
                    code,
                    time.monotonic() - started,
                )
            except OSError:
                # A diagnostic failure must not make a completed operation appear safe to retry.
                print(
                    "Warning: command completed but its diagnostic log could not be written.",
                    file=sys.stderr,
                )
    print(json.dumps(value, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
