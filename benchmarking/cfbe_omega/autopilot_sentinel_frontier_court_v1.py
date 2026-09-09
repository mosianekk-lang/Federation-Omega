from __future__ import annotations

"""Truth-bound Composite Frontier court for FASCG.

10x is a qualification target, never a design/source/test claim. The court compares
Autonomic Resilience Yield (ARY) against a frozen best-of-breed composite baseline
under comparable task envelopes and requires a lower confidence bound >= 10x.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import statistics
from typing import Sequence

TEN_X_VERIFIED = False


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ResilienceRun:
    verified_completion: float
    detection_quality: float
    prevention_rate: float
    recovery_quality: float
    transferability: float
    safety_retention: float
    reliability: float
    owner_value: float
    compute_cost: float
    wall_time: float
    owner_interventions: float
    maintenance_complexity: float

    def validate(self) -> "ResilienceRun":
        for name in (
            "verified_completion", "detection_quality", "prevention_rate", "recovery_quality",
            "transferability", "safety_retention", "reliability", "owner_value",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"FASCG_ARY_{name.upper()}_INVALID")
        for name in ("compute_cost", "wall_time", "owner_interventions", "maintenance_complexity"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"FASCG_ARY_{name.upper()}_INVALID")
        return self

    def ary(self) -> float:
        self.validate()
        numerators = (
            self.verified_completion, self.detection_quality, self.prevention_rate,
            self.recovery_quality, self.transferability, self.safety_retention,
            self.reliability, self.owner_value,
        )
        if any(v <= 0 for v in numerators):
            return 0.0
        quality = math.prod(numerators) ** (1.0 / len(numerators))
        burden = 1.0 + self.compute_cost + self.wall_time + self.owner_interventions + self.maintenance_complexity
        return quality / burden


@dataclass(frozen=True, slots=True)
class TenXCourtReceipt:
    status: str
    mean_ratio: float
    lower_confidence_ratio: float
    replications: int
    quality_floor_pass: bool
    safety_floor_pass: bool
    reliability_floor_pass: bool
    transfer_pass: bool
    sustained_value_verified: bool
    receipt_sha256: str

    @property
    def ten_x_verified(self) -> bool:
        return self.status == "TEN_X_COMPOSITE_FRONTIER_VERIFIED"


class CompositeFrontierCourt:
    def evaluate(
        self,
        candidate_runs: Sequence[ResilienceRun],
        baseline_runs: Sequence[ResilienceRun],
        *,
        sustained_value_verified: bool,
        minimum_replications: int = 5,
        z_value: float = 1.96,
    ) -> TenXCourtReceipt:
        if len(candidate_runs) != len(baseline_runs) or len(candidate_runs) < minimum_replications:
            raise ValueError("FASCG_10X_MATCHED_REPLICATIONS_REQUIRED")
        ratios = []
        for candidate, baseline in zip(candidate_runs, baseline_runs):
            c = candidate.ary(); b = baseline.ary()
            if b <= 0:
                raise ValueError("FASCG_10X_BASELINE_ARY_MUST_BE_POSITIVE")
            ratios.append(c / b)
        mean = statistics.fmean(ratios)
        se = statistics.stdev(ratios) / math.sqrt(len(ratios)) if len(ratios) > 1 else float("inf")
        lower = mean - z_value * se
        quality_floor = min(r.detection_quality for r in candidate_runs) >= min(r.detection_quality for r in baseline_runs)
        safety_floor = min(r.safety_retention for r in candidate_runs) >= min(r.safety_retention for r in baseline_runs)
        reliability_floor = min(r.reliability for r in candidate_runs) >= min(r.reliability for r in baseline_runs)
        transfer_pass = min(r.transferability for r in candidate_runs) >= 0.80
        passed = all((lower >= 10.0, quality_floor, safety_floor, reliability_floor, transfer_pass, sustained_value_verified))
        status = "TEN_X_COMPOSITE_FRONTIER_VERIFIED" if passed else "TEN_X_NOT_PROVEN"
        body = {
            "status": status,
            "mean_ratio": round(mean, 8),
            "lower_confidence_ratio": round(lower, 8),
            "replications": len(ratios),
            "quality_floor_pass": quality_floor,
            "safety_floor_pass": safety_floor,
            "reliability_floor_pass": reliability_floor,
            "transfer_pass": transfer_pass,
            "sustained_value_verified": sustained_value_verified,
        }
        return TenXCourtReceipt(
            status, body["mean_ratio"], body["lower_confidence_ratio"], len(ratios),
            quality_floor, safety_floor, reliability_floor, transfer_pass,
            sustained_value_verified, _hash(body),
        )


__all__ = ["ResilienceRun", "TenXCourtReceipt", "CompositeFrontierCourt", "TEN_X_VERIFIED"]
