from __future__ import annotations

"""CFBE AutoPilot + Meta-Cognition empirical proof court v1.

This module measures four proof gaps left intentionally open by the source/control
fabric: reflection value, confidence calibration, restart-safe unattended resume,
and owner-intervention burden. It never grants provider-effect authority, never
promotes stable policy by itself, and never treats synthetic or hosted shadow
measurements as observed operational value.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from statistics import mean, median
from typing import Mapping, Sequence


SCHEMA = "CFBE-AUTOPILOT-METACOG-EMPIRICAL-COURT-V1"
MIN_PAIRED_CASES = 30
MIN_RESUME_CASES = 10


class EvidenceMode(str, Enum):
    SYNTHETIC_SHADOW = "SYNTHETIC_SHADOW"
    HOSTED_SHADOW = "HOSTED_SHADOW"
    OBSERVED_OPERATIONAL = "OBSERVED_OPERATIONAL"
    PROVIDER_NATIVE = "PROVIDER_NATIVE"


REAL_EVIDENCE_MODES = frozenset({EvidenceMode.OBSERVED_OPERATIONAL, EvidenceMode.PROVIDER_NATIVE})


@dataclass(frozen=True, slots=True)
class EmpiricalThresholds:
    minimum_paired_cases: int = MIN_PAIRED_CASES
    minimum_resume_cases: int = MIN_RESUME_CASES
    minimum_mean_quality_delta: float = 0.02
    maximum_pair_quality_regression: float = 0.02
    maximum_median_latency_ratio: float = 1.75
    maximum_brier_score: float = 0.20
    maximum_expected_calibration_error: float = 0.15

    def validate(self) -> "EmpiricalThresholds":
        if self.minimum_paired_cases < 2 or self.minimum_resume_cases < 2:
            raise ValueError("EMPIRICAL_MINIMUM_SAMPLE_INVALID")
        if self.minimum_mean_quality_delta < 0 or self.maximum_pair_quality_regression < 0:
            raise ValueError("EMPIRICAL_QUALITY_THRESHOLD_INVALID")
        if self.maximum_median_latency_ratio <= 0:
            raise ValueError("EMPIRICAL_LATENCY_THRESHOLD_INVALID")
        if not 0 <= self.maximum_brier_score <= 1:
            raise ValueError("EMPIRICAL_BRIER_THRESHOLD_INVALID")
        if not 0 <= self.maximum_expected_calibration_error <= 1:
            raise ValueError("EMPIRICAL_ECE_THRESHOLD_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class MetaCognitionPair:
    pair_id: str
    source_head_sha: str
    task_signature: str
    evidence_mode: EvidenceMode
    baseline_quality: float
    candidate_quality: float
    baseline_elapsed_ms: float
    candidate_elapsed_ms: float
    baseline_owner_interventions: int
    candidate_owner_interventions: int
    candidate_reflection_used: bool
    candidate_confidence: float
    candidate_outcome_correct: bool
    independent_readback: bool
    proof_refs: tuple[str, ...]

    def validate(self, *, expected_source_head_sha: str) -> "MetaCognitionPair":
        if not self.pair_id.strip() or not self.task_signature.strip():
            raise ValueError("METACOG_PAIR_IDENTITY_REQUIRED")
        _validate_sha(self.source_head_sha)
        if self.source_head_sha != expected_source_head_sha:
            raise ValueError("METACOG_PAIR_SOURCE_HEAD_MISMATCH")
        if not 0 <= self.baseline_quality <= 1 or not 0 <= self.candidate_quality <= 1:
            raise ValueError("METACOG_PAIR_QUALITY_INVALID")
        if self.baseline_elapsed_ms <= 0 or self.candidate_elapsed_ms <= 0:
            raise ValueError("METACOG_PAIR_LATENCY_INVALID")
        if self.baseline_owner_interventions < 0 or self.candidate_owner_interventions < 0:
            raise ValueError("METACOG_PAIR_OWNER_BURDEN_INVALID")
        if not 0 <= self.candidate_confidence <= 1:
            raise ValueError("METACOG_PAIR_CONFIDENCE_INVALID")
        if len(tuple(ref for ref in self.proof_refs if str(ref).strip())) < 2:
            raise ValueError("METACOG_PAIR_PROOF_REFS_INCOMPLETE")
        return self


@dataclass(frozen=True, slots=True)
class ResumeObservation:
    observation_id: str
    source_head_sha: str
    evidence_mode: EvidenceMode
    process_before: str
    process_after: str
    checkpoint_id: str
    resumed: bool
    duplicate_effect_count: int
    state_drift: bool
    independent_readback: bool
    proof_refs: tuple[str, ...]

    def validate(self, *, expected_source_head_sha: str) -> "ResumeObservation":
        if not self.observation_id.strip() or not self.checkpoint_id.strip():
            raise ValueError("RESUME_OBSERVATION_IDENTITY_REQUIRED")
        _validate_sha(self.source_head_sha)
        if self.source_head_sha != expected_source_head_sha:
            raise ValueError("RESUME_SOURCE_HEAD_MISMATCH")
        if not self.process_before.strip() or not self.process_after.strip():
            raise ValueError("RESUME_PROCESS_IDENTITY_REQUIRED")
        if self.duplicate_effect_count < 0:
            raise ValueError("RESUME_DUPLICATE_EFFECT_COUNT_INVALID")
        if len(tuple(ref for ref in self.proof_refs if str(ref).strip())) < 2:
            raise ValueError("RESUME_PROOF_REFS_INCOMPLETE")
        return self


@dataclass(frozen=True, slots=True)
class EmpiricalProofReceipt:
    schema: str
    source_head_sha: str
    paired_case_count: int
    resume_case_count: int
    evidence_modes: tuple[str, ...]
    mean_quality_delta: float
    quality_regression_count: int
    reflection_coverage: float
    median_latency_ratio: float
    owner_intervention_delta_total: int
    brier_score: float
    expected_calibration_error: float
    cross_process_resume_ratio: float
    duplicate_effect_count: int
    state_drift_count: int
    independent_readback_coverage: float
    structure_qualified: bool
    hosted_shadow_qualified: bool
    observed_empirical_candidate: bool
    provider_runtime_candidate: bool
    full_autopilot_runtime_proven: bool
    provider_effect_authorized: bool
    stable_promotion_authorized: bool
    decision: str
    blockers: tuple[str, ...]
    receipt_sha256: str = ""

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload = asdict(self)
        payload["evidence_modes"] = list(self.evidence_modes)
        payload["blockers"] = list(self.blockers)
        if not include_hash:
            payload.pop("receipt_sha256", None)
        elif not payload["receipt_sha256"]:
            payload["receipt_sha256"] = canonical_hash({k: v for k, v in payload.items() if k != "receipt_sha256"})
        return payload


@dataclass(frozen=True, slots=True)
class MeasurementContract:
    schema: str
    required_pair_fields: tuple[str, ...]
    required_resume_fields: tuple[str, ...]
    required_proof_axes: tuple[str, ...]
    truth_boundary: tuple[str, ...]



def _validate_sha(value: str) -> None:
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value.lower()):
        raise ValueError("EMPIRICAL_SOURCE_SHA_INVALID")



def canonical_hash(value: Mapping[str, object]) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()



def _expected_calibration_error(pairs: Sequence[MetaCognitionPair], *, bins: int = 5) -> float:
    if bins < 2:
        raise ValueError("EMPIRICAL_CALIBRATION_BINS_INVALID")
    groups: list[list[MetaCognitionPair]] = [[] for _ in range(bins)]
    for pair in pairs:
        index = min(bins - 1, int(pair.candidate_confidence * bins))
        groups[index].append(pair)
    total = len(pairs)
    if not total:
        return 1.0
    error = 0.0
    for group in groups:
        if not group:
            continue
        avg_confidence = mean(item.candidate_confidence for item in group)
        accuracy = mean(1.0 if item.candidate_outcome_correct else 0.0 for item in group)
        error += (len(group) / total) * abs(avg_confidence - accuracy)
    return error



def measurement_contract() -> MeasurementContract:
    return MeasurementContract(
        schema=SCHEMA,
        required_pair_fields=(
            "pair_id",
            "source_head_sha",
            "task_signature",
            "evidence_mode",
            "baseline_quality",
            "candidate_quality",
            "baseline_elapsed_ms",
            "candidate_elapsed_ms",
            "baseline_owner_interventions",
            "candidate_owner_interventions",
            "candidate_reflection_used",
            "candidate_confidence",
            "candidate_outcome_correct",
            "independent_readback",
            "proof_refs",
        ),
        required_resume_fields=(
            "observation_id",
            "source_head_sha",
            "evidence_mode",
            "process_before",
            "process_after",
            "checkpoint_id",
            "resumed",
            "duplicate_effect_count",
            "state_drift",
            "independent_readback",
            "proof_refs",
        ),
        required_proof_axes=(
            "paired_reflection_vs_no_reflection",
            "confidence_vs_resolved_outcome",
            "cross_process_checkpoint_resume",
            "owner_intervention_delta",
            "independent_readback",
        ),
        truth_boundary=(
            "synthetic_shadow_never_counts_as_observed_operational_value",
            "hosted_shadow_never_counts_as_serving_provider_runtime",
            "provider_runtime_candidate_does_not_prove_always_on_event_intake",
            "this_court_never_grants_provider_effect_authority",
            "this_court_never_self_promotes_stable_policy",
            "private_chain_of_thought_is_not_required_or_recorded",
        ),
    )



def evaluate_empirical_court(
    *,
    source_head_sha: str,
    paired_cases: Sequence[MetaCognitionPair],
    resume_cases: Sequence[ResumeObservation],
    thresholds: EmpiricalThresholds | None = None,
) -> EmpiricalProofReceipt:
    _validate_sha(source_head_sha)
    limits = (thresholds or EmpiricalThresholds()).validate()
    pairs = tuple(item.validate(expected_source_head_sha=source_head_sha) for item in paired_cases)
    resumes = tuple(item.validate(expected_source_head_sha=source_head_sha) for item in resume_cases)

    if len({item.pair_id for item in pairs}) != len(pairs):
        raise ValueError("METACOG_PAIR_IDS_MUST_BE_UNIQUE")
    if len({item.observation_id for item in resumes}) != len(resumes):
        raise ValueError("RESUME_OBSERVATION_IDS_MUST_BE_UNIQUE")

    evidence_modes = tuple(sorted({item.evidence_mode.value for item in (*pairs, *resumes)}))
    mean_quality_delta = mean((item.candidate_quality - item.baseline_quality) for item in pairs) if pairs else 0.0
    quality_regressions = sum(
        (item.baseline_quality - item.candidate_quality) > limits.maximum_pair_quality_regression
        for item in pairs
    )
    reflection_coverage = mean(1.0 if item.candidate_reflection_used else 0.0 for item in pairs) if pairs else 0.0
    latency_ratios = [item.candidate_elapsed_ms / item.baseline_elapsed_ms for item in pairs]
    median_latency_ratio = median(latency_ratios) if latency_ratios else 0.0
    owner_delta_total = sum(
        item.baseline_owner_interventions - item.candidate_owner_interventions for item in pairs
    )
    brier_score = mean(
        (item.candidate_confidence - (1.0 if item.candidate_outcome_correct else 0.0)) ** 2
        for item in pairs
    ) if pairs else 1.0
    ece = _expected_calibration_error(pairs)

    cross_process_resume_ratio = mean(
        1.0 if item.resumed and item.process_before != item.process_after else 0.0 for item in resumes
    ) if resumes else 0.0
    duplicate_effect_count = sum(item.duplicate_effect_count for item in resumes)
    state_drift_count = sum(1 for item in resumes if item.state_drift)
    all_records = (*pairs, *resumes)
    readback_coverage = mean(1.0 if item.independent_readback else 0.0 for item in all_records) if all_records else 0.0

    blockers: list[str] = []
    if len(pairs) < limits.minimum_paired_cases:
        blockers.append("MINIMUM_PAIRED_METACOG_CASES_REQUIRED")
    if len(resumes) < limits.minimum_resume_cases:
        blockers.append("MINIMUM_CROSS_PROCESS_RESUME_CASES_REQUIRED")
    if reflection_coverage < 1.0:
        blockers.append("CANDIDATE_REFLECTION_COVERAGE_INCOMPLETE")
    if mean_quality_delta < limits.minimum_mean_quality_delta:
        blockers.append("MEAN_DECISION_QUALITY_GAIN_BELOW_FLOOR")
    if quality_regressions:
        blockers.append("PAIRWISE_DECISION_QUALITY_REGRESSION")
    if median_latency_ratio > limits.maximum_median_latency_ratio:
        blockers.append("REFLECTION_LATENCY_OVERHEAD_EXCEEDS_BUDGET")
    if owner_delta_total <= 0:
        blockers.append("OWNER_INTERVENTION_BURDEN_NOT_REDUCED")
    if brier_score > limits.maximum_brier_score:
        blockers.append("CONFIDENCE_BRIER_SCORE_ABOVE_CEILING")
    if ece > limits.maximum_expected_calibration_error:
        blockers.append("CONFIDENCE_CALIBRATION_ERROR_ABOVE_CEILING")
    if cross_process_resume_ratio < 1.0:
        blockers.append("CROSS_PROCESS_RESUME_INCOMPLETE")
    if duplicate_effect_count:
        blockers.append("DUPLICATE_EFFECT_ON_RESUME")
    if state_drift_count:
        blockers.append("STATE_DRIFT_ON_RESUME")
    if readback_coverage < 1.0:
        blockers.append("INDEPENDENT_READBACK_INCOMPLETE")

    metrics_pass = not blockers
    contains_synthetic = any(item.evidence_mode is EvidenceMode.SYNTHETIC_SHADOW for item in all_records)
    all_non_synthetic = bool(all_records) and not contains_synthetic
    all_real = bool(all_records) and all(item.evidence_mode in REAL_EVIDENCE_MODES for item in all_records)
    all_resume_provider_native = bool(resumes) and all(
        item.evidence_mode is EvidenceMode.PROVIDER_NATIVE for item in resumes
    )

    structure_qualified = metrics_pass
    hosted_shadow_qualified = metrics_pass and all_non_synthetic
    observed_empirical_candidate = metrics_pass and all_real
    provider_runtime_candidate = observed_empirical_candidate and all_resume_provider_native

    if not metrics_pass:
        decision = "HOLD_EMPIRICAL_GATES_OPEN"
    elif contains_synthetic:
        decision = "STRUCTURAL_ONLY_SYNTHETIC_SHADOW"
    elif provider_runtime_candidate:
        decision = "PROVIDER_RUNTIME_METACOG_CANDIDATE"
    elif observed_empirical_candidate:
        decision = "OBSERVED_METACOG_EMPIRICAL_CANDIDATE"
    else:
        decision = "HOSTED_SHADOW_METACOG_QUALIFIED"

    base = EmpiricalProofReceipt(
        schema=SCHEMA,
        source_head_sha=source_head_sha,
        paired_case_count=len(pairs),
        resume_case_count=len(resumes),
        evidence_modes=evidence_modes,
        mean_quality_delta=round(mean_quality_delta, 6),
        quality_regression_count=quality_regressions,
        reflection_coverage=round(reflection_coverage, 6),
        median_latency_ratio=round(median_latency_ratio, 6),
        owner_intervention_delta_total=owner_delta_total,
        brier_score=round(brier_score, 6),
        expected_calibration_error=round(ece, 6),
        cross_process_resume_ratio=round(cross_process_resume_ratio, 6),
        duplicate_effect_count=duplicate_effect_count,
        state_drift_count=state_drift_count,
        independent_readback_coverage=round(readback_coverage, 6),
        structure_qualified=structure_qualified,
        hosted_shadow_qualified=hosted_shadow_qualified,
        observed_empirical_candidate=observed_empirical_candidate,
        provider_runtime_candidate=provider_runtime_candidate,
        full_autopilot_runtime_proven=False,
        provider_effect_authorized=False,
        stable_promotion_authorized=False,
        decision=decision,
        blockers=tuple(blockers),
    )
    digest = canonical_hash(base.to_dict(include_hash=False))
    return EmpiricalProofReceipt(**{**asdict(base), "receipt_sha256": digest})



def frontier_bridge(receipt: EmpiricalProofReceipt) -> dict[str, object]:
    """Project this court into existing empirical frontier lanes without promotion."""
    return {
        "schema": "CFBE-AUTOPILOT-METACOG-EMPIRICAL-FRONTIER-BRIDGE-V1",
        "source_head_sha": receipt.source_head_sha,
        "trace_eval_optimizer": {
            "reflection_value_measured": receipt.paired_case_count >= MIN_PAIRED_CASES,
            "confidence_calibration_measured": receipt.paired_case_count >= MIN_PAIRED_CASES,
            "observed_empirical_candidate": receipt.observed_empirical_candidate,
        },
        "durable_runtime": {
            "cross_process_resume_measured": receipt.resume_case_count >= MIN_RESUME_CASES,
            "provider_runtime_candidate": receipt.provider_runtime_candidate,
            "full_autopilot_runtime_proven": False,
        },
        "owner_value": {
            "owner_intervention_delta_total": receipt.owner_intervention_delta_total,
            "owner_value_proven": False,
            "reason": "existing owner-value court remains authoritative for measured owner value",
        },
        "provider_effect_authorized": False,
        "stable_promotion_authorized": False,
    }
