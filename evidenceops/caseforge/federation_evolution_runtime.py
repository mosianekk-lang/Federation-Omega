from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, Sequence

from .capability_decision import (
    BlockerKind,
    CapabilityDecision,
    CapabilityDecisionRequest,
    CapabilityResolutionGate,
    CapabilityScope,
    CapabilityState,
    TerminalClaim,
)
from .federation_capability_twin import CapabilityTwin, TwinState
from .federation_evolution_program import AUTHORITY_CEILING, SYSTEM_PROFILES


class DependencyKind(str, Enum):
    HARD = "HARD"
    PROOF = "PROOF"
    DATA = "DATA"
    OBSERVABILITY = "OBSERVABILITY"
    SPECIALIST = "SPECIALIST"


@dataclass(frozen=True)
class DependencyEdge:
    upstream: str
    downstream: str
    kind: DependencyKind
    required: bool = True
    proof_ref: str = ""

    def validate(self) -> "DependencyEdge":
        if self.upstream == self.downstream:
            raise ValueError("self dependency is not allowed")
        if self.upstream not in SYSTEM_PROFILES or self.downstream not in SYSTEM_PROFILES:
            raise ValueError("dependency endpoints must be registered Federation systems")
        if not self.proof_ref.strip():
            raise ValueError("dependency edge requires proof_ref")
        return self


@dataclass(frozen=True)
class DependencyGraph:
    edges: tuple[DependencyEdge, ...]

    def validate(self) -> "DependencyGraph":
        seen: set[tuple[str, str, DependencyKind]] = set()
        for edge in self.edges:
            edge.validate()
            key = (edge.upstream, edge.downstream, edge.kind)
            if key in seen:
                raise ValueError(f"duplicate dependency edge: {key}")
            seen.add(key)
        return self

    def dependencies_of(self, system_id: str, *, required_only: bool = True) -> tuple[str, ...]:
        if system_id not in SYSTEM_PROFILES:
            raise KeyError(system_id)
        values = {
            edge.upstream
            for edge in self.edges
            if edge.downstream == system_id and (edge.required or not required_only)
        }
        return tuple(sorted(values))

    def dependents_of(self, system_id: str) -> tuple[str, ...]:
        if system_id not in SYSTEM_PROFILES:
            raise KeyError(system_id)
        return tuple(sorted({edge.downstream for edge in self.edges if edge.upstream == system_id}))

    def affected_by_failure(self, failed_systems: Iterable[str]) -> tuple[str, ...]:
        """Return only systems transitively dependent on failed required edges."""
        self.validate()
        affected = set(failed_systems)
        frontier = list(failed_systems)
        while frontier:
            failed = frontier.pop()
            for edge in self.edges:
                if edge.required and edge.upstream == failed and edge.downstream not in affected:
                    affected.add(edge.downstream)
                    frontier.append(edge.downstream)
        return tuple(sorted(affected))

    def unaffected_by_failure(self, failed_systems: Iterable[str]) -> tuple[str, ...]:
        affected = set(self.affected_by_failure(failed_systems))
        return tuple(sorted(set(SYSTEM_PROFILES) - affected))

    def assert_no_required_cycle(self) -> "DependencyGraph":
        graph: dict[str, set[str]] = {system_id: set() for system_id in SYSTEM_PROFILES}
        for edge in self.edges:
            if edge.required and edge.kind == DependencyKind.HARD:
                graph[edge.upstream].add(edge.downstream)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError(f"required hard-dependency cycle detected at {node}")
            if node in visited:
                return
            visiting.add(node)
            for child in graph[node]:
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)
        return self


