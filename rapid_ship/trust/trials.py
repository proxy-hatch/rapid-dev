"""Per-capability calibration using controller receipts and external human signoff.

No authority adapter is bundled: callers must install a host-controlled external
verifier. trial_request/promotion_request let an operator service inspect the exact
request before signing it. User-supplied JSON booleans never supply that authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from rapid_ship.models import Component, Contract, Text, Token, digest
from rapid_ship.trust.evidence import EvidenceStore, validate_evidence
from rapid_ship.trust.policy import (
    AuthorityDecision,
    AuthorityRequest,
    AuthorityVerifier,
    CapabilityBinding,
    Grant,
    HostStore,
    PolicyStore,
    binding_problems,
    promotion_request,
    validate_authorization,
    verify_authority,
)

TrialKind = Literal["representative", "recovery", "adversarial"]
HardeningRung = Literal["advisory", "hook", "contract", "provider", "server"]


class TrialRecord(Contract):
    binding: CapabilityBinding
    evidence_digest: Token
    kind: TrialKind
    change_id: Component
    authorization: AuthorityRequest
    authority_provenance: Text = "unverified"

    @property
    def digest(self) -> str:
        return digest(self)


class HardeningRecord(Contract):
    binding: CapabilityBinding
    correction: Text
    rung: HardeningRung
    authorization: AuthorityRequest
    authority_provenance: Text = "unverified"

    @property
    def digest(self) -> str:
        return digest(self)


class TrialStore(HostStore):
    def __init__(
        self,
        directory: Path,
        candidate_root: Path,
        evidence_store: EvidenceStore,
        policy_store: PolicyStore,
        authority_verifier: AuthorityVerifier | None = None,
    ) -> None:
        # Receipt keys must also live outside the candidate, not merely trial keys.
        candidate = candidate_root.resolve()
        if evidence_store.directory.resolve().is_relative_to(candidate):
            raise ValueError("Evidence store must be separate from the candidate")
        super().__init__(directory, candidate_root)
        self.evidence_store = evidence_store
        self.policy_store = policy_store
        self.authority_verifier = authority_verifier

    def _policy(self, binding: CapabilityBinding) -> None:
        binding = CapabilityBinding.model_validate_json(binding.model_dump_json())
        problems = binding_problems(self.policy_store.load_active(), binding)
        if problems:
            raise ValueError("; ".join(problems))

    def _authorize(self, request: AuthorityRequest) -> AuthorityDecision:
        return verify_authority(request, self.authority_verifier)

    def _evidence(self, binding: CapabilityBinding, path: Path) -> str:
        self._policy(binding)
        evidence = self.evidence_store.load(path)
        expected = evidence.binding
        for field in ("policy_digest", "recipe_digest", "environment_digest", "controller_version"):
            if getattr(expected, field) != getattr(binding, field):
                raise ValueError(f"Trial evidence {field} does not match capability binding")
        recipe = next(
            recipe
            for recipe in self.policy_store.load_active().recipes
            if recipe.digest == binding.recipe_digest
        )
        problems = validate_evidence(
            evidence, expected, list(recipe.commands), require_live=True, commands=recipe.commands
        )
        if problems:
            raise ValueError("; ".join(problems))
        return digest(evidence)

    def trial_request(
        self,
        binding: CapabilityBinding,
        evidence_path: Path,
        *,
        kind: TrialKind,
        change_id: str,
        authorization_id: str,
    ) -> AuthorityRequest:
        evidence_digest = self._evidence(binding, evidence_path)
        # Contract construction validates all identifiers/kind before any write.
        placeholder = AuthorityRequest(
            action="review_trial",
            authorization_id=authorization_id,
            binding_digest=digest(binding),
            payload_digest="pending",
        )
        record = TrialRecord(
            binding=binding,
            evidence_digest=evidence_digest,
            kind=kind,
            change_id=change_id,
            authorization=placeholder,
        )
        return placeholder.model_copy(
            update={
                "payload_digest": digest(
                    record.model_dump(
                        mode="json", exclude={"authorization", "authority_provenance"}
                    )
                )
            }
        )

    def record_trial(
        self,
        binding: CapabilityBinding,
        evidence_path: Path,
        *,
        kind: TrialKind,
        change_id: str,
        authorization_id: str,
    ) -> TrialRecord:
        request = self.trial_request(
            binding,
            evidence_path,
            kind=kind,
            change_id=change_id,
            authorization_id=authorization_id,
        )
        decision = self._authorize(request)
        record = TrialRecord(
            binding=binding,
            evidence_digest=self._evidence(binding, evidence_path),
            kind=kind,
            change_id=change_id,
            authorization=request,
            authority_provenance=decision.provenance,
        )
        self.save_record(f"trial-{record.digest}.json", "trial", record.model_dump(mode="json"))
        return record

    def load_trial(self, trial_digest: str) -> TrialRecord:
        self._digest_id(trial_digest)
        record = TrialRecord.model_validate_json(
            json.dumps(self.load_record(f"trial-{trial_digest}.json", "trial"))
        )
        if record.digest != trial_digest:
            raise ValueError("Trial digest does not match")
        return record

    @staticmethod
    def _digest_id(value: str) -> None:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Invalid record digest")

    def promotion_request(
        self, binding: CapabilityBinding, trial_digests: tuple[str, ...], *, authorization_id: str
    ) -> AuthorityRequest:
        self._policy(binding)
        return promotion_request(binding, trial_digests, authorization_id)

    def promote(
        self, binding: CapabilityBinding, trial_digests: tuple[str, ...], *, authorization_id: str
    ) -> Grant:
        request = self.promotion_request(binding, trial_digests, authorization_id=authorization_id)
        if binding.execution == "native":
            raise ValueError("Native workers sharing OS authority cannot receive unattended grants")
        if len(set(trial_digests)) != len(trial_digests):
            raise ValueError("Duplicate trial records cannot qualify")
        records = [self.load_trial(identifier) for identifier in trial_digests]
        heads: set[str] = set()
        changes: set[str] = set()
        kinds: set[TrialKind] = set()
        for record in records:
            if record.binding != binding:
                raise ValueError("Trial is bound to another capability/recipe/environment/risk")
            path = self.evidence_store.directory / f"{record.evidence_digest}.json"
            self._evidence(binding, path)
            expected_request = self.trial_request(
                binding,
                path,
                kind=record.kind,
                change_id=record.change_id,
                authorization_id=record.authorization.authorization_id,
            )
            if expected_request != record.authorization:
                raise ValueError("Trial human signoff is not bound to exact evidence")
            self._authorize(expected_request)
            if record.kind == "representative":
                changes.add(record.change_id)
                heads.add(self.evidence_store.load(path).binding.head_sha)
            kinds.add(record.kind)
        if len(changes) < 3 or len(heads) < 3:
            raise ValueError(
                "At least three distinct human-reviewed representative changes required"
            )
        if "recovery" not in kinds or "adversarial" not in kinds:
            raise ValueError("Both recovery and adversarial evidence are required")
        decision = self._authorize(request)
        grant = Grant(
            binding=binding,
            trial_digests=trial_digests,
            authorization=request,
            authority_provenance=decision.provenance,
        )
        self.save_record(f"grant-{grant.digest}.json", "grant", grant.model_dump(mode="json"))
        return grant

    def load_grant(self, grant_digest: str) -> Grant:
        self._digest_id(grant_digest)
        grant = Grant.model_validate_json(
            json.dumps(self.load_record(f"grant-{grant_digest}.json", "grant"))
        )
        if grant.digest != grant_digest:
            raise ValueError("Grant digest does not match")
        problems = validate_authorization(
            self.policy_store.load_active(), grant, grant.binding, self.authority_verifier
        )
        if problems:
            raise ValueError("; ".join(problems))
        return grant

    def hardening_request(
        self,
        binding: CapabilityBinding,
        correction: str,
        rung: HardeningRung,
        authorization_id: str,
    ) -> AuthorityRequest:
        self._policy(binding)
        placeholder = AuthorityRequest(
            action="harden",
            authorization_id=authorization_id,
            binding_digest=digest(binding),
            payload_digest="pending",
        )
        record = HardeningRecord(
            binding=binding, correction=correction, rung=rung, authorization=placeholder
        )
        return placeholder.model_copy(
            update={
                "payload_digest": digest(
                    record.model_dump(
                        mode="json", exclude={"authorization", "authority_provenance"}
                    )
                )
            }
        )

    def harden(
        self,
        binding: CapabilityBinding,
        correction: str,
        rung: HardeningRung,
        authorization_id: str,
    ) -> HardeningRecord:
        """Record an externally attested enforcement rung; never widen a grant."""
        request = self.hardening_request(binding, correction, rung, authorization_id)
        decision = self._authorize(request)
        record = HardeningRecord(
            binding=binding,
            correction=correction,
            rung=rung,
            authorization=request,
            authority_provenance=decision.provenance,
        )
        self.save_record(
            f"hardening-{record.digest}.json", "hardening", record.model_dump(mode="json")
        )
        return record
