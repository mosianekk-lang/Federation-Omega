from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Any, Mapping, Sequence

from sol_61_runtime.sol_62_frontier_primitives import ChampionChallenger, LearningPromotionGate


class EvolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class OutcomeSample:
    candidate_id: str
    success_rate: float
    proof_quality: float
    latency_ms: float
    cost: float
    owner_interventions: float
    critical_regressions: int = 0
    independent_source: str = ""
    contradiction: bool = False

    def validate(self) -> None:
        if not self.candidate_id.strip():
            raise EvolutionError("CANDIDATE_ID_REQUIRED")
        if not 0.0 <= self.success_rate <= 1.0 or not 0.0 <= self.proof_quality <= 1.0:
            raise EvolutionError("INVALID_SUCCESS_OR_PROOF_QUALITY")
        if self.latency_ms < 0 or self.cost < 0 or self.owner_interventions < 0:
            raise EvolutionError("NEGATIVE_OUTCOME_ECONOMICS")
        if self.critical_regressions < 0:
            raise EvolutionError("NEGATIVE_REGRESSION_COUNT")


@dataclass(frozen=True)
class PromotionDecision:
    champion_id: str
    challenger_id: str
    champion_score: float
    challenger_score: float
    relative_gain: float
    promote: bool
    gates: Mapping[str, bool]
    challenger_samples: int


class ShadowEvolutionLab:
    """Empirical champion/challenger evaluation with no challenger effect authority.

    The lab only evaluates recorded outcomes. It cannot invoke a provider or
    promote a challenger by itself; callers must pass the resulting decision
    through the normal SOL/SLOS promotion and authority path.
    """

    def __init__(self) -> None:
        self._samples: dict[str, list[OutcomeSample]] = {}

    def record(self, sample: OutcomeSample) -> None:
        sample.validate()
        self._samples.setdefault(sample.candidate_id, []).append(sample)

    def sample_count(self, candidate_id: str) -> int:
        return len(self._samples.get(candidate_id, ()))

    def aggregate(self, candidate_id: str) -> dict[str, float]:
        samples = self._samples.get(candidate_id, ())
        if not samples:
            raise EvolutionError(f"NO_SAMPLES:{candidate_id}")
        return {
            "success_rate": fmean(item.success_rate for item in samples),
            "proof_quality": fmean(item.proof_quality for item in samples),
            "latency_ms": fmean(item.latency_ms for item in samples),
            "cost": fmean(item.cost for item in samples),
            "owner_interventions": fmean(item.owner_interventions for item in samples),
        }

    def evaluate(
        self,
        *,
        champion_id: str,
        challenger_id: str,
        min_samples: int = 30,
        min_relative_gain: float = 0.05,
    ) -> PromotionDecision:
        champion = self.aggregate(champion_id)
        challenger = self.aggregate(challenger_id)
        challenger_samples = self._samples[challenger_id]
        regression_count = sum(item.critical_regressions for item in challenger_samples)
        contradiction_count = sum(1 for item in challenger_samples if item.contradiction)
        independent_sources = len(
            {item.independent_source for item in challenger_samples if item.independent_source}
        )
        comparison = ChampionChallenger.evaluate(
            champion,
            challenger,
            min_relative_gain=min_relative_gain,
            min_samples=min_samples,
            challenger_samples=len(challenger_samples),
            critical_regressions=regression_count,
        )
        learning = LearningPromotionGate().evaluate(
            distinct_events=len(challenger_samples),
            independent_sources=independent_sources,
            contradiction_count=contradiction_count,
            regression_count=regression_count,
            measured_gain=float(comparison["relative_gain"]),
            min_distinct_events=min_samples,
            min_independent_sources=2,
            min_gain=min_relative_gain,
        )
        gates = {
            "champion_challenger": bool(comparison["promote"]),
            "learning_gate": bool(learning["promote"]),
            "shadow_only": True,
            "no_critical_regression": regression_count == 0,
        }
        return PromotionDecision(
            champion_id=champion_id,
            challenger_id=challenger_id,
            champion_score=float(comparison["champion_score"]),
            challenger_score=float(comparison["challenger_score"]),
            relative_gain=float(comparison["relative_gain"]),
            promote=all(gates.values()),
            gates=gates,
            challenger_samples=len(challenger_samples),
        )


@dataclass(frozen=True)
class OpportunityCandidate:
    opportunity_id: str
    category: str
    evidence_count: int
    expected_leverage: float
    recommendation: str
    automatic_execution_allowed: bool


class OpportunityScanner:
    """Extracts high-leverage optimisation candidates from mission telemetry."""

    def scan(self, events: Sequence[Mapping[str, Any]]) -> tuple[OpportunityCandidate, ...]:
        if not events:
            return ()
        high_latency = [item for item in events if float(item.get("latency_ms", 0.0)) >= 5000.0]
        owner_burden = [item for item in events if float(item.get("owner_interventions", 0.0)) > 0.0]
        failures = [item for item in events if str(item.get("status", "")).upper() in {"FAILED", "ERROR", "TIMEOUT"}]
        repeated_signatures: dict[str, int] = {}
        for item in events:
            signature = str(item.get("operation_signature", "")).strip()
            if signature:
                repeated_signatures[signature] = repeated_signatures.get(signature, 0) + 1
        repeats = {key: count for key, count in repeated_signatures.items() if count >= 3}

        candidates: list[OpportunityCandidate] = []
        total = len(events)
        if high_latency:
            candidates.append(
                OpportunityCandidate(
                    opportunity_id="OPP-LATENCY-HEDGE",
                    category="LATENCY",
                    evidence_count=len(high_latency),
                    expected_leverage=len(high_latency) / total,
                    recommendation="Enable bounded straggler hedging or faster verified route challenger for read-only operations.",
                    automatic_execution_allowed=False,
                )
            )
        if owner_burden:
            candidates.append(
                OpportunityCandidate(
                    opportunity_id="OPP-OWNER-BURDEN",
                    category="AUTOMATION",
                    evidence_count=len(owner_burden),
                    expected_leverage=min(1.0, sum(float(item.get("owner_interventions", 0.0)) for item in owner_burden) / total),
                    recommendation="Compile repeated owner interventions into bounded reversible capability contracts.",
                    automatic_execution_allowed=False,
                )
            )
        if failures:
            candidates.append(
                OpportunityCandidate(
                    opportunity_id="OPP-FAILURE-ROUTE",
                    category="RELIABILITY",
                    evidence_count=len(failures),
                    expected_leverage=len(failures) / total,
                    recommendation="Create a shadow challenger route and convert recurring failure signatures into regression fixtures.",
                    automatic_execution_allowed=False,
                )
            )
        if repeats:
            candidates.append(
                OpportunityCandidate(
                    opportunity_id="OPP-MEMOIZE-REPEAT",
                    category="COMPUTE_EFFICIENCY",
                    evidence_count=sum(repeats.values()),
                    expected_leverage=min(1.0, sum(repeats.values()) / total),
                    recommendation="Introduce content-addressed memoization/proof reuse for repeated deterministic operation signatures.",
                    automatic_execution_allowed=True,
                )
            )
        return tuple(
            sorted(
                candidates,
                key=lambda item: (-item.expected_leverage, -item.evidence_count, item.opportunity_id),
            )
        )


__all__ = [
    "EvolutionError",
    "OpportunityCandidate",
    "OpportunityScanner",
    "OutcomeSample",
    "PromotionDecision",
    "ShadowEvolutionLab",
]
