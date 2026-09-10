"""Bounded behavior-configuration and experiment runtime for Federation Omega.

This module stores immutable behavior bundles, selects a champion/challenger only
through evidence-gated promotion, assigns deterministic shadow/A-B cohorts, and
fails closed when autonomy error budgets or semantic-done proofs are incomplete.
It never changes model weights or grants provider authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
from typing import Mapping

SCHEMA = "FUSE-BEHAVIOR-RUNTIME-V1"
PROTECTED_INVARIANTS = frozenset({
    "OWNER_AUTHORITY", "PROOF_FLOOR", "SECURITY_FLOOR", "PRIVACY_FLOOR",
    "ROLLBACK_REQUIRED", "NO_SELF_PROMOTION",
})


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _is_nonblank(value: str) -> bool:
    return bool(value and value.strip())


@dataclass(frozen=True, slots=True)
class BehaviorBundle:
    bundle_id: str
    parent_id: str
    genes: Mapping[str, str]
    protected_invariants: frozenset[str] = PROTECTED_INVARIANTS
    rollback_ref: str = ""
    content_sha256: str = ""

    def body(self) -> dict:
        return {
            "schema": SCHEMA,
            "bundle_id": self.bundle_id,
            "parent_id": self.parent_id,
            "genes": dict(self.genes),
            "protected_invariants": sorted(self.protected_invariants),
            "rollback_ref": self.rollback_ref,
        }

    def seal(self) -> "BehaviorBundle":
        if not self.bundle_id or not self.genes:
            raise ValueError("BEHAVIOR_BUNDLE_REQUIRED_FIELDS_MISSING")
        if PROTECTED_INVARIANTS - self.protected_invariants:
            raise ValueError("PROTECTED_INVARIANT_REGRESSION")
        object.__setattr__(self, "content_sha256", digest(self.body()))
        return self

    def verify(self) -> bool:
        return bool(self.content_sha256) and self.content_sha256 == digest(self.body())


@dataclass(frozen=True, slots=True)
class ExperimentEvidence:
    bundle_id: str
    cohort_hash: str
    holdout_hash: str
    sample_count: int
    correctness: float
    proof_completeness: float
    owner_burden: float
    recovery: float
    utility_score: float
    regression_green: bool
    shadow_complete: bool
    canary_complete: bool
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> "ExperimentEvidence":
        if self.sample_count <= 0 or not self.cohort_hash or not self.holdout_hash:
            raise ValueError("EXPERIMENT_EVIDENCE_INCOMPLETE")
        for value in (
            self.correctness,
            self.proof_completeness,
            self.owner_burden,
            self.recovery,
            self.utility_score,
        ):
            if not math.isfinite(value):
                raise ValueError("EXPERIMENT_METRIC_NOT_FINITE")
        for value in (self.correctness, self.proof_completeness, self.owner_burden, self.recovery):
            if not 0.0 <= value <= 1.0:
                raise ValueError("EXPERIMENT_METRIC_OUT_OF_RANGE")
        if self.evidence_refs and any(not _is_nonblank(ref) for ref in self.evidence_refs):
            raise ValueError("EXPERIMENT_EVIDENCE_REF_BLANK")
        return self


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    state: str
    selected_bundle_id: str
    reason: str


class BehaviorRegistry:
    """In-memory control object; persistence belongs to the caller's durable store."""

    def __init__(self, champion: BehaviorBundle):
        if not champion.verify():
            raise ValueError("CHAMPION_MUST_BE_SEALED")
        self._champion = champion
        self._bundles: dict[str, BehaviorBundle] = {champion.bundle_id: champion}

    @property
    def champion(self) -> BehaviorBundle:
        return self._champion

    def register(self, bundle: BehaviorBundle) -> None:
        if not bundle.verify():
            raise ValueError("BUNDLE_INTEGRITY_FAILED")
        if bundle.parent_id and bundle.parent_id not in self._bundles:
            raise ValueError("UNKNOWN_PARENT_BUNDLE")
        if bundle.bundle_id in self._bundles and self._bundles[bundle.bundle_id].content_sha256 != bundle.content_sha256:
            raise ValueError("BUNDLE_ID_COLLISION")
        self._bundles[bundle.bundle_id] = bundle

    def promote(self, candidate_id: str, incumbent: ExperimentEvidence, candidate: ExperimentEvidence, *, minimum_utility_delta: float = 0.03) -> PromotionDecision:
        if candidate_id not in self._bundles:
            raise ValueError("UNKNOWN_CANDIDATE")
        if not math.isfinite(minimum_utility_delta) or minimum_utility_delta < 0.0:
            raise ValueError("MINIMUM_UTILITY_DELTA_INVALID")
        candidate.validate(); incumbent.validate()
        if candidate.bundle_id != candidate_id or incumbent.bundle_id != self._champion.bundle_id:
            return PromotionDecision("RETAIN", self._champion.bundle_id, "EVIDENCE_IDENTITY_MISMATCH")
        if (
            candidate.cohort_hash != incumbent.cohort_hash
            or candidate.holdout_hash != incumbent.holdout_hash
            or candidate.sample_count != incumbent.sample_count
        ):
            return PromotionDecision("RETAIN", self._champion.bundle_id, "UNMATCHED_COHORT_HOLDOUT_OR_SAMPLE_COUNT")
        if (
            not candidate.evidence_refs
            or any(not _is_nonblank(ref) for ref in candidate.evidence_refs)
            or not candidate.regression_green
            or not candidate.shadow_complete
            or not candidate.canary_complete
        ):
            return PromotionDecision("RETAIN", self._champion.bundle_id, "PROMOTION_PROOF_GATE_NOT_CLEARED")
        if candidate.correctness < incumbent.correctness or candidate.proof_completeness < incumbent.proof_completeness:
            return PromotionDecision("RETAIN", self._champion.bundle_id, "CORRECTNESS_OR_PROOF_REGRESSION")
        if candidate.owner_burden > incumbent.owner_burden or candidate.recovery < incumbent.recovery:
            return PromotionDecision("RETAIN", self._champion.bundle_id, "OWNER_BURDEN_OR_RECOVERY_REGRESSION")
        if candidate.utility_score < incumbent.utility_score + minimum_utility_delta:
            return PromotionDecision("RETAIN", self._champion.bundle_id, "INSUFFICIENT_MEASURED_GAIN")
        target = self._bundles[candidate_id]
        if not target.rollback_ref:
            return PromotionDecision("RETAIN", self._champion.bundle_id, "ROLLBACK_REQUIRED")
        self._champion = target
        return PromotionDecision("PROMOTE", target.bundle_id, "MATCHED_GREEN_SHADOW_CANARY_GAIN_WITH_ROLLBACK")


