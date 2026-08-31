from __future__ import annotations

from dataclasses import asdict, dataclass

from benchmarking.cfbe_omega.federation_competitive_upgrade_fabric_v1 import (
    ImplementationMode,
    load_genome,
)


@dataclass(frozen=True, slots=True)
class GeneImplementationReceipt:
    gene_id: str
    state: str
    implementation_target: str
    acceptance_gate: str
    provider_runtime_proven: bool


@dataclass(frozen=True, slots=True)
class CompetitiveGenomeImplementationReceipt:
    schema: str
    gene_count: int
    routed_count: int
    reuse_count: int
    composed_source_count: int
    provider_gated_count: int
    unrouted_gene_ids: tuple[str, ...]
    stable_promotion_allowed: bool
    provider_effect_authorized: bool
    receipts: tuple[GeneImplementationReceipt, ...]

    def canonical_mapping(self) -> dict[str, object]:
        return asdict(self)


def compile_implementation_receipt() -> CompetitiveGenomeImplementationReceipt:
    genes = load_genome()
    receipts: list[GeneImplementationReceipt] = []
    for gene in genes:
        if gene.implementation_mode == ImplementationMode.REUSE_VERIFIED:
            state = "IMPLEMENTED_BY_VERIFIED_REUSE"
            provider_runtime = False
        elif gene.implementation_mode == ImplementationMode.COMPOSED_BY_FABRIC:
            state = "IMPLEMENTED_SOURCE_COMPOSITION"
            provider_runtime = False
        elif gene.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT:
            state = "IMPLEMENTED_PROVIDER_GATE_CONTRACT_RUNTIME_OPEN"
            provider_runtime = False
        else:
            state = "UNROUTED"
            provider_runtime = False
        receipts.append(
            GeneImplementationReceipt(
                gene_id=gene.gene_id,
                state=state,
                implementation_target=gene.implementation_target,
                acceptance_gate=gene.acceptance_gate,
                provider_runtime_proven=provider_runtime,
            )
        )
    unrouted = tuple(item.gene_id for item in receipts if item.state == "UNROUTED")
    return CompetitiveGenomeImplementationReceipt(
        schema="CFBE-FEDERATION-HYPERLEVERAGE-100-IMPLEMENTATION-RECEIPT-V1",
        gene_count=len(receipts),
        routed_count=len(receipts) - len(unrouted),
        reuse_count=sum(item.state == "IMPLEMENTED_BY_VERIFIED_REUSE" for item in receipts),
        composed_source_count=sum(item.state == "IMPLEMENTED_SOURCE_COMPOSITION" for item in receipts),
        provider_gated_count=sum(item.state == "IMPLEMENTED_PROVIDER_GATE_CONTRACT_RUNTIME_OPEN" for item in receipts),
        unrouted_gene_ids=unrouted,
        stable_promotion_allowed=False,
        provider_effect_authorized=False,
        receipts=tuple(receipts),
    )
