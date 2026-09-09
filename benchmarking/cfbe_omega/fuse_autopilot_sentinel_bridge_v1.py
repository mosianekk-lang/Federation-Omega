from __future__ import annotations

"""Specialist FUSE integration bridge for the FASCG profile.

The bridge composes injected, bounded adapters. It contains no provider clients and
cannot mint authority. It is designed to bind existing Autopilot, Sentinel,
AO-CEF, Formation, Bubbles and ProofOS owners without duplicating their state.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Protocol, Sequence

from benchmarking.cfbe_omega.autopilot_sentinel_cognitive_genome_v1 import (
    ActiveSensingPlanner,
    AutonomyContext,
    CausalInterventionCourt,
    ColdSlateAutopilotSentinelCompiler,
    ColdSlateMissionSpec,
    GeneDomain,
    InterventionCandidate,
    MissionHomeostasisController,
    MissionHomeostasisState,
    RiskAdaptiveAutonomyGate,
    SensingCandidate,
    SentinelCellEcology,
)

SCHEMA = "FUSE-AUTOPILOT-SENTINEL-BRIDGE-V1"
EXTERNAL_EFFECTS = False
AUTHORITY_MINTING = False


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class AutopilotAdapter(Protocol):
    def mission_state(self, mission_id: str) -> Mapping[str, Any]: ...


class SentinelAdapter(Protocol):
    def observations(self, mission_id: str) -> Sequence[Mapping[str, Any]]: ...


class EvolutionAdapter(Protocol):
    def evolution_state(self, mission_id: str) -> Mapping[str, Any]: ...


class ProofAdapter(Protocol):
    def proof_refs(self, mission_id: str) -> Sequence[str]: ...


@dataclass(frozen=True, slots=True)
class IntegrationBinding:
    owner: str
    module_path: str
    role: str
    source_state: str


CURRENT_BINDINGS = (
    IntegrationBinding("CFBE Full-Autopilot", "benchmarking.cfbe_omega.federation_autopilot_metacognition_v1", "mission/metacognitive policy", "CURRENT_MAIN_SOURCE"),
    IntegrationBinding("Sentinel Omega", "federation.sentinel_omega.observability_causal_fabric", "observability/causal intelligence", "CURRENT_MAIN_SOURCE"),
    IntegrationBinding("Sentinel Omega Immune", "federation.sentinel_omega.autonomic_immune_system", "repair/immune policy", "CURRENT_MAIN_SOURCE"),
    IntegrationBinding("AO-CEF", "benchmarking.cfbe_omega.cognitive_evolution_v1", "genome/evolution/verification", "CURRENT_MAIN_SOURCE"),
    IntegrationBinding("CFBE vNext Formation", "benchmarking.cfbe_omega.mission_execution_kernel_vnext.multistream", "collision-safe multi-stream execution", "CURRENT_MAIN_SOURCE"),
    IntegrationBinding("AO-Harmonic", "ao_harmonic_v3.resource_market", "resource/information-gain market", "CURRENT_MAIN_SOURCE"),
    IntegrationBinding("Bubbles Recovery", "bubbles.autonomic_recovery_bridge", "mission/provider recovery handoff", "CURRENT_MAIN_SOURCE"),
    IntegrationBinding("ProofOS", "docs.FEDERATION_PROOFOS_OMEGA", "independent proof/terminal assurance", "CURRENT_MAIN_CONTRACT"),
)


@dataclass(frozen=True, slots=True)
class FuseCognitiveCycleReceipt:
    mission_id: str
    homeostasis_action: str
    sentinel_cells: tuple[str, ...]
    best_sensing_id: str | None
    intervention_simulation_id: str | None
    autonomy_level: str
    profile_id: str
    proof_refs: tuple[str, ...]
    external_effect_authorized: bool
    receipt_sha256: str


class FuseAutopilotSentinelBridge:
    def __init__(self, autopilot: AutopilotAdapter, sentinel: SentinelAdapter, evolution: EvolutionAdapter, proof: ProofAdapter) -> None:
        self.autopilot = autopilot
        self.sentinel = sentinel
        self.evolution = evolution
        self.proof = proof
        self.homeostasis = MissionHomeostasisController()
        self.sensing = ActiveSensingPlanner()
        self.interventions = CausalInterventionCourt()
        self.autonomy = RiskAdaptiveAutonomyGate()
        self.compiler = ColdSlateAutopilotSentinelCompiler()

    def run_internal_cycle(
        self,
        mission_id: str,
        *,
        state: MissionHomeostasisState,
        signal_texts: Sequence[str],
        sensing_candidates: Sequence[SensingCandidate],
        intervention_candidates: Sequence[InterventionCandidate],
        autonomy_context: AutonomyContext,
    ) -> FuseCognitiveCycleReceipt:
        mission_state = dict(self.autopilot.mission_state(mission_id))
        observations = tuple(self.sentinel.observations(mission_id))
        evolution_state = dict(self.evolution.evolution_state(mission_id))
        refs = tuple(sorted(set(self.proof.proof_refs(mission_id))))
        if not mission_state or not observations or not evolution_state or not refs:
            raise ValueError("FUSE_FASCG_CURRENT_RECEIVER_STATE_REQUIRED")

        home = self.homeostasis.decide(state)
        cell_plan = SentinelCellEcology.form(signal_texts, evidence_refs=refs)
        best = self.sensing.best(sensing_candidates) if sensing_candidates else None
        intervention = self.interventions.plan(intervention_candidates) if intervention_candidates else None
        auto = self.autonomy.decide(autonomy_context)
        profile = self.compiler.compile(ColdSlateMissionSpec(
            mission_id=mission_id,
            objective=str(mission_state.get("objective", "Maintain mission homeostasis and verified progress")),
            required_domains=(
                GeneDomain.HOMEOSTASIS,
                GeneDomain.MISSION_AUTOPILOT,
                GeneDomain.SENTINEL_CELL_ECOLOGY,
                GeneDomain.CAUSAL_GRAPH,
                GeneDomain.ACTIVE_SENSING,
                GeneDomain.AUTONOMIC_REPAIR,
                GeneDomain.EVOLUTION,
                GeneDomain.ASSURANCE_VALUE,
            ),
            authority_ceiling=str(mission_state.get("authority_ceiling", "A1_INTERNAL")),
            data_boundary=str(mission_state.get("data_boundary", "MISSION_PRIVATE")),
        ))
        body = {
            "schema": SCHEMA,
            "mission_id": mission_id,
            "homeostasis_action": home.action.value,
            "sentinel_cells": [c.cell_id for c in cell_plan.cells],
            "best_sensing_id": best.sensing_id if best else None,
            "intervention_simulation_id": intervention.selected_id if intervention else None,
            "autonomy_level": auto.level.value,
            "profile_id": profile.profile_id,
            "proof_refs": refs,
            "external_effect_authorized": False,
            "receiver_fingerprints": {
                "mission": _hash(mission_state),
                "observations": _hash(observations),
                "evolution": _hash(evolution_state),
            },
        }
        digest = _hash(body)
        return FuseCognitiveCycleReceipt(
            mission_id=mission_id,
            homeostasis_action=home.action.value,
            sentinel_cells=tuple(body["sentinel_cells"]),
            best_sensing_id=body["best_sensing_id"],
            intervention_simulation_id=body["intervention_simulation_id"],
            autonomy_level=auto.level.value,
            profile_id=profile.profile_id,
            proof_refs=refs,
            external_effect_authorized=False,
            receipt_sha256=digest,
        )


def integration_manifest() -> Mapping[str, Any]:
    body = {
        "schema": SCHEMA,
        "bindings": [(b.owner, b.module_path, b.role, b.source_state) for b in CURRENT_BINDINGS],
        "external_effects": False,
        "authority_minting": False,
        "integration_rule": "REUSE_OWNERS;COMPOSE_ONLY_RESIDUAL_SEMANTICS",
    }
    return {**body, "sha256": _hash(body)}


__all__ = ["AutopilotAdapter", "SentinelAdapter", "EvolutionAdapter", "ProofAdapter", "IntegrationBinding", "CURRENT_BINDINGS", "FuseCognitiveCycleReceipt", "FuseAutopilotSentinelBridge", "integration_manifest"]