DEFAULT_DEPENDENCY_EDGES: tuple[DependencyEdge, ...] = tuple(
    DependencyEdge(*row, proof_ref="FEDERATION-EVOLUTION-PROFILE-V1")
    for row in (
        ("KIM_DATAVERSE", "SECONDARY_BRAIN", DependencyKind.DATA, True),
        ("KIM_DATAVERSE", "CHATBRIDGE", DependencyKind.DATA, True),
        ("KIM_DATAVERSE", "MASTER_BIBLE", DependencyKind.DATA, True),
        ("KIM_DATAVERSE", "HEARTBEAT_MESH", DependencyKind.DATA, True),
        ("KIM_DATAVERSE", "MATTER_LEDGER", DependencyKind.DATA, True),
        ("KIM_DATAVERSE", "TRUTHGRID", DependencyKind.DATA, True),
        ("KIM_DATAVERSE", "SUPERIOR_LOGIC", DependencyKind.DATA, False),
        ("FEDERATION_OMEGA", "DIRECT_RUNTIME", DependencyKind.HARD, True),
        ("SECURE_CAPABILITY_BOX", "DIRECT_RUNTIME", DependencyKind.PROOF, True),
        ("DIRECT_RUNTIME", "ARCHITRON", DependencyKind.HARD, True),
        ("HEARTBEAT_MESH", "EVI", DependencyKind.OBSERVABILITY, True),
        ("DIRECT_RUNTIME", "EVI", DependencyKind.HARD, True),
        ("CORPUS_FACTORY", "TRUTHGRID", DependencyKind.DATA, True),
        ("VERITAS", "TRUTHGRID", DependencyKind.SPECIALIST, True),
        ("TRUTHGRID", "MATTER_LEDGER", DependencyKind.PROOF, True),
        ("JFRIE", "MATTER_LEDGER", DependencyKind.PROOF, True),
        ("LEX_OMEGA", "MATTER_LEDGER", DependencyKind.SPECIALIST, True),
        ("TRUTHGRID", "EVIDENCEOPS", DependencyKind.PROOF, True),
        ("JFRIE", "EVIDENCEOPS", DependencyKind.PROOF, True),
        ("LEX_OMEGA", "EVIDENCEOPS", DependencyKind.SPECIALIST, True),
        ("CASEFORGE", "EVIDENCEOPS", DependencyKind.PROOF, True),
        ("SECONDARY_BRAIN", "OMEGA_MAX", DependencyKind.DATA, True),
        ("CASEFORGE", "OMEGA_MAX", DependencyKind.PROOF, True),
        ("SECURE_CAPABILITY_BOX", "OMEGA_MAX", DependencyKind.PROOF, True),
        ("TRUTHGRID", "IN_PLACE_AUDIT", DependencyKind.DATA, True),
        ("KIM_DATAVERSE", "IN_PLACE_AUDIT", DependencyKind.DATA, True),
        ("SECONDARY_BRAIN", "MASTER_BIBLE", DependencyKind.DATA, False),
        ("CAPABILITY_FORMATION_ENGINE", "KAIO", DependencyKind.SPECIALIST, False),
    )
    if row[0] in SYSTEM_PROFILES and row[1] in SYSTEM_PROFILES
)


class RouteClass(str, Enum):
    DIRECT = "DIRECT"
    SPECIALIZED = "SPECIALIZED"
    COMPOSITE = "COMPOSITE"
    REVERSIBLE_EXPERIMENT = "REVERSIBLE_EXPERIMENT"


@dataclass(frozen=True)
class RouteCandidate:
    route_id: str
    target_system: str
    route_class: RouteClass
    systems: tuple[str, ...]
    success_probability: float
    proof_strength: float
    authority_integrity: float
    reversibility: float
    cost_efficiency: float
    owner_burden_reduction: float
    information_gain: float
    proof_ref: str

    def validate(self) -> "RouteCandidate":
        if not self.route_id.strip() or not self.proof_ref.strip():
            raise ValueError("route_id and proof_ref are required")
        if self.target_system not in SYSTEM_PROFILES:
            raise ValueError("unregistered target system")
        if not self.systems or any(item not in SYSTEM_PROFILES for item in self.systems):
            raise ValueError("route systems must be registered")
        for name in (
            "success_probability",
            "proof_strength",
            "authority_integrity",
            "reversibility",
            "cost_efficiency",
            "owner_burden_reduction",
            "information_gain",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0,1]")
        return self


