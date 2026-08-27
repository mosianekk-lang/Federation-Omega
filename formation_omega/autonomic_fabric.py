"""Autonomic Mission Convergence Fabric (AMCF) v1.

Provider-neutral, public-safe evolution layer for Mission Convergence Engine (MCE).
It adds proof-directed scheduling, monotonic closure gating, counterfactual planning,
failure-horizon forecasting, mission genomes and authority-isolated mission swarms.

This module does not create credentials, provider authority, background execution,
or external effects. It produces deterministic plans that require downstream
execution and independent readback.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Iterable


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _stable_hash(payload: object) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _tokens(value: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", value.casefold()))


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a = set(left)
    b = set(right)
    if not a and not b:
        return 1.0
    union = a | b
    return 0.0 if not union else len(a & b) / len(union)


class AuthorityCeiling(str, Enum):
    A0_OBSERVE = "A0_OBSERVE"
    A1_INTERNAL = "A1_INTERNAL"
    A2_BOUNDED_EFFECT = "A2_BOUNDED_EFFECT"
    A3_CONSEQUENTIAL = "A3_CONSEQUENTIAL"


_AUTHORITY_RANK = {
    AuthorityCeiling.A0_OBSERVE: 0,
    AuthorityCeiling.A1_INTERNAL: 1,
    AuthorityCeiling.A2_BOUNDED_EFFECT: 2,
    AuthorityCeiling.A3_CONSEQUENTIAL: 3,
}


@dataclass(frozen=True)
class MissionStateVector:
    """Higher is better on every axis."""

    verified_closure: float = 0.0
    information: float = 0.0
    safety: float = 0.0
    recoverability: float = 0.0
    unlock_leverage: float = 0.0

    def normalized(self) -> "MissionStateVector":
        return MissionStateVector(
            verified_closure=_clip(self.verified_closure),
            information=_clip(self.information),
            safety=_clip(self.safety),
            recoverability=_clip(self.recoverability),
            unlock_leverage=_clip(self.unlock_leverage),
        )


@dataclass(frozen=True)
class ClosureGateDecision:
    accepted: bool
    improved_axes: tuple[str, ...]
    regressed_axes: tuple[str, ...]
    reason: str


class MonotonicClosureGate:
    """Rejects actions that do not create measurable mission progress."""

    AXES = ("verified_closure", "information", "safety", "recoverability", "unlock_leverage")

    def __init__(self, *, tolerance: float = 1e-9) -> None:
        self.tolerance = float(tolerance)

    def evaluate(self, before: MissionStateVector, after: MissionStateVector) -> ClosureGateDecision:
        left = before.normalized()
        right = after.normalized()
        improved: list[str] = []
        regressed: list[str] = []
        for axis in self.AXES:
            delta = getattr(right, axis) - getattr(left, axis)
            if delta > self.tolerance:
                improved.append(axis)
            elif delta < -self.tolerance:
                regressed.append(axis)
        if regressed:
            return ClosureGateDecision(False, tuple(improved), tuple(regressed), "REGRESSION_REJECTED")
        if not improved:
            return ClosureGateDecision(False, (), (), "NO_MEASURABLE_PROGRESS")
        return ClosureGateDecision(True, tuple(improved), (), "MONOTONIC_PROGRESS")


@dataclass(frozen=True)
class ActionCandidate:
    action_id: str
    objective: str
    closure_leverage: float
    information_gain: float
    success_probability: float
    reversibility: float
    cost: float
    risk: float
    latency: float
    unlock_count: int = 0
    shared_state_key: str | None = None
    authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL
    external_effect: bool = False
    required_capabilities: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.action_id.strip():
            raise ValueError("action_id is required")
        if not self.objective.strip():
            raise ValueError("objective is required")
        if self.cost < 0 or self.risk < 0 or self.latency < 0:
            raise ValueError("cost/risk/latency must be non-negative")
        if self.unlock_count < 0:
            raise ValueError("unlock_count must be non-negative")

    @property
    def score(self) -> float:
        leverage = max(0.001, _clip(self.closure_leverage))
        info = max(0.001, _clip(self.information_gain))
        success = max(0.001, _clip(self.success_probability))
        reversible = max(0.05, _clip(self.reversibility))
        unlock_multiplier = 1.0 + math.log1p(self.unlock_count)
        denominator = (1.0 + self.cost) * (1.0 + self.risk) * (1.0 + self.latency)
        return (leverage * info * success * reversible * unlock_multiplier) / denominator


@dataclass(frozen=True)
class ScheduledAction:
    action: ActionCandidate
    score: float
    rank: int
    hold_reason: str | None = None


class ProofDirectedScheduler:
    """Selects high-value ready work while serializing shared state."""

    def __init__(
        self,
        *,
        authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL,
        allow_external_effects: bool = False,
    ) -> None:
        self.authority_ceiling = authority_ceiling
        self.allow_external_effects = bool(allow_external_effects)

    def _hold_reason(self, action: ActionCandidate) -> str | None:
        if _AUTHORITY_RANK[action.authority_ceiling] > _AUTHORITY_RANK[self.authority_ceiling]:
            return "AUTHORITY_CEILING_EXCEEDED"
        if action.external_effect and not self.allow_external_effects:
            return "EXTERNAL_EFFECT_NOT_AUTHORIZED"
        return None

    def rank(self, actions: Iterable[ActionCandidate]) -> tuple[ScheduledAction, ...]:
        ordered = sorted(actions, key=lambda item: (-item.score, item.action_id))
        return tuple(
            ScheduledAction(action, action.score, index, self._hold_reason(action))
            for index, action in enumerate(ordered, start=1)
        )

    def ready_wave(self, actions: Iterable[ActionCandidate], *, max_parallel: int = 4) -> tuple[ScheduledAction, ...]:
        if max_parallel < 1:
            raise ValueError("max_parallel must be at least one")
        selected: list[ScheduledAction] = []
        locked_keys: set[str] = set()
        for item in self.rank(actions):
            if item.hold_reason:
                continue
            key = item.action.shared_state_key
            if key and key in locked_keys:
                continue
            selected.append(item)
            if key:
                locked_keys.add(key)
            if len(selected) >= max_parallel:
                break
        return tuple(selected)


@dataclass(frozen=True)
class CounterfactualOption:
    option_id: str
    label: str
    projected_delta: MissionStateVector
    success_probability: float
    option_value: float = 0.0
    cost: float = 0.0
    risk: float = 0.0
    latency: float = 0.0
    evidence_strength: float = 0.0

    @property
    def utility(self) -> float:
        delta = self.projected_delta.normalized()
        benefit = (
            0.32 * delta.verified_closure
            + 0.22 * delta.information
            + 0.18 * delta.safety
            + 0.14 * delta.recoverability
            + 0.14 * delta.unlock_leverage
        )
        confidence = max(0.05, _clip(self.success_probability))
        proof = 0.5 + 0.5 * _clip(self.evidence_strength)
        denominator = (1.0 + self.cost) * (1.0 + self.risk) * (1.0 + self.latency)
        return ((benefit + max(0.0, self.option_value)) * confidence * proof) / denominator


class CounterfactualPlanner:
    def rank(self, options: Iterable[CounterfactualOption]) -> tuple[CounterfactualOption, ...]:
        return tuple(sorted(options, key=lambda item: (-item.utility, item.option_id)))

    def best(self, options: Iterable[CounterfactualOption]) -> CounterfactualOption:
        ranked = self.rank(options)
        if not ranked:
            raise ValueError("at least one counterfactual option is required")
        return ranked[0]


@dataclass(frozen=True)
class FailureForecast:
    fingerprint: str
    precursor: str
    probability: float
    impact: float
    precursor_confidence: float
    prevention_leverage: float
    lead_time: float
    preventive_action: str
    fallback_route: str

    @property
    def priority(self) -> float:
        numerator = (
            _clip(self.probability)
            * _clip(self.impact)
            * max(0.05, _clip(self.precursor_confidence))
            * max(0.05, _clip(self.prevention_leverage))
        )
        return numerator / (1.0 + max(0.0, self.lead_time))


class FailureHorizon:
    def rank(self, forecasts: Iterable[FailureForecast]) -> tuple[FailureForecast, ...]:
        return tuple(sorted(forecasts, key=lambda item: (-item.priority, item.fingerprint)))

    def preempt(self, forecasts: Iterable[FailureForecast], *, threshold: float = 0.05) -> tuple[FailureForecast, ...]:
        return tuple(item for item in self.rank(forecasts) if item.priority >= threshold)


@dataclass(frozen=True)
class MissionGenome:
    objective_class: str
    invariants: tuple[str, ...]
    proof_axes: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    failure_fingerprints: tuple[str, ...] = ()
    recovery_routes: tuple[str, ...] = ()
    pattern_id: str = ""

    @classmethod
    def create(
        cls,
        *,
        objective_class: str,
        invariants: Iterable[str],
        proof_axes: Iterable[str],
        required_capabilities: Iterable[str],
        failure_fingerprints: Iterable[str] = (),
        recovery_routes: Iterable[str] = (),
    ) -> "MissionGenome":
        body = {
            "objective_class": " ".join(objective_class.split()),
            "invariants": sorted(set(invariants)),
            "proof_axes": sorted(set(proof_axes)),
            "required_capabilities": sorted(set(required_capabilities)),
            "failure_fingerprints": sorted(set(failure_fingerprints)),
            "recovery_routes": sorted(set(recovery_routes)),
        }
        if not body["objective_class"]:
            raise ValueError("objective_class is required")
        return cls(
            objective_class=body["objective_class"],
            invariants=tuple(body["invariants"]),
            proof_axes=tuple(body["proof_axes"]),
            required_capabilities=tuple(body["required_capabilities"]),
            failure_fingerprints=tuple(body["failure_fingerprints"]),
            recovery_routes=tuple(body["recovery_routes"]),
            pattern_id=_stable_hash(body)[:20],
        )

    def similarity(self, other: "MissionGenome") -> float:
        objective_similarity = _jaccard(_tokens(self.objective_class), _tokens(other.objective_class))
        return (
            0.30 * objective_similarity
            + 0.20 * _jaccard(self.invariants, other.invariants)
            + 0.20 * _jaccard(self.proof_axes, other.proof_axes)
            + 0.20 * _jaccard(self.required_capabilities, other.required_capabilities)
            + 0.10 * _jaccard(self.failure_fingerprints, other.failure_fingerprints)
        )


class GenomeLibrary:
    def __init__(self, genomes: Iterable[MissionGenome] = ()) -> None:
        self._genomes: dict[str, MissionGenome] = {item.pattern_id: item for item in genomes}

    def add(self, genome: MissionGenome) -> None:
        self._genomes[genome.pattern_id] = genome

    def match(self, target: MissionGenome, *, minimum_similarity: float = 0.35) -> tuple[tuple[MissionGenome, float], ...]:
        ranked = sorted(
            ((item, item.similarity(target)) for item in self._genomes.values()),
            key=lambda pair: (-pair[1], pair[0].pattern_id),
        )
        return tuple(pair for pair in ranked if pair[1] >= minimum_similarity)


class SwarmRole(str, Enum):
    BUILDER = "BUILDER"
    FALSIFIER = "FALSIFIER"
    EVIDENCE = "EVIDENCE"
    ROUTE = "ROUTE"
    SENTINEL = "SENTINEL"
    RECOVERY = "RECOVERY"
    WITNESS = "WITNESS"


@dataclass(frozen=True)
class SwarmCell:
    cell_id: str
    mission_id: str
    role: SwarmRole
    objective: str
    authority_ceiling: AuthorityCeiling
    independence_domain: str
    required_capabilities: tuple[str, ...] = ()
    may_self_certify: bool = False


class MissionSwarmPlanner:
    """Produces authority-isolated cells around one immutable mission target."""

    _ROLE_AUTHORITY = {
        SwarmRole.BUILDER: AuthorityCeiling.A1_INTERNAL,
        SwarmRole.FALSIFIER: AuthorityCeiling.A0_OBSERVE,
        SwarmRole.EVIDENCE: AuthorityCeiling.A0_OBSERVE,
        SwarmRole.ROUTE: AuthorityCeiling.A1_INTERNAL,
        SwarmRole.SENTINEL: AuthorityCeiling.A0_OBSERVE,
        SwarmRole.RECOVERY: AuthorityCeiling.A1_INTERNAL,
        SwarmRole.WITNESS: AuthorityCeiling.A0_OBSERVE,
    }

    def plan(self, *, mission_id: str, objective: str, required_capabilities: Iterable[str] = ()) -> tuple[SwarmCell, ...]:
        caps = tuple(sorted(set(required_capabilities)))
        cells = []
        for role in SwarmRole:
            cells.append(
                SwarmCell(
                    cell_id=f"{mission_id}:{role.value}",
                    mission_id=mission_id,
                    role=role,
                    objective=objective,
                    authority_ceiling=self._ROLE_AUTHORITY[role],
                    independence_domain="INDEPENDENT_VERIFICATION" if role in {SwarmRole.FALSIFIER, SwarmRole.WITNESS} else role.value,
                    required_capabilities=caps,
                    may_self_certify=False,
                )
            )
        return tuple(cells)


@dataclass(frozen=True)
class AutonomicPlan:
    mission_id: str
    selected_wave: tuple[ScheduledAction, ...]
    preemptions: tuple[FailureForecast, ...]
    matched_genomes: tuple[tuple[str, float], ...]
    swarm: tuple[SwarmCell, ...]
    plan_sha256: str


class AutonomicMissionFabric:
    """Deterministic planning facade around MCE; never executes provider effects."""

    def __init__(
        self,
        *,
        authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL,
        genome_library: GenomeLibrary | None = None,
    ) -> None:
        self.scheduler = ProofDirectedScheduler(authority_ceiling=authority_ceiling, allow_external_effects=False)
        self.horizon = FailureHorizon()
        self.genomes = genome_library or GenomeLibrary()
        self.swarm_planner = MissionSwarmPlanner()

    def plan(
        self,
        *,
        mission_id: str,
        objective: str,
        actions: Iterable[ActionCandidate],
        forecasts: Iterable[FailureForecast] = (),
        genome: MissionGenome | None = None,
        max_parallel: int = 4,
    ) -> AutonomicPlan:
        selected = self.scheduler.ready_wave(actions, max_parallel=max_parallel)
        preemptions = self.horizon.preempt(forecasts)
        matches: tuple[tuple[str, float], ...] = ()
        if genome is not None:
            matches = tuple((item.pattern_id, score) for item, score in self.genomes.match(genome))
        swarm = self.swarm_planner.plan(
            mission_id=mission_id,
            objective=objective,
            required_capabilities=genome.required_capabilities if genome else (),
        )
        body = {
            "mission_id": mission_id,
            "selected": [item.action.action_id for item in selected],
            "preemptions": [item.fingerprint for item in preemptions],
            "matches": matches,
            "swarm": [item.cell_id for item in swarm],
        }
        return AutonomicPlan(
            mission_id=mission_id,
            selected_wave=selected,
            preemptions=preemptions,
            matched_genomes=matches,
            swarm=swarm,
            plan_sha256=_stable_hash(body),
        )
