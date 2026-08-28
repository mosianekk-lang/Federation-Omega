from __future__ import annotations

"""Proof-preserving observation adapters.

An adapter may normalize and transport evidence; it may never upgrade evidence,
create provider authority, return private payloads, or infer health from missing
visibility.
"""

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .contracts import (
    AuthorityClass,
    CivitasError,
    ProofLevel,
    ProofRef,
    PROOF_RANK,
    contains_secret_shape,
    digest,
    safe_id,
)


SUPPORTED_EVENT_CLASSES = {
    "NODE_STATE", "ROUTE_TELEMETRY", "CONTEXT_STATE", "LEARNING", "BENCHMARK",
}


@dataclass(frozen=True)
class RawObservation:
    event_id: str
    source_ref: str
    proof_ref: str
    observed_at: str
    source_proof_level: ProofLevel
    event_class: str
    object_id: str
    object_kind: str
    state: str
    payload: Mapping[str, Any]
    confidence: float = 0.7
    ttl_seconds: int = 3600
    independent_source: str = "UNKNOWN"
    matter_scope: str = "GLOBAL"
    sensitivity: str = "PUBLIC_SAFE"
    authority_ceiling: AuthorityClass = AuthorityClass.A1_INTERNAL
    provider_native: bool = False

    def validate(self) -> "RawObservation":
        safe_id(self.event_id, "event_id")
        safe_id(self.object_id, "object_id")
        if self.event_class not in SUPPORTED_EVENT_CLASSES:
            raise ValueError("unsupported event_class")
        if not self.source_ref.strip() or not self.proof_ref.strip() or not self.state.strip():
            raise ValueError("source_ref, proof_ref and state required")
        ProofRef(
            self.source_ref,
            self.proof_ref,
            self.observed_at,
            self.source_proof_level,
            self.confidence,
            self.ttl_seconds,
            self.independent_source,
            self.matter_scope,
            self.sensitivity,
            self.authority_ceiling,
        ).validate()
        if self.sensitivity == "PUBLIC_SAFE" and contains_secret_shape(self.payload):
            raise CivitasError("secret-shaped material rejected from public-safe observation")
        return self


@dataclass(frozen=True)
class NormalizedObservation:
    event_id: str
    event_class: str
    source_ref: str
    proof_ref: str
    observed_at: str
    proof_level: ProofLevel
    object_id: str
    object_kind: str
    state: str
    payload: Mapping[str, Any]
    confidence: float
    ttl_seconds: int
    independent_source: str
    matter_scope: str
    sensitivity: str
    authority_ceiling: AuthorityClass
    source_proof_level: ProofLevel
    provider_native: bool
    proof_upgraded: bool = False
    authority_created: bool = False
    private_payload_returned: bool = False
    external_effects: int = 0

    def validate(self) -> "NormalizedObservation":
        if PROOF_RANK[self.proof_level] > PROOF_RANK[self.source_proof_level] or self.proof_upgraded:
            raise CivitasError("adapter evidence upgrade blocked")
        if self.authority_created or self.private_payload_returned or self.external_effects:
            raise CivitasError("adapter cannot create authority, return private payload or execute effects")
        return self

    @property
    def envelope_sha256(self) -> str:
        self.validate()
        return digest(asdict(self))


@dataclass(frozen=True)
class AdapterReceipt:
    event_id: str
    adapter_id: str
    source_proof_level: str
    normalized_proof_level: str
    proof_preserved: bool
    envelope_sha256: str
    private_payload_returned: bool = False
    authority_created: bool = False
    external_effects: int = 0

    @property
    def receipt_sha256(self) -> str:
        return digest(asdict(self))


