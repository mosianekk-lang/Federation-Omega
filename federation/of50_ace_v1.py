"""FUSE Ω — Omega Forge 50 Autonomous Completion Engine (OF50-ACE) v1.1.

Provider-neutral, effect-free composition kernel. It composes existing Federation
controls; it does not create another foundry, scheduler, authority, truth/proof
plane, memory root, or provider runtime.

v1.1 adds terminal-predicate-driven orchestration so control-plane activity cannot
masquerade as provider execution or causal mission progress.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence

CAPABILITY_ID = "FUSE-OF50-ACE-V1.1"
LEGACY_CAPABILITY_ID = "FUSE-OF50-ACE-V1"
CANONICAL_NAME = "FUSE Ω — OMEGA FORGE 50 AUTONOMOUS COMPLETION ENGINE"
SCHEMA = "FUSE-OF50-ACE-CYCLE-V1.1"
VERSION = "1.1.0"
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
    EvidenceKind.CONTROL_METADATA,
    EvidenceKind.QUEUE,
    EvidenceKind.SCHEDULE,
    EvidenceKind.SOURCE,
    EvidenceKind.CI,
    EvidenceKind.HEARTBEAT,
    EvidenceKind.GENERIC_HTTP,
    EvidenceKind.LOCAL_RUNTIME,
}


class RegressionCode(str, Enum):
    TERMINAL_OBJECTIVE_EXECUTION_SURFACE_MISMATCH = "TERMINAL_OBJECTIVE_EXECUTION_SURFACE_MISMATCH"
    AVAILABLE_TOOL_BIAS = "AVAILABLE_TOOL_BIAS"
    CONTROL_PLANE_PROGRESS_SUBSTITUTION = "CONTROL_PLANE_PROGRESS_SUBSTITUTION"
    PROGRESS_PROOF_INTERLOCK_FAILURE = "PROGRESS_PROOF_INTERLOCK_FAILURE"
    ZERO_DELTA_ACTION_FAMILY_REPLAY = "ZERO_DELTA_ACTION_FAMILY_REPLAY"
    NARRATION_WITHOUT_CAUSAL_PROGRESS = "NARRATION_WITHOUT_CAUSAL_PROGRESS"
    EXECUTOR_ACQUISITION_BYPASS = "EXECUTOR_ACQUISITION_BYPASS"


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
            self.callable_primitive
            and self.no_effect
            and self.exact_identity_ref.strip()
            and self.execution_ref.strip()
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
            and (
                self.changed_predicate_ids
                or self.terminal_action_became_callable
                or self.material_route_change
            )
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
            100.0 * self.expected_predicate_delta
            + 5.0 * self.information_gain
            + 4.0 * self.proof_strength
            + 2.0 * self.reversibility
            + 3.0 * self.authority_fit
            - self.latency_cost
            - self.monetary_cost
            - 2.0 * self.owner_burden
        )


@dataclass(frozen=True, slots=True)
class ActionFamilyRecord:
    action_family: str
    causal_progress: bool
    materially_distinct: bool = True


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def _authority_within(child: str, parent: str) -> bool:
    return (
        child in _AUTHORITY_RANK
        and parent in _AUTHORITY_RANK
        and _AUTHORITY_RANK[child] <= _AUTHORITY_RANK[parent]
    )


def compile_terminal_predicate_ledger(
    *,
    mission_id: str,
    predicate_specs: Sequence[Mapping[str, Any]],
    authority_ceiling: str = Authority.A1_INTERNAL.value,
) -> TerminalPredicateLedger:
    predicates: list[TerminalPredicate] = []
    for spec in predicate_specs:
        kinds = tuple(EvidenceKind(item) for item in spec.get("allowed_evidence_kinds", ()))
        predicates.append(
            TerminalPredicate(
                predicate_id=str(spec["predicate_id"]),
                desired_state=bool(spec.get("desired_state", True)),
                current_state=bool(spec.get("current_state", False)),
                proof_requirement=str(spec.get("proof_requirement", "")),
                terminal_action=str(spec.get("terminal_action", "")),
                required_execution_surface=str(spec.get("required_execution_surface", "")),
                dependencies=tuple(str(item) for item in spec.get("dependencies", ())),
                authority_ceiling=str(spec.get("authority_ceiling", authority_ceiling)),
                allowed_evidence_kinds=kinds,
                requires_executor_proof=bool(spec.get("requires_executor_proof", False)),
                provider_bound=bool(spec.get("provider_bound", False)),
                requires_substantive=bool(spec.get("requires_substantive", False)),
                evidence_refs=tuple(str(item) for item in spec.get("evidence_refs", ())),
            )
        )
    ledger = TerminalPredicateLedger(mission_id=mission_id, predicates=tuple(predicates))
    errors = ledger.validate(authority_ceiling)
    if errors:
        raise ValueError(";".join(errors))
    return ledger


def strategic_gemini_terminal_ledger(
    mission_id: str,
    *,
    states: Mapping[str, bool] | None = None,
) -> TerminalPredicateLedger:
    states = dict(states or {})
    specs = (
        {
            "predicate_id": "GEM-TP-01",
            "current_state": states.get("GEM-TP-01", False),
            "proof_requirement": "callable no-effect executor + exact identity + action-specific readback",
            "terminal_action": "acquire callable Gemini-capable executor",
            "required_execution_surface": "provider-native executor",
            "allowed_evidence_kinds": (EvidenceKind.EXECUTOR_CALLABILITY.value,),
            "requires_executor_proof": True,
        },
        {
            "predicate_id": "GEM-TP-02",
            "current_state": states.get("GEM-TP-02", False),
            "proof_requirement": "provider-native invocation receipt",
            "terminal_action": "invoke Gemini",
            "required_execution_surface": "Gemini-capable provider runtime",
            "dependencies": ("GEM-TP-01",),
            "allowed_evidence_kinds": (EvidenceKind.PROVIDER_INVOCATION.value,),
            "provider_bound": True,
        },
        {
            "predicate_id": "GEM-TP-03",
            "current_state": states.get("GEM-TP-03", False),
            "proof_requirement": "provider acknowledgement",
            "terminal_action": "receive Gemini acknowledgement",
            "required_execution_surface": "Gemini provider",
            "dependencies": ("GEM-TP-02",),
            "allowed_evidence_kinds": (EvidenceKind.PROVIDER_ACK.value,),
            "provider_bound": True,
        },
        {
            "predicate_id": "GEM-TP-04",
            "current_state": states.get("GEM-TP-04", False),
            "proof_requirement": "substantive provider response",
            "terminal_action": "receive substantive Gemini response",
            "required_execution_surface": "Gemini provider",
            "dependencies": ("GEM-TP-03",),
            "allowed_evidence_kinds": (EvidenceKind.SUBSTANTIVE_RESPONSE.value,),
            "provider_bound": True,
            "requires_substantive": True,
        },
        {
            "predicate_id": "GEM-TP-05",
            "current_state": states.get("GEM-TP-05", False),
            "proof_requirement": "provider receipt",
            "terminal_action": "read Gemini provider receipt",
            "required_execution_surface": "Gemini provider",
            "dependencies": ("GEM-TP-02",),
            "allowed_evidence_kinds": (EvidenceKind.PROVIDER_RECEIPT.value,),
            "provider_bound": True,
        },
        {
            "predicate_id": "GEM-TP-06",
            "current_state": states.get("GEM-TP-06", False),
            "proof_requirement": "action-specific semantic readback",
            "terminal_action": "verify Gemini semantic result",
            "required_execution_surface": "Gemini provider + semantic readback",
            "dependencies": ("GEM-TP-04", "GEM-TP-05"),
            "allowed_evidence_kinds": (EvidenceKind.SEMANTIC_READBACK.value,),
            "provider_bound": True,
        },
    )
    return compile_terminal_predicate_ledger(mission_id=mission_id, predicate_specs=specs)


def advance_terminal_predicates(
    ledger: TerminalPredicateLedger,
    *,
    evidence: Iterable[PredicateEvidence] = (),
    executor_proof: ExecutorProof | None = None,
    authority_ceiling: str = Authority.A1_INTERNAL.value,
) -> TerminalPredicateLedger:
    evidence_by_id: dict[str, list[PredicateEvidence]] = {}
    for item in evidence:
        evidence_by_id.setdefault(item.predicate_id, []).append(item)

    updated: list[TerminalPredicate] = []
    for predicate in ledger.predicates:
        if predicate.current_state == predicate.desired_state:
            updated.append(predicate)
            continue
        refs = list(predicate.evidence_refs)
        becomes_true = False
        if predicate.requires_executor_proof:
            if executor_proof is not None and executor_proof.qualifies(authority_ceiling):
                becomes_true = True
                refs.extend(
                    (
                        executor_proof.exact_identity_ref,
                        executor_proof.execution_ref,
                        executor_proof.action_specific_readback_ref,
                    )
                )
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
        updated.append(
            replace(
                predicate,
                current_state=predicate.desired_state if becomes_true else predicate.current_state,
                evidence_refs=tuple(dict.fromkeys(refs)),
            )
        )
    return TerminalPredicateLedger(ledger.mission_id, tuple(updated))


def held_zero_delta_families(
    history: Sequence[ActionFamilyRecord],
    *,
    threshold: int = 2,
) -> tuple[str, ...]:
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


def rank_actions(
    actions: Sequence[ActionCandidate],
    *,
    held_families: Sequence[str] = (),
) -> tuple[ActionCandidate, ...]:
    held = set(held_families)
    eligible = [item for item in actions if item.action_family not in held]
    return tuple(sorted(eligible, key=lambda item: (-item.causal_score, item.action_id)))


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


class OF50ACEKernel:
    """Deterministic composition, terminal-predicate and anti-bypass court."""

    def evaluate(self, request: OF50CycleRequest) -> OF50CycleReceipt:
        violations: list[str] = []
        stage = {name: "MISSING" for name in REQUIRED_CHAIN}
        if not request.mission_id.strip() or not request.objective.strip():
            violations.append("MISSION_IDENTITY_INCOMPLETE")

        if request.owner_protection_decision:
            stage["OWNER_PROTECTION"] = "PRESENT"
        else:
            violations.append("OWNER_PROTECTION_BYPASS")
        if request.machine_resolvable_owner_tasks or any(
            "MACHINE_RESOLVABLE_WORK_OFFLOADED_TO_OWNER" in item
            for item in request.owner_protection_violations
        ):
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

        terminal_state: Mapping[str, bool] = {}
        executor_state = ExecutorState.EXECUTOR_AVAILABLE
        causal_progress = any(item.causal_progress for item in request.progress_observations)
        held_families = held_zero_delta_families(request.action_family_history)

        terminal_complete = True
        if request.terminal_ledger is not None:
            violations.extend(request.terminal_ledger.validate(request.authority_ceiling))
            effective_ledger = advance_terminal_predicates(
                request.terminal_ledger,
                executor_proof=request.executor_proof_v11,
                authority_ceiling=request.authority_ceiling,
            )
            terminal_state = effective_ledger.state()
            terminal_complete = effective_ledger.complete
            unresolved_executor_actions = tuple(
                item for item in effective_ledger.predicates
                if item.current_state != item.desired_state
                and item.terminal_action.strip()
                and item.required_execution_surface.strip()
            )
            executor_qualified = bool(
                request.executor_proof_v11 is not None
                and request.executor_proof_v11.qualifies(request.authority_ceiling)
            )
            if request.executor_proof_v11 is not None and not _authority_within(
                request.executor_proof_v11.authority_ceiling, request.authority_ceiling
            ):
                violations.append("EXECUTOR_AUTHORITY_WIDENING")
            if unresolved_executor_actions and not executor_qualified:
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
            violations.append(RegressionCode.PROGRESS_PROOF_INTERLOCK_FAILURE.value)
            violations.append(RegressionCode.NARRATION_WITHOUT_CAUSAL_PROGRESS.value)

        outcomes_complete = set(request.required_outcomes).issubset(set(request.proven_outcomes))
        pre_completion_violations = tuple(sorted(set(violations)))
        completion_verified = bool(
            request.completion_requested
            and request.objective_satisfied
            and outcomes_complete
            and terminal_complete
            and proof.executed
            and proof.semantic_readback_ref.strip()
            and not pre_completion_violations
        )
        if request.completion_requested and not completion_verified:
            violations.append("PREMATURE_COMPLETION")
            completion_verified = False

        if request.genuine_owner_decisions and not request.machine_resolvable_owner_tasks:
            decision = CycleDecision.OWNER_DECISION_REQUIRED
        elif (
            "UNCHANGED_FAILED_ROUTE_REPLAY" in violations
            or RegressionCode.ZERO_DELTA_ACTION_FAMILY_REPLAY.value in violations
        ):
            decision = CycleDecision.CHANGED_ROUTE_REQUIRED
        elif "ALPHA_OMEGA_BYPASS_WHEN_IMPLEMENTATION_REQUIRED" in violations:
            decision = CycleDecision.BUILD_REQUIRED
        elif completion_verified:
            decision = CycleDecision.COMPLETE_VERIFIED
            narration_allowed = True
        else:
            decision = CycleDecision.CONTINUE_RECOVERY

        violations_tuple = tuple(sorted(set(violations)))
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "capability_id": CAPABILITY_ID,
            "mission_id": request.mission_id,
            "decision": decision.value,
            "violations": violations_tuple,
            "stage_state": stage,
            "completion_verified": completion_verified,
            "terminal_predicate_state": terminal_state,
            "executor_state": executor_state.value,
            "causal_progress": causal_progress,
            "narration_allowed": narration_allowed,
            "held_action_families": held_families,
        }
        return OF50CycleReceipt(
            SCHEMA,
            VERSION,
            CAPABILITY_ID,
            request.mission_id,
            decision,
            violations_tuple,
            stage,
            completion_verified,
            "sha256:" + _sha(material),
            terminal_state,
            executor_state,
            causal_progress,
            narration_allowed,
            held_families,
        )


__all__ = [
    "ALPHA_OMEGA_LIFECYCLE", "ActionCandidate", "ActionFamilyRecord", "AlphaOmegaPacket",
    "Authority", "CAPABILITY_ID", "CANONICAL_NAME", "CycleDecision", "EvidenceKind",
    "ExecutionProof", "ExecutorProof", "ExecutorState", "FailureTransition", "FormationDecision",
    "HORIZON_IDS", "HorizonCell", "LEGACY_CAPABILITY_ID", "MissionGenome", "OF50ACEKernel",
    "OF50CycleReceipt", "OF50CycleRequest", "PredicateEvidence", "ProgressObservation", "ProofTier",
    "RegressionCode", "ReuseBuildDecision", "RouteCandidate", "SCHEMA", "SwarmManifest",
    "TerminalPredicate", "TerminalPredicateLedger", "VERSION", "advance_terminal_predicates",
    "compile_terminal_predicate_ledger", "held_zero_delta_families", "rank_actions",
    "strategic_gemini_terminal_ledger",
]
