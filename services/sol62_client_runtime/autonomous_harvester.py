from __future__ import annotations

from dataclasses import asdict
from typing import Any

from federation.idea_to_system_compiler import CapabilityRecord, compile_idea_to_system
from superior_logic.codeforge import CapabilityAcquirer, CapabilityCandidate, CapabilityGap
from superior_logic.hypercube_bottleneck_resolver import (
    BottleneckKind,
    BottleneckSignal,
    HypercubeBottleneckResolver,
)
from sol_61_runtime.sol_62_complete_client_runtime import HarvestOutcome
from services.sol62_client_runtime.runtime_upgrade_genome import genome_summary, select_upgrade_genes
from services.sol62_client_runtime.asia_frontier_p0 import compile_p0_plan
from services.sol62_client_runtime.asia_frontier_p1_p2 import compile_p1_p2_plan
from services.sol62_client_runtime.alpha_omega_formation_binding import (
    Sol62AlphaOmegaFormationBinding,
    receipt_to_dict as alpha_omega_formation_receipt_to_dict,
)
from sol_61_runtime.sol_62_frontier_primitives import digest


class FuseAutonomousHarvester:
    """Deterministic FUSE harvest/build planner bound to existing Hypercube + CodeForge.

    It does not grant source/provider/effect authority. It converts a SOL execution
    gap into a reusable/compose/harvest/build-minimum packet for the existing
    engineering/runtime lanes.
    """

    def __init__(self, *, source_frontier: str) -> None:
        self.source_frontier = source_frontier
        self.hypercube = HypercubeBottleneckResolver()
        self.acquirer = CapabilityAcquirer()
        self.strategy = Sol62AlphaOmegaFormationBinding()

    async def harvest(
        self,
        *,
        mission_id: str,
        transition_id: str | None,
        objective: str,
        reason: str,
    ) -> HarvestOutcome:
        reason_upper = reason.upper()
        kind = (
            BottleneckKind.PROVIDER_RUNTIME
            if reason_upper in {"NO_QUALIFIED_ROUTE", "QUALIFIED_ROUTES_EXHAUSTED"}
            else BottleneckKind.ARCHITECTURAL_DUPLICATION
            if "BINDING" in reason_upper
            else BottleneckKind.UNKNOWN
        )
        internal = (
            "SOL_6_2",
            "FUSE_MOBILE_GATEWAY",
            "FUSE_GENESIS_RESIDENT_EXECUTOR_V2",
            "HYPERCUBE",
            "CODEFORGE",
            "PROOFOS",
        )
        signal = BottleneckSignal(
            bottleneck_id="SOL62-" + digest(
                {"mission_id": mission_id, "transition_id": transition_id, "reason": reason}
            )[:20].upper(),
            kind=kind,
            summary=f"SOL mission execution gap: {reason}",
            evidence_refs=(f"SOL62:{mission_id}:{transition_id or 'MISSION'}:{reason}",),
            throughput_drag=0.8,
            latency_share=0.7,
            queue_wait_share=0.5,
            failure_recurrence=0.6,
            dependency_centrality=0.8,
            owner_burden=0.9,
            cost_pressure=0.3,
            proof_gap=0.7,
            risk=0.4,
            commercial_leverage=0.7,
            differentiation_potential=0.7,
            internal_coverage=0.55,
            affected_missions=1,
            internal_capabilities=internal,
        )
        resolution = self.hypercube.resolve(signal)

        required = (
            "provider_neutral_execution",
            "durable_continuation",
            "semantic_readback",
            "verified_reality_closure",
        )
        if "BINDING" in reason_upper:
            required += ("transition_execution_binding",)
        gap = CapabilityGap(
            gap_id=signal.bottleneck_id,
            semantic_operation="SOL62_MISSION_CONTINUATION",
            required_features=required,
        )
        candidates = (
            CapabilityCandidate(
                "SOL62",
                "INTERNAL",
                ("verified_reality_closure", "semantic_readback"),
                "SOURCE_ADMITTED",
                "repo:sol_61_runtime",
                source_available=True,
                tests_present=True,
                security_reviewed=True,
            ),
            CapabilityCandidate(
                "FUSE_GATEWAY",
                "INTERNAL",
                ("provider_neutral_execution", "semantic_readback"),
                "SOURCE_ADMITTED",
                "repo:services/fuse_mobile_gateway",
                source_available=True,
                tests_present=True,
                security_reviewed=True,
            ),
            CapabilityCandidate(
                "GENESIS_RESIDENT",
                "INTERNAL",
                ("durable_continuation",),
                "SOURCE_ADMITTED",
                "repo:fuse_genesis/resident_host.py",
                source_available=True,
                tests_present=True,
                security_reviewed=True,
            ),
        )
        acquisition = self.acquirer.plan(gap, internal_candidates=candidates)

        capability_records = tuple(
            CapabilityRecord(
                capability_id=row.candidate_id,
                name=row.candidate_id,
                tags=tuple(row.capabilities),
                evidence_state="SOURCE_ADMITTED",
                reusable=True,
            )
            for row in candidates
        )
        system_plan = compile_idea_to_system(
            f"{objective}. Close execution gap {reason} without mutating the owner objective.",
            capability_records,
            source_frontier=self.source_frontier,
            domain_hint="SOL62_RUNTIME",
        )

        selected = resolution.selected
        upgrade_genome = select_upgrade_genes(
            objective=objective,
            reason=reason,
            limit=12,
        )
        strategy_receipt = self.strategy.compile(
            mission_id=mission_id,
            objective=objective,
            reason=reason,
            routes=(),
            constraints=("proof-before-claim", "no-authority-expansion", "verified-reality-closure"),
            preferred_surfaces=("FUSE_GATEWAY", "GENESIS", "LOCAL_FUSE"),
            selected_upgrade_genes=tuple(
                {
                    "gene_id": gene.gene_id,
                    "category": gene.category,
                    "mechanism": gene.mechanism,
                    "tags": list(gene.tags),
                    "provenance": gene.provenance,
                    "maturity": gene.maturity,
                }
                for gene in upgrade_genome
            ),
        )
        asia_frontier_p0 = compile_p0_plan(objective=objective, reason=reason)
        asia_frontier_p1_p2 = compile_p1_p2_plan(objective=objective, reason=reason)
        build_packet: dict[str, Any] = {
            "schema": "SOL62_FUSE_AUTOBUILD_PACKET_V1",
            "task_type": "SOL62_CLIENT_BUILD",
            "mission_id": mission_id,
            "transition_id": transition_id,
            "objective": objective,
            "reason": reason,
            "source_frontier": self.source_frontier,
            "hypercube": {
                "bottleneck_id": resolution.bottleneck_id,
                "bottleneck_score": resolution.bottleneck_score,
                "selected_candidate_id": selected.candidate_id,
                "selected_family": selected.family.value,
                "selected_name": selected.name,
                "mechanism_ids": list(selected.mechanism_ids),
                "internal_harvest": list(resolution.internal_harvest),
                "market_harvest": list(resolution.market_harvest),
                "invention_required": resolution.invention_required,
                "receipt_sha256": resolution.receipt_sha256,
            },
            "codeforge": {
                "action": acquisition.action,
                "candidate_id": acquisition.candidate_id,
                "direct_code_allowed": acquisition.direct_code_allowed,
                "residual_features": list(acquisition.residual_features),
                "proof_gates": list(acquisition.proof_gates),
                "plan_sha256": acquisition.plan_sha256,
            },
            "idea_system": {
                "digest": system_plan.digest(),
                "workflow_pattern": system_plan.workflow_pattern,
                "autonomous_steps": list(system_plan.autonomous_steps),
                "capability_decisions": [asdict(x) for x in system_plan.capability_decisions],
                "owner_questions": list(system_plan.owner_questions),
            },
            "alpha_omega_formation": alpha_omega_formation_receipt_to_dict(strategy_receipt),
            "asia_frontier_p0": asia_frontier_p0,
            "asia_frontier_p1_p2": asia_frontier_p1_p2,
            "runtime_upgrade_genome": {
                "summary": genome_summary(),
                "selected": [
                    {
                        "gene_id": gene.gene_id,
                        "category": gene.category,
                        "mechanism": gene.mechanism,
                        "tags": list(gene.tags),
                        "provenance": gene.provenance,
                        "maturity": gene.maturity,
                    }
                    for gene in upgrade_genome
                ],
                "selection_limit": 12,
                "selection_semantic": "RANKED_CANDIDATE_RESIDUALS_ONLY",
            },
            "authority_boundary": {
                "source_mutation_authority_granted": False,
                "provider_effect_authority_granted": False,
                "build_must_run_in_existing_governed_engineering_lane": True,
            },
        }
        return HarvestOutcome(
            build_required=True,
            build_packet=build_packet,
            reason="FUSE_HYPERCUBE_CODEFORGE_BUILD_PACKET_READY",
        )
