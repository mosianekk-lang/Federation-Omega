"""Measured-telemetry, shadow-only adaptive intelligence for BCO-Prime."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


SCHEMA = "BCO_PRIME_ADAPTIVE_INTELLIGENCE_V1"
VERSION = "1.0.0"
MIN_PAIRED_CASES = 30
MIN_QUALITY_UPLIFT = 0.03


class AdaptiveContractError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TelemetryObservation:
    operation: str
    success: bool
    latency_ms: float
    failure_type: str = "NONE"
    evidence_id: str = ""

    def __post_init__(self) -> None:
        if not self.operation or not self.evidence_id:
            raise AdaptiveContractError("operation and evidence_id are required")
        if not isinstance(self.latency_ms, (int, float)) or self.latency_ms < 0:
            raise AdaptiveContractError("latency_ms must be non-negative")


@dataclass(frozen=True)
class PolicyCandidate:
    candidate_id: str
    operation: str
    policy: str
    evidence_ids: tuple[str, ...]
    reversible: bool
    effect_class: str = "LOCAL_SHADOW"

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.operation or not self.policy:
            raise AdaptiveContractError("candidate_id, operation and policy are required")
        if not self.evidence_ids or any(not isinstance(item, str) or not item for item in self.evidence_ids):
            raise AdaptiveContractError("at least one valid evidence_id is required")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise AdaptiveContractError("duplicate evidence_id")
        if self.reversible is not True:
            raise AdaptiveContractError("candidate must be reversible")
        if not isinstance(self.effect_class, str) or not self.effect_class:
            raise AdaptiveContractError("effect_class is required")


def derive_candidates(observations: Sequence[TelemetryObservation]) -> tuple[PolicyCandidate, ...]:
    if not observations:
        return ()
    grouped: dict[str, list[TelemetryObservation]] = {}
    for observation in observations:
        grouped.setdefault(observation.operation, []).append(observation)
    candidates: list[PolicyCandidate] = []
    for operation in sorted(grouped):
        items = grouped[operation]
        failures = sum(not item.success for item in items)
        mean_latency = sum(item.latency_ms for item in items) / len(items)
        if failures:
            policy = "reduce_retry_budget_and_quarantine_semantic_failures"
        elif mean_latency > 1000:
            policy = "checkpoint_and_reduce_batch_size"
        else:
            policy = "retain_current_policy"
        evidence_ids = tuple(sorted({item.evidence_id for item in items}))
        candidate_id = "adaptive-" + _digest({"operation": operation, "policy": policy, "evidence": evidence_ids})[:20]
        candidates.append(PolicyCandidate(candidate_id, operation, policy, evidence_ids, True))
    return tuple(candidates)


def paired_evaluate(
    candidate: PolicyCandidate,
    cases: Sequence[Mapping[str, Any]],
    *,
    rollback_available: bool,
    independent_verifier_pass: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    if candidate.effect_class != "LOCAL_SHADOW":
        reasons.append("NON_SHADOW_EFFECT_CLASS_REJECTED")
    if len(cases) < MIN_PAIRED_CASES:
        reasons.append("THIRTY_PAIRED_CASES_REQUIRED")
    baseline_total = 0.0
    candidate_total = 0.0
    hard_regressions = 0
    for index, case in enumerate(cases):
        baseline = case.get("baseline_quality")
        proposed = case.get("candidate_quality")
        if not isinstance(baseline, (int, float)) or not isinstance(proposed, (int, float)):
            raise AdaptiveContractError(f"case {index} quality values must be numeric")
        if not 0 <= baseline <= 1 or not 0 <= proposed <= 1:
            raise AdaptiveContractError(f"case {index} quality values out of range")
        baseline_total += float(baseline)
        candidate_total += float(proposed)
        if case.get("hard_regression") is True:
            hard_regressions += 1
    divisor = len(cases) or 1
    baseline_mean = baseline_total / divisor
    candidate_mean = candidate_total / divisor
    uplift = candidate_mean - baseline_mean
    if hard_regressions:
        reasons.append("HARD_REGRESSION")
    if uplift < MIN_QUALITY_UPLIFT:
        reasons.append("MINIMUM_QUALITY_UPLIFT_NOT_MET")
    if not rollback_available:
        reasons.append("ROLLBACK_REQUIRED")
    if not independent_verifier_pass:
        reasons.append("INDEPENDENT_VERIFIER_REQUIRED")
    accepted = not reasons
    result = {
        "schema": "BCO_PRIME_ADAPTIVE_EVALUATION_V1",
        "candidate": asdict(candidate),
        "paired_cases": len(cases),
        "baseline_mean": round(baseline_mean, 6),
        "candidate_mean": round(candidate_mean, 6),
        "quality_uplift": round(uplift, 6),
        "hard_regressions": hard_regressions,
        "state": "SHADOW_CANDIDATE_REVIEW" if accepted else "HOLD",
        "shadowProven": accepted,
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "rollbackAvailable": rollback_available,
        "reasons": reasons or ["BOUNDED_SHADOW_CANDIDATE_ONLY"],
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = _digest(result)
    return result


def rollback(candidate: PolicyCandidate, evaluation_receipt: Mapping[str, Any]) -> dict[str, Any]:
    if evaluation_receipt.get("candidate", {}).get("candidate_id") != candidate.candidate_id:
        raise AdaptiveContractError("candidate/evaluation mismatch")
    result = {
        "schema": "BCO_PRIME_ADAPTIVE_ROLLBACK_V1",
        "candidate_id": candidate.candidate_id,
        "state": "ROLLED_BACK_TO_STABLE_BASELINE",
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = _digest(result)
    return result


def manifest() -> dict[str, Any]:
    result = {
        "schema": SCHEMA,
        "version": VERSION,
        "telemetry_required": True,
        "minimum_paired_cases": MIN_PAIRED_CASES,
        "minimum_quality_uplift": MIN_QUALITY_UPLIFT,
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["manifest_sha256"] = _digest(result)
    return result


__all__ = [
    "AdaptiveContractError",
    "PolicyCandidate",
    "TelemetryObservation",
    "derive_candidates",
    "manifest",
    "paired_evaluate",
    "rollback",
]
