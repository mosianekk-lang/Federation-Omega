from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Dict


class Timeliness(str, Enum):
    ON_TIME = "on_time"
    LATE_ACCEPTED = "late_accepted"
    TOO_LATE = "too_late"
    FUTURE_SKEW = "future_skew"


class SequenceState(str, Enum):
    FIRST = "first"
    NEXT = "next"
    GAP = "gap"
    DUPLICATE = "duplicate"
    REGRESSION = "regression"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TemporalPolicy:
    allowed_lateness_ms: int = 5_000
    late_grace_ms: int = 0
    max_future_skew_ms: int = 5_000

    def validate(self) -> None:
        if min(self.allowed_lateness_ms, self.late_grace_ms, self.max_future_skew_ms) < 0:
            raise ValueError("temporal policy values must be nonnegative")


@dataclass(frozen=True)
class TemporalClassification:
    stream_id: str
    event_time_ms: int
    observed_time_ms: int
    watermark_before_ms: int | None
    watermark_after_ms: int
    timeliness: Timeliness
    sequence_state: SequenceState


class StreamTimeTracker:
    """Event-time watermark and sequence tracking.

    This is a semantic adapter, not a replacement for Federation knowledge watermarks,
    Mission Bus ordering, NATS/Temporal, or provider-native stream processors.
    """

    def __init__(self, policy: TemporalPolicy = TemporalPolicy()) -> None:
        policy.validate()
        self.policy = policy
        self._max_event: Dict[str, int] = {}
        self._last_sequence: Dict[str, int] = {}

    def watermark(self, stream_id: str) -> int | None:
        max_event = self._max_event.get(stream_id)
        if max_event is None:
            return None
        return max_event - self.policy.allowed_lateness_ms

    def _sequence_state(self, stream_id: str, sequence: int | None) -> SequenceState:
        if sequence is None:
            return SequenceState.UNKNOWN
        prior = self._last_sequence.get(stream_id)
        if prior is None:
            state = SequenceState.FIRST
        elif sequence == prior:
            state = SequenceState.DUPLICATE
        elif sequence < prior:
            state = SequenceState.REGRESSION
        elif sequence == prior + 1:
            state = SequenceState.NEXT
        else:
            state = SequenceState.GAP
        if prior is None or sequence > prior:
            self._last_sequence[stream_id] = sequence
        return state

    def observe(
        self,
        stream_id: str,
        *,
        event_time_ms: int,
        observed_time_ms: int,
        sequence: int | None = None,
    ) -> TemporalClassification:
        before = self.watermark(stream_id)
        if event_time_ms > observed_time_ms + self.policy.max_future_skew_ms:
            timeliness = Timeliness.FUTURE_SKEW
        elif before is not None and event_time_ms <= before:
            lag = before - event_time_ms
            timeliness = (
                Timeliness.LATE_ACCEPTED
                if lag <= self.policy.late_grace_ms
                else Timeliness.TOO_LATE
            )
        else:
            timeliness = Timeliness.ON_TIME

        max_event = self._max_event.get(stream_id)
        if max_event is None or event_time_ms > max_event:
            self._max_event[stream_id] = event_time_ms
        after = self.watermark(stream_id)
        assert after is not None
        return TemporalClassification(
            stream_id=stream_id,
            event_time_ms=event_time_ms,
            observed_time_ms=observed_time_ms,
            watermark_before_ms=before,
            watermark_after_ms=after,
            timeliness=timeliness,
            sequence_state=self._sequence_state(stream_id, sequence),
        )


@dataclass(frozen=True, order=True)
class HybridTimestamp:
    physical_ms: int
    logical: int = 0


class HybridLogicalClock:
    """Compact HLC for causal ordering when wall clocks are imperfect."""

    def __init__(self) -> None:
        self.last = HybridTimestamp(0, 0)

    def send(self, now_ms: int) -> HybridTimestamp:
        if now_ms > self.last.physical_ms:
            self.last = HybridTimestamp(now_ms, 0)
        else:
            self.last = HybridTimestamp(self.last.physical_ms, self.last.logical + 1)
        return self.last

    def recv(self, remote: HybridTimestamp, now_ms: int) -> HybridTimestamp:
        physical = max(now_ms, self.last.physical_ms, remote.physical_ms)
        if physical == self.last.physical_ms == remote.physical_ms:
            logical = max(self.last.logical, remote.logical) + 1
        elif physical == self.last.physical_ms:
            logical = self.last.logical + 1
        elif physical == remote.physical_ms:
            logical = remote.logical + 1
        else:
            logical = 0
        self.last = HybridTimestamp(physical, logical)
        return self.last


