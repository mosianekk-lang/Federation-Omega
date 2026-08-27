from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import stable_sha256


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


_FATAL = {
    "RECONCILIATION_UNHEALTHY",
    "KILL_SWITCH_ACTIVE",
    "VENUE_UNHEALTHY",
    "STALE_MARKET_DATA",
    "SHADOW_EFFECT_BOUNDARY_VIOLATION",
}


@dataclass(frozen=True)
class CircuitSnapshot:
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    reason_codes: tuple[str, ...] = ()
    digest: str = "GENESIS"


class CapitalCircuitBreaker:
    """Fail-closed execution circuit. It never re-enables live authority."""

    def observe(self, prior: CircuitSnapshot, reason_codes: tuple[str, ...], *, failure_threshold: int = 3) -> CircuitSnapshot:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be positive")
        reasons = tuple(sorted(set(reason_codes)))
        if prior.state == CircuitState.OPEN:
            return prior
        if not reasons:
            failures = 0
            state = CircuitState.CLOSED
        else:
            failures = prior.consecutive_failures + 1
            state = CircuitState.OPEN if _FATAL.intersection(reasons) or failures >= failure_threshold else prior.state
        payload = {"state": state.value, "consecutive_failures": failures, "reason_codes": reasons, "prior_digest": prior.digest}
        return CircuitSnapshot(state, failures, reasons, stable_sha256(payload))

    def prepare_probe(self, prior: CircuitSnapshot) -> CircuitSnapshot:
        if prior.state != CircuitState.OPEN:
            raise ValueError("only an open circuit can enter half-open probe state")
        payload = {"state": CircuitState.HALF_OPEN.value, "prior_digest": prior.digest, "reason_codes": prior.reason_codes}
        return CircuitSnapshot(CircuitState.HALF_OPEN, prior.consecutive_failures, prior.reason_codes, stable_sha256(payload))

    def close_after_verified_probe(self, prior: CircuitSnapshot, *, reconciliation_healthy: bool, venue_healthy: bool) -> CircuitSnapshot:
        if prior.state != CircuitState.HALF_OPEN:
            raise ValueError("verified probe closure requires HALF_OPEN state")
        if not reconciliation_healthy or not venue_healthy:
            return self.observe(CircuitSnapshot(CircuitState.CLOSED, prior.consecutive_failures, prior.reason_codes, prior.digest), ("RECONCILIATION_UNHEALTHY" if not reconciliation_healthy else "VENUE_UNHEALTHY",))
        payload = {"state": CircuitState.CLOSED.value, "prior_digest": prior.digest, "verified_probe": True}
        return CircuitSnapshot(CircuitState.CLOSED, 0, (), stable_sha256(payload))
