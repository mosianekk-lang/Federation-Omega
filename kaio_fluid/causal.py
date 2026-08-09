from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TimedFact:
    id: str
    known_at: datetime
    event_at: datetime
    proof_state: str


@dataclass(frozen=True)
class CausalClaim:
    cause_id: str
    outcome_id: str
    mechanism: str | None


class CausalTimeLockGuard:
    """Prevent hindsight leakage and unsupported chronology-as-causation."""

    def knowledge_available(self, fact: TimedFact, decision_time: datetime) -> bool:
        return fact.known_at <= decision_time

    def temporal_order_valid(self, cause: TimedFact, outcome: TimedFact) -> bool:
        return cause.event_at <= outcome.event_at

    def causal_claim_allowed(
        self,
        claim: CausalClaim,
        *,
        cause: TimedFact,
        outcome: TimedFact,
        decision_time: datetime | None = None,
    ) -> bool:
        if not claim.mechanism or not claim.mechanism.strip():
            return False
        if not self.temporal_order_valid(cause, outcome):
            return False
        if decision_time is not None and not self.knowledge_available(cause, decision_time):
            return False
        return True

    def hindsight_violation(self, fact: TimedFact, decision_time: datetime) -> bool:
        return not self.knowledge_available(fact, decision_time)
