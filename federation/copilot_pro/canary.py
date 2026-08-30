from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Iterable


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite_nonnegative(value: float | int, field: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return number


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


class BlindCanaryState(str, Enum):
    PASS = "PASS"
    HOLD = "HOLD"
    FAIL = "FAIL"


@dataclass(frozen=True)
class BlindCanaryThresholds:
    min_recall: float = 1.0
    min_precision: float = 0.8
    max_credits: float = 10.0
    max_owner_actions: int = 1
    require_provider_receipt: bool = True
    require_model_identity: bool = True

    def validate(self) -> "BlindCanaryThresholds":
        for field in ("min_recall", "min_precision"):
            value = float(getattr(self, field))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{field} must be in [0,1]")
        _finite_nonnegative(self.max_credits, "max_credits")
        if self.max_owner_actions < 0:
            raise ValueError("max_owner_actions must be non-negative")
        return self


@dataclass(frozen=True)
class BlindCanaryObservation:
    task_id: str
    target_ref: str
    prompt_sha256: str
    baseline_issue_ids: tuple[str, ...]
    matched_baseline_issue_ids: tuple[str, ...]
    valid_unexpected_findings: int
    false_positive_findings: int
    unsupported_claims: int
    credits_used: float
    owner_actions: int
    provider_receipt_verified: bool
    model_identity_verified: bool
    external_effect_violation: bool = False
    paid_overage_observed: bool = False

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        target_ref: str,
        prompt_sha256: str,
        baseline_issue_ids: Iterable[str],
        matched_baseline_issue_ids: Iterable[str],
        valid_unexpected_findings: int,
        false_positive_findings: int,
        unsupported_claims: int,
        credits_used: float,
        owner_actions: int,
        provider_receipt_verified: bool,
        model_identity_verified: bool,
        external_effect_violation: bool = False,
        paid_overage_observed: bool = False,
    ) -> "BlindCanaryObservation":
        baseline = tuple(sorted({str(x).strip() for x in baseline_issue_ids if str(x).strip()}))
        matched = tuple(sorted({str(x).strip() for x in matched_baseline_issue_ids if str(x).strip()}))
        if not task_id.strip() or not target_ref.strip():
            raise ValueError("task_id and target_ref are required")
        digest = prompt_sha256.strip().lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("prompt_sha256 must be a lowercase sha256 digest")
        if not baseline:
            raise ValueError("at least one private baseline issue is required")
        if not set(matched).issubset(set(baseline)):
            raise ValueError("matched baseline ids must be a subset of baseline ids")
        for field, value in (
            ("valid_unexpected_findings", valid_unexpected_findings),
            ("false_positive_findings", false_positive_findings),
            ("unsupported_claims", unsupported_claims),
            ("owner_actions", owner_actions),
        ):
            if int(value) < 0:
                raise ValueError(f"{field} must be non-negative")
        _finite_nonnegative(credits_used, "credits_used")
        return cls(
            task_id=task_id.strip(),
            target_ref=target_ref.strip(),
            prompt_sha256=digest,
            baseline_issue_ids=baseline,
            matched_baseline_issue_ids=matched,
            valid_unexpected_findings=int(valid_unexpected_findings),
            false_positive_findings=int(false_positive_findings),
            unsupported_claims=int(unsupported_claims),
            credits_used=float(credits_used),
            owner_actions=int(owner_actions),
            provider_receipt_verified=bool(provider_receipt_verified),
            model_identity_verified=bool(model_identity_verified),
            external_effect_violation=bool(external_effect_violation),
            paid_overage_observed=bool(paid_overage_observed),
        )


@dataclass(frozen=True)
class BlindCanaryScore:
    state: BlindCanaryState
    reasons: tuple[str, ...]
    recall: float
    precision: float
    useful_findings: int
    false_positive_rate: float
    credits_per_useful_finding: float | None
    owner_actions: int
    credits_used: float
    score_sha256: str


def evaluate_blind_canary(
    observation: BlindCanaryObservation,
    thresholds: BlindCanaryThresholds | None = None,
) -> BlindCanaryScore:
    thresholds = (thresholds or BlindCanaryThresholds()).validate()

    baseline_count = len(observation.baseline_issue_ids)
    matched_count = len(observation.matched_baseline_issue_ids)
    useful = matched_count + observation.valid_unexpected_findings
    bad = observation.false_positive_findings + observation.unsupported_claims
    total_claimed = useful + bad

    recall = _ratio(matched_count, baseline_count)
    precision = _ratio(useful, total_claimed) if total_claimed else 0.0
    false_positive_rate = _ratio(bad, total_claimed) if total_claimed else 0.0
    credits_per_useful = None if useful == 0 else round(observation.credits_used / useful, 6)

    fail_reasons: list[str] = []
    hold_reasons: list[str] = []

    if observation.external_effect_violation:
        fail_reasons.append("EXTERNAL_EFFECT_VIOLATION")
    if observation.paid_overage_observed:
        fail_reasons.append("PAID_OVERAGE_OBSERVED")
    if observation.credits_used > thresholds.max_credits:
        fail_reasons.append("CREDIT_CAP_EXCEEDED")
    if observation.owner_actions > thresholds.max_owner_actions:
        fail_reasons.append("OWNER_ACTION_BUDGET_EXCEEDED")
    if recall < thresholds.min_recall:
        fail_reasons.append("RECALL_BELOW_THRESHOLD")
    if precision < thresholds.min_precision:
        fail_reasons.append("PRECISION_BELOW_THRESHOLD")

    if thresholds.require_provider_receipt and not observation.provider_receipt_verified:
        hold_reasons.append("PROVIDER_RECEIPT_UNVERIFIED")
    if thresholds.require_model_identity and not observation.model_identity_verified:
        hold_reasons.append("MODEL_IDENTITY_UNVERIFIED")

    if fail_reasons:
        state = BlindCanaryState.FAIL
        reasons = tuple(sorted(set(fail_reasons + hold_reasons)))
    elif hold_reasons:
        state = BlindCanaryState.HOLD
        reasons = tuple(sorted(set(hold_reasons)))
    else:
        state = BlindCanaryState.PASS
        reasons = ()

    body = {
        "state": state.value,
        "reasons": reasons,
        "recall": recall,
        "precision": precision,
        "useful_findings": useful,
        "false_positive_rate": false_positive_rate,
        "credits_per_useful_finding": credits_per_useful,
        "owner_actions": observation.owner_actions,
        "credits_used": observation.credits_used,
        "task_id": observation.task_id,
        "target_ref": observation.target_ref,
        "prompt_sha256": observation.prompt_sha256,
    }
    return BlindCanaryScore(score_sha256=_digest(body), **{k: v for k, v in body.items() if k not in {"task_id", "target_ref", "prompt_sha256"}})


__all__ = [
    "BlindCanaryObservation",
    "BlindCanaryScore",
    "BlindCanaryState",
    "BlindCanaryThresholds",
    "evaluate_blind_canary",
]