@dataclass(frozen=True)
class RouteScore:
    route: RouteCandidate
    score: float


class RouteSynthesizer:
    def __init__(self, graph: DependencyGraph | None = None) -> None:
        self.graph = (graph or DependencyGraph(DEFAULT_DEPENDENCY_EDGES)).validate().assert_no_required_cycle()

    @staticmethod
    def _twin_factor(twin: CapabilityTwin) -> float:
        return twin.confidence if twin.resolution_complete else 0.0

    def synthesize(self, target_system: str, twins: Mapping[str, CapabilityTwin]) -> tuple[RouteCandidate, ...]:
        if target_system not in SYSTEM_PROFILES:
            raise KeyError(target_system)
        target_twin = twins[target_system]
        target_twin.validate()
        profile = SYSTEM_PROFILES[target_system]
        dependencies = self.graph.dependencies_of(target_system)
        dep_twins = [twins[item] for item in dependencies if item in twins]
        dep_factor = min((self._twin_factor(item) for item in dep_twins), default=1.0)
        direct_factor = self._twin_factor(target_twin)
        specialized_bonus = 0.08 if profile.specialized_algorithms else 0.0

        routes = [
            RouteCandidate(
                route_id=f"{target_system}:DIRECT",
                target_system=target_system,
                route_class=RouteClass.DIRECT,
                systems=(target_system,),
                success_probability=min(1.0, 0.45 + 0.5 * direct_factor),
                proof_strength=direct_factor,
                authority_integrity=1.0,
                reversibility=0.80,
                cost_efficiency=0.90,
                owner_burden_reduction=0.90,
                information_gain=0.55,
                proof_ref=target_twin.proof_ref,
            ),
            RouteCandidate(
                route_id=f"{target_system}:SPECIALIZED",
                target_system=target_system,
                route_class=RouteClass.SPECIALIZED,
                systems=(target_system,),
                success_probability=min(1.0, 0.50 + 0.45 * direct_factor + specialized_bonus),
                proof_strength=direct_factor,
                authority_integrity=1.0,
                reversibility=0.85,
                cost_efficiency=0.82,
                owner_burden_reduction=0.88,
                information_gain=0.72,
                proof_ref=target_twin.proof_ref,
            ),
            RouteCandidate(
                route_id=f"{target_system}:COMPOSITE",
                target_system=target_system,
                route_class=RouteClass.COMPOSITE,
                systems=tuple(sorted(set(dependencies) | {target_system})),
                success_probability=min(1.0, 0.40 + 0.35 * direct_factor + 0.25 * dep_factor),
                proof_strength=min(direct_factor, dep_factor),
                authority_integrity=1.0,
                reversibility=0.75,
                cost_efficiency=0.68,
                owner_burden_reduction=0.85,
                information_gain=0.85,
                proof_ref=target_twin.proof_ref,
            ),
            RouteCandidate(
                route_id=f"{target_system}:REVERSIBLE_EXPERIMENT",
                target_system=target_system,
                route_class=RouteClass.REVERSIBLE_EXPERIMENT,
                systems=(target_system,),
                success_probability=0.55,
                proof_strength=max(0.25, direct_factor),
                authority_integrity=1.0,
                reversibility=1.0,
                cost_efficiency=0.75,
                owner_burden_reduction=0.80,
                information_gain=1.0,
                proof_ref=target_twin.proof_ref,
            ),
        ]
        return tuple(route.validate() for route in routes)


