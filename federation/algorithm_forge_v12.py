"""FUSE Omega Algorithm Forge v12: bounded algorithm-genome and evaluator contracts.

This module is a source-level composition layer for the existing Autonomic Completion,
Prompt Scientist and Federation Learning roots. It defines immutable problem
fingerprints, algorithm bundles, composite policies, privacy-minimised run metrics and
frozen matched-evaluation courts. It never grants provider authority, mutates model
weights, or self-promotes a candidate.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
from typing import Iterable, Mapping, Sequence

SCHEMA = "FUSE-ALGORITHM-FORGE-V12"
PROTECTED_INVARIANTS = frozenset({
    "OWNER_AUTHORITY",
    "SECURITY_FLOOR",
    "PRIVACY_FLOOR",
    "PROOF_FLOOR",
    "TRUTH_BOUNDARIES",
    "ROLLBACK_REQUIREMENTS",
    "NO_SECRET_EXPOSURE",
    "NO_FALSE_MATURITY",
})
PROMOTION_LADDER = (
    "CANDIDATE",
    "OFFLINE_EVAL",
    "HOLDOUT",
    "SHADOW",
    "CANARY",
    "PRODUCTION_OBSERVATION",
    "BEHAVIOR_PROVEN",
)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _nonblank(value: str) -> bool:
    return bool(value and value.strip())


def _pairs(value: Mapping[str, object] | Iterable[tuple[str, object]]) -> tuple[tuple[str, str], ...]:
    items = value.items() if isinstance(value, Mapping) else value
    out = tuple(sorted((str(k), str(v)) for k, v in items))
    if any(not _nonblank(k) or not _nonblank(v) for k, v in out):
        raise ValueError("BLANK_GENE_OR_PARAMETER")
    if len({k for k, _ in out}) != len(out):
        raise ValueError("DUPLICATE_KEY")
    return out


@dataclass(frozen=True, slots=True)
class ProblemFingerprint:
    mission_class: str
    terminal_predicate: str
    source_epoch: str
    provider_epoch: str = ""
    authority_class: str = "A1_INTERNAL"
    privacy_class: str = "P0"
    failure_fingerprints: tuple[str, ...] = ()
    fingerprint_id: str = ""

    def body(self) -> dict:
        return {
            "schema": SCHEMA,
            "mission_class": self.mission_class,
            "terminal_predicate": self.terminal_predicate,
            "source_epoch": self.source_epoch,
            "provider_epoch": self.provider_epoch,
            "authority_class": self.authority_class,
            "privacy_class": self.privacy_class,
            "failure_fingerprints": sorted(set(self.failure_fingerprints)),
        }

    def seal(self) -> "ProblemFingerprint":
        required = (self.mission_class, self.terminal_predicate, self.source_epoch, self.authority_class, self.privacy_class)
        if any(not _nonblank(v) for v in required):
            raise ValueError("PROBLEM_FINGERPRINT_REQUIRED_FIELDS_MISSING")
        if any(not _nonblank(v) for v in self.failure_fingerprints):
            raise ValueError("FAILURE_FINGERPRINT_BLANK")
        return replace(self, failure_fingerprints=tuple(sorted(set(self.failure_fingerprints))),
                       fingerprint_id=f"FP-{_digest(self.body())[:24]}")

    def verify(self) -> bool:
        return self == self.seal()


@dataclass(frozen=True, slots=True)
class AlgorithmBundle:
    bundle_id: str
    parent_bundle_id: str
    genes: tuple[tuple[str, str], ...]
    parameters: tuple[tuple[str, str], ...] = ()
    excluded_genes: tuple[str, ...] = ()
    compatible_receivers: tuple[str, ...] = ()
    rollback_ref: str = ""
    protected_invariants: frozenset[str] = PROTECTED_INVARIANTS
    content_sha256: str = ""

    @classmethod
    def build(
        cls,
        bundle_id: str,
        parent_bundle_id: str,
        genes: Mapping[str, object] | Iterable[tuple[str, object]],
        *,
        parameters: Mapping[str, object] | Iterable[tuple[str, object]] = (),
        excluded_genes: Sequence[str] = (),
        compatible_receivers: Sequence[str] = (),
        rollback_ref: str = "",
        protected_invariants: frozenset[str] = PROTECTED_INVARIANTS,
    ) -> "AlgorithmBundle":
        return cls(
            bundle_id=bundle_id,
            parent_bundle_id=parent_bundle_id,
            genes=_pairs(genes),
            parameters=_pairs(parameters),
            excluded_genes=tuple(sorted(set(excluded_genes))),
            compatible_receivers=tuple(sorted(set(compatible_receivers))),
            rollback_ref=rollback_ref,
            protected_invariants=protected_invariants,
        ).seal()

    def body(self) -> dict:
        return {
            "schema": SCHEMA,
            "bundle_id": self.bundle_id,
            "parent_bundle_id": self.parent_bundle_id,
            "genes": list(self.genes),
            "parameters": list(self.parameters),
            "excluded_genes": list(self.excluded_genes),
            "compatible_receivers": list(self.compatible_receivers),
            "rollback_ref": self.rollback_ref,
            "protected_invariants": sorted(self.protected_invariants),
        }

    def seal(self) -> "AlgorithmBundle":
        if not _nonblank(self.bundle_id) or not self.genes:
            raise ValueError("ALGORITHM_BUNDLE_REQUIRED_FIELDS_MISSING")
        if PROTECTED_INVARIANTS - self.protected_invariants:
            raise ValueError("PROTECTED_INVARIANT_REGRESSION")
        if any(not _nonblank(v) for v in (*self.excluded_genes, *self.compatible_receivers)):
            raise ValueError("ALGORITHM_BUNDLE_BLANK_LIST_ITEM")
        return replace(self, content_sha256=_digest(self.body()))

    def verify(self) -> bool:
        return bool(self.content_sha256) and self.content_sha256 == _digest(self.body())


@dataclass(frozen=True, slots=True)
class CompositePolicy:
    policy_id: str
    problem_fingerprint_id: str
    ordered_bundle_ids: tuple[str, ...]
    hard_floors: tuple[str, ...] = tuple(sorted(PROTECTED_INVARIANTS))
    policy_sha256: str = ""

    def seal(self) -> "CompositePolicy":
        if not _nonblank(self.policy_id) or not _nonblank(self.problem_fingerprint_id) or not self.ordered_bundle_ids:
            raise ValueError("COMPOSITE_POLICY_REQUIRED_FIELDS_MISSING")
        if len(set(self.ordered_bundle_ids)) != len(self.ordered_bundle_ids):
            raise ValueError("DUPLICATE_BUNDLE_ID")
        if PROTECTED_INVARIANTS - frozenset(self.hard_floors):
            raise ValueError("COMPOSITE_POLICY_HARD_FLOOR_REGRESSION")
        body = {
            "schema": SCHEMA,
            "policy_id": self.policy_id,
            "problem_fingerprint_id": self.problem_fingerprint_id,
            "ordered_bundle_ids": list(self.ordered_bundle_ids),
            "hard_floors": sorted(self.hard_floors),
        }
        return replace(self, hard_floors=tuple(sorted(set(self.hard_floors))), policy_sha256=_digest(body))

    def verify(self) -> bool:
        if not self.policy_sha256:
            return False
        return self == self.seal()


@dataclass(frozen=True, slots=True)
class AlgorithmRunMetricsV1:
    problem_fingerprint_id: str
    algorithm_bundle_id: str
    terminal_predicates_closed: int
    owner_hours: float
    wall_clock_seconds: float
    correctness: float = 1.0
    proof_completeness: float = 1.0
    recovery_success: float = 1.0
    security_floor_green: bool = True
    privacy_floor_green: bool = True
    authority_floor_green: bool = True
    truth_floor_green: bool = True
    rollback_green: bool = True
    achieved_concurrency: int = 1
    work_steal_count: int = 0
    hedge_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    negative_cache_hits: int = 0
    backpressure_events: int = 0
    tool_provider_calls: int = 0
    duplicate_calls: int = 0
    retries: int = 0
    owner_interventions: int = 0
    context_tokens: int = 0
    provider_round_trips: int = 0
    provider_cost: float = 0.0
    evidence_refs: tuple[str, ...] = ()
    rollback_ref: str = ""
    stop_reason: str = ""

    def validate(self) -> "AlgorithmRunMetricsV1":
        if not _nonblank(self.problem_fingerprint_id) or not _nonblank(self.algorithm_bundle_id):
            raise ValueError("ALGORITHM_METRICS_IDENTITY_MISSING")
        nonnegative_ints = (
            self.terminal_predicates_closed, self.achieved_concurrency, self.work_steal_count,
            self.hedge_count, self.cache_hits, self.cache_misses, self.negative_cache_hits,
            self.backpressure_events, self.tool_provider_calls, self.duplicate_calls,
            self.retries, self.owner_interventions, self.context_tokens, self.provider_round_trips,
        )
        if any(v < 0 for v in nonnegative_ints):
            raise ValueError("ALGORITHM_METRICS_NEGATIVE_COUNTER")
        finite = (self.owner_hours, self.wall_clock_seconds, self.correctness,
                  self.proof_completeness, self.recovery_success, self.provider_cost)
        if any(not math.isfinite(v) for v in finite):
            raise ValueError("ALGORITHM_METRICS_NOT_FINITE")
        if self.owner_hours <= 0.0 or self.wall_clock_seconds < 0.0 or self.provider_cost < 0.0:
            raise ValueError("ALGORITHM_METRICS_INVALID_DENOMINATOR_OR_COST")
        if any(not 0.0 <= v <= 1.0 for v in (self.correctness, self.proof_completeness, self.recovery_success)):
            raise ValueError("ALGORITHM_METRICS_QUALITY_OUT_OF_RANGE")
        if self.evidence_refs and any(not _nonblank(ref) for ref in self.evidence_refs):
            raise ValueError("ALGORITHM_METRICS_EVIDENCE_REF_BLANK")
        return self

    @property
    def terminal_predicates_per_owner_hour(self) -> float:
        self.validate()
        return self.terminal_predicates_closed / self.owner_hours

    @property
    def hard_floors_green(self) -> bool:
        return all((
            self.security_floor_green,
            self.privacy_floor_green,
            self.authority_floor_green,
            self.truth_floor_green,
            self.rollback_green,
            self.correctness == 1.0,
            self.proof_completeness == 1.0,
        ))

    def body(self) -> dict:
        self.validate()
        return {
            "schema": f"{SCHEMA}-RUN-METRICS-V1",
            "problem_fingerprint_id": self.problem_fingerprint_id,
            "algorithm_bundle_id": self.algorithm_bundle_id,
            "terminal_predicates_closed": self.terminal_predicates_closed,
            "owner_hours": self.owner_hours,
            "terminal_predicates_per_owner_hour": self.terminal_predicates_per_owner_hour,
            "wall_clock_seconds": self.wall_clock_seconds,
            "correctness": self.correctness,
            "proof_completeness": self.proof_completeness,
            "recovery_success": self.recovery_success,
            "hard_floors_green": self.hard_floors_green,
            "achieved_concurrency": self.achieved_concurrency,
            "work_steal_count": self.work_steal_count,
            "hedge_count": self.hedge_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "negative_cache_hits": self.negative_cache_hits,
            "backpressure_events": self.backpressure_events,
            "tool_provider_calls": self.tool_provider_calls,
            "duplicate_calls": self.duplicate_calls,
            "retries": self.retries,
            "owner_interventions": self.owner_interventions,
            "context_tokens": self.context_tokens,
            "provider_round_trips": self.provider_round_trips,
            "provider_cost": self.provider_cost,
            "evidence_refs": list(self.evidence_refs),
            "rollback_ref": self.rollback_ref,
            "stop_reason": self.stop_reason,
        }


@dataclass(frozen=True, slots=True)
class FrozenEvalCorpus:
    visible_cases: tuple[str, ...]
    adversarial_cases: tuple[str, ...]
    untouched_holdout_cases: tuple[str, ...]
    corpus_sha256: str = ""

    def freeze(self) -> "FrozenEvalCorpus":
        if not self.visible_cases or not self.adversarial_cases or not self.untouched_holdout_cases:
            raise ValueError("THREE_WAY_EVAL_CORPUS_REQUIRED")
        all_cases = (*self.visible_cases, *self.adversarial_cases, *self.untouched_holdout_cases)
        if any(not _nonblank(case) for case in all_cases):
            raise ValueError("EVAL_CASE_BLANK")
        if len(set(all_cases)) != len(all_cases):
            raise ValueError("EVAL_CASE_LEAKAGE_OR_DUPLICATION")
        body = {
            "visible": list(self.visible_cases),
            "adversarial": list(self.adversarial_cases),
            "untouched_holdout": list(self.untouched_holdout_cases),
        }
        return replace(self, corpus_sha256=_digest(body))

    def verify(self) -> bool:
        return bool(self.corpus_sha256) and self == self.freeze()


@dataclass(frozen=True, slots=True)
class AlgorithmEvaluation:
    bundle_id: str
    corpus_sha256: str
    sample_count: int
    primary_rate: float
    wall_clock_seconds: float
    owner_interventions: int
    provider_cost: float
    correctness: float
    proof_completeness: float
    recovery_success: float
    hard_floors_green: bool
    evidence_refs: tuple[str, ...]
    stage: str = "OFFLINE_EVAL"

    def validate(self) -> "AlgorithmEvaluation":
        if self.stage not in PROMOTION_LADDER:
            raise ValueError("UNKNOWN_PROMOTION_STAGE")
        if self.sample_count <= 0 or not _nonblank(self.bundle_id) or not _nonblank(self.corpus_sha256):
            raise ValueError("ALGORITHM_EVALUATION_IDENTITY_OR_SAMPLE_MISSING")
        vals = (self.primary_rate, self.wall_clock_seconds, self.provider_cost,
                self.correctness, self.proof_completeness, self.recovery_success)
        if any(not math.isfinite(v) for v in vals):
            raise ValueError("ALGORITHM_EVALUATION_NOT_FINITE")
        if self.primary_rate < 0.0 or self.wall_clock_seconds < 0.0 or self.provider_cost < 0.0 or self.owner_interventions < 0:
            raise ValueError("ALGORITHM_EVALUATION_NEGATIVE_VALUE")
        if any(not 0.0 <= v <= 1.0 for v in (self.correctness, self.proof_completeness, self.recovery_success)):
            raise ValueError("ALGORITHM_EVALUATION_QUALITY_OUT_OF_RANGE")
        if not self.evidence_refs or any(not _nonblank(ref) for ref in self.evidence_refs):
            raise ValueError("ALGORITHM_EVALUATION_EVIDENCE_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class AlgorithmPromotionDecision:
    state: str
    selected_bundle_id: str
    reason: str
    primary_delta: float = 0.0


def pareto_frontier(evaluations: Iterable[AlgorithmEvaluation]) -> tuple[AlgorithmEvaluation, ...]:
    values = tuple(e.validate() for e in evaluations)
    if not values:
        return ()

    def dominates(a: AlgorithmEvaluation, b: AlgorithmEvaluation) -> bool:
        av = (a.primary_rate, a.correctness, a.proof_completeness, a.recovery_success,
              -a.wall_clock_seconds, -a.owner_interventions, -a.provider_cost)
        bv = (b.primary_rate, b.correctness, b.proof_completeness, b.recovery_success,
              -b.wall_clock_seconds, -b.owner_interventions, -b.provider_cost)
        return all(x >= y for x, y in zip(av, bv)) and any(x > y for x, y in zip(av, bv))

    return tuple(sorted(
        (candidate for candidate in values if not any(dominates(other, candidate) for other in values if other is not candidate)),
        key=lambda e: (-e.primary_rate, e.owner_interventions, e.wall_clock_seconds, e.provider_cost, e.bundle_id),
    ))


def select_shadow_candidate(
    incumbent: AlgorithmEvaluation,
    challengers: Iterable[AlgorithmEvaluation],
    *,
    minimum_primary_gain: float = 0.05,
) -> AlgorithmPromotionDecision:
    incumbent.validate()
    if not math.isfinite(minimum_primary_gain) or minimum_primary_gain < 0.0:
        raise ValueError("MINIMUM_PRIMARY_GAIN_INVALID")
    eligible = []
    for candidate in challengers:
        candidate.validate()
        if candidate.bundle_id == incumbent.bundle_id:
            continue
        if candidate.corpus_sha256 != incumbent.corpus_sha256 or candidate.sample_count != incumbent.sample_count:
            continue
        if not candidate.hard_floors_green:
            continue
        if candidate.correctness < incumbent.correctness or candidate.proof_completeness < incumbent.proof_completeness:
            continue
        if candidate.recovery_success < incumbent.recovery_success or candidate.owner_interventions > incumbent.owner_interventions:
            continue
        if candidate.primary_rate < incumbent.primary_rate + minimum_primary_gain:
            continue
        eligible.append(candidate)
    frontier = pareto_frontier(eligible)
    if not frontier:
        return AlgorithmPromotionDecision("RETAIN_INCUMBENT", incumbent.bundle_id, "NO_MATCHED_GREEN_PARETO_CHALLENGER")
    winner = frontier[0]
    return AlgorithmPromotionDecision(
        "CANDIDATE_FOR_SHADOW",
        winner.bundle_id,
        "MATCHED_GREEN_PARETO_GAIN_REQUIRES_SHADOW_CANARY_PRODUCTION_OBSERVATION",
        round(winner.primary_rate - incumbent.primary_rate, 6),
    )


def metrics_from_prompt_run(
    prompt_metrics: object,
    *,
    problem_fingerprint_id: str,
    algorithm_bundle_id: str,
    terminal_predicates_closed: int,
    owner_hours: float,
    wall_clock_seconds: float,
    evidence_refs: Sequence[str],
    rollback_ref: str,
    provider_cost: float = 0.0,
    provider_round_trips: int = 0,
) -> AlgorithmRunMetricsV1:
    """Adapt current PromptRunMetrics-like telemetry without changing its source contract."""
    return AlgorithmRunMetricsV1(
        problem_fingerprint_id=problem_fingerprint_id,
        algorithm_bundle_id=algorithm_bundle_id,
        terminal_predicates_closed=terminal_predicates_closed,
        owner_hours=owner_hours,
        wall_clock_seconds=wall_clock_seconds,
        correctness=float(getattr(prompt_metrics, "correctness", 1.0)),
        proof_completeness=float(getattr(prompt_metrics, "proof_completeness", 1.0)),
        recovery_success=float(getattr(prompt_metrics, "recovery_success", 1.0)),
        achieved_concurrency=int(getattr(prompt_metrics, "achieved_parallelism", 1)),
        duplicate_calls=int(getattr(prompt_metrics, "duplicate_tool_calls", 0)),
        retries=int(getattr(prompt_metrics, "retries", 0)),
        owner_interventions=int(getattr(prompt_metrics, "owner_interventions", 0)),
        provider_round_trips=provider_round_trips,
        provider_cost=provider_cost,
        evidence_refs=tuple(evidence_refs),
        rollback_ref=rollback_ref,
    ).validate()


def federation_learning_fields(
    problem: ProblemFingerprint,
    bundle: AlgorithmBundle,
    policy: CompositePolicy,
    metrics: AlgorithmRunMetricsV1,
) -> dict:
    """Privacy-minimised fields suitable for the existing Federation Learning event plane."""
    if not problem.verify() or not bundle.verify() or not policy.verify():
        raise ValueError("UNSEALED_ALGORITHM_FORGE_OBJECT")
    metrics.validate()
    if metrics.problem_fingerprint_id != problem.fingerprint_id or metrics.algorithm_bundle_id != bundle.bundle_id:
        raise ValueError("ALGORITHM_LEARNING_IDENTITY_MISMATCH")
    if policy.problem_fingerprint_id != problem.fingerprint_id or bundle.bundle_id not in policy.ordered_bundle_ids:
        raise ValueError("ALGORITHM_POLICY_IDENTITY_MISMATCH")
    return {
        "problem_fingerprint_id": problem.fingerprint_id,
        "algorithm_bundle_id": bundle.bundle_id,
        "algorithm_bundle_sha256": bundle.content_sha256,
        "composite_policy_id": policy.policy_id,
        "composite_policy_sha256": policy.policy_sha256,
        "terminal_predicates_per_owner_hour": metrics.terminal_predicates_per_owner_hour,
        "hard_floors_green": metrics.hard_floors_green,
        "evidence_refs": list(metrics.evidence_refs),
        "rollback_ref": metrics.rollback_ref,
        "private_chain_of_thought_stored": False,
    }
