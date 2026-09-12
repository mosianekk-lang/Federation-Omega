"""Provider-neutral incumbent challenge and reflexive architecture governor.

The governor separates *admissibility* from *optimality*. A currently proven route
is not permanently preferred, and a newer route is not superior merely because it
is new. Challengers may be assessed and shadowed without changing the serving
incumbent. Migration remains proof-, value-, authority-, cost- and rollback-bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


class ReflexivityError(ValueError):
    """Raised when a challenge contract is malformed."""


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    mission_value: float
    quality: float
    reliability: float
    latency_performance: float
    cost_efficiency: float
    proof_strength: float
    reversibility: float
    failure_domain_diversity: float
    owner_burden_reduction: float
    compatibility: float
    maintainability: float
    capability_unlock: float
    information_gain: float
    eligible: bool = True
    proof_current: bool = True
    authority_current: bool = True
    cost_known_included: bool = True
    independent_readback: bool = False
    positive_measured_value: bool = False
    rollback_ready: bool = False
    external_effect: bool = False
    consequential: bool = False
    iam_or_secret_change: bool = False
    destructive_change: bool = False
    novelty_only: bool = False

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ReflexivityError("candidate_id must be non-empty")
        for name in _SCORE_FIELDS:
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ReflexivityError(f"{name} must be numeric")
            if value < 0.0 or value > 1.0:
                raise ReflexivityError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class ChallengeContext:
    role_id: str
    trigger: str
    challenge_due: bool = False
    material_event: bool = False
    migration_margin: float = 0.08
    hysteresis_margin: float = 0.05

    def __post_init__(self) -> None:
        if not self.role_id.strip():
            raise ReflexivityError("role_id must be non-empty")
        if not self.trigger.strip():
            raise ReflexivityError("trigger must be non-empty")
        if not 0.0 <= self.migration_margin <= 1.0:
            raise ReflexivityError("migration_margin must be between 0 and 1")
        if not 0.0 <= self.hysteresis_margin <= 1.0:
            raise ReflexivityError("hysteresis_margin must be between 0 and 1")


@dataclass(frozen=True)
class ChallengeDecision:
    role_id: str
    incumbent_id: str
    clean_slate_winner: str
    challenger_id: str | None
    incumbent_fitness: float
    challenger_fitness: float | None
    fitness_delta: float | None
    verdict: str
    serving_route: str
    migration_authorized: bool
    shadow_admissible: bool
    reasons: tuple[str, ...]


_SCORE_FIELDS = (
    "mission_value",
    "quality",
    "reliability",
    "latency_performance",
    "cost_efficiency",
    "proof_strength",
    "reversibility",
    "failure_domain_diversity",
    "owner_burden_reduction",
    "compatibility",
    "maintainability",
    "capability_unlock",
    "information_gain",
)

# The weights intentionally remain multi-dimensional. No activity count, company
# prestige, novelty flag or repository size participates in fitness.
_WEIGHTS = {
    "mission_value": 0.15,
    "quality": 0.10,
    "reliability": 0.10,
    "latency_performance": 0.06,
    "cost_efficiency": 0.07,
    "proof_strength": 0.12,
    "reversibility": 0.07,
    "failure_domain_diversity": 0.07,
    "owner_burden_reduction": 0.07,
    "compatibility": 0.07,
    "maintainability": 0.04,
    "capability_unlock": 0.04,
    "information_gain": 0.04,
}


def fitness(candidate: Candidate) -> float:
    """Return deterministic multi-dimensional candidate fitness in [0, 1]."""
    return round(sum(getattr(candidate, k) * w for k, w in _WEIGHTS.items()), 6)


def admissible_for_comparison(candidate: Candidate) -> bool:
    """Whether a candidate may participate in the current clean-slate ranking."""
    return bool(
        candidate.eligible
        and candidate.proof_current
        and candidate.authority_current
        and candidate.cost_known_included
        and not candidate.destructive_change
    )


def admissible_for_shadow(candidate: Candidate) -> bool:
    """Whether a challenger may run as a no-effect/internal bounded shadow."""
    return bool(
        admissible_for_comparison(candidate)
        and not candidate.external_effect
        and not candidate.consequential
        and not candidate.iam_or_secret_change
    )


def migration_gate(candidate: Candidate) -> tuple[bool, tuple[str, ...]]:
    """Hard migration gate. It never grants provider/consequential authority."""
    reasons: list[str] = []
    if not admissible_for_comparison(candidate):
        reasons.append("CHALLENGER_NOT_CURRENTLY_ADMISSIBLE")
    if candidate.external_effect or candidate.consequential:
        reasons.append("CONSEQUENTIAL_OR_EXTERNAL_EFFECT_SEPARATELY_GATED")
    if candidate.iam_or_secret_change:
        reasons.append("IAM_OR_SECRET_CHANGE_SEPARATELY_GATED")
    if candidate.destructive_change:
        reasons.append("DESTRUCTIVE_CHANGE_PROHIBITED_AUTONOMOUSLY")
    if not candidate.independent_readback:
        reasons.append("INDEPENDENT_READBACK_REQUIRED")
    if not candidate.positive_measured_value:
        reasons.append("POSITIVE_MEASURED_VALUE_REQUIRED")
    if not candidate.rollback_ready:
        reasons.append("ROLLBACK_REQUIRED")
    if candidate.novelty_only:
        reasons.append("NOVELTY_ALONE_CANNOT_JUSTIFY_MIGRATION")
    return (not reasons, tuple(reasons))


def should_challenge(context: ChallengeContext) -> bool:
    """Periodic cadence or a material event is sufficient to invoke challenge."""
    return bool(context.challenge_due or context.material_event)


def _rank(candidates: Iterable[Candidate]) -> list[Candidate]:
    eligible = [c for c in candidates if admissible_for_comparison(c)]
    return sorted(eligible, key=lambda c: (-fitness(c), c.candidate_id))


def challenge_incumbent(
    *,
    context: ChallengeContext,
    incumbent: Candidate,
    challengers: Sequence[Candidate],
) -> ChallengeDecision:
    """Challenge a role incumbent without silently changing the serving route.

    The clean-slate winner is calculated from all currently admissible candidates.
    A challenger can win that comparison while migration remains held behind proof.
    """
    if not should_challenge(context):
        return ChallengeDecision(
            role_id=context.role_id,
            incumbent_id=incumbent.candidate_id,
            clean_slate_winner=incumbent.candidate_id,
            challenger_id=None,
            incumbent_fitness=fitness(incumbent),
            challenger_fitness=None,
            fitness_delta=None,
            verdict="NO_CHALLENGE_DUE",
            serving_route=incumbent.candidate_id,
            migration_authorized=False,
            shadow_admissible=False,
            reasons=("NO_PERIODIC_OR_MATERIAL_TRIGGER",),
        )

    all_candidates = (incumbent, *challengers)
    ranked = _rank(all_candidates)
    incumbent_score = fitness(incumbent)
    if not ranked:
        return ChallengeDecision(
            role_id=context.role_id,
            incumbent_id=incumbent.candidate_id,
            clean_slate_winner=incumbent.candidate_id,
            challenger_id=None,
            incumbent_fitness=incumbent_score,
            challenger_fitness=None,
            fitness_delta=None,
            verdict="HOLD_NO_ADMISSIBLE_ROUTE",
            serving_route=incumbent.candidate_id,
            migration_authorized=False,
            shadow_admissible=False,
            reasons=("NO_CURRENT_ADMISSIBLE_CANDIDATE",),
        )

    winner = ranked[0]
    if winner.candidate_id == incumbent.candidate_id:
        return ChallengeDecision(
            role_id=context.role_id,
            incumbent_id=incumbent.candidate_id,
            clean_slate_winner=winner.candidate_id,
            challenger_id=None,
            incumbent_fitness=incumbent_score,
            challenger_fitness=None,
            fitness_delta=0.0,
            verdict="RETAIN_INCUMBENT_CONTINUES_TO_WIN",
            serving_route=incumbent.candidate_id,
            migration_authorized=False,
            shadow_admissible=False,
            reasons=("INCUMBENT_WINS_CURRENT_CLEAN_SLATE_COMPARISON",),
        )

    challenger_score = fitness(winner)
    delta = round(challenger_score - incumbent_score, 6)
    shadow_ok = admissible_for_shadow(winner)
    migration_ok, migration_reasons = migration_gate(winner)

    # Hysteresis protects a stable incumbent from near-tie churn.
    if delta < context.hysteresis_margin:
        verdict = "HOLD_ANTI_CHURN_HYSTERESIS"
        reasons = ("SUPERIORITY_MARGIN_NOT_DURABLE",)
        migration_ok = False
    elif delta < context.migration_margin:
        verdict = "TRIAL_CHALLENGER_SHADOW" if shadow_ok else "ASSESS_CHALLENGER"
        reasons = ("CLEAN_SLATE_CHALLENGER_WINS_BUT_MIGRATION_MARGIN_NOT_MET",)
        migration_ok = False
    elif migration_ok:
        verdict = "MIGRATION_CANDIDATE_PROVEN"
        reasons = ("NET_FITNESS_GAIN_AND_MIGRATION_GATES_PASS",)
    else:
        verdict = "MIGRATION_CANDIDATE_PROOF_GATED"
        reasons = migration_reasons or ("MIGRATION_PROOF_INCOMPLETE",)

    return ChallengeDecision(
        role_id=context.role_id,
        incumbent_id=incumbent.candidate_id,
        clean_slate_winner=winner.candidate_id,
        challenger_id=winner.candidate_id,
        incumbent_fitness=incumbent_score,
        challenger_fitness=challenger_score,
        fitness_delta=delta,
        verdict=verdict,
        serving_route=winner.candidate_id if migration_ok else incumbent.candidate_id,
        migration_authorized=migration_ok,
        shadow_admissible=shadow_ok,
        reasons=tuple(reasons),
    )


def self_challenge_required(*, governor_changed: bool, architecture_changed: bool) -> bool:
    """Reflexivity applies to the governor itself."""
    return bool(governor_changed or architecture_changed)