class RoutePortfolioOptimizer:
    weights: Mapping[str, float] = {
        "success_probability": 0.24,
        "proof_strength": 0.20,
        "authority_integrity": 0.16,
        "reversibility": 0.12,
        "cost_efficiency": 0.08,
        "owner_burden_reduction": 0.08,
        "information_gain": 0.12,
    }

    def score(self, route: RouteCandidate) -> RouteScore:
        route.validate()
        value = sum(self.weights[name] * float(getattr(route, name)) for name in self.weights)
        return RouteScore(route=route, score=round(value, 8))

    def rank(self, routes: Sequence[RouteCandidate]) -> tuple[RouteScore, ...]:
        if not routes:
            raise ValueError("at least one route required")
        return tuple(sorted((self.score(route) for route in routes), key=lambda item: (-item.score, item.route.route_id)))


@dataclass(frozen=True)
class FailureClassification:
    blocker: BlockerKind
    normalized_fingerprint: str
    evidence: str


class SemanticFailureClassifier:
    def classify(self, message: str, *, evidence: str) -> FailureClassification:
        text = (message or "").lower()
        if not evidence.strip():
            raise ValueError("failure classification requires evidence")
        if any(token in text for token in ("invalid argument", "unable to parse", "schema", "bad request")):
            blocker = BlockerKind.INVALID_ARGUMENT_OR_SCHEMA
        elif any(token in text for token in ("unauthorized", "authentication", "not connected", "credential")):
            blocker = BlockerKind.AUTHENTICATION_OR_CONNECTION_REQUIRED
        elif any(token in text for token in ("approval required", "permission denied", "forbidden")):
            blocker = BlockerKind.APPROVAL_OR_PERMISSION_REQUIRED
        elif any(token in text for token in ("timeout", "temporarily unavailable", "503", "502", "transient")):
            blocker = BlockerKind.TRANSIENT_TECHNICAL_LIMITATION
        elif any(token in text for token in ("policy boundary", "safety boundary", "prohibited")):
            blocker = BlockerKind.SAFETY_OR_POLICY_HARD_BOUNDARY
        elif any(token in text for token in ("platform hard limit", "not supported by platform")):
            blocker = BlockerKind.PLATFORM_HARD_LIMIT
        elif any(token in text for token in ("external dependency", "custodian", "third party controls")):
            blocker = BlockerKind.EXTERNAL_DEPENDENCY
        elif any(token in text for token in ("routes exhausted", "no authorized route remains")):
            blocker = BlockerKind.AUTHORIZED_ROUTE_SPACE_EXHAUSTED
        else:
            blocker = BlockerKind.LOCAL_ROUTE_ERROR
        fingerprint = f"{blocker.value}:{' '.join(text.split())[:160]}"
        return FailureClassification(blocker=blocker, normalized_fingerprint=fingerprint, evidence=evidence)


@dataclass(frozen=True)
class RepairDecision:
    blocker: BlockerKind
    repair_action: str
    retry_same_route: bool
    continue_unaffected_lanes: bool
    approval_required: bool
    terminal_for_exact_scope: bool


