from __future__ import annotations

"""Machine-observable burden court beneath the strict owner-value court.

This court evaluates only machine-observable burden signals: owner intervention
count, clarification count, correction count, verified-output ratio, elapsed
mission time, exact source/task/oracle identity and independent proof refs.

It deliberately does not infer active owner time from wall-clock gaps. A passing
receipt is only an OBSERVABLE_BURDEN_REDUCTION_CANDIDATE and cannot prove owner
value, deployment, stable promotion or provider-effect authority.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from statistics import median
from typing import Any, Mapping, Sequence


SCHEMA = "BUBBLES-OBSERVABLE-BURDEN-COURT-V1"
OBSERVABLE_BURDEN_MODE = "OBSERVED_MACHINE_BURDEN"
DEFAULT_MINIMUM_PAIRS = 10


def _hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")).hexdigest()


def _is_sha(value: str) -> bool:
    value = str(value).strip().lower()
    return len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


@dataclass(frozen=True, slots=True)
class ObservableBurdenObservation:
    pair_id: str
    mission_class: str
    task_signature: str
    oracle_id: str
    source_head_sha: str
    evidence_mode: str
    baseline_owner_interventions: int
    candidate_owner_interventions: int
    baseline_clarification_count: int
    candidate_clarification_count: int
    baseline_correction_count: int
    candidate_correction_count: int
    baseline_verified_output_ratio: float
    candidate_verified_output_ratio: float
    baseline_elapsed_seconds: float
    candidate_elapsed_seconds: float
    independent_readback: bool
    proof_refs: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ObservableBurdenObservation":
        return cls(
            pair_id=str(value.get("pair_id") or "").strip(),
            mission_class=str(value.get("mission_class") or "").strip(),
            task_signature=str(value.get("task_signature") or "").strip(),
            oracle_id=str(value.get("oracle_id") or "").strip(),
            source_head_sha=str(value.get("source_head_sha") or "").strip(),
            evidence_mode=str(value.get("evidence_mode") or "").strip(),
            baseline_owner_interventions=int(value.get("baseline_owner_interventions", 0)),
            candidate_owner_interventions=int(value.get("candidate_owner_interventions", 0)),
            baseline_clarification_count=int(value.get("baseline_clarification_count", 0)),
            candidate_clarification_count=int(value.get("candidate_clarification_count", 0)),
            baseline_correction_count=int(value.get("baseline_correction_count", 0)),
            candidate_correction_count=int(value.get("candidate_correction_count", 0)),
            baseline_verified_output_ratio=float(value.get("baseline_verified_output_ratio", 0)),
            candidate_verified_output_ratio=float(value.get("candidate_verified_output_ratio", 0)),
            baseline_elapsed_seconds=float(value.get("baseline_elapsed_seconds", 0)),
            candidate_elapsed_seconds=float(value.get("candidate_elapsed_seconds", 0)),
            independent_readback=value.get("independent_readback") is True,
            proof_refs=tuple(str(item).strip() for item in value.get("proof_refs") or () if str(item).strip()),
        )

    @property
    def intervention_delta(self) -> int:
        return self.baseline_owner_interventions - self.candidate_owner_interventions

    @property
    def clarification_delta(self) -> int:
        return self.baseline_clarification_count - self.candidate_clarification_count

    @property
    def correction_delta(self) -> int:
        return self.baseline_correction_count - self.candidate_correction_count

    @property
    def elapsed_delta_seconds(self) -> float:
        return self.baseline_elapsed_seconds - self.candidate_elapsed_seconds

    @property
    def has_strict_burden_improvement(self) -> bool:
        return any(value > 0 for value in (self.intervention_delta, self.clarification_delta, self.correction_delta, self.elapsed_delta_seconds))

    def failures(self, expected_source_head_sha: str) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.pair_id or not self.mission_class:
            failures.append("OBSERVABLE_BURDEN_IDENTITY_REQUIRED")
        if not self.task_signature or not self.oracle_id:
            failures.append("OBSERVABLE_BURDEN_TASK_ORACLE_REQUIRED")
        if not _is_sha(self.source_head_sha) or self.source_head_sha != expected_source_head_sha:
            failures.append("OBSERVABLE_BURDEN_SOURCE_HEAD_MISMATCH")
        if self.evidence_mode != OBSERVABLE_BURDEN_MODE:
            failures.append("OBSERVABLE_BURDEN_EVIDENCE_MODE_INVALID")
        counts = (
            self.baseline_owner_interventions,
            self.candidate_owner_interventions,
            self.baseline_clarification_count,
            self.candidate_clarification_count,
            self.baseline_correction_count,
            self.candidate_correction_count,
        )
        if any(value < 0 for value in counts):
            failures.append("OBSERVABLE_BURDEN_COUNTS_NONNEGATIVE_REQUIRED")
        if self.baseline_elapsed_seconds <= 0 or self.candidate_elapsed_seconds <= 0:
            failures.append("OBSERVABLE_BURDEN_ELAPSED_POSITIVE_REQUIRED")
        if not 0 < self.baseline_verified_output_ratio <= 1:
            failures.append("OBSERVABLE_BURDEN_BASELINE_RATIO_INVALID")
        if not 0 < self.candidate_verified_output_ratio <= 1:
            failures.append("OBSERVABLE_BURDEN_CANDIDATE_RATIO_INVALID")
        if self.candidate_verified_output_ratio < self.baseline_verified_output_ratio:
            failures.append("OBSERVABLE_BURDEN_OUTPUT_RATIO_REGRESSION")
        if self.candidate_owner_interventions > self.baseline_owner_interventions:
            failures.append("OBSERVABLE_BURDEN_INTERVENTION_REGRESSION")
        if self.candidate_clarification_count > self.baseline_clarification_count:
            failures.append("OBSERVABLE_BURDEN_CLARIFICATION_REGRESSION")
        if self.candidate_correction_count > self.baseline_correction_count:
            failures.append("OBSERVABLE_BURDEN_CORRECTION_REGRESSION")
        if self.candidate_elapsed_seconds > self.baseline_elapsed_seconds:
            failures.append("OBSERVABLE_BURDEN_LATENCY_REGRESSION")
        if not self.has_strict_burden_improvement:
            failures.append("OBSERVABLE_BURDEN_STRICT_IMPROVEMENT_REQUIRED")
        if not self.independent_readback:
            failures.append("OBSERVABLE_BURDEN_INDEPENDENT_READBACK_REQUIRED")
        if len(set(self.proof_refs)) < 2:
            failures.append("OBSERVABLE_BURDEN_PROOF_REFS_INCOMPLETE")
        return tuple(failures)


@dataclass(frozen=True, slots=True)
class ObservableBurdenReceipt:
    schema: str
    source_head_sha: str
    candidate_id: str
    pair_count: int
    observable_burden_reduction_candidate: bool
    median_intervention_delta: float
    median_clarification_delta: float
    median_correction_delta: float
    median_elapsed_delta_seconds: float
    owner_minutes_proven: bool
    owner_value_proven: bool
    stable_promotion_authorized: bool
    provider_effect_authorized: bool
    external_effect: bool
    blockers: tuple[str, ...]
    next_gate: str
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_observable_burden_court(*, candidate_id: str, source_head_sha: str, observations: Sequence[Mapping[str, Any]] = (), minimum_pairs: int = DEFAULT_MINIMUM_PAIRS) -> ObservableBurdenReceipt:
    if not str(candidate_id).strip():
        raise ValueError("OBSERVABLE_BURDEN_CANDIDATE_ID_REQUIRED")
    if not _is_sha(source_head_sha):
        raise ValueError("OBSERVABLE_BURDEN_SOURCE_HEAD_SHA_REQUIRED")
    if int(minimum_pairs) <= 0:
        raise ValueError("OBSERVABLE_BURDEN_MINIMUM_PAIRS_INVALID")
    items = tuple(ObservableBurdenObservation.from_mapping(item) for item in observations)
    blockers: set[str] = set()
    if len(items) < int(minimum_pairs):
        blockers.add("OBSERVABLE_BURDEN_MINIMUM_PAIRS_REQUIRED")
    pair_ids = [item.pair_id for item in items]
    if len(set(pair_ids)) != len(pair_ids):
        blockers.add("OBSERVABLE_BURDEN_PAIR_IDS_MUST_BE_UNIQUE")
    for item in items:
        blockers.update(item.failures(source_head_sha))
    candidate = len(items) >= int(minimum_pairs) and not blockers
    if items:
        median_intervention = median(item.intervention_delta for item in items)
        median_clarification = median(item.clarification_delta for item in items)
        median_correction = median(item.correction_delta for item in items)
        median_elapsed = median(item.elapsed_delta_seconds for item in items)
    else:
        median_intervention = median_clarification = median_correction = median_elapsed = 0.0
    truth_boundary = (
        "Machine-observable burden evidence does not measure active human time.",
        "Wall-clock gaps are not owner-minutes evidence.",
        "This receipt cannot prove owner value, deployment, stable promotion or provider-effect authority.",
    )
    payload = {
        "schema": SCHEMA,
        "source_head_sha": source_head_sha,
        "candidate_id": str(candidate_id).strip(),
        "pair_count": len(items),
        "observable_burden_reduction_candidate": candidate,
        "median_intervention_delta": float(median_intervention),
        "median_clarification_delta": float(median_clarification),
        "median_correction_delta": float(median_correction),
        "median_elapsed_delta_seconds": float(median_elapsed),
        "owner_minutes_proven": False,
        "owner_value_proven": False,
        "stable_promotion_authorized": False,
        "provider_effect_authorized": False,
        "external_effect": False,
        "blockers": tuple(sorted(blockers)),
        "next_gate": "COLLECT_ACTIVE_OWNER_TIME_EVIDENCE_FOR_STRICT_OWNER_VALUE_COURT" if candidate else "COLLECT_VALID_MACHINE_OBSERVABLE_MATCHED_PAIRS",
        "truth_boundary": truth_boundary,
    }
    return ObservableBurdenReceipt(**payload, receipt_sha256=_hash(payload))


__all__ = ["DEFAULT_MINIMUM_PAIRS", "OBSERVABLE_BURDEN_MODE", "ObservableBurdenObservation", "ObservableBurdenReceipt", "evaluate_observable_burden_court"]
