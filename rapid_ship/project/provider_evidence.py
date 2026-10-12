"""Typed provider observations, retained model proofs, and selection requirements."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError, model_validator

from rapid_ship.models import ProjectConfig

ProviderName = Literal["codex", "claude", "agy"]


def _model_id(value: str) -> str:
    if (
        not value
        or value.startswith("-")
        or not value.isprintable()
        or any(character.isspace() for character in value)
    ):
        raise ValueError("Invalid model identifier")
    return value


def _timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp requires a timezone")
    return value


ModelId = Annotated[str, AfterValidator(_model_id)]
Timestamp = Annotated[str, AfterValidator(_timestamp)]


class ProviderModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: ModelId
    label: str | None = None


class ProviderObservation(BaseModel):
    """One discovery or explicit check; missing presentation fields stay absent."""

    model_config = ConfigDict(strict=True, extra="forbid")

    provider: ProviderName
    authenticated: bool | None
    models: list[ProviderModel]
    checked_at: Timestamp
    installed: bool | None = None
    sources: list[str] = Field(default_factory=list)
    hint: str = ""
    ready: bool = False
    selected_model: ModelId | None = None
    verified: bool = False
    verified_at: Timestamp | None = None
    verification_method: Literal["inference", "native-status"] | None = None
    request_sent: bool = False
    tool_activity: bool | None = None
    tool_event_count: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        identifiers = {model.id for model in self.models}
        if len(identifiers) != len(self.models):
            raise ValueError("Duplicate catalog model")
        if self.ready and not self.observed_ready:
            raise ValueError("Readiness conflicts with the observed status/catalog")
        if self.provider == "agy" and self.authenticated is True and not self.verified:
            raise ValueError("agy authentication requires selected-model inference evidence")
        if self.verified:
            method = "inference" if self.provider == "agy" else "native-status"
            if not (
                self.authenticated is True
                and self.verification_method == method
                and self.selected_model in identifiers
                and self.verified_at is not None
                and (self.provider != "agy" or self.request_sent)
            ):
                raise ValueError("Verification requires complete selected-model evidence")
        return self

    @property
    def observed_ready(self) -> bool:
        return (
            self.authenticated is True
            and bool(self.models)
            and (self.provider != "agy" or self.verified)
        )

    def report(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class ProviderEvidence(ProviderObservation):
    model_verifications: dict[ModelId, Timestamp] = Field(default_factory=dict)


def recent(timestamp: str, now: datetime) -> bool:
    """Use one caller-supplied clock for the catalog and every relevant proof."""
    try:
        checked = datetime.fromisoformat(_timestamp(timestamp).replace("Z", "+00:00"))
        return 0 <= (now - checked).total_seconds() <= 86400
    except (TypeError, ValueError):
        return False


def merge_provider_records(
    existing: dict[str, Any], records: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        observations = [ProviderObservation.model_validate(record) for record in records]
    except ValidationError:
        # Validation diagnostics include raw input; never expose provider output or credentials.
        raise ValueError("Invalid provider observation; run devctl providers again") from None

    merged = dict(existing)
    for observation in observations:
        evidence = ProviderEvidence.model_validate(observation.report())
        if observation.provider == "agy":
            try:
                previous = ProviderEvidence.model_validate(merged.get("agy"))
                proofs = dict(previous.model_verifications) if previous.provider == "agy" else {}
            except ValidationError:
                proofs = {}
            model = observation.selected_model
            if observation.verification_method == "inference" and model is not None:
                # Explicit failures remove only their model, even after it leaves the catalog.
                proofs.pop(model, None)
                if observation.verified:
                    assert observation.verified_at is not None
                    proofs[model] = observation.verified_at
            evidence.model_verifications = proofs
        report = evidence.report()
        merged[observation.provider] = report
    effective = [merged[observation.provider] for observation in observations]
    return merged, effective


def check_model_readiness(
    reports: dict[str, Any], config: ProjectConfig, *, now: datetime | None = None
) -> None:
    current = datetime.now(UTC) if now is None else now
    evidence: dict[str, ProviderEvidence] = {}
    for provider in config.providers:
        try:
            report = ProviderEvidence.model_validate(reports.get(provider))
            if report.provider != provider:
                raise ValueError("Provider does not match its saved key")
        except ValueError:
            raise ValueError(
                f"Refresh provider checks for {provider}; invalid status or model catalog"
            ) from None
        evidence[provider] = report
        if not recent(report.checked_at, current):
            raise ValueError(f"Refresh provider checks for {provider}")
        authenticated = (
            any(recent(timestamp, current) for timestamp in report.model_verifications.values())
            if provider == "agy"
            else report.authenticated is True
        )
        if not authenticated:
            raise ValueError(f"Verify authentication for {provider} with devctl providers")
    for choice in config.models.values():
        report = evidence[choice.provider]
        if choice.model not in {model.id for model in report.models}:
            raise ValueError(f"Choose {choice.provider} model from the discovered catalog")
        if choice.provider == "agy":
            proof = report.model_verifications.get(choice.model)
            if proof is None or not recent(proof, current):
                raise ValueError(f"Verify authentication for agy model {choice.model} explicitly")
