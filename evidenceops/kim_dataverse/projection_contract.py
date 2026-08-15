from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


class ProjectionContractError(ValueError):
    """Raised when current-state projection truth dimensions are collapsed."""


def _aware_iso(value: str, field: str) -> str:
    text = str(value).strip()
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ProjectionContractError(f"INVALID_TIMESTAMP:{field}") from exc
    if parsed.tzinfo is None:
        raise ProjectionContractError(f"TIMEZONE_REQUIRED:{field}")
    return text


@dataclass(frozen=True)
class SourceFrontierObservation:
    source_id: str
    version_or_sha: str
    observed_at: str
    verification_state: str
    query_time_provider_read: bool = False

    def __post_init__(self) -> None:
        _aware_iso(self.observed_at, "source.observed_at")
        if not self.source_id or not self.version_or_sha:
            raise ProjectionContractError("SOURCE_ID_AND_VERSION_REQUIRED")


@dataclass(frozen=True)
class RuntimeAttestationObservation:
    attestation_id: str
    bound_source_version: str
    observed_at: str
    scope: str
    qualification_state: str

    def __post_init__(self) -> None:
        _aware_iso(self.observed_at, "runtime.observed_at")
        if not all((self.attestation_id, self.bound_source_version, self.scope)):
            raise ProjectionContractError("RUNTIME_ATTESTATION_FIELDS_REQUIRED")


@dataclass(frozen=True)
class ProviderEffectProof:
    provider: str
    receipt_id: str
    observed_at: str
    scope: str
    effect_state: str
    truth_boundary: str

    def __post_init__(self) -> None:
        _aware_iso(self.observed_at, "provider.observed_at")
        if not all((self.provider, self.receipt_id, self.scope, self.truth_boundary)):
            raise ProjectionContractError("PROVIDER_PROOF_FIELDS_REQUIRED")


@dataclass(frozen=True)
class CompiledProjection:
    source_frontier: Mapping[str, Any] | None
    runtime_attestation_frontier: Mapping[str, Any] | None
    provider_effect_proof: Mapping[str, Any] | None
    present_tense_source_claim_allowed: bool
    source_runtime_same_version: bool | None
    maturity_inheritance_allowed: bool
    as_of_only: bool


def compile_projection(
    *,
    source: SourceFrontierObservation | None = None,
    runtime: RuntimeAttestationObservation | None = None,
    provider: ProviderEffectProof | None = None,
) -> CompiledProjection:
    same: bool | None = None
    if source and runtime:
        same = source.version_or_sha == runtime.bound_source_version
    source_payload = source.__dict__.copy() if source else None
    runtime_payload = runtime.__dict__.copy() if runtime else None
    provider_payload = provider.__dict__.copy() if provider else None
    return CompiledProjection(
        source_frontier=source_payload,
        runtime_attestation_frontier=runtime_payload,
        provider_effect_proof=provider_payload,
        present_tense_source_claim_allowed=bool(source and source.query_time_provider_read),
        source_runtime_same_version=same,
        maturity_inheritance_allowed=False,
        as_of_only=not bool(source and source.query_time_provider_read),
    )


def require_expected_source(*, expected: str, observed: str) -> None:
    """Compare-and-set precondition for mutable projection writes."""
    if expected != observed:
        raise ProjectionContractError(
            f"SOURCE_PRECONDITION_FAILED:expected={expected}:observed={observed}"
        )