class SelfHealingRouteEngine:
    policies: Mapping[BlockerKind, RepairDecision] = {
        BlockerKind.INVALID_ARGUMENT_OR_SCHEMA: RepairDecision(BlockerKind.INVALID_ARGUMENT_OR_SCHEMA, "DISCOVER_SCHEMA_AND_RETRY_CORRECTED_ROUTE", False, True, False, False),
        BlockerKind.AUTHENTICATION_OR_CONNECTION_REQUIRED: RepairDecision(BlockerKind.AUTHENTICATION_OR_CONNECTION_REQUIRED, "DISCOVER_ALTERNATE_CONNECTED_ROUTE_OR_BOUND_AUTH_DEPENDENCY", False, True, False, False),
        BlockerKind.APPROVAL_OR_PERMISSION_REQUIRED: RepairDecision(BlockerKind.APPROVAL_OR_PERMISSION_REQUIRED, "STAGE_GATED_ACTION_AND_CONTINUE_SAFE_LANES", False, True, True, False),
        BlockerKind.EXTERNAL_DEPENDENCY: RepairDecision(BlockerKind.EXTERNAL_DEPENDENCY, "DISPOSITION_EXTERNAL_DEPENDENCY_AND_CONTINUE_INTERNAL", False, True, False, False),
        BlockerKind.TRANSIENT_TECHNICAL_LIMITATION: RepairDecision(BlockerKind.TRANSIENT_TECHNICAL_LIMITATION, "RETRY_ONCE_OR_SWITCH_MATERIALLY_DISTINCT_ROUTE", True, True, False, False),
        BlockerKind.SAFETY_OR_POLICY_HARD_BOUNDARY: RepairDecision(BlockerKind.SAFETY_OR_POLICY_HARD_BOUNDARY, "STOP_PROHIBITED_SCOPE_AND_SELECT_ALLOWED_ALTERNATIVE", False, True, False, True),
        BlockerKind.PLATFORM_HARD_LIMIT: RepairDecision(BlockerKind.PLATFORM_HARD_LIMIT, "CHECK_OBJECTIVE_EQUIVALENT_USER_LEVEL_ROUTE", False, True, False, True),
        BlockerKind.AUTHORIZED_ROUTE_SPACE_EXHAUSTED: RepairDecision(BlockerKind.AUTHORIZED_ROUTE_SPACE_EXHAUSTED, "PRESERVE_BOUND_DEPENDENCY_AND_REOPEN_ON_CAPABILITY_CHANGE", False, True, False, True),
        BlockerKind.LOCAL_ROUTE_ERROR: RepairDecision(BlockerKind.LOCAL_ROUTE_ERROR, "CLASSIFY_DEEPER_AND_SWITCH_ROUTE", False, True, False, False),
    }

    def decide(self, classification: FailureClassification) -> RepairDecision:
        return self.policies[classification.blocker]


@dataclass(frozen=True)
class SuccessRouteRecipe:
    recipe_id: str
    objective_class: str
    route_id: str
    prerequisites: tuple[str, ...]
    proof_ref: str
    freshness_rule: str
    known_failure_fingerprints: tuple[str, ...] = ()

    def validate(self) -> "SuccessRouteRecipe":
        if not all((self.recipe_id.strip(), self.objective_class.strip(), self.route_id.strip(), self.proof_ref.strip(), self.freshness_rule.strip())):
            raise ValueError("success route recipe is incomplete")
        return self


@dataclass(frozen=True)
class FailureMemoryEntry:
    fingerprint: str
    repair_action: str
    repair_proof_ref: str
    recurrence_count: int = 1

    def validate(self) -> "FailureMemoryEntry":
        if not self.fingerprint.strip() or not self.repair_action.strip() or not self.repair_proof_ref.strip():
            raise ValueError("failure memory entry is incomplete")
        if self.recurrence_count < 1:
            raise ValueError("recurrence_count must be positive")
        return self


@dataclass
class OperationalMemory:
    success_routes: dict[str, SuccessRouteRecipe] = field(default_factory=dict)
    failures: dict[str, FailureMemoryEntry] = field(default_factory=dict)

    def record_success(self, recipe: SuccessRouteRecipe) -> None:
        recipe.validate()
        self.success_routes[recipe.recipe_id] = recipe

    def record_failure(self, entry: FailureMemoryEntry) -> None:
        entry.validate()
        existing = self.failures.get(entry.fingerprint)
        if existing:
            entry = FailureMemoryEntry(
                fingerprint=entry.fingerprint,
                repair_action=entry.repair_action,
                repair_proof_ref=entry.repair_proof_ref,
                recurrence_count=existing.recurrence_count + 1,
            )
        self.failures[entry.fingerprint] = entry

    def known_route(self, objective_class: str) -> tuple[SuccessRouteRecipe, ...]:
        return tuple(sorted((r for r in self.success_routes.values() if r.objective_class == objective_class), key=lambda r: r.recipe_id))


