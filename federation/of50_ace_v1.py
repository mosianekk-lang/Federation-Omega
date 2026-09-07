"""FUSE Ω — Omega Forge 50 Autonomous Completion Engine (OF50-ACE) v1.

Provider-neutral, effect-free composition kernel. It composes existing Federation
controls; it does not create another foundry, scheduler, authority, truth/proof
plane, memory root, or provider runtime.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping

CAPABILITY_ID = "FUSE-OF50-ACE-V1"
CANONICAL_NAME = "FUSE Ω — OMEGA FORGE 50 AUTONOMOUS COMPLETION ENGINE"
SCHEMA = "FUSE-OF50-ACE-CYCLE-V1"
VERSION = "1.0.0"
HORIZON_IDS = tuple(f"H{i:02d}" for i in range(1, 51))
ALPHA_OMEGA_LIFECYCLE = (
    "INTAKE", "DISCOVERY", "DECOMPOSITION", "ARCHITECTURE", "BUILD",
    "TEST", "DEPLOY", "VERIFY", "OPERATE", "MAINTAIN",
)
REQUIRED_CHAIN = (
    "OWNER_PROTECTION", "AAREK", "OH50", "FORMATION_INNOVATION",
    "ALPHA_OMEGA_IF_REQUIRED", "EXECUTION", "SEMANTIC_READBACK",
    "FAILURE_WIN_LEARNING", "MISSION_GENOME_IF_REUSABLE_WIN",
    "OH50_RESCAN", "MISSION_RECOMPILE",
)


class Authority(str, Enum):
    A0_INTERNAL = "A0_INTERNAL"
    A1_INTERNAL = "A1_INTERNAL"
    A2_OWNER_RESERVED = "A2_OWNER_RESERVED"


_AUTHORITY_RANK = {Authority.A0_INTERNAL.value: 0, Authority.A1_INTERNAL.value: 1, Authority.A2_OWNER_RESERVED.value: 2}


class ProofTier(str, Enum):
    SOURCE = "SOURCE"
    CI = "CI"
    LOCAL_RUNTIME = "LOCAL_RUNTIME"
    PROVIDER_RUNTIME = "PROVIDER_RUNTIME"
    SEMANTIC_READBACK = "SEMANTIC_READBACK"


_PROOF_RANK = {ProofTier.SOURCE.value: 0, ProofTier.CI.value: 1, ProofTier.LOCAL_RUNTIME.value: 2, ProofTier.PROVIDER_RUNTIME.value: 3, ProofTier.SEMANTIC_READBACK.value: 4}


class ReuseBuildDecision(str, Enum):
    REUSE = "REUSE"
    REBIND = "REBIND"
    REPAIR = "REPAIR"
    RECONFIGURE = "RECONFIGURE"
    COMPOSE = "COMPOSE"
    UPGRADE = "UPGRADE"
    HARVEST = "HARVEST"
    EXPERIMENT = "EXPERIMENT"
    TEMPORARY_BUILD = "TEMPORARY_BUILD"
    PERMANENT_BUILD = "PERMANENT_BUILD"


class CycleDecision(str, Enum):
    CONTINUE_RECOVERY = "CONTINUE_RECOVERY"
    CHANGED_ROUTE_REQUIRED = "CHANGED_ROUTE_REQUIRED"
    BUILD_REQUIRED = "BUILD_REQUIRED"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"
    COMPLETE_VERIFIED = "COMPLETE_VERIFIED"


@dataclass(frozen=True, slots=True)
class HorizonCell:
    horizon_id: str
    state: str
    evidence_ref: str = ""
    owner_role: str = ""


@dataclass(frozen=True, slots=True)
class SwarmManifest:
    mission_id: str
    host_algorithm_id: str
    objective: str
    authority_ceiling: str
    horizons: tuple[HorizonCell, ...]
    specialist_roles: tuple[str, ...] = ()
    role: str = "FORESIGHT_AND_SPECIALIST_FORMATION_ONLY"
    foundry_authority: bool = False
    build_authority: bool = False
    semantic_readback_contract: str = ""

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        ids = tuple(cell.horizon_id for cell in self.horizons)
        if len(ids) != 50 or set(ids) != set(HORIZON_IDS):
            errors.append("OH50_HORIZON_COVERAGE_NOT_50_OF_50")
        if len(ids) != len(set(ids)):
            errors.append("OH50_DUPLICATE_HORIZON")
        if self.role != "FORESIGHT_AND_SPECIALIST_FORMATION_ONLY":
            errors.append("OH50_ROLE_DRIFT")
        if self.foundry_authority or self.build_authority:
            errors.append("OH50_PARALLEL_FOUNDRY_OR_BUILD_AUTHORITY_FORBIDDEN")
        if not self.mission_id.strip() or not self.host_algorithm_id.strip() or not self.objective.strip():
            errors.append("OH50_MANIFEST_IDENTITY_INCOMPLETE")
        if not self.semantic_readback_contract.strip():
            errors.append("OH50_SEMANTIC_READBACK_CONTRACT_MISSING")
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    route_id: str
    route_family: str
    score: float
    falsifier: str
    capability_hypothesis: str


@dataclass(frozen=True, slots=True)
class FormationDecision:
    mission_id: str
    foundry_cycle_ref: str
    route_candidates: tuple[RouteCandidate, ...]
    selected_route_id: str
    reuse_vs_build: ReuseBuildDecision
    selected_capability_hypothesis: str
    implementation_required: bool
    authority_ceiling: str = Authority.A1_INTERNAL.value
    external_effect: bool = False

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        ids = [item.route_id for item in self.route_candidates]
        families = {item.route_family for item in self.route_candidates}
        if len(self.route_candidates) < 2 or len(families) < 2:
            errors.append("FORMATION_COMPETING_ROUTE_FAMILIES_MISSING")
        if len(ids) != len(set(ids)):
            errors.append("FORMATION_DUPLICATE_ROUTE_ID")
        if self.selected_route_id not in ids:
            errors.append("FORMATION_SELECTED_ROUTE_NOT_IN_CANDIDATES")
        if any(not item.falsifier.strip() for item in self.route_candidates):
            errors.append("FORMATION_FALSIFIER_MISSING")
        if not self.foundry_cycle_ref.strip():
            errors.append("FORMATION_FOUNDRY_CYCLE_REF_MISSING")
        if not self.selected_capability_hypothesis.strip():
            errors.append("FORMATION_SELECTED_CAPABILITY_HYPOTHESIS_MISSING")
        if self.external_effect:
            errors.append("FORMATION_EXTERNAL_EFFECT_FORBIDDEN")
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class AlphaOmegaPacket:
    mission_id: str
    packet_ref: str
    build_plan_ref: str
    lifecycle: tuple[str, ...]
    proof_gates: tuple[str, ...]
    rollback_ref: str
    runtime_target: str
    terminal_criteria: tuple[str, ...]
    authority_ceiling: str = Authority.A1_INTERNAL.value
    truth_boundary: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.lifecycle != ALPHA_OMEGA_LIFECYCLE:
            errors.append("ALPHA_OMEGA_LIFECYCLE_INCOMPLETE")
        if not {"TEST", "ROLLBACK", "SEMANTIC_READBACK"}.issubset(set(self.proof_gates)):
            errors.append("ALPHA_OMEGA_PROOF_GATES_INCOMPLETE")
        if not self.rollback_ref.strip():
            errors.append("ALPHA_OMEGA_ROLLBACK_REF_MISSING")
        if not self.runtime_target.strip():
            errors.append("ALPHA_OMEGA_RUNTIME_TARGET_MISSING")
        if not self.terminal_criteria:
            errors.append("ALPHA_OMEGA_TERMINAL_CRITERIA_MISSING")
        if self.truth_boundary.get("provider_deployed") and not self.truth_boundary.get("provider_readback"):
            errors.append("ALPHA_OMEGA_PROVIDER_DEPLOYMENT_WITHOUT_READBACK")
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class ExecutionProof:
    executed: bool
    proof_tier: ProofTier
    execution_ref: str = ""
    semantic_readback_ref: str = ""
    provider_ack_ref: str = ""
    provider_receipt_ref: str = ""


@dataclass(frozen=True, slots=True)
class FailureTransition:
    current_fingerprint: str = ""
    prior_fingerprint: str = ""
    predicate_changed: bool = False
    route_changed: bool = False
    learning_ref: str = ""

    @property
    def unchanged_replay(self) -> bool:
        return bool(self.current_fingerprint and self.current_fingerprint == self.prior_fingerprint and not self.predicate_changed and not self.route_changed)


@dataclass(frozen=True, slots=True)
class MissionGenome:
    genome_id: str
    objective_pattern: str
    dependency_graph_ref: str
    winning_route: str
    required_capabilities: tuple[str, ...]
    authority_ceiling: str
    proof_gates: tuple[str, ...]
    rollback_ref: str
    runtime_identity: str
    failure_fingerprints: tuple[str, ...]
    value_delta: Mapping[str, Any]
    reusable_conditions: tuple[str, ...]
    provider_truth_inherited: bool = False

    def digest(self) -> str:
        return "sha256:" + _sha(asdict(self))


@dataclass(frozen=True, slots=True)
class OF50CycleRequest:
    mission_id: str
    objective: str
    authority_ceiling: str
    owner_protection_decision: str
    owner_protection_violations: tuple[str, ...]
    aarek_receipt_ref: str
    swarm_manifest: SwarmManifest | None
    formation_decision: FormationDecision | None
    alpha_omega_packet: AlphaOmegaPacket | None
    execution_proof: ExecutionProof
    failure_transition: FailureTransition = field(default_factory=FailureTransition)
    machine_resolvable_owner_tasks: tuple[str, ...] = ()
    genuine_owner_decisions: tuple[str, ...] = ()
    provider_runtime_required: bool = False
    objective_satisfied: bool = False
    required_outcomes: tuple[str, ...] = ()
    proven_outcomes: tuple[str, ...] = ()
    reusable_verified_win: bool = False
    mission_genome: MissionGenome | None = None
    oh50_rescan_ref: str = ""
    mission_recompiled: bool = False
    completion_requested: bool = False


@dataclass(frozen=True, slots=True)
class OF50CycleReceipt:
    schema: str
    version: str
    capability_id: str
    mission_id: str
    decision: CycleDecision
    violations: tuple[str, ...]
    stage_state: Mapping[str, str]
    completion_verified: bool
    receipt_digest: str


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def _authority_within(child: str, parent: str) -> bool:
    return child in _AUTHORITY_RANK and parent in _AUTHORITY_RANK and _AUTHORITY_RANK[child] <= _AUTHORITY_RANK[parent]


class OF50ACEKernel:
    """Deterministic composition and anti-bypass court for material missions."""

    def evaluate(self, request: OF50CycleRequest) -> OF50CycleReceipt:
        violations: list[str] = []
        stage = {name: "MISSING" for name in REQUIRED_CHAIN}
        if not request.mission_id.strip() or not request.objective.strip():
            violations.append("MISSION_IDENTITY_INCOMPLETE")

        if request.owner_protection_decision:
            stage["OWNER_PROTECTION"] = "PRESENT"
        else:
            violations.append("OWNER_PROTECTION_BYPASS")
        if request.machine_resolvable_owner_tasks or any("MACHINE_RESOLVABLE_WORK_OFFLOADED_TO_OWNER" in item for item in request.owner_protection_violations):
            violations.append("MACHINE_RESOLVABLE_OWNER_OFFLOAD")

        if request.aarek_receipt_ref.strip():
            stage["AAREK"] = "PRESENT"
        else:
            violations.append("AAREK_BYPASS")

        if request.swarm_manifest is None:
            violations.append("OH50_BYPASS")
        else:
            stage["OH50"] = "PRESENT"
            violations.extend(request.swarm_manifest.validate())
            if not _authority_within(request.swarm_manifest.authority_ceiling, request.authority_ceiling):
                violations.append("OH50_AUTHORITY_WIDENING")

        implementation_required = False
        if request.formation_decision is None:
            violations.append("FORMATION_BYPASS")
        else:
            stage["FORMATION_INNOVATION"] = "PRESENT"
            violations.extend(request.formation_decision.validate())
            implementation_required = request.formation_decision.implementation_required
            if not _authority_within(request.formation_decision.authority_ceiling, request.authority_ceiling):
                violations.append("FORMATION_AUTHORITY_WIDENING")

        if implementation_required:
            if request.alpha_omega_packet is None:
                violations.append("ALPHA_OMEGA_BYPASS_WHEN_IMPLEMENTATION_REQUIRED")
            else:
                stage["ALPHA_OMEGA_IF_REQUIRED"] = "PRESENT"
                violations.extend(request.alpha_omega_packet.validate())
                if not _authority_within(request.alpha_omega_packet.authority_ceiling, request.authority_ceiling):
                    violations.append("ALPHA_OMEGA_AUTHORITY_WIDENING")
        else:
            stage["ALPHA_OMEGA_IF_REQUIRED"] = "NOT_REQUIRED"

        proof = request.execution_proof
        if proof.executed and proof.execution_ref.strip():
            stage["EXECUTION"] = "PRESENT"
        else:
            violations.append("EXECUTION_PROOF_MISSING")
        if proof.semantic_readback_ref.strip():
            stage["SEMANTIC_READBACK"] = "PRESENT"
        elif request.completion_requested:
            violations.append("SEMANTIC_READBACK_MISSING")

        if request.provider_runtime_required:
            if _PROOF_RANK[proof.proof_tier.value] < _PROOF_RANK[ProofTier.PROVIDER_RUNTIME.value]:
                violations.append("SOURCE_OR_CI_PROMOTED_AS_PROVIDER_RUNTIME_PROOF")
            if not proof.provider_ack_ref.strip() or not proof.provider_receipt_ref.strip():
                violations.append("PROVIDER_ACK_OR_RECEIPT_MISSING")
            if not proof.semantic_readback_ref.strip():
                violations.append("PROVIDER_SEMANTIC_READBACK_MISSING")

        if request.failure_transition.unchanged_replay:
            violations.append("UNCHANGED_FAILED_ROUTE_REPLAY")
        if request.failure_transition.learning_ref.strip():
            stage["FAILURE_WIN_LEARNING"] = "PRESENT"
        elif request.failure_transition.current_fingerprint:
            violations.append("FAILURE_WIN_LEARNING_MISSING")
        else:
            stage["FAILURE_WIN_LEARNING"] = "NO_FAILURE"

        if request.reusable_verified_win:
            if request.mission_genome is None:
                violations.append("MISSION_GENOME_MISSING_AFTER_REUSABLE_WIN")
            else:
                stage["MISSION_GENOME_IF_REUSABLE_WIN"] = "PRESENT"
                if request.mission_genome.provider_truth_inherited:
                    violations.append("MISSION_GENOME_STALE_PROVIDER_TRUTH_INHERITANCE")
                if not _authority_within(request.mission_genome.authority_ceiling, request.authority_ceiling):
                    violations.append("MISSION_GENOME_AUTHORITY_WIDENING")
        else:
            stage["MISSION_GENOME_IF_REUSABLE_WIN"] = "NOT_REQUIRED"

        if request.oh50_rescan_ref.strip():
            stage["OH50_RESCAN"] = "PRESENT"
        elif request.completion_requested:
            violations.append("OH50_RESCAN_MISSING")
        if request.mission_recompiled:
            stage["MISSION_RECOMPILE"] = "PRESENT"
        elif request.completion_requested:
            violations.append("MISSION_RECOMPILE_MISSING")

        outcomes_complete = set(request.required_outcomes).issubset(set(request.proven_outcomes))
        completion_verified = bool(request.completion_requested and request.objective_satisfied and outcomes_complete and proof.executed and proof.semantic_readback_ref.strip() and not violations)
        if request.completion_requested and not completion_verified:
            violations.append("PREMATURE_COMPLETION")
            completion_verified = False

        if request.genuine_owner_decisions and not request.machine_resolvable_owner_tasks:
            decision = CycleDecision.OWNER_DECISION_REQUIRED
        elif "UNCHANGED_FAILED_ROUTE_REPLAY" in violations:
            decision = CycleDecision.CHANGED_ROUTE_REQUIRED
        elif "ALPHA_OMEGA_BYPASS_WHEN_IMPLEMENTATION_REQUIRED" in violations:
            decision = CycleDecision.BUILD_REQUIRED
        elif completion_verified:
            decision = CycleDecision.COMPLETE_VERIFIED
        else:
            decision = CycleDecision.CONTINUE_RECOVERY

        violations_tuple = tuple(sorted(set(violations)))
        material = {"schema": SCHEMA, "version": VERSION, "capability_id": CAPABILITY_ID, "mission_id": request.mission_id, "decision": decision.value, "violations": violations_tuple, "stage_state": stage, "completion_verified": completion_verified}
        return OF50CycleReceipt(SCHEMA, VERSION, CAPABILITY_ID, request.mission_id, decision, violations_tuple, stage, completion_verified, "sha256:" + _sha(material))


__all__ = [
    "ALPHA_OMEGA_LIFECYCLE", "AlphaOmegaPacket", "Authority", "CAPABILITY_ID", "CANONICAL_NAME",
    "CycleDecision", "ExecutionProof", "FailureTransition", "FormationDecision", "HORIZON_IDS",
    "HorizonCell", "MissionGenome", "OF50ACEKernel", "OF50CycleReceipt", "OF50CycleRequest",
    "ProofTier", "ReuseBuildDecision", "RouteCandidate", "SwarmManifest",
]
