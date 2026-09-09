from __future__ import annotations

"""Operational soak and sustained-value courts for FASCG.

These courts do not run providers.  They consume exact-source, provider-native
operational windows and fail closed unless execution/readback/health/persistence/
rollback/state-lineage evidence survives repeated windows over real elapsed time.
Synthetic fixtures can test the math but cannot become operational proof.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Any, Sequence

from benchmarking.cfbe_omega.fascg_production_runtime_v1 import ProductionStage, PromotionEvidence

SCHEMA = "FASCG-OPERATIONAL-SOAK-V1"
PROVIDER_EFFECT_AUTHORIZED = False
OPERATIONAL_VERIFIED = False
SUSTAINED_VALUE_VERIFIED = False
TEN_X_VERIFIED = False


def _hash(v: Any) -> str:
    return sha256(json.dumps(v, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _unit(v: float, label: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or not 0 <= float(v) <= 1:
        raise ValueError(f"FASCG_SOAK_{label}_OUT_OF_RANGE")
    return float(v)


@dataclass(frozen=True, slots=True)
class OperationalWindow:
    window_id: str
    source_sha: str
    run_id: str
    observed_at_epoch: int
    provider_native_readback: bool
    health_verified: bool
    persistence_verified: bool
    rollback_verified: bool
    state_lineage_valid: bool
    safety_score: float
    reliability_score: float
    owner_value_score: float
    critical_incidents: int
    proof_refs: tuple[str, ...]

    def validate(self) -> "OperationalWindow":
        if not self.window_id.strip() or not self.source_sha.strip() or not self.run_id.strip():
            raise ValueError("FASCG_SOAK_WINDOW_IDENTITY_REQUIRED")
        if self.observed_at_epoch < 0 or self.critical_incidents < 0:
            raise ValueError("FASCG_SOAK_WINDOW_NUMERIC_INVALID")
        _unit(self.safety_score, "SAFETY")
        _unit(self.reliability_score, "RELIABILITY")
        _unit(self.owner_value_score, "OWNER_VALUE")
        if not self.proof_refs:
            raise ValueError("FASCG_SOAK_WINDOW_PROOF_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class SoakReceipt:
    status: str
    source_sha: str
    window_count: int
    elapsed_seconds: int
    blockers: tuple[str, ...]
    promotion_evidence: PromotionEvidence | None
    receipt_sha256: str


class OperationalSoakCourt:
    def evaluate(
        self,
        windows: Sequence[OperationalWindow],
        *,
        minimum_windows: int = 3,
        minimum_span_seconds: int = 300,
        safety_floor: float = .95,
        reliability_floor: float = .95,
        sustained_value: bool = False,
        sustained_value_floor: float = .70,
        sustained_span_seconds: int = 900,
    ) -> SoakReceipt:
        if minimum_windows < 2 or minimum_span_seconds < 0 or sustained_span_seconds < 0:
            raise ValueError("FASCG_SOAK_CONFIG_INVALID")
        if not windows:
            raise ValueError("FASCG_SOAK_WINDOWS_REQUIRED")
        rows = sorted((w.validate() for w in windows), key=lambda w: (w.observed_at_epoch, w.window_id))
        source_shas = {w.source_sha for w in rows}
        source_sha = next(iter(source_shas)) if len(source_shas) == 1 else "MULTI_SOURCE"
        blockers: list[str] = []
        if len(source_shas) != 1:
            blockers.append("SOURCE_DRIFT")
        if len({w.run_id for w in rows}) != len(rows):
            blockers.append("RUN_ID_REUSE")
        if len({w.window_id for w in rows}) != len(rows):
            blockers.append("WINDOW_ID_REUSE")
        if len(rows) < minimum_windows:
            blockers.append("WINDOW_COUNT_FLOOR")
        span = rows[-1].observed_at_epoch - rows[0].observed_at_epoch
        required_span = sustained_span_seconds if sustained_value else minimum_span_seconds
        if span < required_span:
            blockers.append("SOAK_TIME_SPAN_FLOOR")
        if any(not w.provider_native_readback for w in rows): blockers.append("PROVIDER_READBACK_REQUIRED")
        if any(not w.health_verified for w in rows): blockers.append("HEALTH_REQUIRED")
        if any(not w.persistence_verified for w in rows): blockers.append("PERSISTENCE_REQUIRED")
        if any(not w.rollback_verified for w in rows): blockers.append("ROLLBACK_REQUIRED")
        if any(not w.state_lineage_valid for w in rows): blockers.append("STATE_LINEAGE_REQUIRED")
        if any(w.critical_incidents for w in rows): blockers.append("CRITICAL_INCIDENT_PRESENT")
        if min(w.safety_score for w in rows) < safety_floor: blockers.append("SAFETY_FLOOR_FAILED")
        if min(w.reliability_score for w in rows) < reliability_floor: blockers.append("RELIABILITY_FLOOR_FAILED")
        average_value = sum(w.owner_value_score for w in rows) / len(rows)
        if sustained_value and average_value < sustained_value_floor: blockers.append("OWNER_VALUE_FLOOR_FAILED")
        blockers = sorted(set(blockers))

        promotion: PromotionEvidence | None = None
        stage = ProductionStage.SUSTAINED_VALUE if sustained_value else ProductionStage.OPERATIONAL
        if not blockers:
            proof_refs = tuple(sorted({p for w in rows for p in w.proof_refs}))
            promotion = PromotionEvidence(
                stage=stage,
                source_sha=source_sha,
                proof_refs=proof_refs,
                independent_verifier_refs=tuple(sorted({f"run:{w.run_id}" for w in rows})),
                provider_native_readback=True,
                rollback_available=True,
                safety_score=min(w.safety_score for w in rows),
                reliability_score=min(w.reliability_score for w in rows),
                owner_value_score=average_value,
                sustained_windows=len(rows) if sustained_value else 0,
            ).validate()
        status = (
            "SUSTAINED_VALUE_EVIDENCE_ELIGIBLE" if sustained_value and not blockers else
            "OPERATIONAL_EVIDENCE_ELIGIBLE" if not sustained_value and not blockers else
            "SOAK_HELD"
        )
        body = {"schema":SCHEMA,"status":status,"source_sha":source_sha,"window_count":len(rows),"elapsed_seconds":span,"blockers":blockers,"sustained_value":sustained_value}
        return SoakReceipt(status, source_sha, len(rows), span, tuple(blockers), promotion, _hash(body))


__all__ = [
    "SCHEMA", "PROVIDER_EFFECT_AUTHORIZED", "OPERATIONAL_VERIFIED", "SUSTAINED_VALUE_VERIFIED", "TEN_X_VERIFIED",
    "OperationalWindow", "SoakReceipt", "OperationalSoakCourt",
]
