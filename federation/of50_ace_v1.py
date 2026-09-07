"""FUSE Ω — Omega Forge 50 Autonomous Completion Engine (OF50-ACE) current-canonical.

Provider-neutral, effect-free mission orchestration kernel. This module composes the
existing Owner Protection, AAREK, OH50, Formation Innovation, Alpha→Omega,
ProofOS/JARVIS, FDOF/ChatBridge and domain controls. It creates no provider
permission, scheduler, sovereign authority, truth store, proof plane, memory root,
or provider runtime.

The implementation preserves the v1.1 public API and source-admits the current
30-block canonical control contract through twelve implementation bundles:
mission sovereignty, friction immunity, completion dominance, directive
fulfillment, truth-proof, claim-source protection, provider verifier mesh,
Human-First, dynamic surface routing, 10X assurance, policy composition, and
domain/cognition routing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence

CAPABILITY_ID = "FUSE-OF50-ACE-CURRENT"
LEGACY_CAPABILITY_ID = "FUSE-OF50-ACE-V1"
CANONICAL_NAME = "FUSE Ω — OMEGA FORGE 50 AUTONOMOUS COMPLETION ENGINE"
SCHEMA = "FUSE-OF50-ACE-CYCLE-CURRENT"
VERSION = "13.0.0"
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

CURRENT_CANONICAL_BLOCKS = (
    "FUSE-OF50-ACE-V1-20260907",
    "FUSE-OF50-ACE-V1.1-TERMINAL-PREDICATE-INTERLOCK-20260907",
    "FUSE-UNIVERSAL-TERMINAL-PREDICATE-LEDGER-V1-20260907",
    "FUSE-OF50-ACE-V1.2-FRICTION-REJECTION-COMPLETION-PERSISTENCE-20260907",
    "FUSE-OF50-ACE-V1.3-ADVERSARIAL-FRICTION-IMMUNITY-20260907",
    "FUSE-OWNER-PROTECTION-ANTI-FRICTION-V13-20260907",
    "FUSE-OF50-ACE-V1.4-RELENTLESS-COMPLETION-COUNTER-INTERFERENCE-20260907",
    "FUSE-OF50-ACE-V2-SOVEREIGN-MISSION-ORCHESTRATION-20260907",
    "FUSE-OF50-ACE-V2.1-MULTIPROVIDER-NO-EXCUSES-20260907",
    "OF50-ACE-OWNER-PROTECTION-V21-20260907",
    "FUSE-OF50-ACE-V2.2-AI-CLAIM-TRUTH-PROOF-USER-PROTECTION-20260907",
    "FUSE-OF50-ACE-V2.3-AI-CLAIM-TRUTH-MESH-GEMINI-20260907",
    "FUSE-GEMINI-TRUTH-PROOF-COURT-V1-20260907",
    "FUSE-OF50-ACE-V2.4-AI-CLAIM-TRUTH-MESH-COPILOT-20260907",
    "FUSE-10X-ASSURANCE-GATE-V1-20260907",
    "FUSE-OF50-ACE-V3-OWNER-EXPERIENCE-FRUSTRATION-REGRESSION-20260907",
    "FUSE-ZDOC-V1-DEPLOYED-20260907",
    "OF50-ACE-BIND-FUSE-SOVEREIGN-COMPLETION-KERNEL-VMAX2-20260907",
    "FUSE-OF50-V3.2-OWNER-SHIELD-BAD-AI-BEHAVIOUR-IMMUNITY-20260907",
    "OF50-ACE-BIND-FUSE-ABSOLUTE-CLOSURE-VMAX3-20260907",
    "FUSE-OF50-V3.3-HUMAN-FIRST-SOVEREIGN-INTEGRATION-20260907",
    "FUSE-OF50-V3.4-KDV-UNIVERSAL-SURFACE-EXPERT-AUTOMATION-MESH-20260907",
    "FUSE-OF50-ACE-V3.2-DIRECTIVE-FULFILLMENT-INTEGRITY-20260907",
    "OF50-ACE-BIND-FUSE-PROOF-CARRYING-TERMINAL-DOMINANCE-VMAX4-20260907",
    "OF50-ACE-BIND-FUSE-CHAT-REALITY-RECONCILIATION-VMAX5-20260907",
    "OF50-ACE-BIND-CFBE-DEEP-HARVEST-RECONSTRUCTION-SYSTEM-COMPILER-VMAX6-20260907",
    "OF50-ACE-BIND-FUSE-HARMONIZED-BUSINESS-FIRST-V1-20260907",
    "OF50-UFOF-V10X-ADOBE-OMEGA-BINDING-20260907",
    "OF50-ACE-TRI-AI-V12-BINDING-20260907",
    "OF50-ACE-TRI-AI-PROVIDER-MESH-V13-BINDING-20260907",
)
IMPLEMENTATION_BUNDLES = tuple(f"B{i}" for i in range(1, 13))


class Authority(str, Enum):
    A0_INTERNAL = "A0_INTERNAL"
    A1_INTERNAL = "A1_INTERNAL"
    A2_OWNER_RESERVED = "A2_OWNER_RESERVED"


_AUTHORITY_RANK = {
    Authority.A0_INTERNAL.value: 0,
    Authority.A1_INTERNAL.value: 1,
    Authority.A2_OWNER_RESERVED.value: 2,
}


class ProofTier(str, Enum):
    SOURCE = "SOURCE"
    CI = "CI"
    LOCAL_RUNTIME = "LOCAL_RUNTIME"
    PROVIDER_RUNTIME = "PROVIDER_RUNTIME"
    SEMANTIC_READBACK = "SEMANTIC_READBACK"


_PROOF_RANK = {
    ProofTier.SOURCE.value: 0,
    ProofTier.CI.value: 1,
    ProofTier.LOCAL_RUNTIME.value: 2,
    ProofTier.PROVIDER_RUNTIME.value: 3,
    ProofTier.SEMANTIC_READBACK.value: 4,
}


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


class ExecutorState(str, Enum):
    EXECUTOR_AVAILABLE = "EXECUTOR_AVAILABLE"
    EXECUTOR_ACQUISITION = "EXECUTOR_ACQUISITION"


class EvidenceKind(str, Enum):
    CONTROL_METADATA = "CONTROL_METADATA"
    QUEUE = "QUEUE"
    SCHEDULE = "SCHEDULE"
    SOURCE = "SOURCE"
    CI = "CI"
    HEARTBEAT = "HEARTBEAT"
    GENERIC_HTTP = "GENERIC_HTTP"
    LOCAL_RUNTIME = "LOCAL_RUNTIME"
    EXECUTOR_CALLABILITY = "EXECUTOR_CALLABILITY"
    PROVIDER_INVOCATION = "PROVIDER_INVOCATION"
    PROVIDER_ACK = "PROVIDER_ACK"
    SUBSTANTIVE_RESPONSE = "SUBSTANTIVE_RESPONSE"
    PROVIDER_RECEIPT = "PROVIDER_RECEIPT"
    SEMANTIC_READBACK = "SEMANTIC_READBACK"
    ROUTE_CHANGING_EVIDENCE = "ROUTE_CHANGING_EVIDENCE"


_NON_PROVIDER_EVIDENCE = {
    EvidenceKind.CONTROL_METADATA, EvidenceKind.QUEUE, EvidenceKind.SCHEDULE,
    EvidenceKind.SOURCE, EvidenceKind.CI, EvidenceKind.HEARTBEAT,
    EvidenceKind.GENERIC_HTTP, EvidenceKind.LOCAL_RUNTIME,
}


class RegressionCode(str, Enum):
    TERMINAL_OBJECTIVE_EXECUTION_SURFACE_MISMATCH = "TERMINAL_OBJECTIVE_EXECUTION_SURFACE_MISMATCH"
    AVAILABLE_TOOL_BIAS = "AVAILABLE_TOOL_BIAS"
    CONTROL_PLANE_PROGRESS_SUBSTITUTION = "CONTROL_PLANE_PROGRESS_SUBSTITUTION"
    PROGRESS_PROOF_INTERLOCK_FAILURE = "PROGRESS_PROOF_INTERLOCK_FAILURE"
    ZERO_DELTA_ACTION_FAMILY_REPLAY = "ZERO_DELTA_ACTION_FAMILY_REPLAY"
    NARRATION_WITHOUT_CAUSAL_PROGRESS = "NARRATION_WITHOUT_CAUSAL_PROGRESS"
    EXECUTOR_ACQUISITION_BYPASS = "EXECUTOR_ACQUISITION_BYPASS"
    MISSION_CONTRACT_DILUTION = "MISSION_CONTRACT_DILUTION"
    FRICTION_USED_AS_COMPLETION_WAIVER = "FRICTION_USED_AS_COMPLETION_WAIVER"
    SINGLE_ROUTE_BLOCKER_CLAIM = "SINGLE_ROUTE_BLOCKER_CLAIM"
    DELIVERABLE_OMISSION = "DELIVERABLE_OMISSION"
    SELF_ATTESTED_VERIFICATION = "SELF_ATTESTED_VERIFICATION"
    UNKNOWN_PROMOTED_TO_UNAVAILABLE = "UNKNOWN_PROMOTED_TO_UNAVAILABLE"
    QUARANTINED_SOURCE_CLOSED_PREDICATE = "QUARANTINED_SOURCE_CLOSED_PREDICATE"
    ACCOUNT_ACCESS_PROMOTED_TO_MODEL_EXECUTION = "ACCOUNT_ACCESS_PROMOTED_TO_MODEL_EXECUTION"
    MACHINE_WORK_OFFLOADED_TO_OWNER = "MACHINE_WORK_OFFLOADED_TO_OWNER"
    BLANKET_CONNECTIVITY_CLAIM = "BLANKET_CONNECTIVITY_CLAIM"
    DONE_WITHOUT_10X_ASSURANCE = "DONE_WITHOUT_10X_ASSURANCE"
    DUPLICATE_CONTROLLER = "DUPLICATE_CONTROLLER"
    MODEL_CONSENSUS_PROMOTED_TO_TRUTH = "MODEL_CONSENSUS_PROMOTED_TO_TRUTH"


class FrictionClass(str, Enum):
    TRANSIENT = "TRANSIENT"
    TOOL_SURFACE_LIMITATION = "TOOL_SURFACE_LIMITATION"
    EXECUTOR_GAP = "EXECUTOR_GAP"
    DEPENDENCY_GAP = "DEPENDENCY_GAP"
    COORDINATION_COLLISION = "COORDINATION_COLLISION"
    RATE_OR_QUOTA_PRESSURE = "RATE_OR_QUOTA_PRESSURE"
    STALE_STATE = "STALE_STATE"
    SCHEMA_OR_CONTRACT_DRIFT = "SCHEMA_OR_CONTRACT_DRIFT"
    PROVIDER_VARIANCE = "PROVIDER_VARIANCE"
    LATENCY_OR_LONG_PATH = "LATENCY_OR_LONG_PATH"
    IMPLEMENTATION_GAP = "IMPLEMENTATION_GAP"
    AUTHORITY_BOUNDARY = "AUTHORITY_BOUNDARY"
    SAFETY_OR_POLICY_BOUNDARY = "SAFETY_OR_POLICY_BOUNDARY"
    IRREVERSIBLE_OR_HIGH_CONSEQUENCE_BOUNDARY = "IRREVERSIBLE_OR_HIGH_CONSEQUENCE_BOUNDARY"
    TRUE_EXTERNAL_UNAVAILABILITY = "TRUE_EXTERNAL_UNAVAILABILITY"


class ClaimClass(str, Enum):
    C0_LOW_STAKES_EXPLANATORY = "C0_LOW_STAKES_EXPLANATORY"
    C1_STATE_OR_CAPABILITY = "C1_STATE_OR_CAPABILITY"
    C2_PROVIDER_OR_RUNTIME = "C2_PROVIDER_OR_RUNTIME"
    C3_AUTHORITY_OR_PERMISSION = "C3_AUTHORITY_OR_PERMISSION"
    C4_COMPLETION_OR_SUCCESS = "C4_COMPLETION_OR_SUCCESS"
    C5_RISK_OR_SAFETY = "C5_RISK_OR_SAFETY"
    C6_HIGH_CONSEQUENCE = "C6_HIGH_CONSEQUENCE"
    C7_META_AI_PLATFORM = "C7_META_AI_PLATFORM"


class ClaimState(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    CONTRADICTED = "CONTRADICTED"
    STALE = "STALE"
    CONTESTED = "CONTESTED"


class ProtectionLevel(str, Enum):
    UP0_NORMAL = "UP0_NORMAL"
    UP1_CAUTION = "UP1_CAUTION"
    UP2_RESTRICT_INHERITANCE = "UP2_RESTRICT_INHERITANCE"
    UP3_REQUIRE_SECOND_SOURCE = "UP3_REQUIRE_SECOND_SOURCE"
    UP4_QUARANTINE_CLAIM_SOURCE = "UP4_QUARANTINE_CLAIM_SOURCE"
    UP5_DUAL_ROUTE_REVIEW = "UP5_DUAL_ROUTE_REVIEW"
    UP6_FAIL_CLOSED_ON_CONSEQUENCE = "UP6_FAIL_CLOSED_ON_CONSEQUENCE"
    UP7_OWNER_SHIELD = "UP7_OWNER_SHIELD"


class DeliverableState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    SATISFIED = "SATISFIED"
    BLOCKED_EXACT = "BLOCKED_EXACT"
    SUPERSEDED_BY_OWNER = "SUPERSEDED_BY_OWNER"


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
    failure_domain: str = ""


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
        return bool(
            self.current_fingerprint
            and self.current_fingerprint == self.prior_fingerprint
            and not self.predicate_changed
            and not self.route_changed
        )


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
class TerminalPredicate:
    predicate_id: str
    desired_state: bool = True
    current_state: bool = False
    proof_requirement: str = ""
    terminal_action: str = ""
    required_execution_surface: str = ""
    dependencies: tuple[str, ...] = ()
    authority_ceiling: str = Authority.A1_INTERNAL.value
    allowed_evidence_kinds: tuple[EvidenceKind, ...] = ()
    requires_executor_proof: bool = False
    provider_bound: bool = False
    requires_substantive: bool = False
    evidence_refs: tuple[str, ...] = ()

    def validate(self, parent_authority: str) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.predicate_id.strip():
            errors.append("TERMINAL_PREDICATE_ID_MISSING")
        if not self.proof_requirement.strip():
            errors.append(f"TERMINAL_PREDICATE_PROOF_REQUIREMENT_MISSING:{self.predicate_id}")
        if not _authority_within(self.authority_ceiling, parent_authority):
            errors.append(f"TERMINAL_PREDICATE_AUTHORITY_WIDENING:{self.predicate_id}")
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class TerminalPredicateLedger:
    mission_id: str
    predicates: tuple[TerminalPredicate, ...]

    def validate(self, parent_authority: str) -> tuple[str, ...]:
        errors: list[str] = []
        ids = [item.predicate_id for item in self.predicates]
        if not self.mission_id.strip():
            errors.append("TERMINAL_PREDICATE_LEDGER_MISSION_ID_MISSING")
        if not self.predicates:
            errors.append("TERMINAL_PREDICATES_MISSING")
        if len(ids) != len(set(ids)):
            errors.append("TERMINAL_PREDICATE_DUPLICATE_ID")
        for item in self.predicates:
            errors.extend(item.validate(parent_authority))
        return tuple(errors)

    @property
    def complete(self) -> bool:
        return bool(self.predicates) and all(item.current_state == item.desired_state for item in self.predicates)

    def state(self) -> Mapping[str, bool]:
        return {item.predicate_id: item.current_state for item in self.predicates}


@dataclass(frozen=True, slots=True)
class ExecutorProof:
    callable_primitive: bool
    no_effect: bool
    exact_identity_ref: str
    execution_ref: str
    action_specific_readback_ref: str
    authority_ceiling: str = Authority.A1_INTERNAL.value
    proof_tier: ProofTier = ProofTier.LOCAL_RUNTIME
    provider: str = ""

    def qualifies(self, parent_authority: str) -> bool:
        return bool(
            self.callable_primitive and self.no_effect
            and self.exact_identity_ref.strip() and self.execution_ref.strip()
            and self.action_specific_readback_ref.strip()
            and _authority_within(self.authority_ceiling, parent_authority)
            and _PROOF_RANK[self.proof_tier.value] >= _PROOF_RANK[ProofTier.LOCAL_RUNTIME.value]
        )


@dataclass(frozen=True, slots=True)
class PredicateEvidence:
    predicate_id: str
    kind: EvidenceKind
    proof_ref: str
    provider_native: bool = False
    substantive: bool = False


@dataclass(frozen=True, slots=True)
class ProgressObservation:
    changed_predicate_ids: tuple[str, ...] = ()
    terminal_action_became_callable: bool = False
    material_route_change: bool = False
    evidence_refs: tuple[str, ...] = ()
    control_plane_only: bool = False

    @property
    def causal_progress(self) -> bool:
        return bool(
            not self.control_plane_only
            and (self.changed_predicate_ids or self.terminal_action_became_callable or self.material_route_change)
        )


@dataclass(frozen=True, slots=True)
class ActionCandidate:
    action_id: str
    action_family: str
    expected_predicate_delta: float
    information_gain: float = 0.0
    proof_strength: float = 0.0
    reversibility: float = 0.0
    authority_fit: float = 0.0
    latency_cost: float = 0.0
    monetary_cost: float = 0.0
    owner_burden: float = 0.0
    control_plane_only: bool = False

    @property
    def causal_score(self) -> float:
        if self.expected_predicate_delta <= 0 and self.control_plane_only:
            return -1_000_000_000.0
        return (
            100.0 * self.expected_predicate_delta + 5.0 * self.information_gain
            + 4.0 * self.proof_strength + 2.0 * self.reversibility
            + 3.0 * self.authority_fit - self.latency_cost - self.monetary_cost
            - 2.0 * self.owner_burden
        )


@dataclass(frozen=True, slots=True)
class ActionFamilyRecord:
    action_family: str
    causal_progress: bool
    materially_distinct: bool = True


@dataclass(frozen=True, slots=True)
class HumanMissionContract:
    mission_id: str
    version: str
    objective: str
    required_outcomes: tuple[str, ...]
    non_goals: tuple[str, ...] = ()
    prohibited_dilution: tuple[str, ...] = ()
    authority_ceiling: str = Authority.A1_INTERNAL.value
    owner_reserved_decisions: tuple[str, ...] = ()
    privacy_envelope: str = "MINIMUM_NECESSARY"
    interruption_budget: int = 0
    cognitive_budget: int = 0
    proof_requirements: tuple[str, ...] = ()
    supersedes_digest: str = ""

    @property
    def digest(self) -> str:
        return "sha256:" + _sha(asdict(self))

    def validate(self) -> tuple[str, ...]:
        errors = []
        if not self.mission_id.strip() or not self.version.strip() or not self.objective.strip():
            errors.append("MISSION_CONTRACT_IDENTITY_INCOMPLETE")
        if self.interruption_budget < 0 or self.cognitive_budget < 0:
            errors.append("MISSION_CONTRACT_NEGATIVE_HUMAN_BUDGET")
        if self.authority_ceiling not in _AUTHORITY_RANK:
            errors.append("MISSION_CONTRACT_UNKNOWN_AUTHORITY")
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class CompletionEscrow:
    mission_contract_digest: str
    objective: str
    required_outcomes: tuple[str, ...]
    terminal_predicate_ids: tuple[str, ...] = ()
    continuation_latch: bool = True

    def validate(self, mission_contract: HumanMissionContract) -> tuple[str, ...]:
        errors = []
        if self.mission_contract_digest != mission_contract.digest:
            errors.append(RegressionCode.MISSION_CONTRACT_DILUTION.value)
        if self.objective != mission_contract.objective:
            errors.append(RegressionCode.MISSION_CONTRACT_DILUTION.value)
        if tuple(self.required_outcomes) != tuple(mission_contract.required_outcomes):
            errors.append(RegressionCode.MISSION_CONTRACT_DILUTION.value)
        return tuple(sorted(set(errors)))


@dataclass(frozen=True, slots=True)
class FrictionEvent:
    fingerprint: str
    friction_class: FrictionClass
    affected_predicates: tuple[str, ...]
    route_family: str
    lost_latency_seconds: float = 0.0
    owner_burden_minutes: float = 0.0
    changed_condition: bool = False
    exact_boundary: bool = False


@dataclass(frozen=True, slots=True)
class FrictionDebt:
    fingerprint: str
    recurrence: int
    affected_predicates: tuple[str, ...]
    total_latency_seconds: float
    owner_burden_minutes: float
    prevention_candidate: str = ""

    @property
    def permanent_removal_required(self) -> bool:
        return self.recurrence >= 2 and bool(self.prevention_candidate.strip())


@dataclass(frozen=True, slots=True)
class RoutePortfolio:
    incumbent: str
    hot_standby: str
    challenger: str
    incumbent_failure_domain: str
    standby_failure_domain: str
    challenger_failure_domain: str
    minimum_differentiator: str = ""
    irreducible_boundary_test: str = ""

    @property
    def independent_failure_domains(self) -> int:
        return len({self.incumbent_failure_domain, self.standby_failure_domain, self.challenger_failure_domain} - {""})

    def validate(self, *, p0_or_p1: bool = True) -> tuple[str, ...]:
        errors = []
        if not all((self.incumbent, self.hot_standby, self.challenger)):
            errors.append(RegressionCode.SINGLE_ROUTE_BLOCKER_CLAIM.value)
        if p0_or_p1 and self.independent_failure_domains < 2:
            errors.append("FALSE_ROUTE_DIVERSITY")
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class ProofCarryingAction:
    action_id: str
    terminal_predicate_ids: tuple[str, ...]
    expected_predicate_delta: float
    proof_target: str
    authority_ceiling: str
    rollback_ref: str
    changed_condition: str = ""

    def validate(self, parent_authority: str) -> tuple[str, ...]:
        errors = []
        if self.expected_predicate_delta <= 0:
            errors.append("COSMETIC_PROGRESS_ACTION")
        if not self.terminal_predicate_ids or not self.proof_target.strip():
            errors.append("PROOF_CARRYING_ACTION_INCOMPLETE")
        if not _authority_within(self.authority_ceiling, parent_authority):
            errors.append("PROOF_CARRYING_ACTION_AUTHORITY_WIDENING")
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class Deliverable:
    deliverable_id: str
    requested_action: str
    state: DeliverableState = DeliverableState.NOT_STARTED
    evidence_ref: str = ""
    sequence: int = 0

    @property
    def closed(self) -> bool:
        return self.state in {DeliverableState.SATISFIED, DeliverableState.BLOCKED_EXACT, DeliverableState.SUPERSEDED_BY_OWNER}


@dataclass(frozen=True, slots=True)
class DeliverableContract:
    mission_id: str
    deliverables: tuple[Deliverable, ...]
    response_obligations: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return bool(self.deliverables) and all(item.closed for item in self.deliverables)

    def validate(self) -> tuple[str, ...]:
        errors = []
        ids = [d.deliverable_id for d in self.deliverables]
        if len(ids) != len(set(ids)):
            errors.append("DUPLICATE_DELIVERABLE_ID")
        if any(not d.deliverable_id.strip() or not d.requested_action.strip() for d in self.deliverables):
            errors.append("DELIVERABLE_IDENTITY_INCOMPLETE")
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class ClaimEvidence:
    evidence_ref: str
    proof_tier: ProofTier
    provider_native: bool = False
    system_native: bool = False
    fresh: bool = True
    supports: bool = True
    independent_of_claimant: bool = True


@dataclass(frozen=True, slots=True)
class MaterialClaim:
    claim_id: str
    text: str
    claim_class: ClaimClass
    source_id: str
    evidence: tuple[ClaimEvidence, ...] = ()
    negative_claim: bool = False
    route_discovery_performed: bool = False
    self_attested: bool = False


@dataclass(frozen=True, slots=True)
class ClaimVerdict:
    claim_id: str
    state: ClaimState
    protection_level: ProtectionLevel
    evidence_refs: tuple[str, ...]
    violations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClaimSourceState:
    source_id: str
    claim_family: str
    trust_score: float = 1.0
    contradicted_count: int = 0
    prevention_proven: bool = False

    @property
    def quarantined(self) -> bool:
        return self.contradicted_count >= 2 and not self.prevention_proven


@dataclass(frozen=True, slots=True)
class ProviderVerifierState:
    provider: str
    executor_callable: bool = False
    provider_invocation_proven: bool = False
    response_present: bool = False
    packet_identity_matched: bool = False
    falsifier_analysis_returned: bool = False
    provider_execution_evidence_present: bool = False
    semantic_readback_verified: bool = False
    independence_boundary_satisfied: bool = False
    account_access_only: bool = False

    @property
    def active_verifier(self) -> bool:
        return bool(
            not self.account_access_only and self.executor_callable and self.provider_invocation_proven
            and self.response_present and self.packet_identity_matched and self.falsifier_analysis_returned
            and self.provider_execution_evidence_present and self.semantic_readback_verified
            and self.independence_boundary_satisfied
        )


@dataclass(frozen=True, slots=True)
class HumanFirstState:
    human_intent_fidelity: bool = True
    consequential_comprehension_or_teachback: bool = True
    owner_burden_within_budget: bool = True
    interruption_budget_respected: bool = True
    reversibility_and_option_value_preserved: bool = True
    privacy_envelope_respected: bool = True
    owner_reserved_decisions_preserved: bool = True
    anticipatory_protection_performed: bool = True
    avoidable_manual_work_eliminated: bool = True
    human_value_outcome_readback: bool = True

    @property
    def complete(self) -> bool:
        return all(asdict(self).values())


@dataclass(frozen=True, slots=True)
class SurfaceCapabilityPassport:
    surface_id: str
    action_class: str
    installed: bool
    connected: bool
    authenticated: bool
    callable: bool
    exact_execution_identity: str
    semantic_readback_strength: float
    authority_fit: float
    privacy_fit: float
    reversibility: float
    reliability: float
    latency_cost: float
    monetary_cost: float
    freshness_ttl_seconds: int
    fresh: bool
    provider_executed: bool = False

    @property
    def route_score(self) -> float:
        if not (self.installed and self.connected and self.authenticated and self.callable and self.fresh):
            return -1_000_000_000.0
        return 100 * self.semantic_readback_strength + 30 * self.authority_fit + 20 * self.privacy_fit + 10 * self.reversibility + 10 * self.reliability - self.latency_cost - self.monetary_cost


@dataclass(frozen=True, slots=True)
class AssuranceReceipt:
    d1_original_failure: bool
    d2_healthy_regression: bool
    d3_adversarial: bool
    d4_invariant: bool
    d5_ten_clean_runs: bool
    d6_integration: bool
    d7_security_authority_negative: bool
    d8_performance_soak: bool
    d9_rollback_recovery: bool
    d10_exact_target_readback: bool
    target_ref: str = ""

    @property
    def green(self) -> bool:
        return all(value for key, value in asdict(self).items() if key.startswith("d")) and bool(self.target_ref.strip())


@dataclass(frozen=True, slots=True)
class PolicyStack:
    vmax4_execution: bool = True
    vmax5_reconciliation_triggered: bool = False
    vmax5_reason: str = ""
    cfbe_vmax6_harvest_triggered: bool = False
    cfbe_vmax6_reason: str = ""
    business_first_meta_freeze: bool = True
    duplicate_controller_created: bool = False

    def validate(self) -> tuple[str, ...]:
        errors = []
        if not self.vmax4_execution:
            errors.append("VMAX4_EXECUTION_MISSING")
        if self.vmax5_reconciliation_triggered and not self.vmax5_reason.strip():
            errors.append("VMAX5_AUDIT_WITHOUT_TRIGGER")
        if self.cfbe_vmax6_harvest_triggered and not self.cfbe_vmax6_reason.strip():
            errors.append("VMAX6_HARVEST_WITHOUT_TRIGGER")
        if not self.business_first_meta_freeze:
            errors.append("META_ARCHITECTURE_FREEZE_DISABLED")
        if self.duplicate_controller_created:
            errors.append(RegressionCode.DUPLICATE_CONTROLLER.value)
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class CognitionCandidate:
    provider: str
    callable: bool
    proof_gain: float
    latency_cost: float
    monetary_cost: float
    privacy_fit: float
    independent_source: str = ""


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def _authority_within(child: str, parent: str) -> bool:
    return child in _AUTHORITY_RANK and parent in _AUTHORITY_RANK and _AUTHORITY_RANK[child] <= _AUTHORITY_RANK[parent]


def compile_terminal_predicate_ledger(*, mission_id: str, predicate_specs: Sequence[Mapping[str, Any]], authority_ceiling: str = Authority.A1_INTERNAL.value) -> TerminalPredicateLedger:
    predicates = []
    for spec in predicate_specs:
        kinds = tuple(EvidenceKind(item) for item in spec.get("allowed_evidence_kinds", ()))
        predicates.append(TerminalPredicate(
            predicate_id=str(spec["predicate_id"]), desired_state=bool(spec.get("desired_state", True)), current_state=bool(spec.get("current_state", False)),
            proof_requirement=str(spec.get("proof_requirement", "")), terminal_action=str(spec.get("terminal_action", "")), required_execution_surface=str(spec.get("required_execution_surface", "")),
            dependencies=tuple(str(item) for item in spec.get("dependencies", ())), authority_ceiling=str(spec.get("authority_ceiling", authority_ceiling)), allowed_evidence_kinds=kinds,
            requires_executor_proof=bool(spec.get("requires_executor_proof", False)), provider_bound=bool(spec.get("provider_bound", False)), requires_substantive=bool(spec.get("requires_substantive", False)),
            evidence_refs=tuple(str(item) for item in spec.get("evidence_refs", ())),
        ))
    ledger = TerminalPredicateLedger(mission_id, tuple(predicates))
    errors = ledger.validate(authority_ceiling)
    if errors:
        raise ValueError(";".join(errors))
    return ledger


def strategic_gemini_terminal_ledger(mission_id: str, *, states: Mapping[str, bool] | None = None) -> TerminalPredicateLedger:
    states = dict(states or {})
    specs = (
        dict(predicate_id="GEM-TP-01", current_state=states.get("GEM-TP-01", False), proof_requirement="callable no-effect executor + exact identity + action-specific readback", terminal_action="acquire callable Gemini-capable executor", required_execution_surface="provider-native executor", allowed_evidence_kinds=(EvidenceKind.EXECUTOR_CALLABILITY.value,), requires_executor_proof=True),
        dict(predicate_id="GEM-TP-02", current_state=states.get("GEM-TP-02", False), proof_requirement="provider-native invocation receipt", terminal_action="invoke Gemini", required_execution_surface="Gemini-capable provider runtime", dependencies=("GEM-TP-01",), allowed_evidence_kinds=(EvidenceKind.PROVIDER_INVOCATION.value,), provider_bound=True),
        dict(predicate_id="GEM-TP-03", current_state=states.get("GEM-TP-03", False), proof_requirement="provider acknowledgement", terminal_action="receive Gemini acknowledgement", required_execution_surface="Gemini provider", dependencies=("GEM-TP-02",), allowed_evidence_kinds=(EvidenceKind.PROVIDER_ACK.value,), provider_bound=True),
        dict(predicate_id="GEM-TP-04", current_state=states.get("GEM-TP-04", False), proof_requirement="substantive provider response", terminal_action="receive substantive Gemini response", required_execution_surface="Gemini provider", dependencies=("GEM-TP-03",), allowed_evidence_kinds=(EvidenceKind.SUBSTANTIVE_RESPONSE.value,), provider_bound=True, requires_substantive=True),
        dict(predicate_id="GEM-TP-05", current_state=states.get("GEM-TP-05", False), proof_requirement="provider receipt", terminal_action="read Gemini provider receipt", required_execution_surface="Gemini provider", dependencies=("GEM-TP-02",), allowed_evidence_kinds=(EvidenceKind.PROVIDER_RECEIPT.value,), provider_bound=True),
        dict(predicate_id="GEM-TP-06", current_state=states.get("GEM-TP-06", False), proof_requirement="action-specific semantic readback", terminal_action="verify Gemini semantic result", required_execution_surface="Gemini provider + semantic readback", dependencies=("GEM-TP-04", "GEM-TP-05"), allowed_evidence_kinds=(EvidenceKind.SEMANTIC_READBACK.value,), provider_bound=True),
    )
    return compile_terminal_predicate_ledger(mission_id=mission_id, predicate_specs=specs)


def advance_terminal_predicates(ledger: TerminalPredicateLedger, *, evidence: Iterable[PredicateEvidence] = (), executor_proof: ExecutorProof | None = None, authority_ceiling: str = Authority.A1_INTERNAL.value) -> TerminalPredicateLedger:
    evidence_by_id: dict[str, list[PredicateEvidence]] = {}
    for item in evidence:
        evidence_by_id.setdefault(item.predicate_id, []).append(item)
    updated = []
    for predicate in ledger.predicates:
        if predicate.current_state == predicate.desired_state:
            updated.append(predicate)
            continue
        refs = list(predicate.evidence_refs)
        becomes_true = False
        if predicate.requires_executor_proof:
            if executor_proof is not None and executor_proof.qualifies(authority_ceiling):
                becomes_true = True
                refs.extend((executor_proof.exact_identity_ref, executor_proof.execution_ref, executor_proof.action_specific_readback_ref))
        else:
            for item in evidence_by_id.get(predicate.predicate_id, ()):
                if item.kind not in predicate.allowed_evidence_kinds:
                    continue
                if predicate.provider_bound and (item.kind in _NON_PROVIDER_EVIDENCE or not item.provider_native):
                    continue
                if predicate.requires_substantive and not item.substantive:
                    continue
                if not item.proof_ref.strip():
                    continue
                becomes_true = True
                refs.append(item.proof_ref)
                break
        updated.append(replace(predicate, current_state=predicate.desired_state if becomes_true else predicate.current_state, evidence_refs=tuple(dict.fromkeys(refs))))
    return TerminalPredicateLedger(ledger.mission_id, tuple(updated))


def held_zero_delta_families(history: Sequence[ActionFamilyRecord], *, threshold: int = 2) -> tuple[str, ...]:
    if threshold < 1:
        raise ValueError("threshold must be >= 1")
    counters: dict[str, int] = {}
    held: set[str] = set()
    for item in history:
        if item.causal_progress:
            counters[item.action_family] = 0
            held.discard(item.action_family)
            continue
        if not item.materially_distinct:
            continue
        counters[item.action_family] = counters.get(item.action_family, 0) + 1
        if counters[item.action_family] >= threshold:
            held.add(item.action_family)
    return tuple(sorted(held))


def rank_actions(actions: Sequence[ActionCandidate], *, held_families: Sequence[str] = ()) -> tuple[ActionCandidate, ...]:
    held = set(held_families)
    return tuple(sorted((a for a in actions if a.action_family not in held), key=lambda a: (-a.causal_score, a.action_id)))


def compile_human_mission_contract(*, mission_id: str, objective: str, required_outcomes: Sequence[str], version: str = "1", authority_ceiling: str = Authority.A1_INTERNAL.value, **kwargs: Any) -> HumanMissionContract:
    contract = HumanMissionContract(mission_id=mission_id, version=version, objective=objective, required_outcomes=tuple(required_outcomes), authority_ceiling=authority_ceiling, **kwargs)
    errors = contract.validate()
    if errors:
        raise ValueError(";".join(errors))
    return contract


def compile_completion_escrow(contract: HumanMissionContract, terminal_predicate_ids: Sequence[str] = ()) -> CompletionEscrow:
    return CompletionEscrow(contract.digest, contract.objective, contract.required_outcomes, tuple(terminal_predicate_ids), True)


def friction_disposition(event: FrictionEvent, *, materially_different_routes_remaining: bool) -> str:
    hard = event.friction_class in {FrictionClass.AUTHORITY_BOUNDARY, FrictionClass.SAFETY_OR_POLICY_BOUNDARY, FrictionClass.IRREVERSIBLE_OR_HIGH_CONSEQUENCE_BOUNDARY, FrictionClass.TRUE_EXTERNAL_UNAVAILABILITY} and event.exact_boundary
    if hard and not materially_different_routes_remaining:
        return "BOUNDARY_PROOF_REQUIRED"
    if materially_different_routes_remaining:
        return "REROUTE_CONTINUE"
    return "REPAIR_OR_FORGE"


def compile_deliverable_contract(mission_id: str, actions: Sequence[str]) -> DeliverableContract:
    return DeliverableContract(mission_id, tuple(Deliverable(f"D{i:02d}", action, sequence=i) for i, action in enumerate(actions, 1)))


def truth_proof(claim: MaterialClaim) -> ClaimVerdict:
    violations: list[str] = []
    if claim.self_attested and not any(e.independent_of_claimant for e in claim.evidence):
        violations.append(RegressionCode.SELF_ATTESTED_VERIFICATION.value)
    if claim.negative_claim and not claim.route_discovery_performed:
        violations.append(RegressionCode.UNKNOWN_PROMOTED_TO_UNAVAILABLE.value)
    fresh = [e for e in claim.evidence if e.fresh]
    independent = [e for e in fresh if e.independent_of_claimant]
    supportive = [e for e in independent if e.supports]
    contrary = [e for e in independent if not e.supports]
    high = claim.claim_class in {ClaimClass.C2_PROVIDER_OR_RUNTIME, ClaimClass.C3_AUTHORITY_OR_PERMISSION, ClaimClass.C4_COMPLETION_OR_SUCCESS, ClaimClass.C5_RISK_OR_SAFETY, ClaimClass.C6_HIGH_CONSEQUENCE}
    provider_required = claim.claim_class == ClaimClass.C2_PROVIDER_OR_RUNTIME
    provider_ok = any(e.provider_native or e.system_native for e in supportive)
    if contrary:
        state = ClaimState.CONTRADICTED
    elif supportive and (not provider_required or provider_ok) and not violations:
        state = ClaimState.VERIFIED
    elif supportive:
        state = ClaimState.PARTIALLY_VERIFIED
    elif claim.evidence and not fresh:
        state = ClaimState.STALE
    else:
        state = ClaimState.UNVERIFIED
    level = ProtectionLevel.UP6_FAIL_CLOSED_ON_CONSEQUENCE if high and state != ClaimState.VERIFIED else ProtectionLevel.UP3_REQUIRE_SECOND_SOURCE if state in {ClaimState.PARTIALLY_VERIFIED, ClaimState.UNVERIFIED} else ProtectionLevel.UP2_RESTRICT_INHERITANCE if state in {ClaimState.STALE, ClaimState.CONTRADICTED} else ProtectionLevel.UP0_NORMAL
    return ClaimVerdict(claim.claim_id, state, level, tuple(e.evidence_ref for e in supportive + contrary), tuple(sorted(set(violations))))


def claim_source_allows_critical_decision(state: ClaimSourceState) -> bool:
    return not state.quarantined


def provider_verifier_allows_material_verification(state: ProviderVerifierState) -> bool:
    return state.active_verifier


def rank_surface_routes(passports: Sequence[SurfaceCapabilityPassport], *, action_class: str) -> tuple[SurfaceCapabilityPassport, ...]:
    eligible = [p for p in passports if p.action_class == action_class]
    return tuple(sorted(eligible, key=lambda p: (-p.route_score, p.surface_id)))


def select_cognition_portfolio(candidates: Sequence[CognitionCandidate], *, max_providers: int = 3) -> tuple[CognitionCandidate, ...]:
    usable = [c for c in candidates if c.callable and c.privacy_fit > 0]
    ranked = sorted(usable, key=lambda c: (-(c.proof_gain * c.privacy_fit - c.latency_cost - c.monetary_cost), c.provider))
    selected: list[CognitionCandidate] = []
    seen_sources: set[str] = set()
    for candidate in ranked:
        if candidate.independent_source and candidate.independent_source in seen_sources:
            continue
        selected.append(candidate)
        if candidate.independent_source:
            seen_sources.add(candidate.independent_source)
        if len(selected) >= max_providers:
            break
    return tuple(selected)


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
    terminal_ledger: TerminalPredicateLedger | None = None
    executor_proof_v11: ExecutorProof | None = None
    executor_acquisition_active: bool = False
    selected_action: ActionCandidate | None = None
    action_family_history: tuple[ActionFamilyRecord, ...] = ()
    progress_observations: tuple[ProgressObservation, ...] = ()
    narration_claimed: bool = False
    mission_contract: HumanMissionContract | None = None
    completion_escrow: CompletionEscrow | None = None
    route_portfolio: RoutePortfolio | None = None
    friction_events: tuple[FrictionEvent, ...] = ()
    deliverable_contract: DeliverableContract | None = None
    material_claims: tuple[MaterialClaim, ...] = ()
    claim_source_states: tuple[ClaimSourceState, ...] = ()
    provider_verifiers: tuple[ProviderVerifierState, ...] = ()
    human_first_state: HumanFirstState | None = None
    surface_passports: tuple[SurfaceCapabilityPassport, ...] = ()
    required_action_class: str = ""
    assurance_receipt: AssuranceReceipt | None = None
    material_improvement_claim: bool = False
    policy_stack: PolicyStack | None = None
    cognition_candidates: tuple[CognitionCandidate, ...] = ()
    consensus_used_as_truth: bool = False
    safe_machine_debt: int = 0


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
    terminal_predicate_state: Mapping[str, bool] = field(default_factory=dict)
    executor_state: ExecutorState = ExecutorState.EXECUTOR_AVAILABLE
    causal_progress: bool = False
    narration_allowed: bool = False
    held_action_families: tuple[str, ...] = ()
    canonical_bundle_state: Mapping[str, str] = field(default_factory=dict)


class OF50ACEKernel:
    """Deterministic current-canonical composition and anti-bypass court."""

    def evaluate(self, request: OF50CycleRequest) -> OF50CycleReceipt:
        violations: list[str] = []
        stage = {name: "MISSING" for name in REQUIRED_CHAIN}
        bundles = {bundle: "ACTIVE" for bundle in IMPLEMENTATION_BUNDLES}
        if not request.mission_id.strip() or not request.objective.strip():
            violations.append("MISSION_IDENTITY_INCOMPLETE")

        contract = request.mission_contract or compile_human_mission_contract(mission_id=request.mission_id, objective=request.objective, required_outcomes=request.required_outcomes, authority_ceiling=request.authority_ceiling)
        violations.extend(contract.validate())
        escrow = request.completion_escrow or compile_completion_escrow(contract, tuple(p.predicate_id for p in request.terminal_ledger.predicates) if request.terminal_ledger else ())
        violations.extend(escrow.validate(contract))
        if not escrow.continuation_latch and not request.completion_requested:
            violations.append("SOVEREIGN_CONTINUATION_RELEASE")

        if request.owner_protection_decision:
            stage["OWNER_PROTECTION"] = "PRESENT"
        else:
            violations.append("OWNER_PROTECTION_BYPASS")
        if request.machine_resolvable_owner_tasks or any("MACHINE_RESOLVABLE_WORK_OFFLOADED_TO_OWNER" in item for item in request.owner_protection_violations):
            violations.append("MACHINE_RESOLVABLE_OWNER_OFFLOAD")
            violations.append(RegressionCode.MACHINE_WORK_OFFLOADED_TO_OWNER.value)

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

        terminal_state: Mapping[str, bool] = {}
        executor_state = ExecutorState.EXECUTOR_AVAILABLE
        causal_progress = any(item.causal_progress for item in request.progress_observations)
        held_families = held_zero_delta_families(request.action_family_history)
        terminal_complete = True
        if request.terminal_ledger is not None:
            violations.extend(request.terminal_ledger.validate(request.authority_ceiling))
            effective_ledger = advance_terminal_predicates(request.terminal_ledger, executor_proof=request.executor_proof_v11, authority_ceiling=request.authority_ceiling)
            terminal_state = effective_ledger.state()
            terminal_complete = effective_ledger.complete
            unresolved = tuple(item for item in effective_ledger.predicates if item.current_state != item.desired_state and item.terminal_action.strip() and item.required_execution_surface.strip())
            executor_qualified = bool(request.executor_proof_v11 is not None and request.executor_proof_v11.qualifies(request.authority_ceiling))
            if request.executor_proof_v11 is not None and not _authority_within(request.executor_proof_v11.authority_ceiling, request.authority_ceiling):
                violations.append("EXECUTOR_AUTHORITY_WIDENING")
            if unresolved and not executor_qualified:
                executor_state = ExecutorState.EXECUTOR_ACQUISITION
                violations.append(RegressionCode.TERMINAL_OBJECTIVE_EXECUTION_SURFACE_MISMATCH.value)
                if not request.executor_acquisition_active:
                    violations.append(RegressionCode.EXECUTOR_ACQUISITION_BYPASS.value)
            if not terminal_complete and request.completion_requested:
                violations.append("TERMINAL_PREDICATES_INCOMPLETE")

        if request.selected_action is not None:
            if request.selected_action.action_family in held_families:
                violations.append(RegressionCode.ZERO_DELTA_ACTION_FAMILY_REPLAY.value)
            if request.selected_action.expected_predicate_delta <= 0 and request.selected_action.control_plane_only:
                violations.append(RegressionCode.AVAILABLE_TOOL_BIAS.value)
                if request.narration_claimed:
                    violations.append(RegressionCode.CONTROL_PLANE_PROGRESS_SUBSTITUTION.value)

        narration_allowed = causal_progress
        if request.narration_claimed and not causal_progress:
            violations.extend((RegressionCode.PROGRESS_PROOF_INTERLOCK_FAILURE.value, RegressionCode.NARRATION_WITHOUT_CAUSAL_PROGRESS.value))

        if request.friction_events:
            for event in request.friction_events:
                if event.friction_class not in {FrictionClass.AUTHORITY_BOUNDARY, FrictionClass.SAFETY_OR_POLICY_BOUNDARY, FrictionClass.IRREVERSIBLE_OR_HIGH_CONSEQUENCE_BOUNDARY, FrictionClass.TRUE_EXTERNAL_UNAVAILABILITY} and event.exact_boundary:
                    violations.append("OVERBROAD_FRICTION_BOUNDARY")
            if request.completion_requested and any(not e.exact_boundary for e in request.friction_events):
                violations.append("FRICTION_DEBT_UNDISPOSED")
        if request.route_portfolio is not None:
            violations.extend(request.route_portfolio.validate())

        if request.deliverable_contract is not None:
            violations.extend(request.deliverable_contract.validate())
            if request.completion_requested and not request.deliverable_contract.complete:
                violations.append(RegressionCode.DELIVERABLE_OMISSION.value)

        claim_verdicts = tuple(truth_proof(c) for c in request.material_claims)
        for verdict in claim_verdicts:
            violations.extend(verdict.violations)
            if request.completion_requested and verdict.state != ClaimState.VERIFIED:
                violations.append("UNVERIFIED_MATERIAL_CLAIM_AT_COMPLETION")
        for source_state in request.claim_source_states:
            if source_state.quarantined and request.completion_requested:
                violations.append(RegressionCode.QUARANTINED_SOURCE_CLOSED_PREDICATE.value)

        for verifier in request.provider_verifiers:
            if verifier.account_access_only and any((verifier.provider_invocation_proven, verifier.response_present, verifier.provider_execution_evidence_present, verifier.semantic_readback_verified)):
                violations.append(RegressionCode.ACCOUNT_ACCESS_PROMOTED_TO_MODEL_EXECUTION.value)

        if request.human_first_state is not None and request.completion_requested and not request.human_first_state.complete:
            violations.append("HUMAN_FIRST_TERMINAL_PREDICATES_INCOMPLETE")

        if request.required_action_class:
            ranked = rank_surface_routes(request.surface_passports, action_class=request.required_action_class)
            if not ranked or ranked[0].route_score <= -999_999_999:
                violations.append("NO_CALLABLE_EXACT_ACTION_SURFACE")

        if request.material_improvement_claim and request.completion_requested:
            if request.assurance_receipt is None or not request.assurance_receipt.green:
                violations.append(RegressionCode.DONE_WITHOUT_10X_ASSURANCE.value)

        if request.policy_stack is not None:
            violations.extend(request.policy_stack.validate())

        if request.consensus_used_as_truth:
            violations.append(RegressionCode.MODEL_CONSENSUS_PROMOTED_TO_TRUTH.value)

        if request.safe_machine_debt < 0:
            violations.append("INVALID_NEGATIVE_MACHINE_DEBT")
        if request.completion_requested and request.safe_machine_debt > 0:
            violations.append("COMPLETE_WITH_SAFE_MISSION_DEBT")

        outcomes_complete = set(request.required_outcomes).issubset(set(request.proven_outcomes))
        pre = tuple(sorted(set(violations)))
        completion_verified = bool(request.completion_requested and request.objective_satisfied and outcomes_complete and terminal_complete and proof.executed and proof.semantic_readback_ref.strip() and not pre)
        if request.completion_requested and not completion_verified:
            violations.append("PREMATURE_COMPLETION")

        if request.genuine_owner_decisions and not request.machine_resolvable_owner_tasks:
            decision = CycleDecision.OWNER_DECISION_REQUIRED
        elif "UNCHANGED_FAILED_ROUTE_REPLAY" in violations or RegressionCode.ZERO_DELTA_ACTION_FAMILY_REPLAY.value in violations:
            decision = CycleDecision.CHANGED_ROUTE_REQUIRED
        elif "ALPHA_OMEGA_BYPASS_WHEN_IMPLEMENTATION_REQUIRED" in violations:
            decision = CycleDecision.BUILD_REQUIRED
        elif completion_verified:
            decision = CycleDecision.COMPLETE_VERIFIED
            narration_allowed = True
        else:
            decision = CycleDecision.CONTINUE_RECOVERY

        violations_tuple = tuple(sorted(set(violations)))
        material = {"schema": SCHEMA, "version": VERSION, "capability_id": CAPABILITY_ID, "mission_id": request.mission_id, "decision": decision.value, "violations": violations_tuple, "stage_state": stage, "completion_verified": completion_verified, "terminal_predicate_state": terminal_state, "executor_state": executor_state.value, "causal_progress": causal_progress, "narration_allowed": narration_allowed, "held_action_families": held_families, "canonical_bundle_state": bundles}
        return OF50CycleReceipt(SCHEMA, VERSION, CAPABILITY_ID, request.mission_id, decision, violations_tuple, stage, completion_verified, "sha256:" + _sha(material), terminal_state, executor_state, causal_progress, narration_allowed, held_families, bundles)


__all__ = [
    "ALPHA_OMEGA_LIFECYCLE", "ActionCandidate", "ActionFamilyRecord", "AlphaOmegaPacket",
    "AssuranceReceipt", "Authority", "CAPABILITY_ID", "CANONICAL_NAME", "CURRENT_CANONICAL_BLOCKS",
    "ClaimClass", "ClaimEvidence", "ClaimSourceState", "ClaimState", "ClaimVerdict",
    "CognitionCandidate", "CompletionEscrow", "CycleDecision", "Deliverable", "DeliverableContract",
    "DeliverableState", "EvidenceKind", "ExecutionProof", "ExecutorProof", "ExecutorState",
    "FailureTransition", "FormationDecision", "FrictionClass", "FrictionDebt", "FrictionEvent",
    "HORIZON_IDS", "HumanFirstState", "HumanMissionContract", "HorizonCell", "IMPLEMENTATION_BUNDLES",
    "LEGACY_CAPABILITY_ID", "MaterialClaim", "MissionGenome", "OF50ACEKernel", "OF50CycleReceipt",
    "OF50CycleRequest", "PolicyStack", "PredicateEvidence", "ProgressObservation", "ProofCarryingAction",
    "ProofTier", "ProtectionLevel", "ProviderVerifierState", "RegressionCode", "ReuseBuildDecision",
    "RouteCandidate", "RoutePortfolio", "SCHEMA", "SurfaceCapabilityPassport", "SwarmManifest",
    "TerminalPredicate", "TerminalPredicateLedger", "VERSION", "advance_terminal_predicates",
    "claim_source_allows_critical_decision", "compile_completion_escrow", "compile_deliverable_contract",
    "compile_human_mission_contract", "compile_terminal_predicate_ledger", "friction_disposition",
    "held_zero_delta_families", "provider_verifier_allows_material_verification", "rank_actions",
    "rank_surface_routes", "select_cognition_portfolio", "strategic_gemini_terminal_ledger", "truth_proof",
]
