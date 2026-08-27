from __future__ import annotations

from dataclasses import dataclass, asdict

from .models import stable_sha256


@dataclass(frozen=True)
class CapitalGateState:
    research_admitted: bool
    capital_intent_valid: bool
    risk_governor_passed: bool
    venue_healthy: bool
    reconciliation_healthy: bool
    kill_switch_clear: bool
    execution_lease_present: bool = False
    owner_capital_authority_present: bool = False
    mode: str = "SHADOW"


@dataclass(frozen=True)
class CapitalGateDecision:
    allowed: bool
    mode: str
    reason_codes: tuple[str, ...]
    digest: str


class CapitalConstitution:
    """Monotonic capital authority gate. v1 can authorize shadow analysis only."""

    def evaluate(self, state: CapitalGateState) -> CapitalGateDecision:
        reasons: list[str] = []
        if not state.research_admitted:
            reasons.append("RESEARCH_NOT_ADMITTED")
        if not state.capital_intent_valid:
            reasons.append("CAPITAL_INTENT_INVALID")
        if not state.risk_governor_passed:
            reasons.append("RISK_GOVERNOR_BLOCK")
        if not state.venue_healthy:
            reasons.append("VENUE_UNHEALTHY")
        if not state.reconciliation_healthy:
            reasons.append("RECONCILIATION_UNHEALTHY")
        if not state.kill_switch_clear:
            reasons.append("KILL_SWITCH_ACTIVE")

        if state.mode == "SHADOW":
            pass
        elif state.mode == "PAPER":
            reasons.append("PAPER_MODE_NOT_ADMITTED_V1")
        elif state.mode in {"MICRO_CAPITAL", "LIVE"}:
            reasons.append("LIVE_CAPITAL_HARD_DISABLED_V1")
            if not state.execution_lease_present:
                reasons.append("EXECUTION_LEASE_REQUIRED")
            if not state.owner_capital_authority_present:
                reasons.append("OWNER_CAPITAL_AUTHORITY_REQUIRED")
        else:
            reasons.append("UNKNOWN_EXECUTION_MODE")

        payload = {"state": asdict(state), "allowed": not reasons, "reasons": reasons}
        return CapitalGateDecision(not reasons, state.mode, tuple(reasons), stable_sha256(payload))
