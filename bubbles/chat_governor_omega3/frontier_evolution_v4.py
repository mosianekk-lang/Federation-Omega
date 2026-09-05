from __future__ import annotations

"""ChatGov/FUSE frontier evolution controls v4.

The goal is to turn repeated, independently proven operational intelligence into
cheaper deterministic candidates while preventing rapid concurrent development
from weakening assurance.

This module adds only proposal/qualification logic:
* trajectory crystallization into non-authorized skill candidates;
* Pareto policy optimization under hard proof/success constraints;
* independent author/test/review harness gating for high-risk changes;
* intervening-change reconciliation for safe re-anchor vs semantic conflict court.

It does not generate executable code, merge branches, alter provider traffic,
promote skills, or authorize effects.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Any, Mapping, Sequence


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _finite(value: float, name: str, minimum: float = 0.0) -> float:
    value = float(value)
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name}_INVALID")
    return value


@dataclass(frozen=True, slots=True)
class TrajectoryObservation:
    trajectory_id: str
    tool_sequence: tuple[str, ...]
    precondition_schema_sha256: str
    context_fingerprint: str
    effect_class: str
    proof_axes: tuple[str, ...]
    success: bool
    proof_valid: bool
    latency_ms: float
    cost: float
    owner_burden: float

    def validate(self) -> "TrajectoryObservation":
        if not self.trajectory_id.strip() or not self.tool_sequence:
            raise ValueError("TRAJECTORY_IDENTITY_REQUIRED")
        if len(self.precondition_schema_sha256) != 64 or not self.context_fingerprint.strip():
            raise ValueError("TRAJECTORY_PRECONDITION_OR_CONTEXT_INVALID")
        if self.effect_class not in {"NO_EFFECT", "READ_ONLY", "PURE_COMPUTE", "BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"}:
            raise ValueError("TRAJECTORY_EFFECT_CLASS_INVALID")
        _finite(self.latency_ms, "TRAJECTORY_LATENCY")
        _finite(self.cost, "TRAJECTORY_COST")
        _finite(self.owner_burden, "TRAJECTORY_OWNER_BURDEN")
        return self


@dataclass(frozen=True, slots=True)
class SkillCandidate:
    skill_id: str
    trajectory_signature: str
    tool_sequence: tuple[str, ...]
    precondition_schema_sha256: str
    effect_class: str
    required_proof_axes: tuple[str, ...]
    observed_runs: int
    context_diversity: int
    median_latency_ms: float
    mean_cost: float
    mean_owner_burden: float
    state: str
    auto_execution_authorized: bool
    source_admission_authorized: bool


class TrajectoryCrystallizer:
    """Crystallize a repeated stable route into a *candidate*, never a promotion."""

    def __init__(self, *, min_runs: int = 20, min_context_diversity: int = 3) -> None:
        if min_runs < 2 or min_context_diversity < 1:
            raise ValueError("CRYSTALLIZER_POLICY_INVALID")
        self.min_runs = int(min_runs)
        self.min_context_diversity = int(min_context_diversity)

    @staticmethod
    def signature(row: TrajectoryObservation) -> str:
        row.validate()
        return _digest(
            {
                "tools": row.tool_sequence,
                "preconditions": row.precondition_schema_sha256,
                "effect_class": row.effect_class,
                "proof_axes": tuple(sorted(set(row.proof_axes))),
            }
        )

    def compile(self, observations: Sequence[TrajectoryObservation]) -> SkillCandidate | None:
        rows = [row.validate() for row in observations]
        if len(rows) < self.min_runs:
            return None
        signatures = {self.signature(row) for row in rows}
        if len(signatures) != 1:
            raise ValueError("CRYSTALLIZER_MIXED_TRAJECTORIES")
        if any(not row.success or not row.proof_valid for row in rows):
            return None
        contexts = {row.context_fingerprint for row in rows}
        if len(contexts) < self.min_context_diversity:
            return None
        tools = rows[0].tool_sequence
        effect_class = rows[0].effect_class
        proof_axes = tuple(sorted({axis for row in rows for axis in row.proof_axes}))
        latencies = sorted(row.latency_ms for row in rows)
        middle = len(latencies) // 2
        median = latencies[middle] if len(latencies) % 2 else (latencies[middle - 1] + latencies[middle]) / 2.0
        signature = next(iter(signatures))
        state = "CANDIDATE_EFFECT_GATED" if effect_class in {"BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"} else "CANDIDATE_DETERMINISTIC_SKILL"
        return SkillCandidate(
            skill_id="SKILL-CAND-" + signature[:16],
            trajectory_signature=signature,
            tool_sequence=tools,
            precondition_schema_sha256=rows[0].precondition_schema_sha256,
            effect_class=effect_class,
            required_proof_axes=proof_axes,
            observed_runs=len(rows),
            context_diversity=len(contexts),
            median_latency_ms=median,
            mean_cost=sum(row.cost for row in rows) / len(rows),
            mean_owner_burden=sum(row.owner_burden for row in rows) / len(rows),
            state=state,
            auto_execution_authorized=False,
            source_admission_authorized=False,
        )


@dataclass(frozen=True, slots=True)
class PolicyOutcome:
    policy_id: str
    success_lower_bound: float
    proof_violations: int
    p95_latency_ms: float
    cost_per_success: float
    owner_burden: float
    sample_size: int

    def validate(self) -> "PolicyOutcome":
        if not self.policy_id.strip() or not 0 <= float(self.success_lower_bound) <= 1:
            raise ValueError("POLICY_OUTCOME_ID_OR_SUCCESS_INVALID")
        if self.proof_violations < 0 or self.sample_size < 1:
            raise ValueError("POLICY_OUTCOME_SAMPLE_INVALID")
        _finite(self.p95_latency_ms, "POLICY_LATENCY")
        _finite(self.cost_per_success, "POLICY_COST")
        _finite(self.owner_burden, "POLICY_OWNER_BURDEN")
        return self


@dataclass(frozen=True, slots=True)
class ParetoPolicyResult:
    eligible: tuple[str, ...]
    frontier: tuple[str, ...]
    rejected: tuple[str, ...]
    reason: str
    auto_promotion_authorized: bool


class ParetoPolicyOptimizer:
    """Find non-dominated runtime policies without collapsing quality into one score."""

    def __init__(self, *, min_success_lower_bound: float = 0.80, min_sample_size: int = 30) -> None:
        if not 0 <= min_success_lower_bound <= 1 or min_sample_size < 1:
            raise ValueError("PARETO_POLICY_INVALID")
        self.min_success_lower_bound = float(min_success_lower_bound)
        self.min_sample_size = int(min_sample_size)

    @staticmethod
    def _dominates(a: PolicyOutcome, b: PolicyOutcome) -> bool:
        at_least = (
            a.success_lower_bound >= b.success_lower_bound
            and a.p95_latency_ms <= b.p95_latency_ms
            and a.cost_per_success <= b.cost_per_success
            and a.owner_burden <= b.owner_burden
        )
        strict = (
            a.success_lower_bound > b.success_lower_bound
            or a.p95_latency_ms < b.p95_latency_ms
            or a.cost_per_success < b.cost_per_success
            or a.owner_burden < b.owner_burden
        )
        return at_least and strict

    def evaluate(self, outcomes: Sequence[PolicyOutcome]) -> ParetoPolicyResult:
        rows = [row.validate() for row in outcomes]
        if len({row.policy_id for row in rows}) != len(rows):
            raise ValueError("POLICY_OUTCOME_DUPLICATE")
        eligible = [
            row
            for row in rows
            if row.proof_violations == 0
            and row.sample_size >= self.min_sample_size
            and row.success_lower_bound >= self.min_success_lower_bound
        ]
        rejected = sorted(set(row.policy_id for row in rows) - set(row.policy_id for row in eligible))
        frontier = [
            row
            for row in eligible
            if not any(self._dominates(other, row) for other in eligible if other.policy_id != row.policy_id)
        ]
        frontier.sort(key=lambda row: row.policy_id)
        return ParetoPolicyResult(
            eligible=tuple(sorted(row.policy_id for row in eligible)),
            frontier=tuple(row.policy_id for row in frontier),
            rejected=tuple(rejected),
            reason="HARD_PROOF_GATE_THEN_MULTI_OBJECTIVE_NON_DOMINATION",
            auto_promotion_authorized=False,
        )


@dataclass(frozen=True, slots=True)
class HarnessDecision:
    allow: bool
    reason: str
    independent_test_author: bool
    independent_reviewer: bool


class IndependentHarnessGate:
    """High-risk source candidates require independent test and review principals."""

    def decide(
        self,
        *,
        risk_class: str,
        author_principal: str,
        test_principal: str,
        review_principal: str,
    ) -> HarnessDecision:
        values = [str(x).strip() for x in (author_principal, test_principal, review_principal)]
        if any(not value for value in values):
            raise ValueError("HARNESS_PRINCIPAL_REQUIRED")
        independent_test = values[0] != values[1]
        independent_review = values[0] != values[2] and values[1] != values[2]
        high_risk = str(risk_class).upper() in {"R4", "R4_CORE", "R5", "MISSION_CRITICAL"}
        if high_risk and not independent_test:
            return HarnessDecision(False, "HIGH_RISK_TEST_HARNESS_NOT_INDEPENDENT", independent_test, independent_review)
        if high_risk and not independent_review:
            return HarnessDecision(False, "HIGH_RISK_REVIEW_HARNESS_NOT_INDEPENDENT", independent_test, independent_review)
        return HarnessDecision(True, "INDEPENDENCE_REQUIREMENT_SATISFIED_OR_NOT_REQUIRED", independent_test, independent_review)


@dataclass(frozen=True, slots=True)
class InterveningChange:
    path: str
    dependency_tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReconciliationDecision:
    action: str
    exact_path_conflicts: tuple[str, ...]
    semantic_dependency_conflicts: tuple[str, ...]
    reason: str
    wholesale_rollback_authorized: bool


class InterveningChangeReconciler:
    """Classify concurrent-main drift before one late re-anchor/fix-forward."""

    def decide(
        self,
        *,
        candidate_paths: Sequence[str],
        candidate_dependency_tags: Sequence[str],
        intervening_changes: Sequence[InterveningChange],
    ) -> ReconciliationDecision:
        candidate = {str(path).strip() for path in candidate_paths if str(path).strip()}
        tags = {str(tag).strip() for tag in candidate_dependency_tags if str(tag).strip()}
        exact = sorted(candidate & {row.path.strip() for row in intervening_changes if row.path.strip()})
        semantic: set[str] = set()
        for row in intervening_changes:
            overlap = tags & {str(tag).strip() for tag in row.dependency_tags if str(tag).strip()}
            semantic.update(overlap)
        if exact:
            action = "CONFLICT_COURT_REQUIRED"
            reason = "INTERVENING_CHANGE_TOUCHES_CANDIDATE_PATH"
        elif semantic:
            action = "SEMANTIC_REVALIDATION_REQUIRED"
            reason = "DISJOINT_PATHS_SHARE_DEPENDENCY_DOMAIN"
        else:
            action = "LATE_REANCHOR_SAFE"
            reason = "NO_EXACT_OR_DECLARED_SEMANTIC_OVERLAP"
        return ReconciliationDecision(action, tuple(exact), tuple(sorted(semantic)), reason, False)


@dataclass(frozen=True, slots=True)
class FrontierEvolutionV4Receipt:
    schema: str
    capabilities: tuple[str, ...]
    skill_promotion_authorized: bool
    source_merge_authorized: bool
    effect_authorized: bool


def frontier_evolution_v4_receipt() -> FrontierEvolutionV4Receipt:
    return FrontierEvolutionV4Receipt(
        "CHATGOV-FRONTIER-EVOLUTION-V4",
        (
            "PROVEN_TRAJECTORY_TO_SKILL_CANDIDATE_CRYSTALLIZATION",
            "PROOF_GATED_PARETO_POLICY_OPTIMIZATION",
            "INDEPENDENT_HIGH_RISK_AUTHOR_TEST_REVIEW_HARNESS",
            "INTERVENING_CHANGE_LATE_REANCHOR_RECONCILIATION",
        ),
        False,
        False,
        False,
    )


__all__ = [
    "FrontierEvolutionV4Receipt",
    "HarnessDecision",
    "IndependentHarnessGate",
    "InterveningChange",
    "InterveningChangeReconciler",
    "ParetoPolicyOptimizer",
    "ParetoPolicyResult",
    "PolicyOutcome",
    "ReconciliationDecision",
    "SkillCandidate",
    "TrajectoryCrystallizer",
    "TrajectoryObservation",
    "frontier_evolution_v4_receipt",
]
