"""Pinned host policy and authority contracts; this module never executes commands.

The host directory/key must be inaccessible to workers. Filesystem modes do not
isolate native workers sharing the host OS identity; those cannot receive grants.
An injected authority verifier is trusted host infrastructure, never candidate code.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from agentic_engineering.models import Argument, Component, Contract, Text, Token, digest


class Recipe(Contract):
    name: Component
    checks: tuple[tuple[Token, tuple[Argument, ...]], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_checks(self) -> Recipe:
        names = [name for name, _ in self.checks]
        if len(set(names)) != len(names):
            raise ValueError("duplicate recipe checks")
        if any(not argv or not argv[0].strip() for _, argv in self.checks):
            raise ValueError("recipe checks need a nonempty executable")
        return self

    @property
    def digest(self) -> str:
        return digest(self)

    @property
    def commands(self) -> dict[str, list[str]]:
        return {name: list(argv) for name, argv in self.checks}


class Policy(Contract):
    project_id: Component
    controller_version: Token
    repository: Token | None = None
    default_branch: Token = "main"
    controller_check_context: Token | None = None
    controller_check_app_id: int | None = Field(default=None, gt=0)
    recipes: tuple[Recipe, ...] = Field(min_length=1)
    capabilities: tuple[
        Literal["read", "create_pr", "merge", "release", "deploy", "controller_upgrade"], ...
    ]

    @model_validator(mode="after")
    def unique_names(self) -> Policy:
        if len({recipe.name for recipe in self.recipes}) != len(self.recipes):
            raise ValueError("duplicate recipes")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("duplicate capabilities")
        return self

    @property
    def digest(self) -> str:
        return digest(self)


class CapabilityBinding(Contract):
    capability: Literal["read", "create_pr", "merge", "release", "deploy", "controller_upgrade"]
    policy_digest: Token
    recipe_digest: Token
    environment_digest: Token
    controller_version: Token
    risk_class: Token
    execution: Literal["native", "docker", "sbx", "openhands"]


class AuthorityRequest(Contract):
    action: Literal["review_trial", "promote", "harden", "controller_upgrade"]
    authorization_id: Token
    binding_digest: Token
    payload_digest: Token

    @property
    def digest(self) -> str:
        return digest(self)


class AuthorityDecision(Contract):
    request_digest: Token
    authorized: bool
    human_reviewed: bool
    environment_verified: bool
    authority_isolated: bool
    provenance: Text


AuthorityVerifier = Callable[[AuthorityRequest], AuthorityDecision]


def verify_authority(
    request: AuthorityRequest, verifier: AuthorityVerifier | None
) -> AuthorityDecision:
    """Consult the host-installed operator service and retain its provenance."""
    if verifier is None:
        raise ValueError("External authority verification is required")
    try:
        decision = verifier(request)
        decision = AuthorityDecision.model_validate_json(decision.model_dump_json())
    except Exception:
        raise ValueError(
            "External authority is unavailable or returned invalid verification"
        ) from None
    problems = []
    if decision.request_digest != request.digest or not decision.authorized:
        problems.append("Authorization does not cover the exact request")
    if not decision.human_reviewed:
        problems.append("Explicit human signoff is required")
    if not decision.environment_verified:
        problems.append("Environment is unverified")
    if not decision.authority_isolated:
        problems.append("Worker/host authority isolation is unverified")
    if problems:
        raise ValueError("; ".join(problems))
    return decision


def authority_problems(request: AuthorityRequest, verifier: AuthorityVerifier | None) -> list[str]:
    try:
        verify_authority(request, verifier)
    except ValueError as error:
        return [str(error)]
    return []


class HostStore:
    """Append-only, sealed files outside the candidate tree; no identity claims."""

    def __init__(self, directory: Path, candidate_root: Path) -> None:
        self.directory = directory.absolute()
        self.candidate_root = candidate_root.absolute()
        self._check_directory()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = self.directory.stat()
        if info.st_mode & 0o077:
            raise ValueError("Host store must be a private directory")
        self.key_path = self.directory / ".authority-key"
        try:
            fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(secrets.token_bytes(32))
                stream.flush()
                os.fsync(stream.fileno())
        self._key = self._read(self.key_path, private=True)
        if len(self._key) != 32:
            raise ValueError("Invalid host store key")

    def _check_directory(self) -> None:
        for path in [self.directory, *self.directory.parents]:
            if path.is_symlink():
                raise ValueError("Host store must not traverse a symlink")
        host = self.directory.resolve()
        candidate = self.candidate_root.resolve()
        if host == candidate or host.is_relative_to(candidate):
            raise ValueError("Host store must be separate from the candidate")

    def _read(self, path: Path, *, private: bool = False) -> bytes:
        self._check_directory()
        if path.parent != self.directory or path.is_symlink():
            raise ValueError("Store path must be a direct regular file, not a symlink")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or (private and info.st_mode & 0o077):
                raise ValueError("Host key must be a private regular file")
            return stream.read()

    def seal(self, payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hmac.new(self._key, body.encode(), hashlib.sha256).hexdigest()

    def save_record(self, name: str, kind: str, payload: dict[str, Any]) -> None:
        if not name or Path(name).name != name or name in {".", ".."} or "\x00" in name:
            raise ValueError("Unsafe store filename")
        self._check_directory()
        envelope = {"schema_version": 1, "kind": kind, "payload": payload}
        envelope["signature"] = self.seal(envelope)
        path = self.directory / name
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
        except FileExistsError:
            if self.load_record(name, kind) != payload:
                raise ValueError("Existing host record cannot be overwritten") from None
            return
        with os.fdopen(fd, "w") as stream:
            json.dump(envelope, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

    def load_record(self, name: str, kind: str) -> dict[str, Any]:
        if Path(name).name != name or name in {"", ".", ".."}:
            raise ValueError("Unsafe store filename")
        envelope = json.loads(self._read(self.directory / name))
        if not isinstance(envelope, dict):
            raise ValueError("Invalid store envelope")
        if type(envelope.get("schema_version")) is not int or envelope["schema_version"] != 1:
            raise ValueError("Unsupported store version")
        if set(envelope) != {"schema_version", "kind", "payload", "signature"}:
            raise ValueError("Unknown store fields")
        signature = envelope.pop("signature")
        if not isinstance(signature, str) or not hmac.compare_digest(
            self.seal(envelope), signature
        ):
            raise ValueError("Store signature does not match")
        if envelope["kind"] != kind or not isinstance(envelope["payload"], dict):
            raise ValueError("Invalid store record kind/payload")
        return dict(envelope["payload"])


class PolicyStore(HostStore):
    def initialize(self, policy: Policy) -> str:
        policy = Policy.model_validate_json(policy.model_dump_json())
        if (self.directory / "active.json").exists():
            if self.load_active() != policy:
                raise ValueError("Policy/controller replacement requires a separate human ceremony")
            return policy.digest
        # Store the policy under its own field for inspectability; seal includes its digest.
        self.save_record(
            f"policy-{policy.digest}.json", "policy", {"policy": policy.model_dump(mode="json")}
        )
        self.save_record("active.json", "active_policy", {"policy_digest": policy.digest})
        return policy.digest

    def load(self, policy_digest: str) -> Policy:
        if len(policy_digest) != 64 or any(c not in "0123456789abcdef" for c in policy_digest):
            raise ValueError("Invalid policy digest")
        payload = self.load_record(f"policy-{policy_digest}.json", "policy")
        if set(payload) != {"policy"}:
            raise ValueError("Unknown policy record fields")
        policy = Policy.model_validate_json(json.dumps(payload["policy"]))
        if policy.digest != policy_digest:
            raise ValueError("Policy digest does not match")
        return policy

    def load_active(self) -> Policy:
        payload = self.load_record("active.json", "active_policy")
        if set(payload) != {"policy_digest"} or not isinstance(payload["policy_digest"], str):
            raise ValueError("Invalid active policy")
        return self.load(payload["policy_digest"])


class Grant(Contract):
    """Exact promotion request; the external verifier supplies human authority.

    Persisted grants have an additional host seal. This object alone is not proof
    of authority: validate_authorization must consult the verifier on every use.
    """

    binding: CapabilityBinding
    trial_digests: tuple[Token, ...]
    authorization: AuthorityRequest
    authority_provenance: Text = "unverified"

    @property
    def digest(self) -> str:
        return digest(self)


def binding_problems(policy: Policy, binding: CapabilityBinding) -> list[str]:
    problems = []
    if binding.policy_digest != policy.digest:
        problems.append("Binding does not match governing policy")
    if binding.controller_version != policy.controller_version:
        problems.append("Binding does not match pinned controller version")
    if binding.capability not in policy.capabilities:
        problems.append("Capability is not permitted by governing policy")
    if binding.recipe_digest not in {recipe.digest for recipe in policy.recipes}:
        problems.append("Recipe is not permitted by governing policy")
    if binding.capability == "controller_upgrade":
        problems.append("Controller upgrade requires a separate human ceremony")
    return problems


def promotion_request(
    binding: CapabilityBinding, trial_digests: tuple[str, ...], authorization_id: str
) -> AuthorityRequest:
    return AuthorityRequest(
        action="promote",
        authorization_id=authorization_id,
        binding_digest=digest(binding),
        payload_digest=digest(
            {"binding": binding.model_dump(mode="json"), "trial_digests": list(trial_digests)}
        ),
    )


def validate_authorization(
    policy: Policy,
    grant: Grant,
    expected: CapabilityBinding,
    authority_verifier: AuthorityVerifier | None = None,
) -> list[str]:
    """Pure eligibility gate; a grant or config's verified flag never suffices."""
    try:
        policy = Policy.model_validate_json(policy.model_dump_json())
        grant = Grant.model_validate_json(grant.model_dump_json())
        expected = CapabilityBinding.model_validate_json(expected.model_dump_json())
    except (ValueError, TypeError, AttributeError):
        return ["Invalid policy/grant/binding contract"]
    problems = binding_problems(policy, expected)
    if grant.binding != expected:
        problems.append("Capability grant does not match current binding")
    if expected.execution == "native":
        problems.append("Native shared OS authority cannot authorize unattended operations")
    if len(set(grant.trial_digests)) != len(grant.trial_digests) or len(grant.trial_digests) < 5:
        problems.append("Capability grant requires distinct representative and recovery trials")
    request = promotion_request(expected, grant.trial_digests, grant.authorization.authorization_id)
    if grant.authorization != request:
        problems.append("Human signoff does not match exact grant and trials")
    problems.extend(authority_problems(request, authority_verifier))
    return problems
