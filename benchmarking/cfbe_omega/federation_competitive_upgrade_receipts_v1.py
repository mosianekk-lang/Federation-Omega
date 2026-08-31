from __future__ import annotations

from dataclasses import asdict, dataclass

from benchmarking.cfbe_omega.federation_competitive_upgrade_fabric_v1 import (
    ControlBindingKind,
    ImplementationMode,
    compile_control_bindings,
    evaluate_gene_control,
    load_genome,
)


@dataclass(frozen=True, slots=True)
class GeneImplementationReceipt:
    gene_id: str
    state: str
    implementation_target: str
    acceptance_gate: str
    binding_kind: str
    handler_name: str
    source_control_implemented: bool
    evidence_state: str
    missing_evidence: tuple[str, ...]
    provider_runtime_proven: bool


@dataclass(frozen=True, slots=True)
class CompetitiveGenomeImplementationReceipt:
    schema: str
    gene_count: int
    routed_count: int
    reuse_count: int
    composed_source_count: int
    provider_gated_count: int
    source_control_count: int
    executable_binding_count: int
    evidence_ready_count: int
    runtime_proven_count: int
    unrouted_gene_ids: tuple[str, ...]
    stable_promotion_allowed: bool
    provider_effect_authorized: bool
    receipts: tuple[GeneImplementationReceipt, ...]

    def canonical_mapping(self) -> dict[str, object]:
        return asdict(self)


def compile_implementation_receipt() -> CompetitiveGenomeImplementationReceipt:
    genes = load_genome()
    bindings = {item.gene_id: item for item in compile_control_bindings(genes)}
    receipts: list[GeneImplementationReceipt] = []
    for gene in genes:
        binding = bindings[gene.gene_id]
        decision = evaluate_gene_control(gene.gene_id)
        if binding.kind == ControlBindingKind.REUSED_CONTROL_GATE:
            state = "SOURCE_REUSE_GATE_BOUND_PROOF_REQUIRED"
        elif binding.kind == ControlBindingKind.FABRIC_POLICY_GATE:
            state = "SOURCE_COMPOSITION_GATE_BOUND_PROOF_REQUIRED"
        else:
            state = "SOURCE_PROVIDER_GATE_BOUND_RUNTIME_OPEN"
        receipts.append(
            GeneImplementationReceipt(
                gene_id=gene.gene_id,
                state=state,
                implementation_target=gene.implementation_target,
                acceptance_gate=gene.acceptance_gate,
                binding_kind=binding.kind.value,
                handler_name=binding.handler_name,
                source_control_implemented=binding.source_control_implemented,
                evidence_state=decision.state.value,
                missing_evidence=decision.missing_evidence,
                provider_runtime_proven=decision.runtime_proven,
            )
        )
    unrouted = tuple(item.gene_id for item in receipts if not item.source_control_implemented)
    return CompetitiveGenomeImplementationReceipt(
        schema="CFBE-FEDERATION-HYPERLEVERAGE-100-IMPLEMENTATION-RECEIPT-V2",
        gene_count=len(receipts),
        routed_count=len(receipts) - len(unrouted),
        reuse_count=sum(gene.implementation_mode == ImplementationMode.REUSE_VERIFIED for gene in genes),
        composed_source_count=sum(gene.implementation_mode == ImplementationMode.COMPOSED_BY_FABRIC for gene in genes),
        provider_gated_count=sum(gene.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT for gene in genes),
        source_control_count=sum(item.source_control_implemented for item in receipts),
        executable_binding_count=len(bindings),
        evidence_ready_count=sum(not item.missing_evidence for item in receipts),
        runtime_proven_count=sum(item.provider_runtime_proven for item in receipts),
        unrouted_gene_ids=unrouted,
        stable_promotion_allowed=False,
        provider_effect_authorized=False,
        receipts=tuple(receipts),
    )
