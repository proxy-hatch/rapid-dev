"""Evidence validity is tied to a candidate; receipts are sealed by the controller."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
from collections import Counter
from pathlib import Path
from typing import Any

from agentic_engineering.models import EvidenceBinding, TaskEvidence, digest


def validate_evidence(
    evidence: TaskEvidence,
    expected: EvidenceBinding,
    required_checks: list[str],
    *,
    require_live: bool = False,
    commands: dict[str, list[str]] | None = None,
) -> list[str]:
    problems: list[str] = []
    if evidence.binding != expected:
        problems.append("Evidence binding does not match the current candidate")
    if require_live and not evidence.live:
        problems.append("Simulated evidence cannot authorize live operations")
    names = Counter(result.name for result in evidence.checks)
    if not required_checks:
        problems.append("At least one required check must be configured")
    for name in required_checks:
        if names[name] != 1:
            problems.append(f"Required check {name} must appear exactly once")
    for result in evidence.checks:
        if result.exit_code != 0:
            problems.append(f"Check {result.name} failed")
        if commands is not None and commands.get(result.name) != result.argv:
            problems.append(f"Check {result.name} did not use its approved command")
    review = evidence.review
    if review is None:
        problems.append("Independent review is required")
    else:
        if review.binding != expected:
            problems.append("Review binding is stale")
        if review.verdict != "approve" or not review.independent:
            problems.append("Independent approval is required")
        if any(finding.severity in {"critical", "important"} for finding in review.findings):
            problems.append("Blocking review findings remain unresolved")
    return problems


class EvidenceStore:
    """Host-owned receipts; the key directory must never be mounted in a worker.

    A seal proves origin/integrity, not correctness of the underlying checks.
    Native workers under the same OS identity cannot provide this trust boundary.
    """

    def __init__(self, directory: Path) -> None:
        absolute = directory.absolute()
        for parent in [absolute, *absolute.parents]:
            if parent.is_symlink():
                raise ValueError("Evidence directory must not traverse a symlink")
        self.directory = absolute
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.key_path = self.directory / ".receipt-key"
        if self.key_path.is_symlink():
            raise ValueError("Evidence key must not be a symlink")
        try:
            fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(secrets.token_bytes(32))
                stream.flush()
                os.fsync(stream.fileno())
        info = self.key_path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError("Evidence key must be a private regular file")
        self._key = self.key_path.read_bytes()
        if len(self._key) != 32:
            raise ValueError("Invalid evidence receipt key")

    def _seal(self, payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hmac.new(self._key, body, hashlib.sha256).hexdigest()

    def save(self, evidence: TaskEvidence) -> Path:
        payload = evidence.model_dump(mode="json")
        destination = self.directory / f"{digest(evidence)}.json"
        envelope = {"schema_version": 1, "evidence": payload, "signature": self._seal(payload)}
        try:
            with destination.open("x") as stream:
                json.dump(envelope, stream, sort_keys=True, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            if self.load(destination) != evidence:
                raise ValueError("Conflicting evidence receipt") from None
        return destination

    def load(self, path: Path) -> TaskEvidence:
        if path.is_symlink() or path.resolve().parent != self.directory.resolve():
            raise ValueError("Receipt must be a direct file in the evidence directory")
        envelope = json.loads(path.read_text())
        if not isinstance(envelope, dict) or envelope.get("schema_version") != 1:
            raise ValueError("Invalid evidence receipt")
        payload = envelope.get("evidence")
        signature = envelope.get("signature")
        if not isinstance(payload, dict) or not isinstance(signature, str):
            raise ValueError("Invalid evidence receipt")
        if not hmac.compare_digest(self._seal(payload), signature):
            raise ValueError("Evidence signature does not match")
        evidence = TaskEvidence.model_validate(payload)
        if path.name != f"{digest(evidence)}.json":
            raise ValueError("Evidence filename does not match its digest")
        return evidence
