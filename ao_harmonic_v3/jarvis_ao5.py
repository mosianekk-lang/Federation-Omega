"""Jarvis ΑΩ5 forensic-decision profile for AO-HARMONIC.

This module converts the JARVIS ΑΩ5 operating specification into an executable,
provider-neutral, no-effect runtime. It is an operating profile inside the existing
ChatGov/Jarvis/Forest-First/AO-HARMONIC architecture; importing or running it does not
create external authority, background autonomy, provider effects, or model-weight learning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Iterable, Mapping, Sequence

from .models import TruthState


class JarvisAO5Error(ValueError):
    """Raised when an ΑΩ5 invariant or transition gate fails."""


class ExecutionState(str, Enum):
    S00_BOOT = "S00_BOOT"
    S01_RESTORE = "S01_RESTORE"
    S02_VERIFY_RESTORE = "S02_VERIFY_RESTORE"
    S03_RECONCILE = "S03_RECONCILE"
    S04_OBJECTIVE_RESOLUTION = "S04_OBJECTIVE_RESOLUTION"
    S05_ALPHA_DISCOVERY = "S05_ALPHA_DISCOVERY"
    S06_OMEGA_DEFINITION = "S06_OMEGA_DEFINITION"
    S07_PREFLIGHT = "S07_PREFLIGHT"
    S08_DECOMPOSITION = "S08_DECOMPOSITION"
    S09_DAG_BUILD = "S09_DAG_BUILD"
    S10_SCHEDULING = "S10_SCHEDULING"
    S11_EXECUTION = "S11_EXECUTION"
    S12_FAST_EVIDENCE_RELEASE = "S12_FAST_EVIDENCE_RELEASE"
    S13_DEEP_ANALYSIS = "S13_DEEP_ANALYSIS"
    S14_FAN_IN = "S14_FAN_IN"
    S15_CONVERGENCE = "S15_CONVERGENCE"
    S16_ADVERSARIAL_GATE = "S16_ADVERSARIAL_GATE"
    S17_NEUTRAL_GATE = "S17_NEUTRAL_GATE"
    S18_SEMANTIC_QA = "S18_SEMANTIC_QA"
    S19_PERSIST = "S19_PERSIST"
    S20_READBACK_VERIFY = "S20_READBACK_VERIFY"
    S21_RELEASE = "S21_RELEASE"
    S22_NEXT_ACTION = "S22_NEXT_ACTION"
    S23_HANDOFF_PREP = "S23_HANDOFF_PREP"
    S24_HANDOFF_READY = "S24_HANDOFF_READY"
    S25_CLOSED = "S25_CLOSED"


class CapabilityRealityState(str, Enum):
    C0_CONCEPTUAL = "C0_CONCEPTUAL"
    C1_ACTIVE_TURN = "C1_ACTIVE_TURN"
    C2_TOOL_BOUND = "C2_TOOL_BOUND"
    C3_SCHEDULED = "C3_SCHEDULED"
    C4_PROVIDER_VERIFIED = "C4_PROVIDER_VERIFIED"
    C5_LIVE_RUNTIME = "C5_LIVE_RUNTIME"


class Complexity(str, Enum):
    C1_SMALL = "C1_SMALL"
    C2_MODERATE = "C2_MODERATE"
    C3_LARGE = "C3_LARGE"
    C4_VERY_LARGE = "C4_VERY_LARGE"
    C5_EXTREME = "C5_EXTREME"


class PathState(str, Enum):
    CANDIDATE = "CANDIDATE"
    SHADOW = "SHADOW"
    ACTIVE = "ACTIVE"
    PROTECTED = "PROTECTED"
    BLOCKED = "BLOCKED"
    DEGRADED = "DEGRADED"
    SUPERSEDED = "SUPERSEDED"
    PRUNED = "PRUNED"
    FAILED = "FAILED"
    CLOSED = "CLOSED"
    OMEGA_REACHED = "OMEGA_REACHED"


class ChallengeState(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    REPAIR = "REPAIR"
    HOLD = "HOLD"
    FAIL = "FAIL"


class ContextState(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    HANDOFF_READY = "HANDOFF_READY"


KERNEL_INVARIANTS: tuple[str, ...] = (
    "ACT_ON_RISK_ACCUSE_ON_PROOF",
    "SOURCE_BEFORE_CLAIM",
    "PRIMARY_EVIDENCE_CONTROLS_SYNTHESIS",
    "RECONCILE_BEFORE_REBUILD",
    "BUILD_FIRST_VERIFY_IMMEDIATELY",
    "NO_SINGLE_POINT_OF_FAILURE",
    "DECISION_CHANGING_EVIDENCE_OVER_VOLUME",
    "ADVERSE_EVIDENCE_IS_MANDATORY",
    "THEORY_MUST_SURVIVE_BEST_COUNTERCASE",
    "CORRELATION_IS_NOT_CAUSATION",
    "ACCESS_IS_NOT_AUTOMATIC_KNOWLEDGE",
    "SILENCE_IS_NOT_AUTOMATIC_BAD_FAITH",
    "INSTITUTIONAL_FAILURE_IS_NOT_PERSONAL_CULPABILITY",
    "PROCEDURAL_SUCCESS_IS_NOT_MERITS_SUCCESS",
    "DERIVATIVE_REPETITION_IS_NOT_INDEPENDENT_CORROBORATION",
    "RELEASE_LANGUAGE_MAY_NOT_EXCEED_PROOF_STATE",
    "OWNER_IS_NOT_DEFAULT_QA",
    "HANDOFF_BEFORE_DEGRADATION",
    "FAILURE_MUST_PRODUCE_TESTED_LEARNING",
    "NOTHING_MATERIAL_SKIPPED_ASSUMED_OR_LOST",
)


@dataclass(frozen=True)
class CapabilityRecord:
    capability_id: str
    name: str
    reality_state: CapabilityRealityState
    tool_binding: str = ""
    required_input: str = ""
    execution_permission: str = "A1_INTERNAL"
    last_verified: str = ""
    limitations: tuple[str, ...] = ()

    def assert_claim(self, claimed_state: CapabilityRealityState) -> None:
        order = list(CapabilityRealityState)
        if order.index(claimed_state) > order.index(self.reality_state):
            raise JarvisAO5Error(
                f"CAPABILITY_OVERCLAIM:{self.capability_id}:"
                f"actual={self.reality_state.value}:claimed={claimed_state.value}"
            )


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    title: str
    source_type: str
    proof_state: TruthState
    authority: str
    pointer: str
    primary: bool = False
    independent_group: str = ""
    notes: str = ""


@dataclass(frozen=True)
class AlphaRecord:
    alpha_id: str
    alpha_type: str
    date: str
    source_id: str
    actor: str
    event: str
    proposition: str
    authentication: str
    proof_state: TruthState
    why_alpha: str
    predecessor_check: str
    competing_alpha: tuple[str, ...] = ()
    downstream_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class OmegaRecord:
    omega_id: str
    omega_class: str
    desired_state: str
    decision_maker: str
    decision_required: str
    required_elements: tuple[str, ...]
    burden: str
    required_facts: tuple[str, ...]
    required_evidence: tuple[str, ...]
    procedural_preconditions: tuple[str, ...]
    remedy: str
    minimum_success_state: str
    blockers: tuple[str, ...] = ()
    distance_to_omega: str = "UNKNOWN"
    active_paths: tuple[str, ...] = ()
    fallback_paths: tuple[str, ...] = ()


@dataclass
class PathRecord:
    path_id: str
    omega_id: str
    path_class: str
    objective: str
    required_elements: list[str] = field(default_factory=list)
    supporting_facts: list[str] = field(default_factory=list)
    adverse_facts: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    shared_dependencies: list[str] = field(default_factory=list)
    required_streams: list[str] = field(default_factory=list)
    legal_viability: float = 0.0
    factual_strength: float = 0.0
    evidence_strength: float = 0.0
    decision_impact: float = 0.0
    remedy_value: float = 0.0
    timeliness: float = 0.0
    risk: float = 1.0
    dependency_cost: float = 1.0
    execution_cost: float = 1.0
    time_sensitivity: str = "NORMAL"
    owner_gate: bool = False
    status: PathState = PathState.CANDIDATE
    relative_rank: int | None = None

    def value(self) -> float:
        positive = (
            max(self.legal_viability, 0.01)
            * max(self.factual_strength, 0.01)
            * max(self.evidence_strength, 0.01)
            * max(self.decision_impact, 0.01)
            * max(self.remedy_value, 0.01)
            * max(self.timeliness, 0.01)
        )
        negative = (
            max(self.risk, 0.1)
            * max(self.dependency_cost, 0.1)
            * max(self.execution_cost, 0.1)
        )
        return positive / negative


@dataclass(frozen=True)
class StreamRecord:
    stream_id: str
    name: str
    source_ids: tuple[str, ...]
    facts_used: tuple[str, ...]
    inferences: tuple[str, ...]
    route: str
    confidence: str
    limitations: tuple[str, ...]
    required: bool = True


@dataclass(frozen=True)
class GapRecord:
    gap_id: str
    description: str
    custodian: str
    source_system: str
    retrieval_route: str
    information_gain: float
    decision_value: float
    source_quality_potential: float
    retrieval_cost: float
    proof_state: TruthState = TruthState.MISSING_PRIMARY_RECORD

    def priority_value(self) -> float:
        return (
            max(self.information_gain, 0.0)
            * max(self.decision_value, 0.0)
            * max(self.source_quality_potential, 0.0)
            / max(self.retrieval_cost, 0.1)
        )


@dataclass(frozen=True)
class EvidenceQualityVector:
    authenticity: str
    proximity: str
    contemporaneity: str
    independence: str
    completeness: str
    specificity: str
    consistency: str
    chain_of_custody: str
    admissibility_or_usability: str
    decision_relevance: str


@dataclass(frozen=True)
class ConfidenceVector:
    source_confidence: str
    fact_confidence: str
    temporal_confidence: str
    actor_knowledge_confidence: str
    authority_confidence: str
    causal_confidence: str
    legal_fit_confidence: str
    policy_fit_confidence: str
    theory_confidence: str
    remedy_confidence: str


@dataclass(frozen=True)
class PreflightInput:
    file_count: int = 0
    page_count: int = 0
    annexure_count: int = 0
    format_count: int = 0
    nested_object_count: int = 0
    domain_count: int = 1
    expected_ocr_load: int = 0
    expected_visual_load: int = 0
    legal_research_load: int = 0
    tool_complexity: int = 0
    path_count: int = 0
    stream_count: int = 0
    context_risk: int = 0
    failure_risk: int = 0

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if value < 0:
                raise JarvisAO5Error(f"NEGATIVE_PREFLIGHT_INPUT:{name}")


@dataclass(frozen=True)
class PreflightResult:
    preflight_id: str
    complexity: Complexity
    auto_decompose: bool
    lane_plan: tuple[str, ...]
    path_plan: tuple[str, ...]
    stream_plan: tuple[str, ...]
    budgets: Mapping[str, int]
    first_output_target: str
    persistence_target: str
    handoff_threshold: str
    state: str = "PASS"


@dataclass(frozen=True)
class DAGNode:
    node_id: str
    node_type: str
    label: str
    proof_state: TruthState = TruthState.UNKNOWN


@dataclass(frozen=True)
class DAGEdge:
    source: str
    target: str
    edge_type: str


class DecisionDAG:
    """Small replayable decision dependency DAG with cycle and SPOF checks."""

    def __init__(self) -> None:
        self.nodes: dict[str, DAGNode] = {}
        self.edges: list[DAGEdge] = []

    def add_node(self, node: DAGNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: DAGEdge) -> None:
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise JarvisAO5Error(f"DAG_UNKNOWN_NODE:{edge.source}->{edge.target}")
        self.edges.append(edge)
        if self._has_cycle():
            self.edges.pop()
            raise JarvisAO5Error(f"DAG_CYCLE:{edge.source}->{edge.target}")

    def _has_cycle(self) -> bool:
        graph: dict[str, list[str]] = {node_id: [] for node_id in self.nodes}
        for edge in self.edges:
            graph[edge.source].append(edge.target)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> bool:
            if node_id in visiting:
                return True
            if node_id in visited:
                return False
            visiting.add(node_id)
            for child in graph[node_id]:
                if visit(child):
                    return True
            visiting.remove(node_id)
            visited.add(node_id)
            return False

        return any(visit(node_id) for node_id in graph)

    def to_dict(self) -> dict[str, object]:
        return {
            "nodes": [asdict(node) for node in self.nodes.values()],
            "edges": [asdict(edge) for edge in self.edges],
        }


@dataclass(frozen=True)
class TheoryRecord:
    theory_id: str
    statement: str
    supporting_evidence: tuple[str, ...]
    adverse_evidence: tuple[str, ...]
    strongest_countercase: str
    falsifiers: tuple[str, ...]
    confidence: ConfidenceVector


@dataclass(frozen=True)
class ConclusionRecord:
    conclusion_id: str
    statement: str
    theory_id: str
    element: str
    fact_ids: tuple[str, ...]
    proposition: str
    source_refs: tuple[str, ...]
    proof_state: TruthState


@dataclass(frozen=True)
class FailureEvent:
    failure_id: str
    failure_class: str
    observed_state: str
    expected_state: str
    root_cause: str
    available_signal: str
    detector_that_should_have_fired: str
    repair: str
    regression_test: str
    recurrence_count: int = 1

    @property
    def required_response(self) -> str:
        if self.recurrence_count >= 3:
            return "REDESIGN_OR_ROLLBACK"
        if self.recurrence_count == 2:
            return "MANDATORY_OMEGA_SCIENTIST_ARCHITECTURE_REVIEW"
        return "STRENGTHEN_CONTROL"


@dataclass(frozen=True)
class ForensicRunRequest:
    run_id: str
    project_id: str
    workstream_id: str
    objective: str
    sources: tuple[SourceRecord, ...]
    alphas: tuple[AlphaRecord, ...]
    omegas: tuple[OmegaRecord, ...]
    paths: tuple[PathRecord, ...]
    streams: tuple[StreamRecord, ...]
    gaps: tuple[GapRecord, ...]
    theory: TheoryRecord
    conclusions: tuple[ConclusionRecord, ...]
    adverse_evidence: tuple[str, ...]
    neutral_view: str
    counterfactual_worlds: tuple[str, ...]
    preflight: PreflightInput
    privacy_boundary: str
    owner_approval_for_external_action: bool = False
    external_action_requested: bool = False
    persistence_target: str = "LOCAL_RECEIPT"


@dataclass(frozen=True)
class ForensicRunResult:
    run_id: str
    engine_id: str
    engine_version: str
    execution_state: str
    preflight: Mapping[str, object]
    active_paths: tuple[Mapping[str, object], ...]
    shadow_paths: tuple[Mapping[str, object], ...]
    pruned_paths: tuple[Mapping[str, object], ...]
    active_streams: tuple[Mapping[str, object], ...]
    hidden_spofs: tuple[Mapping[str, object], ...]
    highest_information_gain_action: Mapping[str, object]
    fast_evidence_release: tuple[Mapping[str, object], ...]
    challenge_results: Mapping[str, str]
    semantic_qa: Mapping[str, object]
    replay_state: str
    convergence_state: str
    next_action: str
    handoff_state: Mapping[str, object]
    failure_learning: tuple[Mapping[str, object], ...]
    scientist_review: Mapping[str, object]
    receipt_sha256: str
    truth_boundary: Mapping[str, object]


class JarvisAO5Engine:
    """Executable ΑΩ5 profile inside the existing AO-HARMONIC architecture."""

    ENGINE_ID = "JARVIS-ALPHA-OMEGA-5-SOVEREIGN-PROFILE"
    VERSION = "5.0.0"
    ACTIVE_PATHS_MAX = 3
    SHADOW_PATHS_MAX = 3
    DEFAULT_STREAMS_MAX = 12
    AUTHORITY_CEILING = "A1_INTERNAL"

    _ORDER: tuple[ExecutionState, ...] = tuple(ExecutionState)

    def __init__(
        self,
        *,
        formation: object | None = None,
        scientia: object | None = None,
        state_fabric: object | None = None,
    ) -> None:
        self.formation = formation
        self.scientia = scientia
        self.state_fabric = state_fabric
        self.state = ExecutionState.S00_BOOT
        self.preflight_passed = False
        self.adversarial_gate = ChallengeState.HOLD
        self.neutral_gate = ChallengeState.HOLD
        self.semantic_gate = ChallengeState.HOLD
        self.failures: list[FailureEvent] = []

    @classmethod
    def contract(cls) -> dict[str, object]:
        return {
            "engine_id": cls.ENGINE_ID,
            "version": cls.VERSION,
            "kernel_invariants": list(KERNEL_INVARIANTS),
            "active_path_budget": cls.ACTIVE_PATHS_MAX,
            "shadow_path_budget": cls.SHADOW_PATHS_MAX,
            "authority_ceiling": cls.AUTHORITY_CEILING,
            "external_effect_default": False,
            "architecture_role": "OPERATING_PROFILE_INSIDE_EXISTING_JARVIS_AO_HARMONIC_STACK",
            "cross_project_rule": "METHODS_ONLY_NO_CASE_FACT_TRANSFER",
        }

    def reset(self) -> None:
        self.state = ExecutionState.S00_BOOT
        self.preflight_passed = False
        self.adversarial_gate = ChallengeState.HOLD
        self.neutral_gate = ChallengeState.HOLD
        self.semantic_gate = ChallengeState.HOLD
        self.failures.clear()

    def transition(
        self,
        target: ExecutionState,
        *,
        owner_approval: bool = False,
        consequential_external_action: bool = False,
    ) -> ExecutionState:
        current_index = self._ORDER.index(self.state)
        target_index = self._ORDER.index(target)
        if target_index != current_index + 1:
            raise JarvisAO5Error(
                f"INVALID_STATE_TRANSITION:{self.state.value}->{target.value}"
            )
        if target is ExecutionState.S11_EXECUTION and not self.preflight_passed:
            raise JarvisAO5Error("EXECUTION_REQUIRES_PREFLIGHT_PASS")
        if target is ExecutionState.S21_RELEASE:
            if any(
                state is not ChallengeState.PASS
                for state in (self.adversarial_gate, self.neutral_gate, self.semantic_gate)
            ):
                raise JarvisAO5Error("RELEASE_REQUIRES_ALL_GATES_PASS")
            if consequential_external_action and not owner_approval:
                raise JarvisAO5Error("CONSEQUENTIAL_EXTERNAL_ACTION_REQUIRES_OWNER_APPROVAL")
        self.state = target
        return self.state

    def _advance_to(self, target: ExecutionState) -> None:
        while self.state is not target:
            next_state = self._ORDER[self._ORDER.index(self.state) + 1]
            self.transition(next_state)

    @staticmethod
    def preflight_assess(
        run_id: str,
        inputs: PreflightInput,
        *,
        path_ids: Sequence[str],
        stream_ids: Sequence[str],
        persistence_target: str,
    ) -> PreflightResult:
        score = (
            inputs.file_count
            + inputs.page_count // 10
            + inputs.annexure_count * 2
            + inputs.format_count
            + inputs.nested_object_count
            + inputs.domain_count * 3
            + inputs.expected_ocr_load * 2
            + inputs.expected_visual_load
            + inputs.legal_research_load * 2
            + inputs.tool_complexity * 2
            + inputs.path_count
            + inputs.stream_count
            + inputs.context_risk * 2
            + inputs.failure_risk * 2
        )
        threshold_decompose = (
            inputs.page_count > 50
            or inputs.file_count > 8
            or inputs.annexure_count > 8
            or inputs.domain_count > 3
            or inputs.expected_ocr_load >= 3
            or inputs.expected_visual_load >= 3
        )
        if score >= 80:
            complexity = Complexity.C5_EXTREME
        elif score >= 50 or threshold_decompose:
            complexity = Complexity.C4_VERY_LARGE
        elif score >= 28:
            complexity = Complexity.C3_LARGE
        elif score >= 12:
            complexity = Complexity.C2_MODERATE
        else:
            complexity = Complexity.C1_SMALL
        auto_decompose = threshold_decompose or complexity in {
            Complexity.C4_VERY_LARGE,
            Complexity.C5_EXTREME,
        }
        lane_plan = (
            "LANE-01-DECISION-CHANGING-EVIDENCE",
            "LANE-02-LEGAL-POLICY-AND-ROUTE-CLASSIFICATION",
            "LANE-03-ADVERSARIAL-NEUTRAL-HEARING-USE",
        ) if auto_decompose else ("LANE-01-BOUNDED-DECISION-QUESTION",)
        budgets = {
            "max_source_objects": min(max(inputs.file_count, 2), 8),
            "max_pages_per_lane": 30,
            "max_tool_operations_per_lane": 12,
            "max_active_propositions": 12,
            "max_unpersisted_findings": 5,
            "max_active_paths": JarvisAO5Engine.ACTIVE_PATHS_MAX,
            "max_active_streams": min(
                max(len(stream_ids), 1), JarvisAO5Engine.DEFAULT_STREAMS_MAX
            ),
        }
        return PreflightResult(
            preflight_id=f"PREFLIGHT-{run_id}",
            complexity=complexity,
            auto_decompose=auto_decompose,
            lane_plan=lane_plan,
            path_plan=tuple(path_ids),
            stream_plan=tuple(stream_ids),
            budgets=budgets,
            first_output_target="FIRST_DECISION_CHANGING_VERIFIED_FINDING",
            persistence_target=persistence_target,
            handoff_threshold="YELLOW_BEFORE_DEGRADATION",
        )

    @staticmethod
    def rank_paths(
        paths: Iterable[PathRecord],
    ) -> tuple[list[PathRecord], list[PathRecord], list[PathRecord]]:
        candidates = [path for path in paths if path.status not in {PathState.FAILED, PathState.CLOSED}]
        ranked = sorted(candidates, key=lambda path: path.value(), reverse=True)
        active: list[PathRecord] = []
        shadow: list[PathRecord] = []
        pruned: list[PathRecord] = []
        for index, path in enumerate(ranked, start=1):
            path.relative_rank = index
            if index <= JarvisAO5Engine.ACTIVE_PATHS_MAX:
                path.status = PathState.ACTIVE
                active.append(path)
            elif index <= JarvisAO5Engine.ACTIVE_PATHS_MAX + JarvisAO5Engine.SHADOW_PATHS_MAX:
                path.status = PathState.SHADOW
                shadow.append(path)
            else:
                path.status = PathState.PRUNED
                pruned.append(path)
        return active, shadow, pruned

    @staticmethod
    def activate_streams(
        streams: Iterable[StreamRecord], active_paths: Sequence[PathRecord]
    ) -> list[StreamRecord]:
        required = {stream_id for path in active_paths for stream_id in path.required_streams}
        selected = [stream for stream in streams if stream.required or stream.stream_id in required]
        unique: dict[str, StreamRecord] = {stream.stream_id: stream for stream in selected}
        return list(unique.values())[: JarvisAO5Engine.DEFAULT_STREAMS_MAX]

    @staticmethod
    def hidden_spof_scan(paths: Sequence[PathRecord]) -> list[dict[str, object]]:
        dependency_to_paths: dict[str, list[str]] = {}
        for path in paths:
            for dependency in set(path.dependencies + path.shared_dependencies):
                dependency_to_paths.setdefault(dependency, []).append(path.path_id)
        findings = []
        for dependency, path_ids in dependency_to_paths.items():
            if len(path_ids) > 1:
                findings.append(
                    {
                        "spof_id": f"SPOF-{hashlib.sha256(dependency.encode()).hexdigest()[:10]}",
                        "node": dependency,
                        "paths_dependent": sorted(path_ids),
                        "consequence_if_false": "MULTIPLE_ACTIVE_ROUTES_DEGRADE_OR_FAIL",
                        "alternative_proof": "REQUIRED",
                        "mitigation": "SEEK_INDEPENDENT_SOURCE_OR_CREATE_FALLBACK_PROOF_PATH",
                        "priority": "CRITICAL" if len(path_ids) >= 3 else "HIGH",
                    }
                )
        return findings

    @staticmethod
    def build_dag(request: ForensicRunRequest) -> DecisionDAG:
        dag = DecisionDAG()
        for source in request.sources:
            dag.add_node(
                DAGNode(
                    node_id=f"SOURCE::{source.source_id}",
                    node_type="SOURCE_NODE",
                    label=source.title,
                    proof_state=source.proof_state,
                )
            )
        for alpha in request.alphas:
            alpha_node = f"ALPHA::{alpha.alpha_id}"
            dag.add_node(
                DAGNode(
                    node_id=alpha_node,
                    node_type="ALPHA_NODE",
                    label=alpha.proposition,
                    proof_state=alpha.proof_state,
                )
            )
            source_node = f"SOURCE::{alpha.source_id}"
            if source_node in dag.nodes:
                dag.add_edge(DAGEdge(source_node, alpha_node, "AUTHENTICATES"))
        for gap in request.gaps:
            dag.add_node(
                DAGNode(
                    node_id=f"GAP::{gap.gap_id}",
                    node_type="GAP_NODE",
                    label=gap.description,
                    proof_state=gap.proof_state,
                )
            )
        for path in request.paths:
            path_node = f"PATH::{path.path_id}"
            dag.add_node(DAGNode(path_node, "PATH_NODE", path.objective, TruthState.INFERENCE))
            for dependency in path.dependencies:
                dependency_node = f"DEP::{dependency}"
                if dependency_node not in dag.nodes:
                    dag.add_node(DAGNode(dependency_node, "ELEMENT_NODE", dependency))
                dag.add_edge(DAGEdge(dependency_node, path_node, "REQUIRES"))
        for omega in request.omegas:
            omega_node = f"OMEGA::{omega.omega_id}"
            dag.add_node(DAGNode(omega_node, "OMEGA_NODE", omega.desired_state, TruthState.UNKNOWN))
            for path_id in omega.active_paths:
                path_node = f"PATH::{path_id}"
                if path_node in dag.nodes:
                    dag.add_edge(DAGEdge(path_node, omega_node, "SUPPORTS"))
        return dag

    @staticmethod
    def cross_stream_contamination_check(streams: Sequence[StreamRecord]) -> list[str]:
        violations: list[str] = []
        for stream in streams:
            for inference in stream.inferences:
                if inference.startswith("FACT:"):
                    violations.append(
                        f"INFERENCE_MISLABELLED_AS_FACT:{stream.stream_id}:{inference}"
                    )
        return violations

    @staticmethod
    def semantic_firewall(conclusions: Sequence[ConclusionRecord]) -> dict[str, object]:
        violations: list[str] = []
        forbidden_promotions = {
            " MAY ": " DID ",
            " RISK ": " FINDING ",
            " ALLEGATION ": " FACT ",
            " ACCESS ": " KNOWLEDGE ",
            " CHRONOLOGY ": " CAUSATION ",
            " REFERRAL ": " ACCEPTANCE ",
            " PARTIAL ": " COMPLETE ",
            " POSSIBILITY ": " INTENT ",
        }
        for conclusion in conclusions:
            text = f" {conclusion.statement.upper()} "
            if conclusion.proof_state in {TruthState.INFERENCE, TruthState.UNVERIFIED, TruthState.UNKNOWN}:
                absolute_markers = (" PROVES ", " DEFINITIVELY ", " CERTAINLY ", " DID ")
                for marker in absolute_markers:
                    if marker in text:
                        violations.append(
                            f"PROOF_LANGUAGE_EXCEEDS_STATE:{conclusion.conclusion_id}:{marker.strip()}"
                        )
            for weak, strong in forbidden_promotions.items():
                if weak in text and strong in text:
                    violations.append(
                        f"SEMANTIC_PROMOTION:{conclusion.conclusion_id}:{weak.strip()}->{strong.strip()}"
                    )
        return {
            "state": "PASS" if not violations else "BLOCKED",
            "violations": violations,
        }

    @staticmethod
    def replay_test(conclusions: Sequence[ConclusionRecord]) -> dict[str, object]:
        failures: list[str] = []
        for conclusion in conclusions:
            if not conclusion.source_refs:
                failures.append(f"MISSING_SOURCE_REFS:{conclusion.conclusion_id}")
            if not conclusion.fact_ids:
                failures.append(f"MISSING_FACT_LINEAGE:{conclusion.conclusion_id}")
            if conclusion.proof_state is TruthState.UNKNOWN:
                failures.append(f"UNKNOWN_PROOF_STATE:{conclusion.conclusion_id}")
        return {
            "state": "PASS" if not failures else "NOT_DURABLY_VERIFIED",
            "failures": failures,
        }

    @staticmethod
    def convergence_test(request: ForensicRunRequest) -> dict[str, object]:
        unresolved = [gap.gap_id for gap in request.gaps]
        if not unresolved:
            state = "CONVERGED"
        elif all(gap.proof_state is TruthState.MISSING_PRIMARY_RECORD for gap in request.gaps):
            state = "BOUNDED_GAPS_EXPLICIT"
        else:
            state = "CONTINUE_HIGH_VALUE_LANE"
        return {
            "state": state,
            "named_gaps": unresolved,
            "additional_search_value": "HIGH" if unresolved else "LOW",
        }

    @staticmethod
    def _fast_release(request: ForensicRunRequest) -> list[dict[str, object]]:
        findings: list[dict[str, object]] = []
        for alpha in request.alphas:
            if alpha.proof_state is TruthState.VERIFIED:
                findings.append(
                    {
                        "label": "VERIFIED",
                        "finding": alpha.proposition,
                        "source_id": alpha.source_id,
                        "decision_value": "MATERIAL",
                    }
                )
        for gap in sorted(request.gaps, key=lambda item: item.priority_value(), reverse=True)[:3]:
            findings.append(
                {
                    "label": "GAP",
                    "finding": gap.description,
                    "source_id": gap.source_system,
                    "decision_value": "HIGH_INFORMATION_GAIN",
                }
            )
        return findings

    @staticmethod
    def _challenge(request: ForensicRunRequest) -> dict[str, str]:
        return {
            "opposing_counsel": ChallengeState.PASS.value
            if request.theory.strongest_countercase
            else ChallengeState.HOLD.value,
            "neutral_fact_finder": ChallengeState.PASS.value
            if request.neutral_view
            else ChallengeState.HOLD.value,
            "review_appeal": ChallengeState.PASS.value
            if all(conclusion.source_refs for conclusion in request.conclusions)
            else ChallengeState.REPAIR.value,
            "governance_audit": ChallengeState.PASS.value
            if request.gaps
            else ChallengeState.PARTIAL.value,
            "practical_outcome": ChallengeState.PASS.value
            if request.omegas
            else ChallengeState.HOLD.value,
        }

    @staticmethod
    def _scientist_review(
        *,
        request: ForensicRunRequest,
        active_paths: Sequence[PathRecord],
        highest_gap: GapRecord,
        hidden_spofs: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        return {
            "method_question": "WHICH_ACTION_MAXIMISES_DECISION_VALUE_PER_OWNER_AND_CONTEXT_COST",
            "existing_method": "BULK_CONTEXT_ACCUMULATION",
            "candidate_method": "INFORMATION_GAIN_FIRST_WITH_BOUNDED_PATHS_AND_STREAMS",
            "hypothesis": "A discriminator-first P0 record lane will improve decision value and reduce owner load.",
            "observations": {
                "active_path_count": len(active_paths),
                "highest_gap": highest_gap.gap_id,
                "hidden_spof_count": len(hidden_spofs),
                "source_count": len(request.sources),
            },
            "promotion_state": "PROVISIONAL_BOUNDED_RUN",
            "next_experiment": "MEASURE_RECORD_ACQUISITION_YIELD_AND_THEORY_CHANGE_AFTER_P0_LANE",
            "no_model_weight_learning_claim": True,
        }

    @staticmethod
    def _handoff_state(
        request: ForensicRunRequest,
        *,
        next_action: str,
        active_paths: Sequence[PathRecord],
        streams: Sequence[StreamRecord],
        context_state: ContextState,
    ) -> dict[str, object]:
        return {
            "handoff_id": f"HANDOFF-{request.run_id}",
            "project_id": request.project_id,
            "workstream_id": request.workstream_id,
            "current_state_machine_state": ExecutionState.S22_NEXT_ACTION.value,
            "alpha_nodes": [alpha.alpha_id for alpha in request.alphas],
            "omega_portfolio": [omega.omega_id for omega in request.omegas],
            "active_paths": [path.path_id for path in active_paths],
            "active_streams": [stream.stream_id for stream in streams],
            "source_state": [source.source_id for source in request.sources],
            "gap_state": [gap.gap_id for gap in request.gaps],
            "last_verified_source": next(
                (
                    source.source_id
                    for source in request.sources
                    if source.proof_state is TruthState.VERIFIED
                ),
                "NONE",
            ),
            "next_exact_action": next_action,
            "restore_command": f'chatbridge restore "{request.workstream_id}"',
            "context_state": context_state.value,
        }

    @staticmethod
    def _receipt_hash(payload: Mapping[str, object]) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=lambda value: value.value if isinstance(value, Enum) else str(value),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def record_owner_correction(
        self,
        *,
        failure_id: str,
        observed_state: str,
        expected_state: str,
        available_signal: str,
        repair: str,
        regression_test: str,
        recurrence_count: int = 1,
    ) -> FailureEvent:
        event = FailureEvent(
            failure_id=failure_id,
            failure_class="OWNER_DETECTED",
            observed_state=observed_state,
            expected_state=expected_state,
            root_cause="AUTOMATED_CONTROL_DID_NOT_FIRE_BEFORE_OWNER_CORRECTION",
            available_signal=available_signal,
            detector_that_should_have_fired="STATE_DELTA_OR_STALE_STATE_OR_OBJECTIVE_RESOLUTION_GATE",
            repair=repair,
            regression_test=regression_test,
            recurrence_count=recurrence_count,
        )
        self.failures.append(event)
        return event

    def run(self, request: ForensicRunRequest) -> ForensicRunResult:
        self.reset()
        if not request.sources:
            raise JarvisAO5Error("SOURCE_REGISTER_EMPTY")
        if not request.omegas:
            raise JarvisAO5Error("OMEGA_PORTFOLIO_EMPTY")
        if request.external_action_requested and not request.owner_approval_for_external_action:
            raise JarvisAO5Error("EXTERNAL_ACTION_REQUIRES_OWNER_APPROVAL")

        self._advance_to(ExecutionState.S06_OMEGA_DEFINITION)
        preflight = self.preflight_assess(
            request.run_id,
            request.preflight,
            path_ids=[path.path_id for path in request.paths],
            stream_ids=[stream.stream_id for stream in request.streams],
            persistence_target=request.persistence_target,
        )
        self.transition(ExecutionState.S07_PREFLIGHT)
        self.preflight_passed = preflight.state == "PASS"
        self.transition(ExecutionState.S08_DECOMPOSITION)

        active_paths, shadow_paths, pruned_paths = self.rank_paths(request.paths)
        active_streams = self.activate_streams(request.streams, active_paths)
        dag = self.build_dag(request)
        hidden_spofs = self.hidden_spof_scan(active_paths)

        self.transition(ExecutionState.S09_DAG_BUILD)
        self.transition(ExecutionState.S10_SCHEDULING)
        self.transition(ExecutionState.S11_EXECUTION)
        fast_release = self._fast_release(request)
        self.transition(ExecutionState.S12_FAST_EVIDENCE_RELEASE)
        self.transition(ExecutionState.S13_DEEP_ANALYSIS)

        contamination = self.cross_stream_contamination_check(active_streams)
        self.transition(ExecutionState.S14_FAN_IN)
        convergence = self.convergence_test(request)
        self.transition(ExecutionState.S15_CONVERGENCE)

        challenges = self._challenge(request)
        self.adversarial_gate = (
            ChallengeState.PASS
            if all(value in {ChallengeState.PASS.value, ChallengeState.PARTIAL.value} for value in challenges.values())
            else ChallengeState.HOLD
        )
        self.transition(ExecutionState.S16_ADVERSARIAL_GATE)
        self.neutral_gate = (
            ChallengeState.PASS if request.neutral_view else ChallengeState.HOLD
        )
        self.transition(ExecutionState.S17_NEUTRAL_GATE)

        semantic = self.semantic_firewall(request.conclusions)
        if contamination:
            semantic = {
                "state": "BLOCKED",
                "violations": list(semantic["violations"]) + contamination,
            }
        self.semantic_gate = (
            ChallengeState.PASS if semantic["state"] == "PASS" else ChallengeState.HOLD
        )
        self.transition(ExecutionState.S18_SEMANTIC_QA)

        replay = self.replay_test(request.conclusions)
        if replay["state"] != "PASS":
            raise JarvisAO5Error("REPLAY_GATE_FAILED")
        if any(
            gate is not ChallengeState.PASS
            for gate in (self.adversarial_gate, self.neutral_gate, self.semantic_gate)
        ):
            raise JarvisAO5Error("MATERIAL_RELEASE_GATE_FAILED")

        highest_gap = max(request.gaps, key=lambda gap: gap.priority_value())
        next_action = (
            f"Acquire and reconcile {highest_gap.gap_id}: {highest_gap.description}; "
            "then update the charge/process-election crosswalk before any external action."
        )
        context_state = (
            ContextState.YELLOW
            if request.preflight.context_risk >= 3
            or preflight.complexity in {Complexity.C4_VERY_LARGE, Complexity.C5_EXTREME}
            else ContextState.GREEN
        )
        scientist = self._scientist_review(
            request=request,
            active_paths=active_paths,
            highest_gap=highest_gap,
            hidden_spofs=hidden_spofs,
        )
        handoff = self._handoff_state(
            request,
            next_action=next_action,
            active_paths=active_paths,
            streams=active_streams,
            context_state=context_state,
        )

        self.transition(ExecutionState.S19_PERSIST)
        self.transition(ExecutionState.S20_READBACK_VERIFY)
        self.transition(
            ExecutionState.S21_RELEASE,
            owner_approval=request.owner_approval_for_external_action,
            consequential_external_action=request.external_action_requested,
        )
        self.transition(ExecutionState.S22_NEXT_ACTION)

        payload_for_hash = {
            "run_id": request.run_id,
            "state": self.state.value,
            "preflight": asdict(preflight),
            "active_paths": [asdict(path) for path in active_paths],
            "active_streams": [asdict(stream) for stream in active_streams],
            "hidden_spofs": hidden_spofs,
            "next_action": next_action,
            "replay": replay,
            "semantic": semantic,
            "dag": dag.to_dict(),
        }
        receipt_hash = self._receipt_hash(payload_for_hash)

        return ForensicRunResult(
            run_id=request.run_id,
            engine_id=self.ENGINE_ID,
            engine_version=self.VERSION,
            execution_state=self.state.value,
            preflight=asdict(preflight),
            active_paths=tuple(asdict(path) for path in active_paths),
            shadow_paths=tuple(asdict(path) for path in shadow_paths),
            pruned_paths=tuple(asdict(path) for path in pruned_paths),
            active_streams=tuple(asdict(stream) for stream in active_streams),
            hidden_spofs=tuple(hidden_spofs),
            highest_information_gain_action=asdict(highest_gap),
            fast_evidence_release=tuple(fast_release),
            challenge_results=challenges,
            semantic_qa=semantic,
            replay_state=str(replay["state"]),
            convergence_state=str(convergence["state"]),
            next_action=next_action,
            handoff_state=handoff,
            failure_learning=tuple(asdict(failure) for failure in self.failures),
            scientist_review=scientist,
            receipt_sha256=receipt_hash,
            truth_boundary={
                "external_effect": False,
                "provider_mutation": False,
                "legal_outcome_proved": False,
                "model_weight_learning": False,
                "background_daemon": False,
                "case_facts_are_adapter_local": True,
                "capability_state": CapabilityRealityState.C1_ACTIVE_TURN.value,
            },
        )


def result_to_json(result: ForensicRunResult) -> str:
    return json.dumps(asdict(result), sort_keys=True, indent=2, ensure_ascii=False, default=str)
