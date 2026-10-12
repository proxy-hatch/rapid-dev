"""Evidence validity is tied to a candidate; receipts are sealed by the controller."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from rapid_ship.models import EvidenceBinding, TaskEvidence, digest


def _publish(path: Path, data: bytes) -> None:
    """Publish complete private bytes without overwriting another writer's result."""
    fd, temporary = tempfile.mkstemp(prefix=".receipt-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)


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
            _publish(self.key_path, secrets.token_bytes(32))
        except FileExistsError:
            pass
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
            _publish(destination, (json.dumps(envelope, sort_keys=True, indent=2) + "\n").encode())
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