class ProofPreservingAdapter:
    """Generic fail-closed normalizer with an explicit proof ceiling."""

    def __init__(self, adapter_id: str, *, maximum_output_level: ProofLevel) -> None:
        self.adapter_id = safe_id(adapter_id, "adapter_id")
        self.maximum_output_level = ProofLevel(maximum_output_level)

    def normalize(self, observation: RawObservation) -> tuple[NormalizedObservation, AdapterReceipt]:
        observation.validate()
        source_rank = PROOF_RANK[observation.source_proof_level]
        ceiling_rank = PROOF_RANK[self.maximum_output_level]
        selected_level = observation.source_proof_level if source_rank <= ceiling_rank else self.maximum_output_level
        if observation.provider_native and observation.source_proof_level not in {
            ProofLevel.PROVIDER_READBACK,
            ProofLevel.RECEIPT_VERIFIED,
        }:
            raise CivitasError("provider_native flag conflicts with source proof level")
        normalized = NormalizedObservation(
            event_id=observation.event_id,
            event_class=observation.event_class,
            source_ref=observation.source_ref,
            proof_ref=observation.proof_ref,
            observed_at=observation.observed_at,
            proof_level=selected_level,
            object_id=observation.object_id,
            object_kind=observation.object_kind,
            state=observation.state,
            payload=dict(observation.payload),
            confidence=observation.confidence,
            ttl_seconds=observation.ttl_seconds,
            independent_source=observation.independent_source,
            matter_scope=observation.matter_scope,
            sensitivity=observation.sensitivity,
            authority_ceiling=observation.authority_ceiling,
            source_proof_level=observation.source_proof_level,
            provider_native=observation.provider_native,
        ).validate()
        receipt = AdapterReceipt(
            observation.event_id,
            self.adapter_id,
            observation.source_proof_level.value,
            selected_level.value,
            PROOF_RANK[selected_level] <= PROOF_RANK[observation.source_proof_level],
            normalized.envelope_sha256,
        )
        return normalized, receipt


class ProviderReadbackAdapter(ProofPreservingAdapter):
    def __init__(self) -> None:
        super().__init__("ADAPTER:PROVIDER_READBACK", maximum_output_level=ProofLevel.PROVIDER_READBACK)


class SourceReadbackAdapter(ProofPreservingAdapter):
    def __init__(self) -> None:
        super().__init__("ADAPTER:SOURCE_READBACK", maximum_output_level=ProofLevel.SOURCE_READBACK)


class DeterministicTestAdapter(ProofPreservingAdapter):
    def __init__(self) -> None:
        super().__init__("ADAPTER:DETERMINISTIC_TEST", maximum_output_level=ProofLevel.DETERMINISTIC_TESTED)


class ContextHealthAdapter(ProofPreservingAdapter):
    def __init__(self) -> None:
        super().__init__("ADAPTER:CONTEXT_HEALTH", maximum_output_level=ProofLevel.RUNTIME_READBACK)


class FailureLearningAdapter(ProofPreservingAdapter):
    def __init__(self) -> None:
        super().__init__("ADAPTER:FAILURE_LEARNING", maximum_output_level=ProofLevel.RUNTIME_READBACK)


class BenchmarkAdapter(ProofPreservingAdapter):
    def __init__(self) -> None:
        super().__init__("ADAPTER:CFBE_BENCHMARK", maximum_output_level=ProofLevel.RUNTIME_READBACK)


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ProofPreservingAdapter] = {}

    def register(self, adapter: ProofPreservingAdapter) -> None:
        if adapter.adapter_id in self._adapters:
            raise CivitasError("duplicate adapter id")
        self._adapters[adapter.adapter_id] = adapter

    def adapter(self, adapter_id: str) -> ProofPreservingAdapter:
        if adapter_id not in self._adapters:
            raise CivitasError("unknown adapter")
        return self._adapters[adapter_id]

    @classmethod
    def default(cls) -> "AdapterRegistry":
        registry = cls()
        for adapter in (
            ProviderReadbackAdapter(),
            SourceReadbackAdapter(),
            DeterministicTestAdapter(),
            ContextHealthAdapter(),
            FailureLearningAdapter(),
            BenchmarkAdapter(),
        ):
            registry.register(adapter)
        return registry


__all__ = [
    "SUPPORTED_EVENT_CLASSES", "RawObservation", "NormalizedObservation",
    "AdapterReceipt", "ProofPreservingAdapter", "ProviderReadbackAdapter",
    "SourceReadbackAdapter", "DeterministicTestAdapter", "ContextHealthAdapter",
    "FailureLearningAdapter", "BenchmarkAdapter", "AdapterRegistry",
]