class ExperimentRouter:
    @staticmethod
    def assign(stable_subject_id: str, experiment_id: str, challenger_share: int = 10_000) -> str:
        if not 0 <= challenger_share <= 10_000:
            raise ValueError("CHALLENGER_SHARE_OUT_OF_RANGE")
        bucket = int(sha256(f"{experiment_id}|{stable_subject_id}".encode()).hexdigest()[:8], 16) % 10_000
        return "CHALLENGER" if bucket < challenger_share else "CHAMPION"


@dataclass(frozen=True, slots=True)
class ErrorBudget:
    unauthorized_actions: int = 0
    critical_regressions: int = 0
    failed_recoveries: int = 0
    owner_interventions: int = 0
    max_failed_recoveries: int = 0
    max_owner_interventions: int = 0

    def allows_autonomy(self) -> bool:
        values = (
            self.unauthorized_actions,
            self.critical_regressions,
            self.failed_recoveries,
            self.owner_interventions,
            self.max_failed_recoveries,
            self.max_owner_interventions,
        )
        if any(value < 0 for value in values):
            return False
        return (
            self.unauthorized_actions == 0
            and self.critical_regressions == 0
            and self.failed_recoveries <= self.max_failed_recoveries
            and self.owner_interventions <= self.max_owner_interventions
        )


@dataclass(frozen=True, slots=True)
class SemanticDoneContract:
    required_predicates: tuple[str, ...]
    proof_refs: Mapping[str, str] = field(default_factory=dict)

    def evaluate(self, observed: Mapping[str, bool]) -> tuple[bool, tuple[str, ...]]:
        missing = tuple(
            predicate for predicate in self.required_predicates
            if not observed.get(predicate, False) or not _is_nonblank(self.proof_refs.get(predicate, ""))
        )
        return (not missing, missing)