@dataclass(frozen=True)
class PreloadPlan:
    target_system: str
    required_systems: tuple[str, ...]
    refresh_required: tuple[str, ...]
    adapter_required: tuple[str, ...]


class PredictiveCapabilityPreloader:
    def __init__(self, graph: DependencyGraph | None = None) -> None:
        self.graph = (graph or DependencyGraph(DEFAULT_DEPENDENCY_EDGES)).validate()

    def plan(self, target_system: str, twins: Mapping[str, CapabilityTwin]) -> PreloadPlan:
        required = tuple(sorted(set(self.graph.dependencies_of(target_system)) | {target_system}))
        refresh = []
        adapter = []
        for system_id in required:
            twin = twins[system_id]
            if not twin.fresh or not twin.resolution_complete:
                refresh.append(system_id)
            if twin.twin_state == TwinState.CANONICAL_VERIFIED_ADAPTER_REQUIRED:
                adapter.append(system_id)
        return PreloadPlan(target_system, required, tuple(sorted(refresh)), tuple(sorted(adapter)))


class TerminalStateFirewall:
    """Wrap the already-admitted CapabilityResolutionGate for terminal claims."""

    def __init__(self) -> None:
        self.gate = CapabilityResolutionGate()

    def evaluate(self, request: CapabilityDecisionRequest) -> CapabilityDecision:
        return self.gate.evaluate(request)


@dataclass(frozen=True)
class NegativeProofReceipt:
    proposition: str
    scope: str
    routes_checked: tuple[str, ...]
    search_receipts: tuple[str, ...]
    hard_boundary: BlockerKind | None = None

    def validate(self) -> "NegativeProofReceipt":
        if not self.proposition.strip() or not self.scope.strip():
            raise ValueError("negative proof proposition and scope required")
        if not self.routes_checked and self.hard_boundary not in {
            BlockerKind.SAFETY_OR_POLICY_HARD_BOUNDARY,
            BlockerKind.PLATFORM_HARD_LIMIT,
        }:
            raise ValueError("negative proof requires checked routes or hard boundary")
        if self.routes_checked and not self.search_receipts:
            raise ValueError("checked routes require receipts")
        return self


@dataclass(frozen=True)
class Counterfactual:
    blocker: BlockerKind
    minimum_changed_condition: str
    next_action: str
    objective_remains_open: bool


class CounterfactualEngine:
    conditions: Mapping[BlockerKind, tuple[str, str, bool]] = {
        BlockerKind.INVALID_ARGUMENT_OR_SCHEMA: ("VALID_SCHEMA_OR_IDENTIFIER", "DISCOVER_SCHEMA_AND_RETRY", True),
        BlockerKind.AUTHENTICATION_OR_CONNECTION_REQUIRED: ("CURRENT_AUTHENTICATED_ROUTE", "DISCOVER_OR_BIND_AUTHORIZED_CONNECTION", True),
        BlockerKind.APPROVAL_OR_PERMISSION_REQUIRED: ("REQUIRED_APPROVAL_OR_PERMISSION", "STAGE_ACTION_AND_CONTINUE_SAFE_WORK", True),
        BlockerKind.EXTERNAL_DEPENDENCY: ("EXTERNAL_INPUT_BECOMES_AVAILABLE", "DISPOSITION_AND_RECHECK_ON_EVENT", True),
        BlockerKind.TRANSIENT_TECHNICAL_LIMITATION: ("ROUTE_RECOVERS_OR_ALTERNATE_ROUTE_EXISTS", "RETRY_OR_SWITCH_ROUTE", True),
        BlockerKind.PLATFORM_HARD_LIMIT: ("OBJECTIVE_EQUIVALENT_USER_LEVEL_IMPLEMENTATION", "SYNTHESIZE_EQUIVALENT_ROUTE", True),
        BlockerKind.SAFETY_OR_POLICY_HARD_BOUNDARY: ("REQUESTED_ACTION_CHANGES_TO_ALLOWED_SCOPE", "SELECT_SAFE_ALLOWED_ALTERNATIVE", False),
        BlockerKind.AUTHORIZED_ROUTE_SPACE_EXHAUSTED: ("CAPABILITY_OR_AUTHORITY_STATE_CHANGES", "REOPEN_WHEN_STATE_CHANGES", True),
        BlockerKind.LOCAL_ROUTE_ERROR: ("MATERIALLY_DISTINCT_ROUTE", "CLASSIFY_AND_SWITCH", True),
    }

    def derive(self, blocker: BlockerKind) -> Counterfactual:
        condition, action, remains_open = self.conditions[blocker]
        return Counterfactual(blocker, condition, action, remains_open)


