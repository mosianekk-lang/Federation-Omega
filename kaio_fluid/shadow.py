from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .compiler import CognitiveCompiler
from .models import EvidenceItem, EvidenceState, ProblemContext


@dataclass(frozen=True)
class ShadowValidationResult:
    status: str
    domain: str
    experiment_id: str
    source_count: int
    open_provider_proofs: int
    mode: str
    authority_ceiling: str
    external_effect: bool
    provider_mutation_permitted: bool
    provider_runtime_verified: bool
    release_claim: str


class RegisteredSourceShadowValidator:
    """Run KAIO against an already-registered read-only Federation packet.

    The validator consumes packet metadata and source identities only. It does not
    mutate provider state, elevate source proof states, or turn a shadow result
    into runtime/provider proof.
    """

    REQUIRED_PACKET_FIELDS = {
        "authority_ceiling",
        "domain",
        "experiment_id",
        "external_effect",
        "objective",
        "provider_mutation_permitted",
        "required_provider_proof",
        "sources",
    }

    def __init__(self) -> None:
        self.compiler = CognitiveCompiler()

    def validate(self, packet: dict[str, Any]) -> ShadowValidationResult:
        missing = sorted(self.REQUIRED_PACKET_FIELDS - set(packet))
        if missing:
            raise ValueError(f"missing packet fields: {','.join(missing)}")
        if packet["external_effect"] is not False:
            raise ValueError("shadow packet must have external_effect=false")
        if packet["provider_mutation_permitted"] is not False:
            raise ValueError("shadow packet must forbid provider mutation")
        if str(packet["authority_ceiling"]) != "A1_INTERNAL_READ_ONLY":
            raise ValueError("shadow packet requires exact A1_INTERNAL_READ_ONLY authority")

        sources = tuple(packet["sources"])
        if not sources:
            raise ValueError("shadow packet has no registered sources")
        source_ids = tuple(str(source.get("source_id", "")).strip() for source in sources)
        if any(not source_id for source_id in source_ids):
            raise ValueError("shadow packet source identities must be nonblank")
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("shadow packet source identities must be unique")

        evidence = tuple(
            EvidenceItem(
                id=source_id,
                state=EvidenceState.SUPPORTED,
                source_identity=str(source["title"]),
                independent_lineage=source_id,
                reliability=0.8,
                materiality=1.0,
            )
            for source, source_id in zip(sources, source_ids)
        )
        provider_proofs = tuple(packet["required_provider_proof"])
        invalid_provider_states = tuple(
            str(proof.get("initial_state", ""))
            for proof in provider_proofs
            if not str(proof.get("initial_state", "")).startswith("UNVERIFIED")
        )
        if invalid_provider_states:
            raise ValueError("shadow packet cannot import promoted provider proof state")
        unresolved = provider_proofs
        uncertainty = min(1.0, 0.35 + 0.05 * len(unresolved))
        novelty = min(1.0, 0.35 + 0.03 * len(unresolved))
        ctx = ProblemContext(
            objective=str(packet["objective"]),
            stakes=0.75,
            uncertainty=uncertainty,
            novelty=novelty,
            irreversibility=0.65,
            evidence=evidence,
            constraints=tuple(str(p.get("requirement", "")) for p in unresolved),
            assumptions=("registered-source control packet is read-only shadow input",),
        )
        plan = self.compiler.compile(ctx)
        if plan.external_effect or plan.authority_ceiling != "A1_INTERNAL":
            raise AssertionError("compiler violated shadow authority boundary")

        return ShadowValidationResult(
            status="SHADOW_VALIDATED_REGISTERED_SOURCE_PACKET",
            domain=str(packet["domain"]),
            experiment_id=str(packet["experiment_id"]),
            source_count=len(sources),
            open_provider_proofs=len(unresolved),
            mode=plan.mode.value,
            authority_ceiling=plan.authority_ceiling,
            external_effect=False,
            provider_mutation_permitted=False,
            provider_runtime_verified=False,
            release_claim=(
                "KAIO shadow validation passed on a registered read-only source packet; "
                "provider runtime and real-world outcome effectiveness remain unverified."
            ),
        )