@dataclass(frozen=True)
class BitemporalFact:
    fact_id: str
    subject: str
    predicate: str
    value: str
    valid_from_ms: int
    valid_to_ms: int | None
    recorded_at_ms: int
    superseded_at_ms: int | None = None
    source_ref: str = ""

    def valid_at(self, valid_ms: int) -> bool:
        return self.valid_from_ms <= valid_ms and (
            self.valid_to_ms is None or valid_ms < self.valid_to_ms
        )

    def known_at(self, transaction_ms: int) -> bool:
        return self.recorded_at_ms <= transaction_ms and (
            self.superseded_at_ms is None or transaction_ms < self.superseded_at_ms
        )


class BitemporalStore:
    def __init__(self) -> None:
        self._facts: Dict[str, BitemporalFact] = {}

    def add(self, fact: BitemporalFact, *, supersede_prior: bool = True) -> None:
        if fact.fact_id in self._facts:
            raise ValueError(f"duplicate fact_id: {fact.fact_id}")
        if fact.valid_to_ms is not None and fact.valid_to_ms <= fact.valid_from_ms:
            raise ValueError("valid_to_ms must be > valid_from_ms")
        if supersede_prior:
            for fid, prior in list(self._facts.items()):
                if (
                    prior.subject == fact.subject
                    and prior.predicate == fact.predicate
                    and prior.superseded_at_ms is None
                    and prior.recorded_at_ms <= fact.recorded_at_ms
                ):
                    self._facts[fid] = replace(
                        prior, superseded_at_ms=fact.recorded_at_ms
                    )
        self._facts[fact.fact_id] = fact

    def as_of(
        self,
        *,
        subject: str,
        predicate: str,
        valid_ms: int,
        transaction_ms: int,
    ) -> BitemporalFact | None:
        candidates = [
            f
            for f in self._facts.values()
            if f.subject == subject
            and f.predicate == predicate
            and f.valid_at(valid_ms)
            and f.known_at(transaction_ms)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda f: (f.recorded_at_ms, f.fact_id))


@dataclass(frozen=True)
class DeadlineState:
    due: bool
    expired: bool
    stale: bool
    remaining_ms: int | None


class TemporalSemantics:
    @staticmethod
    def window_start(event_time_ms: int, *, width_ms: int, offset_ms: int = 0) -> int:
        if width_ms <= 0:
            raise ValueError("width_ms must be >0")
        return ((event_time_ms - offset_ms) // width_ms) * width_ms + offset_ms

    @staticmethod
    def classify_deadline(
        *,
        now_ms: int,
        deadline_ms: int | None = None,
        expires_ms: int | None = None,
        freshness_ms: int | None = None,
        observed_ms: int | None = None,
    ) -> DeadlineState:
        due = deadline_ms is not None and now_ms >= deadline_ms
        expired = expires_ms is not None and now_ms >= expires_ms
        stale = (
            freshness_ms is not None
            and observed_ms is not None
            and now_ms - observed_ms > freshness_ms
        )
        remaining = None if deadline_ms is None else deadline_ms - now_ms
        return DeadlineState(
            due=due, expired=expired, stale=stale, remaining_ms=remaining
        )


@dataclass(frozen=True)
class TemporalRelation:
    left: str
    right: str
    relation: str


class TemporalOrder:
    @staticmethod
    def compare(
        left_id: str,
        left: HybridTimestamp,
        right_id: str,
        right: HybridTimestamp,
    ) -> TemporalRelation:
        if left < right:
            return TemporalRelation(left_id, right_id, "BEFORE")
        if left > right:
            return TemporalRelation(left_id, right_id, "AFTER")
        return TemporalRelation(left_id, right_id, "SAME_LOGICAL_TIME")
