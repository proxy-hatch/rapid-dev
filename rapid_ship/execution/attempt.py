"""Own an attempt's lease, environments, cancellation and finalization order."""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..models import EnvironmentSpec, TaskEvidence
from ..storage import Store
from ..trust.evidence import EvidenceStore
from .environments import EnvironmentHandle, EnvironmentManager


@dataclass(frozen=True)
class ApprovedAttempt:
    """Evidence validated by the pipeline, pending cleanup and a final ownership check."""

    evidence: TaskEvidence
    artifact: Path


@dataclass(frozen=True)
class AttemptContext:
    """Live resources supplied to the task pipeline for one owned attempt."""

    task_id: str
    attempt_id: str
    owner: str
    store: Store
    manager: EnvironmentManager
    cancel_event: threading.Event

    def prepare(
        self, spec: EnvironmentSpec, origin: Path, revision: str, role: str
    ) -> EnvironmentHandle:
        def observed(handle: EnvironmentHandle) -> None:
            self.store.record_event(
                "environment",
                {
                    "task_id": self.task_id,
                    "attempt_id": self.attempt_id,
                    "role": role,
                    "id": handle.id,
                    "workspace": str(handle.workspace),
                    "provider_id": handle.provider_id,
                    "metadata": handle.metadata,
                    "spec": handle.spec.model_dump(mode="json"),
                },
            )

        self.manager.set_observer(observed)
        return self.manager.prepare(spec, origin, self.task_id, revision)


def _cleanup(context: AttemptContext) -> bool:
    complete = True
    # Preparation may fail after creating a handle but before returning it.
    for handle in reversed(context.manager.owned_handles()):
        try:
            context.manager.cleanup(handle)
            context.store.record_event(
                "environment_cleaned",
                {
                    "task_id": context.task_id,
                    "attempt_id": context.attempt_id,
                    "id": handle.id,
                },
            )
        except Exception as exc:
            complete = False
            context.store.record_event(
                "cleanup_uncertain",
                {
                    "task_id": context.task_id,
                    "attempt_id": context.attempt_id,
                    "handle_id": handle.id,
                    "message": str(exc),
                },
            )
    return complete


def run_attempt(
    *,
    database: Path,
    state_dir: Path,
    task_id: str,
    attempt_id: str,
    owner: str,
    manager: EnvironmentManager,
    cancel_event: threading.Event,
    lease_seconds: float,
    execute: Callable[[AttemptContext], ApprovedAttempt | None],
) -> None:
    """Run the pipeline, then finalize only after cleanup and current ownership.

    Ordinary pipeline failures become blocked attempts. Finalization failures
    propagate; neither they nor cancellation may bypass heartbeat shutdown.
    """
    heartbeat_done = threading.Event()
    fence_lost = threading.Event()
    local_cancel = threading.Event()

    def heartbeat() -> None:
        with Store(database) as lease_store:
            while not heartbeat_done.wait(lease_seconds / 3):
                if cancel_event.is_set() or (state_dir / "cancel" / attempt_id).exists():
                    local_cancel.set()
                try:
                    lease_store.heartbeat(attempt_id, owner, lease_seconds)
                except ValueError:
                    fence_lost.set()
                    local_cancel.set()
                    return

    pulse = threading.Thread(target=heartbeat, daemon=True)
    pulse.start()
    try:
        with Store(database) as store:
            context = AttemptContext(task_id, attempt_id, owner, store, manager, local_cancel)
            approved: ApprovedAttempt | None = None
            note = "Attempt did not produce evidence"
            try:
                approved = execute(context)
            except Exception as exc:
                note = str(exc)
                partial_result = getattr(exc, "process_result", None)
                if partial_result is not None:
                    store.record_event(
                        "partial_agent_output",
                        {
                            "task_id": task_id,
                            "attempt_id": attempt_id,
                            "stdout": partial_result.stdout,
                            "stderr": partial_result.stderr,
                        },
                    )
                store.record_event(
                    "attempt_error",
                    {"task_id": task_id, "attempt_id": attempt_id, "message": note},
                )
            finally:
                # Heartbeats continue during cleanup. Uncertain cleanup retains the
                # active reservations until expiry and explicit reconciliation.
                if _cleanup(context) and not fence_lost.is_set():
                    target_state = "blocked"
                    if approved is not None:
                        target_state, note = "approved", "Independent evidence complete"
                    if cancel_event.is_set() or local_cancel.is_set():
                        target_state, note = "cancelled", "Cancellation requested"
                    store.heartbeat(attempt_id, owner, lease_seconds)
                    if target_state == "approved" and approved is not None:
                        receipt = EvidenceStore(state_dir / "receipts").save(approved.evidence)
                        store.record_event(
                            "evidence",
                            {
                                "task_id": task_id,
                                "attempt_id": attempt_id,
                                "receipt": str(receipt),
                                "head_sha": approved.evidence.binding.head_sha,
                                "bundle_sha256": hashlib.sha256(
                                    approved.artifact.read_bytes()
                                ).hexdigest(),
                            },
                        )
                    store.transition(task_id, target_state, attempt_id, owner, note)
    finally:
        heartbeat_done.set()
        pulse.join(timeout=lease_seconds)
