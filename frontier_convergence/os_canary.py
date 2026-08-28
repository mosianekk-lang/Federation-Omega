"""Deterministic provider-disabled canary for Frontier Convergence OS v1."""
from __future__ import annotations

import json

from .core import digest
from .os_core import (
    CapabilityGene,
    CapabilityGenome,
    ConstitutionalEvolutionGate,
    EvidenceVirtualizer,
    EvolutionMode,
    EvolutionProposal,
    ExperimentOption,
    FrontierConvergenceOS,
)


def run_canary() -> dict[str, object]:
    gene = CapabilityGene.create(
        name="bounded evidence virtualization",
        mechanism="large evidence remains external while compact hash-bound receipts enter control flows",
        proof_requirements=("byte digest", "bounded excerpt", "storage reference"),
    )
    genome = CapabilityGenome.compile(
        capability_class="execution continuity",
        genes=(gene,),
    )
    option = ExperimentOption.create(
        label="bounded internal shadow experiment",
        expected_information_gain=0.95,
        mission_value=0.9,
        proof_strength_gain=0.9,
        reversibility=1.0,
        estimated_cost=0.0,
        latency_burden=0.1,
        owner_burden=0.05,
        risk=0.05,
        evidence_refs=("fixture:public-synthetic",),
    )
    plan = FrontierConvergenceOS().plan(
        genome=genome,
        experiment_options=(option,),
        evolution_mode=EvolutionMode.VERTICAL,
    )
    pointer = EvidenceVirtualizer.virtualize(
        storage_ref="artifact:public-synthetic",
        content="FCOS-CANARY-" * 6_000,
    )
    architectural = EvolutionProposal.create(
        mode=EvolutionMode.ARCHITECTURAL,
        capability_key=genome.genome_key,
        source_receiver="superior-logic",
        target_receiver="superior-logic",
        description="Canary architectural change that must remain owner-gated.",
        changes_constitutional_boundary=True,
    )
    architecture_gate = ConstitutionalEvolutionGate.evaluate(
        architectural,
        proof_refs=("fixture:architecture",),
        simulation_ref="fixture:simulation",
        rollback_ref="fixture:rollback",
        independent_readback_ref="fixture:readback",
        owner_approved=False,
    )
    body = {
        "schema": "FRONTIER-CONVERGENCE-OS-CANARY-1",
        "state": "PASS",
        "authority_ceiling": plan.authority_ceiling,
        "provider_effects": False,
        "external_effect": plan.external_effect,
        "genome_key": genome.genome_key,
        "selected_experiment_key": plan.selected_experiment_key,
        "evidence_pointer_key": pointer.pointer_key,
        "evidence_byte_count": pointer.byte_count,
        "evidence_chunk_count": pointer.chunk_count,
        "raw_evidence_inline": pointer.raw_inline,
        "architectural_gate": architecture_gate.decision,
        "architectural_owner_block": "OWNER_APPROVAL_REQUIRED_FOR_ARCHITECTURAL_EVOLUTION" in architecture_gate.blockers,
        "next_gate": plan.next_gate,
    }
    body["receipt_sha256"] = digest(body)
    return body


def main() -> int:
    receipt = run_canary()
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["state"] == "PASS" and receipt["provider_effects"] is False else 1


if __name__ == "__main__":
    raise SystemExit(main())
