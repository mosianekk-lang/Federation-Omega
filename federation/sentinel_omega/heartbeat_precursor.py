from __future__ import annotations

"""Proof-bound heartbeat cadence and precursor detection for Sentinel Ω.

The engine learns a robust cadence profile from observed heartbeat timestamps and
classifies current heartbeat age as HEALTHY, WATCH, PRECURSOR, or STALE.  It is a
provider-neutral diagnostic primitive only: it does not schedule work, restart
services, mutate providers, or claim that a correlation is a verified cause.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import math
import statistics
from typing import Iterable, Sequence

from .observability_causal_fabric import NormalizedObservation, SignalKind

SCHEMA = "SENTINEL-OMEGA-HEARTBEAT-PRECURSOR-V1"
EXTERNAL_EFFECTS = False


def _time(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("heartbeat timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class CadenceState(StrEnum):
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    PRECURSOR = "PRECURSOR"
    STALE = "STALE"


@dataclass(frozen=True)
class HeartbeatCadenceProfile:
    sample_count: int
    interval_count: int
    median_interval_seconds: float
    mad_seconds: float
    robust_jitter_seconds: float
    watch_after_seconds: float
    precursor_after_seconds: float
    stale_after_seconds: float
    recent_interval_seconds: float
    recent_interval_ratio: float
    recurrence_risk: bool
    confidence: float
    external_effect: bool = False


@dataclass(frozen=True)
class HeartbeatCadenceAssessment:
    target_id: str
    state: CadenceState
    last_seen_at: str
    assessed_at: str
    age_seconds: float
    expected_next_at: str
    watch_at: str
    precursor_at: str
    stale_at: str
    missed_cycles: int
    recurrence_risk: bool
    confidence: float
    reason_codes: tuple[str, ...]
    external_effect: bool = False


class HeartbeatCadenceForecaster:
    """Robust cadence learner with an early-warning band before staleness.

    The model uses the median interval and median absolute deviation (MAD).  It
    deliberately avoids means/standard deviations so a single long outage does
    not immediately redefine "normal".  A recent anomalously long interval is
    retained as a recurrence-risk signal without rewriting the baseline.
    """

    def __init__(self, *, minimum_intervals: int = 5) -> None:
        if minimum_intervals < 3:
            raise ValueError("minimum_intervals must be at least 3")
        self.minimum_intervals = int(minimum_intervals)

    def fit(self, timestamps: Sequence[str | datetime]) -> HeartbeatCadenceProfile:
        points = tuple(_time(x) for x in timestamps)
        if len(points) < self.minimum_intervals + 1:
            raise ValueError("insufficient heartbeat history")
        for left, right in zip(points, points[1:]):
            if right <= left:
                raise ValueError("heartbeat history must be strictly increasing")

        intervals = [(right - left).total_seconds() for left, right in zip(points, points[1:])]
        clean = [float(x) for x in intervals if math.isfinite(float(x)) and x > 0]
        if len(clean) < self.minimum_intervals:
            raise ValueError("insufficient valid heartbeat intervals")

        median = float(statistics.median(clean))
        deviations = [abs(x - median) for x in clean]
        mad = float(statistics.median(deviations))
        # 1.4826*MAD approximates sigma for a normal distribution.  A one-minute
        # floor avoids pathological zero-jitter profiles becoming hypersensitive.
        jitter = max(60.0, 1.4826 * mad)

        watch_after = median + max(60.0, jitter)
        precursor_after = max(watch_after + 60.0, median + max(120.0, 2.0 * jitter))
        stale_after = max(precursor_after + 60.0, 2.0 * median, median + max(300.0, 4.0 * jitter))

        recent = clean[-1]
        recent_ratio = recent / median if median > 0 else float("inf")
        recurrence_risk = recent >= precursor_after

        # Confidence rises with repeated intervals but is reduced by relative
        # cadence jitter.  It is a diagnostic confidence, not a probability.
        sample_factor = min(1.0, len(clean) / 12.0)
        jitter_penalty = min(0.65, jitter / max(median, 1.0))
        confidence = max(0.0, min(1.0, sample_factor * (1.0 - jitter_penalty)))

        return HeartbeatCadenceProfile(
            sample_count=len(points),
            interval_count=len(clean),
            median_interval_seconds=round(median, 6),
            mad_seconds=round(mad, 6),
            robust_jitter_seconds=round(jitter, 6),
            watch_after_seconds=round(watch_after, 6),
            precursor_after_seconds=round(precursor_after, 6),
            stale_after_seconds=round(stale_after, 6),
            recent_interval_seconds=round(recent, 6),
            recent_interval_ratio=round(recent_ratio, 6),
            recurrence_risk=recurrence_risk,
            confidence=round(confidence, 6),
        )

    def assess(
        self,
        target_id: str,
        profile: HeartbeatCadenceProfile,
        *,
        last_seen_at: str | datetime,
        assessed_at: str | datetime,
    ) -> HeartbeatCadenceAssessment:
        if not str(target_id).strip():
            raise ValueError("target_id is required")
        last_seen = _time(last_seen_at)
        now = _time(assessed_at)
        if now < last_seen:
            raise ValueError("assessment time cannot precede last heartbeat")

        age = (now - last_seen).total_seconds()
        reasons: list[str] = []
        if age >= profile.stale_after_seconds:
            state = CadenceState.STALE
            reasons.append("MISSED_STALE_THRESHOLD")
        elif age >= profile.precursor_after_seconds:
            state = CadenceState.PRECURSOR
            reasons.append("EXPECTED_HEARTBEAT_OVERDUE_PRECURSOR")
        elif age >= profile.watch_after_seconds:
            state = CadenceState.WATCH
            reasons.append("EXPECTED_HEARTBEAT_LATE")
        else:
            state = CadenceState.HEALTHY
            reasons.append("WITHIN_ROBUST_CADENCE")

        # A recently anomalous interval becomes a bounded recurrence signal.  It
        # can lift a healthy state to WATCH only after half of the expected cadence
        # has elapsed, avoiding permanent alarm immediately after recovery.
        if profile.recurrence_risk:
            reasons.append("RECENT_INTERVAL_EXPANSION")
            if state == CadenceState.HEALTHY and age >= 0.5 * profile.median_interval_seconds:
                state = CadenceState.WATCH
                reasons.append("RECURRENCE_PREWARM")

        missed_cycles = max(0, int(age // max(profile.median_interval_seconds, 1.0)) - 1)
        expected_next = last_seen + timedelta(seconds=profile.median_interval_seconds)
        watch_at = last_seen + timedelta(seconds=profile.watch_after_seconds)
        precursor_at = last_seen + timedelta(seconds=profile.precursor_after_seconds)
        stale_at = last_seen + timedelta(seconds=profile.stale_after_seconds)

        return HeartbeatCadenceAssessment(
            target_id=str(target_id),
            state=state,
            last_seen_at=_iso(last_seen),
            assessed_at=_iso(now),
            age_seconds=round(age, 6),
            expected_next_at=_iso(expected_next),
            watch_at=_iso(watch_at),
            precursor_at=_iso(precursor_at),
            stale_at=_iso(stale_at),
            missed_cycles=missed_cycles,
            recurrence_risk=profile.recurrence_risk,
            confidence=profile.confidence,
            reason_codes=tuple(reasons),
        )

    def to_observation(
        self,
        assessment: HeartbeatCadenceAssessment,
        *,
        proof_refs: Iterable[str],
        source: str = "sentinel.heartbeat_precursor_v1",
    ) -> NormalizedObservation:
        refs = tuple(sorted({str(x) for x in proof_refs if str(x)}))
        if not refs:
            raise ValueError("heartbeat precursor observation requires proof_refs")
        severity = {
            CadenceState.HEALTHY: 0.05,
            CadenceState.WATCH: 0.35,
            CadenceState.PRECURSOR: 0.65,
            CadenceState.STALE: 0.9,
        }[assessment.state]
        return NormalizedObservation(
            observation_id=(
                f"HB-CADENCE-{assessment.target_id}-{assessment.assessed_at}"
                .replace(":", "-")
                .replace("+", "-")
            ),
            source=source,
            signal_kind=SignalKind.HEALTH,
            target_id=assessment.target_id,
            observed_at=assessment.assessed_at,
            fingerprint=f"HEARTBEAT_CADENCE_{assessment.state.value}",
            severity=severity,
            proof_refs=refs,
            attributes={
                "schema": SCHEMA,
                "age_seconds": assessment.age_seconds,
                "expected_next_at": assessment.expected_next_at,
                "watch_at": assessment.watch_at,
                "precursor_at": assessment.precursor_at,
                "stale_at": assessment.stale_at,
                "missed_cycles": assessment.missed_cycles,
                "recurrence_risk": assessment.recurrence_risk,
                "confidence": assessment.confidence,
                "reason_codes": assessment.reason_codes,
            },
            external_effect=False,
        ).validate()