@dataclass(frozen=True)
class MissionExecutionState:
    mission_id: str
    executable_internal_dependencies: int
    external_dependencies: tuple[str, ...] = ()
    approval_holds: tuple[str, ...] = ()
    hard_boundaries: tuple[str, ...] = ()
    user_stopped: bool = False

    def validate(self) -> "MissionExecutionState":
        if not self.mission_id.strip():
            raise ValueError("mission_id required")
        if self.executable_internal_dependencies < 0:
            raise ValueError("executable_internal_dependencies must be non-negative")
        return self


@dataclass(frozen=True)
class ContinuationDecision:
    continue_execution: bool
    mission_complete: bool
    reason: str
    next_mode: str


class MissionContinuationKernel:
    def decide(self, state: MissionExecutionState) -> ContinuationDecision:
        state.validate()
        if state.user_stopped:
            return ContinuationDecision(False, False, "USER_STOP", "STOP")
        if state.executable_internal_dependencies > 0:
            return ContinuationDecision(True, False, "EXECUTABLE_INTERNAL_WORK_REMAINS", "EXECUTE_REPAIR_CONTINUE")
        if state.approval_holds or state.external_dependencies or state.hard_boundaries:
            return ContinuationDecision(False, True, "INTERNAL_COMPLETE_NON_EXECUTABLE_BOUNDARIES_DISPOSITIONED", "BOUND_EXTERNAL_HOLDS")
        return ContinuationDecision(False, True, "ALL_DEPENDENCIES_CLOSED", "CLOSE")


@dataclass(frozen=True)
class WorkZeroDecision:
    internal_complete: bool
    mission_complete: bool
    external_dependencies: tuple[str, ...]
    approval_holds: tuple[str, ...]
    hard_boundaries: tuple[str, ...]


class ExecutableWorkZeroGate:
    def evaluate(self, state: MissionExecutionState) -> WorkZeroDecision:
        state.validate()
        internal_complete = state.executable_internal_dependencies == 0
        return WorkZeroDecision(
            internal_complete=internal_complete,
            mission_complete=internal_complete,
            external_dependencies=tuple(state.external_dependencies),
            approval_holds=tuple(state.approval_holds),
            hard_boundaries=tuple(state.hard_boundaries),
        )


COMMON_RUNTIME_STAGES = tuple(range(3, 16))


__all__ = [
    "COMMON_RUNTIME_STAGES",
    "Counterfactual",
    "CounterfactualEngine",
    "DEFAULT_DEPENDENCY_EDGES",
    "DependencyEdge",
    "DependencyGraph",
    "DependencyKind",
    "ExecutableWorkZeroGate",
    "FailureClassification",
    "FailureMemoryEntry",
    "MissionContinuationKernel",
    "MissionExecutionState",
    "NegativeProofReceipt",
    "OperationalMemory",
    "PredictiveCapabilityPreloader",
    "PreloadPlan",
    "RepairDecision",
    "RouteCandidate",
    "RouteClass",
    "RoutePortfolioOptimizer",
    "RouteScore",
    "RouteSynthesizer",
    "SelfHealingRouteEngine",
    "SemanticFailureClassifier",
    "SuccessRouteRecipe",
    "TerminalStateFirewall",
    "WorkZeroDecision",
]
