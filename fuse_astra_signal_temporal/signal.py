from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import prod, sqrt
from typing import Dict, Iterable, Mapping, Sequence, Tuple


class SignalKind(str, Enum):
    TRACE = "trace"
    METRIC = "metric"
    LOG = "log"
    EVENT = "event"
    MESSAGE = "message"
    STATE = "state"
    EXTERNAL = "external"


@dataclass(frozen=True)
class SignalObservation:
    signal_id: str
    source_id: str
    independence_group: str
    kind: SignalKind
    topic: str
    event_time_ms: int
    observed_time_ms: int
    severity: float = 0.0
    confidence: float = 1.0
    polarity: float = 1.0
    numeric_value: float | None = None
    sequence: int | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    tags: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.signal_id:
            raise ValueError("signal_id is required")
        if not self.source_id or not self.independence_group:
            raise ValueError("source_id and independence_group are required")
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError("severity must be in [0,1]")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")
        if not -1.0 <= self.polarity <= 1.0:
            raise ValueError("polarity must be in [-1,1]")
        if self.observed_time_ms < self.event_time_ms:
            raise ValueError(
                "observed_time_ms cannot precede event_time_ms without clock-skew reconciliation"
            )


@dataclass(frozen=True)
class SourceQuality:
    source_id: str
    reliability: float = 1.0
    authority: float = 1.0
    freshness_half_life_ms: int = 60_000

    def validate(self) -> None:
        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError("reliability must be in [0,1]")
        if not 0.0 <= self.authority <= 1.0:
            raise ValueError("authority must be in [0,1]")
        if self.freshness_half_life_ms <= 0:
            raise ValueError("freshness_half_life_ms must be >0")


@dataclass(frozen=True)
class FusedSignal:
    topic: str
    signed_score: float
    confidence: float
    salience: float
    independent_groups: int
    source_count: int
    freshest_event_ms: int
    evidence_ids: Tuple[str, ...]


class SignalFusionEngine:
    """Fuse authorized observations without treating duplicated sources as corroboration."""

    @staticmethod
    def _freshness(age_ms: int, half_life_ms: int) -> float:
        if age_ms <= 0:
            return 1.0
        return 1.0 / (1.0 + (age_ms / float(half_life_ms)))

    def fuse(
        self,
        topic: str,
        observations: Iterable[SignalObservation],
        source_quality: Mapping[str, SourceQuality],
        *,
        now_ms: int,
        novelty: float = 0.5,
    ) -> FusedSignal:
        if not 0.0 <= novelty <= 1.0:
            raise ValueError("novelty must be in [0,1]")
        obs = [o for o in observations if o.topic == topic]
        if not obs:
            raise ValueError(f"no observations for topic {topic}")

        by_group: Dict[str, list[tuple[SignalObservation, float]]] = {}
        freshnesses = []
        severities = []
        for o in obs:
            o.validate()
            q = source_quality.get(o.source_id, SourceQuality(o.source_id))
            q.validate()
            age = max(0, now_ms - o.event_time_ms)
            freshness = self._freshness(age, q.freshness_half_life_ms)
            freshnesses.append(freshness)
            severities.append(o.severity)
            effective = o.confidence * q.reliability * q.authority * freshness
            by_group.setdefault(o.independence_group, []).append((o, effective))

        representatives: list[tuple[SignalObservation, float]] = []
        for items in by_group.values():
            representatives.append(max(items, key=lambda x: (x[1], x[0].signal_id)))

        weights = [w for _, w in representatives]
        total_weight = sum(weights)
        signed_score = (
            0.0
            if total_weight == 0
            else sum(o.polarity * w for o, w in representatives) / total_weight
        )
        confidence = 1.0 - prod(
            1.0 - min(1.0, max(0.0, w)) for w in weights
        )
        severity = max(severities) if severities else 0.0
        freshness = max(freshnesses) if freshnesses else 0.0
        diversity = min(1.0, len(representatives) / 3.0)
        salience = min(
            1.0,
            max(
                0.0,
                0.30 * severity
                + 0.30 * confidence
                + 0.15 * novelty
                + 0.15 * freshness
                + 0.10 * diversity,
            ),
        )
        return FusedSignal(
            topic=topic,
            signed_score=signed_score,
            confidence=confidence,
            salience=salience,
            independent_groups=len(representatives),
            source_count=len(obs),
            freshest_event_ms=max(o.event_time_ms for o in obs),
            evidence_ids=tuple(sorted(o.signal_id for o in obs)),
        )


class SignalGate:
    @staticmethod
    def qualified(
        fused: FusedSignal,
        *,
        min_confidence: float,
        min_independent_groups: int,
        min_abs_score: float = 0.0,
    ) -> bool:
        return (
            fused.confidence >= min_confidence
            and fused.independent_groups >= min_independent_groups
            and abs(fused.signed_score) >= min_abs_score
        )


@dataclass(frozen=True)
class CorrelationLink:
    left_id: str
    right_id: str
    relation: str
    delta_ms: int


class SignalCorrelator:
    """Create correlation links while refusing to infer causation from proximity alone."""

    def correlate(
        self,
        observations: Sequence[SignalObservation],
        *,
        max_delta_ms: int,
    ) -> Tuple[CorrelationLink, ...]:
        links = []
        for i, left in enumerate(observations):
            left.validate()
            for right in observations[i + 1 :]:
                right.validate()
                delta = abs(left.event_time_ms - right.event_time_ms)
                if left.causation_id == right.signal_id:
                    links.append(
                        CorrelationLink(
                            left.signal_id,
                            right.signal_id,
                            "EXPLICIT_CAUSATION",
                            delta,
                        )
                    )
                    continue
                if right.causation_id == left.signal_id:
                    links.append(
                        CorrelationLink(
                            left.signal_id,
                            right.signal_id,
                            "EXPLICIT_CAUSATION",
                            delta,
                        )
                    )
                    continue
                if left.correlation_id and left.correlation_id == right.correlation_id:
                    links.append(
                        CorrelationLink(
                            left.signal_id,
                            right.signal_id,
                            "CORRELATED_ID",
                            delta,
                        )
                    )
                    continue
                if delta <= max_delta_ms and left.topic == right.topic:
                    links.append(
                        CorrelationLink(
                            left.signal_id,
                            right.signal_id,
                            "TEMPORAL_CORRELATION",
                            delta,
                        )
                    )
        return tuple(sorted(links, key=lambda x: (x.left_id, x.right_id, x.relation)))


class ChangeDetector:
    @staticmethod
    def zscore_change(
        history: Sequence[float], new_value: float, *, threshold: float = 3.0
    ) -> tuple[bool, float]:
        if len(history) < 2:
            return False, 0.0
        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        stdev = sqrt(variance)
        if stdev == 0.0:
            z = float("inf") if new_value != mean else 0.0
        else:
            z = abs(new_value - mean) / stdev
        return z >= threshold, z
