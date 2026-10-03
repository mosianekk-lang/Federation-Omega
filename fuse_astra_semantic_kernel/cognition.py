from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class CognitionTier(IntEnum):
    C0_DETERMINISTIC = 0
    C1_SMALL_LOCAL = 1
    C2_LARGE_LOCAL = 2
    C3_PROVIDER_VALUE = 3
    C4_FRONTIER = 4
    C5_ENSEMBLE_JUDGE = 5


@dataclass(frozen=True)
class TaskSignals:
    uncertainty: float = 0.0
    novelty: float = 0.0
    failure_cost: float = 0.0
    irreversibility: float = 0.0
    contradiction_density: float = 0.0
    tool_complexity: float = 0.0
    latency_pressure: float = 0.0
    privacy_requirement: float = 0.0
    deterministic_fit: float = 0.0

    def normalized(self) -> "TaskSignals":
        values = {
            name: max(0.0, min(1.0, getattr(self, name)))
            for name in self.__dataclass_fields__
        }
        return TaskSignals(**values)


@dataclass(frozen=True)
class CognitionPlan:
    tier: CognitionTier
    reasoning_depth: str
    candidate_branches: int
    specialist_agents: int
    verifier_count: int
    adversarial_falsifier: bool
    external_judge_required: bool
    require_local_first: bool
    explanation: str


class AdaptiveCognitionGovernor:
    """Allocate cognition from task risk/uncertainty rather than static model preference.

    The governor produces a compute plan only. It does not authorize effects and
    cannot weaken policy/proof gates. High privacy can bias to local execution;
    high failure cost/irreversibility can still force stronger verification.
    """

    def plan(self, raw: TaskSignals) -> CognitionPlan:
        s = raw.normalized()

        # Deterministic work should remain deterministic unless risk/uncertainty
        # makes model interpretation necessary.
        complexity = (
            0.22 * s.uncertainty
            + 0.18 * s.novelty
            + 0.20 * s.contradiction_density
            + 0.15 * s.tool_complexity
            + 0.15 * s.failure_cost
            + 0.10 * s.irreversibility
        )
        verification_pressure = max(
            s.failure_cost,
            s.irreversibility,
            s.contradiction_density,
        )
        privacy_local_bias = s.privacy_requirement >= 0.75

        if s.deterministic_fit >= 0.9 and complexity < 0.25:
            return CognitionPlan(
                CognitionTier.C0_DETERMINISTIC,
                "none",
                1,
                0,
                1 if verification_pressure >= 0.5 else 0,
                False,
                verification_pressure >= 0.8,
                True,
                "Stable deterministic semantics dominate; models are unnecessary for the primary path.",
            )

        # Latency pressure can lower deliberation only when verification pressure
        # is low. It never suppresses high-risk verification.
        effective = complexity - (0.12 * s.latency_pressure if verification_pressure < 0.5 else 0.0)

        if effective < 0.25:
            tier = CognitionTier.C1_SMALL_LOCAL
            depth = "low"
            branches, agents, verifiers = 1, 1, 0
        elif effective < 0.45:
            tier = CognitionTier.C2_LARGE_LOCAL
            depth = "medium"
            branches, agents, verifiers = 1, 1, 1
        elif effective < 0.65:
            tier = CognitionTier.C3_PROVIDER_VALUE
            depth = "high"
            branches, agents, verifiers = 2, 2, 1
        elif effective < 0.82:
            tier = CognitionTier.C4_FRONTIER
            depth = "xhigh"
            branches, agents, verifiers = 3, 3, 2
        else:
            tier = CognitionTier.C5_ENSEMBLE_JUDGE
            depth = "max"
            branches, agents, verifiers = 4, 4, 3

        if verification_pressure >= 0.8:
            verifiers = max(verifiers, 2)
            branches = max(branches, 2)

        adversarial = verification_pressure >= 0.65 or s.contradiction_density >= 0.6
        external_judge = verification_pressure >= 0.85

        return CognitionPlan(
            tier=tier,
            reasoning_depth=depth,
            candidate_branches=branches,
            specialist_agents=agents,
            verifier_count=verifiers,
            adversarial_falsifier=adversarial,
            external_judge_required=external_judge,
            require_local_first=privacy_local_bias,
            explanation=(
                f"complexity={complexity:.3f}; verification_pressure={verification_pressure:.3f}; "
                f"latency_pressure={s.latency_pressure:.3f}; privacy_local_bias={privacy_local_bias}"
            ),
        )
